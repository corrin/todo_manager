# AI Chatbot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a task-focused AI chatbot as the primary app interface, with streaming responses, tool calling for task/calendar management, and a live dashboard.

**Architecture:** Flask blueprint with SSE streaming endpoint. LiteLLM proxies to any LLM backend. The AI has tools to read/write tasks and calendar data via existing models. Two new DB tables store conversation history. A vanilla JS chat UI sits alongside a task/calendar dashboard.

**Tech Stack:** Flask, LiteLLM, SSE (Server-Sent Events), vanilla JS, marked.js (CDN), SQLAlchemy, Flask-Migrate

**Design doc:** `docs/plans/2026-03-07-ai-chatbot-design.md`

---

### Task 1: Create feature branch and add LiteLLM dependency

**Files:**
- Modify: `pyproject.toml`

**Step 1: Create branch**

```bash
git checkout -b feature/ai-chatbot
```

**Step 2: Add litellm dependency**

```bash
cd /home/corrin/src/virtual_assistant
poetry add litellm
```

**Step 3: Verify installation**

```bash
poetry run python -c "import litellm; print(litellm.__version__)"
```
Expected: prints version number without error

**Step 4: Commit**

```bash
git add pyproject.toml poetry.lock
git commit -m "Add litellm dependency for AI chatbot feature"
```

---

### Task 2: Add database models for Conversation and ChatMessage

**Files:**
- Create: `virtual_assistant/chat/__init__.py`
- Create: `virtual_assistant/chat/models.py`
- Test: `tests/test_chat_models.py`

**Step 1: Write the failing test**

Create `tests/test_chat_models.py`:

```python
import uuid
import pytest
from virtual_assistant.flask_app import create_app
from virtual_assistant.database.database import db
from virtual_assistant.database.user import User
from virtual_assistant.chat.models import Conversation, ChatMessage


@pytest.fixture()
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture()
def user(app):
    with app.app_context():
        u = User(app_login="test@example.com")
        db.session.add(u)
        db.session.commit()
        yield u


def test_create_conversation(app, user):
    with app.app_context():
        conv = Conversation(user_id=user.id, title="Test chat")
        db.session.add(conv)
        db.session.commit()

        assert conv.id is not None
        assert conv.user_id == user.id
        assert conv.title == "Test chat"


def test_create_chat_message(app, user):
    with app.app_context():
        conv = Conversation(user_id=user.id)
        db.session.add(conv)
        db.session.commit()

        msg = ChatMessage(
            conversation_id=conv.id,
            role="user",
            content="Hello",
        )
        db.session.add(msg)
        db.session.commit()

        assert msg.id is not None
        assert msg.role == "user"
        assert msg.content == "Hello"


def test_conversation_messages_relationship(app, user):
    with app.app_context():
        conv = Conversation(user_id=user.id)
        db.session.add(conv)
        db.session.commit()

        msg1 = ChatMessage(conversation_id=conv.id, role="user", content="Hi")
        msg2 = ChatMessage(conversation_id=conv.id, role="assistant", content="Hello!")
        db.session.add_all([msg1, msg2])
        db.session.commit()

        assert len(conv.messages) == 2
        assert conv.messages[0].content == "Hi"
        assert conv.messages[1].content == "Hello!"


def test_tool_call_message(app, user):
    with app.app_context():
        conv = Conversation(user_id=user.id)
        db.session.add(conv)
        db.session.commit()

        msg = ChatMessage(
            conversation_id=conv.id,
            role="assistant",
            content="",
            tool_calls=[{"id": "call_1", "function": {"name": "get_tasks", "arguments": "{}"}}],
        )
        db.session.add(msg)
        db.session.commit()

        assert msg.tool_calls[0]["function"]["name"] == "get_tasks"


def test_get_conversation_history(app, user):
    with app.app_context():
        conv = Conversation(user_id=user.id)
        db.session.add(conv)
        db.session.commit()

        msgs = [
            ChatMessage(conversation_id=conv.id, role="user", content="Hi"),
            ChatMessage(conversation_id=conv.id, role="assistant", content="Hello!"),
        ]
        db.session.add_all(msgs)
        db.session.commit()

        history = Conversation.get_history(conv.id)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
```

**Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/test_chat_models.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'virtual_assistant.chat'`

**Step 3: Write minimal implementation**

Create `virtual_assistant/chat/__init__.py` (empty file).

Create `virtual_assistant/chat/models.py`:

```python
import uuid
from datetime import datetime, timezone
from virtual_assistant.database.database import db
from virtual_assistant.database.user import MySQLUUID


class Conversation(db.Model):
    __tablename__ = "conversation"

    id = db.Column(MySQLUUID(), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(MySQLUUID(), db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    messages = db.relationship(
        "ChatMessage",
        backref="conversation",
        lazy=True,
        order_by="ChatMessage.created_at",
        cascade="all, delete-orphan",
    )

    @staticmethod
    def get_history(conversation_id):
        messages = ChatMessage.query.filter_by(
            conversation_id=conversation_id
        ).order_by(ChatMessage.created_at).all()
        return [msg.to_dict() for msg in messages]

    def __repr__(self):
        return f"<Conversation {self.id} user={self.user_id}>"


class ChatMessage(db.Model):
    __tablename__ = "chat_message"

    id = db.Column(MySQLUUID(), primary_key=True, default=uuid.uuid4)
    conversation_id = db.Column(
        MySQLUUID(), db.ForeignKey("conversation.id"), nullable=False
    )
    role = db.Column(db.String(20), nullable=False)  # user, assistant, system, tool
    content = db.Column(db.Text, nullable=True)
    tool_calls = db.Column(db.JSON, nullable=True)
    tool_call_id = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        d = {"role": self.role, "content": self.content or ""}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d

    def __repr__(self):
        return f"<ChatMessage {self.id} role={self.role}>"
```

**Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/test_chat_models.py -v
```
Expected: all 6 tests PASS

**Step 5: Commit**

```bash
git add virtual_assistant/chat/ tests/test_chat_models.py
git commit -m "Add Conversation and ChatMessage database models"
```

---

### Task 3: Create Alembic migration for new tables

**Files:**
- Create: new migration file (auto-generated)

**Step 1: Generate migration**

```bash
poetry run flask db migrate -m "Add conversation and chat_message tables"
```

**Step 2: Review the generated migration**

Read the generated file in `migrations/versions/` and verify it creates `conversation` and `chat_message` tables with the correct columns.

**Step 3: Apply migration**

```bash
poetry run flask db upgrade
```
Expected: no errors

**Step 4: Commit**

```bash
git add migrations/
git commit -m "Add migration for conversation and chat_message tables"
```

---

### Task 4: Define AI tool functions for task management

**Files:**
- Create: `virtual_assistant/chat/tools.py`
- Test: `tests/test_chat_tools.py`

**Step 1: Write the failing test**

Create `tests/test_chat_tools.py`:

```python
import uuid
import pytest
from virtual_assistant.flask_app import create_app
from virtual_assistant.database.database import db
from virtual_assistant.database.user import User
from virtual_assistant.database.task import Task
from virtual_assistant.chat.tools import TOOL_DEFINITIONS, execute_tool


@pytest.fixture()
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture()
def user(app):
    with app.app_context():
        u = User(app_login="test@example.com")
        db.session.add(u)
        db.session.commit()
        yield u


@pytest.fixture()
def sample_tasks(app, user):
    with app.app_context():
        tasks = []
        for i, title in enumerate(["Buy groceries", "Write report", "Call dentist"]):
            t = Task(
                user_id=user.id,
                title=title,
                provider="sqlite",
                provider_task_id=str(uuid.uuid4()),
                task_user_email="test@example.com",
                status="active",
                priority=3 - i,
                list_type="prioritized",
                position=i,
            )
            db.session.add(t)
            tasks.append(t)
        db.session.commit()
        # Re-fetch to get IDs
        tasks = Task.query.filter_by(user_id=user.id).order_by(Task.position).all()
        yield tasks


def test_tool_definitions_are_valid():
    assert len(TOOL_DEFINITIONS) > 0
    for tool in TOOL_DEFINITIONS:
        assert tool["type"] == "function"
        assert "function" in tool
        assert "name" in tool["function"]
        assert "parameters" in tool["function"]


def test_get_tasks(app, user, sample_tasks):
    with app.app_context():
        result = execute_tool("get_tasks", {"status": "active"}, user.id)
        assert "tasks" in result
        assert len(result["tasks"]) == 3


def test_complete_task(app, user, sample_tasks):
    with app.app_context():
        task_id = str(sample_tasks[0].id)
        result = execute_tool("complete_task", {"task_id": task_id}, user.id)
        assert result["success"] is True

        task = db.session.get(Task, sample_tasks[0].id)
        assert task.status == "completed"


def test_create_task(app, user):
    with app.app_context():
        result = execute_tool(
            "create_task",
            {"title": "New task", "priority": 3},
            user.id,
        )
        assert result["success"] is True
        assert "task_id" in result

        task = Task.query.filter_by(user_id=user.id, title="New task").first()
        assert task is not None
        assert task.priority == 3


def test_update_task(app, user, sample_tasks):
    with app.app_context():
        task_id = str(sample_tasks[0].id)
        result = execute_tool(
            "update_task",
            {"task_id": task_id, "title": "Updated title", "priority": 4},
            user.id,
        )
        assert result["success"] is True

        task = db.session.get(Task, sample_tasks[0].id)
        assert task.title == "Updated title"
        assert task.priority == 4


def test_execute_unknown_tool(app, user):
    with app.app_context():
        result = execute_tool("nonexistent_tool", {}, user.id)
        assert "error" in result
```

**Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/test_chat_tools.py -v
```
Expected: FAIL with `ModuleNotFoundError` or `ImportError`

**Step 3: Write minimal implementation**

Create `virtual_assistant/chat/tools.py`:

```python
import uuid
from datetime import datetime, timezone
from virtual_assistant.database.database import db
from virtual_assistant.database.task import Task
from virtual_assistant.utils.logger import logger


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_tasks",
            "description": "Get the user's tasks. Returns prioritized, unprioritized, and optionally completed tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["active", "completed", "all"],
                        "description": "Filter by status. Default is 'active' which returns both prioritized and unprioritized.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Mark a task as completed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The UUID of the task to complete.",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a new task for the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The task title.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional task description.",
                    },
                    "priority": {
                        "type": "integer",
                        "enum": [1, 2, 3, 4],
                        "description": "Priority: 1=low, 2=medium, 3=high, 4=urgent.",
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update an existing task's title, description, priority, or status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The UUID of the task to update.",
                    },
                    "title": {"type": "string", "description": "New title."},
                    "description": {"type": "string", "description": "New description."},
                    "priority": {
                        "type": "integer",
                        "enum": [1, 2, 3, 4],
                        "description": "New priority.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "completed"],
                        "description": "New status.",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_calendar",
            "description": "Get calendar events for a given date. Defaults to today.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format. Defaults to today.",
                    },
                },
                "required": [],
            },
        },
    },
]


def execute_tool(tool_name, arguments, user_id):
    """Execute a tool by name with the given arguments for the specified user."""
    tool_map = {
        "get_tasks": _get_tasks,
        "complete_task": _complete_task,
        "create_task": _create_task,
        "update_task": _update_task,
        "get_calendar": _get_calendar,
    }

    fn = tool_map.get(tool_name)
    if not fn:
        return {"error": f"Unknown tool: {tool_name}"}

    try:
        return fn(user_id=user_id, **arguments)
    except Exception as e:
        logger.exception(f"Error executing tool {tool_name}: {e}")
        return {"error": str(e)}


def _get_tasks(user_id, status="active"):
    prioritized, unprioritized, completed = Task.get_user_tasks_by_list(user_id)

    tasks = []
    if status in ("active", "all"):
        for t in prioritized:
            tasks.append(t.to_dict() | {"list": "prioritized"})
        for t in unprioritized:
            tasks.append(t.to_dict() | {"list": "unprioritized"})
    if status in ("completed", "all"):
        for t in completed:
            tasks.append(t.to_dict() | {"list": "completed"})

    return {"tasks": tasks}


def _complete_task(user_id, task_id):
    task = db.session.get(Task, uuid.UUID(task_id))
    if not task or task.user_id != user_id:
        return {"error": "Task not found"}
    task.status = "completed"
    task.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return {"success": True, "task": task.to_dict()}


def _create_task(user_id, title, description=None, priority=2):
    task = Task(
        user_id=user_id,
        title=title,
        description=description,
        provider="sqlite",
        provider_task_id=str(uuid.uuid4()),
        task_user_email="chat",
        status="active",
        priority=priority,
        list_type="unprioritized",
        position=0,
    )
    db.session.add(task)
    db.session.commit()
    return {"success": True, "task_id": str(task.id), "task": task.to_dict()}


def _update_task(user_id, task_id, **kwargs):
    task = db.session.get(Task, uuid.UUID(task_id))
    if not task or task.user_id != user_id:
        return {"error": "Task not found"}
    for field in ("title", "description", "priority", "status"):
        if field in kwargs and kwargs[field] is not None:
            setattr(task, field, kwargs[field])
    task.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return {"success": True, "task": task.to_dict()}


def _get_calendar(user_id, date=None):
    # Placeholder — will integrate with calendar providers in a later task
    return {"events": [], "message": "Calendar integration pending"}
```

**Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/test_chat_tools.py -v
```
Expected: all 6 tests PASS

**Step 5: Commit**

```bash
git add virtual_assistant/chat/tools.py tests/test_chat_tools.py
git commit -m "Add AI tool definitions and executor for task management"
```

---

### Task 5: Build the chat streaming API endpoint

**Files:**
- Create: `virtual_assistant/chat/chat_routes.py`
- Test: `tests/test_chat_routes.py`

**Step 1: Write the failing test**

Create `tests/test_chat_routes.py`:

```python
import json
import pytest
from unittest.mock import patch, MagicMock
from virtual_assistant.flask_app import create_app
from virtual_assistant.database.database import db
from virtual_assistant.database.user import User


@pytest.fixture()
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture()
def user(app):
    with app.app_context():
        u = User(app_login="test@example.com")
        u.openai_key = "test-key"
        u.ai_provider = "openai"
        db.session.add(u)
        db.session.commit()
        yield u


@pytest.fixture()
def client(app, user):
    with app.test_client() as c:
        # Simulate login
        with c.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
        yield c


def test_chat_endpoint_requires_message(client):
    resp = client.post(
        "/api/chat",
        json={},
        headers={"Accept": "text/event-stream"},
    )
    assert resp.status_code == 400


def test_chat_creates_conversation(app, client, user):
    with patch("virtual_assistant.chat.chat_routes.litellm") as mock_llm:
        # Mock a simple non-streaming response for easier testing
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello! How can I help?"
        mock_choice.message.tool_calls = None
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_llm.completion.return_value = mock_response

        resp = client.post(
            "/api/chat",
            json={"message": "Hi there"},
        )
        assert resp.status_code == 200

        with app.app_context():
            from virtual_assistant.chat.models import Conversation
            convs = Conversation.query.filter_by(user_id=user.id).all()
            assert len(convs) == 1


def test_dashboard_endpoint(client):
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "tasks" in data
    assert "events" in data
```

**Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/test_chat_routes.py -v
```
Expected: FAIL with `ImportError`

**Step 3: Write minimal implementation**

Create `virtual_assistant/chat/chat_routes.py`:

```python
import json
import uuid
from flask import Blueprint, request, Response, jsonify, stream_with_context
from flask_login import login_required, current_user
import litellm

from virtual_assistant.chat.models import Conversation, ChatMessage
from virtual_assistant.chat.tools import TOOL_DEFINITIONS, execute_tool
from virtual_assistant.database.database import db
from virtual_assistant.database.task import Task
from virtual_assistant.utils.logger import logger

chat_bp = Blueprint("chat", __name__)

SYSTEM_PROMPT = """You are Aligned, a task management assistant. You help users:
- Break down complex tasks into smaller, actionable subtasks
- Track progress by marking tasks complete
- Prioritize and reorder their task list
- Plan their day using their calendar and tasks

Be concise and action-oriented. When a user mentions completing something, use the complete_task tool. When they want to add something, use create_task. Proactively suggest breaking down large tasks.

Current date/time context will be provided with each message."""


def _get_model_for_user(user):
    """Get the LiteLLM model string for the user's configured provider."""
    # Default to gpt-4o if no provider configured
    provider = user.ai_provider or "openai"
    if provider == "openai":
        return "gpt-4o"
    return "gpt-4o"  # Fallback; user can configure model string in future


def _get_api_key_for_user(user):
    """Get the API key for the user's configured provider."""
    return user.openai_key


def _build_messages(conversation_id, new_message):
    """Build the full message list for the LLM from conversation history."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if conversation_id:
        history = Conversation.get_history(conversation_id)
        messages.extend(history)

    messages.append({"role": "user", "content": new_message})
    return messages


@chat_bp.route("/api/chat", methods=["POST"])
@login_required
def chat():
    data = request.get_json()
    if not data or not data.get("message"):
        return jsonify({"error": "message is required"}), 400

    user_message = data["message"]
    conversation_id = data.get("conversation_id")

    api_key = _get_api_key_for_user(current_user)
    if not api_key:
        return jsonify({"error": "No API key configured. Please add one in Settings."}), 400

    # Create or fetch conversation
    if conversation_id:
        conversation = db.session.get(Conversation, uuid.UUID(conversation_id))
        if not conversation or conversation.user_id != current_user.id:
            return jsonify({"error": "Conversation not found"}), 404
    else:
        conversation = Conversation(user_id=current_user.id)
        db.session.add(conversation)
        db.session.commit()
        conversation_id = conversation.id

    # Save user message
    user_msg = ChatMessage(
        conversation_id=conversation_id,
        role="user",
        content=user_message,
    )
    db.session.add(user_msg)
    db.session.commit()

    # Auto-title from first message
    if not conversation.title:
        conversation.title = user_message[:100]
        db.session.commit()

    model = _get_model_for_user(current_user)
    messages = _build_messages(conversation_id, user_message)
    # Remove the duplicate user message (it's already in history after save)
    # Actually, we saved it but get_history was called before save in _build_messages
    # so we built messages correctly with history + new message

    wants_stream = "text/event-stream" in request.headers.get("Accept", "")

    if wants_stream:
        return Response(
            stream_with_context(_stream_response(
                model, api_key, messages, conversation_id, current_user.id
            )),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "X-Conversation-Id": str(conversation_id),
            },
        )
    else:
        # Non-streaming fallback
        result = _non_streaming_response(
            model, api_key, messages, conversation_id, current_user.id
        )
        return jsonify(result)


def _non_streaming_response(model, api_key, messages, conversation_id, user_id):
    """Handle non-streaming chat completion with tool calling loop."""
    response = litellm.completion(
        model=model,
        api_key=api_key,
        messages=messages,
        tools=TOOL_DEFINITIONS,
    )

    assistant_message = response.choices[0].message
    tool_calls = assistant_message.tool_calls

    # Handle tool calls iteratively
    while tool_calls:
        # Save assistant message with tool calls
        assistant_msg = ChatMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_message.content or "",
            tool_calls=[tc.model_dump() for tc in tool_calls],
        )
        db.session.add(assistant_msg)

        # Execute each tool call and add results
        for tc in tool_calls:
            fn_name = tc.function.name
            fn_args = json.loads(tc.function.arguments)
            result = execute_tool(fn_name, fn_args, user_id)

            tool_msg = ChatMessage(
                conversation_id=conversation_id,
                role="tool",
                content=json.dumps(result),
                tool_call_id=tc.id,
            )
            db.session.add(tool_msg)
            messages.append({
                "role": "tool",
                "content": json.dumps(result),
                "tool_call_id": tc.id,
            })

        db.session.commit()

        # Add assistant message to messages for next round
        messages.append({
            "role": "assistant",
            "content": assistant_message.content or "",
            "tool_calls": [tc.model_dump() for tc in tool_calls],
        })

        # Call LLM again with tool results
        response = litellm.completion(
            model=model,
            api_key=api_key,
            messages=messages,
            tools=TOOL_DEFINITIONS,
        )
        assistant_message = response.choices[0].message
        tool_calls = assistant_message.tool_calls

    # Save final assistant message
    final_msg = ChatMessage(
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_message.content or "",
    )
    db.session.add(final_msg)
    db.session.commit()

    return {
        "conversation_id": str(conversation_id),
        "message": assistant_message.content or "",
        "tools_used": True,  # Simplified; could track which tools
    }


def _stream_response(model, api_key, messages, conversation_id, user_id):
    """Stream chat completion with tool calling support via SSE."""
    try:
        response = litellm.completion(
            model=model,
            api_key=api_key,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            stream=True,
        )

        collected_content = ""
        collected_tool_calls = {}

        for chunk in response:
            delta = chunk.choices[0].delta

            # Stream content tokens
            if delta.content:
                collected_content += delta.content
                yield f"data: {json.dumps({'type': 'token', 'content': delta.content})}\n\n"

            # Collect tool call chunks
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in collected_tool_calls:
                        collected_tool_calls[idx] = {
                            "id": tc.id or "",
                            "function": {"name": "", "arguments": ""},
                        }
                    if tc.id:
                        collected_tool_calls[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            collected_tool_calls[idx]["function"]["name"] = tc.function.name
                        if tc.function.arguments:
                            collected_tool_calls[idx]["function"]["arguments"] += tc.function.arguments

        # If there were tool calls, execute them and continue
        if collected_tool_calls:
            tool_calls_list = list(collected_tool_calls.values())

            # Save assistant message with tool calls
            assistant_msg = ChatMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=collected_content,
                tool_calls=tool_calls_list,
            )
            db.session.add(assistant_msg)

            # Execute tools and add results to messages
            messages.append({
                "role": "assistant",
                "content": collected_content,
                "tool_calls": tool_calls_list,
            })

            tools_modified_state = False
            for tc in tool_calls_list:
                fn_name = tc["function"]["name"]
                fn_args = json.loads(tc["function"]["arguments"])
                result = execute_tool(fn_name, fn_args, user_id)

                if fn_name in ("complete_task", "create_task", "update_task"):
                    tools_modified_state = True

                yield f"data: {json.dumps({'type': 'tool_call', 'name': fn_name, 'result': result})}\n\n"

                tool_msg = ChatMessage(
                    conversation_id=conversation_id,
                    role="tool",
                    content=json.dumps(result),
                    tool_call_id=tc["id"],
                )
                db.session.add(tool_msg)
                messages.append({
                    "role": "tool",
                    "content": json.dumps(result),
                    "tool_call_id": tc["id"],
                })

            db.session.commit()

            if tools_modified_state:
                yield f"data: {json.dumps({'type': 'dashboard_refresh'})}\n\n"

            # Continue streaming with tool results
            yield from _stream_response(
                model, api_key, messages, conversation_id, user_id
            )
        else:
            # No tool calls — save final message
            final_msg = ChatMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=collected_content,
            )
            db.session.add(final_msg)
            db.session.commit()

            yield f"data: {json.dumps({'type': 'done', 'conversation_id': str(conversation_id)})}\n\n"

    except Exception as e:
        logger.exception(f"Error in chat stream: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


@chat_bp.route("/api/dashboard", methods=["GET"])
@login_required
def dashboard():
    """Return current task and calendar state for the dashboard panel."""
    prioritized, unprioritized, completed = Task.get_user_tasks_by_list(current_user.id)

    tasks = {
        "prioritized": [t.to_dict() for t in prioritized],
        "unprioritized": [t.to_dict() for t in unprioritized],
        "completed": [t.to_dict() for t in (completed[:10] if completed else [])],
    }

    # Calendar events placeholder — integrate with calendar providers later
    events = []

    return jsonify({"tasks": tasks, "events": events})
```

**Step 4: Register the blueprint in `flask_app.py`**

Add to `flask_app.py` imports (after other blueprint imports, around line 27):
```python
from virtual_assistant.chat.chat_routes import chat_bp
```

Add in `create_app()` after the other `register_blueprint` calls (after line 98):
```python
app.register_blueprint(chat_bp)
```

**Step 5: Run test to verify it passes**

```bash
poetry run pytest tests/test_chat_routes.py -v
```
Expected: all 3 tests PASS

**Step 6: Commit**

```bash
git add virtual_assistant/chat/chat_routes.py virtual_assistant/flask_app.py tests/test_chat_routes.py
git commit -m "Add chat streaming API endpoint and dashboard endpoint"
```

---

### Task 6: Build the chat page template

**Files:**
- Create: `virtual_assistant/templates/chat.html`
- Modify: `virtual_assistant/flask_app.py` (add `/chat` route, redirect `/`)

**Step 1: Create the chat template**

Create `virtual_assistant/templates/chat.html`:

```html
{% extends "base.html" %}

{% block title %}Aligned - Chat{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
    .chat-layout {
        display: flex;
        height: calc(100vh - 76px);
        margin: -20px;
        gap: 0;
    }
    .chat-panel {
        flex: 6;
        display: flex;
        flex-direction: column;
        border-right: 1px solid #dee2e6;
    }
    .dashboard-panel {
        flex: 4;
        overflow-y: auto;
        padding: 1rem;
        background: #f8f9fa;
    }
    .messages {
        flex: 1;
        overflow-y: auto;
        padding: 1rem;
    }
    .message {
        margin-bottom: 1rem;
        max-width: 85%;
    }
    .message.user {
        margin-left: auto;
        background: #007bff;
        color: white;
        border-radius: 1rem 1rem 0.25rem 1rem;
        padding: 0.75rem 1rem;
    }
    .message.assistant {
        background: #e9ecef;
        border-radius: 1rem 1rem 1rem 0.25rem;
        padding: 0.75rem 1rem;
    }
    .message.assistant .content {
        line-height: 1.5;
    }
    .message.assistant .content p:last-child {
        margin-bottom: 0;
    }
    .chat-input-area {
        padding: 1rem;
        border-top: 1px solid #dee2e6;
        background: white;
    }
    .chat-input-area form {
        display: flex;
        gap: 0.5rem;
    }
    .chat-input-area textarea {
        flex: 1;
        resize: none;
        border-radius: 1.5rem;
        padding: 0.75rem 1rem;
        border: 1px solid #dee2e6;
        max-height: 120px;
    }
    .chat-input-area button {
        border-radius: 50%;
        width: 44px;
        height: 44px;
        padding: 0;
        align-self: flex-end;
    }
    .typing-indicator {
        display: none;
        padding: 0.5rem 1rem;
        color: #6c757d;
        font-style: italic;
    }
    .dashboard-section {
        margin-bottom: 1.5rem;
    }
    .dashboard-section h6 {
        border-bottom: 2px solid #dee2e6;
        padding-bottom: 0.5rem;
        margin-bottom: 0.75rem;
    }
    .task-item {
        padding: 0.5rem;
        border-radius: 0.375rem;
        margin-bottom: 0.25rem;
        background: white;
        border: 1px solid #dee2e6;
        font-size: 0.9rem;
    }
    .task-item.completed {
        text-decoration: line-through;
        opacity: 0.6;
    }
    .event-item {
        padding: 0.5rem;
        border-radius: 0.375rem;
        margin-bottom: 0.25rem;
        background: white;
        border-left: 3px solid #007bff;
        font-size: 0.9rem;
    }
    .priority-badge {
        font-size: 0.7rem;
        padding: 0.15rem 0.4rem;
        border-radius: 0.25rem;
    }
    @media (max-width: 768px) {
        .chat-layout {
            flex-direction: column;
        }
        .chat-panel {
            border-right: none;
            height: 60vh;
        }
        .dashboard-panel {
            height: 40vh;
        }
    }
</style>
{% endblock %}

{% block content %}
<div class="chat-layout">
    <div class="chat-panel">
        <div class="messages" id="messages"></div>
        <div class="typing-indicator" id="typingIndicator">
            <i class="fas fa-circle-notch fa-spin"></i> Aligned is thinking...
        </div>
        <div class="chat-input-area">
            <form id="chatForm">
                <textarea id="chatInput" placeholder="Ask about your tasks..." rows="1"
                    autofocus></textarea>
                <button type="submit" class="btn btn-primary" id="sendBtn">
                    <i class="fas fa-paper-plane"></i>
                </button>
            </form>
        </div>
    </div>
    <div class="dashboard-panel" id="dashboard">
        <div class="dashboard-section">
            <h6><i class="fas fa-calendar-day"></i> Today's Schedule</h6>
            <div id="calendarEvents">
                <span class="text-muted">No events loaded</span>
            </div>
        </div>
        <div class="dashboard-section">
            <h6><i class="fas fa-star"></i> Prioritized Tasks</h6>
            <div id="prioritizedTasks"></div>
        </div>
        <div class="dashboard-section">
            <h6><i class="fas fa-list"></i> Other Tasks</h6>
            <div id="unprioritizedTasks"></div>
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script>
const messagesEl = document.getElementById('messages');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
const typingIndicator = document.getElementById('typingIndicator');
let conversationId = null;

// Auto-resize textarea
chatInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});

// Submit on Enter (Shift+Enter for newline)
chatInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event('submit'));
    }
});

chatForm.addEventListener('submit', async function(e) {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;

    appendMessage('user', message);
    chatInput.value = '';
    chatInput.style.height = 'auto';
    typingIndicator.style.display = 'block';
    messagesEl.scrollTop = messagesEl.scrollHeight;

    try {
        const resp = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream',
            },
            body: JSON.stringify({
                message: message,
                conversation_id: conversationId,
            }),
        });

        if (!resp.ok) {
            const err = await resp.json();
            appendMessage('assistant', 'Error: ' + (err.error || 'Something went wrong'));
            typingIndicator.style.display = 'none';
            return;
        }

        // Read the conversation ID from header
        const newConvId = resp.headers.get('X-Conversation-Id');
        if (newConvId) conversationId = newConvId;

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let assistantEl = appendMessage('assistant', '');
        let contentEl = assistantEl.querySelector('.content');
        let fullContent = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const text = decoder.decode(value);
            const lines = text.split('\n');

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const data = JSON.parse(line.slice(6));

                if (data.type === 'token') {
                    fullContent += data.content;
                    contentEl.innerHTML = marked.parse(fullContent);
                    messagesEl.scrollTop = messagesEl.scrollHeight;
                } else if (data.type === 'tool_call') {
                    // Could show tool call indicator
                } else if (data.type === 'dashboard_refresh') {
                    loadDashboard();
                } else if (data.type === 'done') {
                    if (data.conversation_id) conversationId = data.conversation_id;
                } else if (data.type === 'error') {
                    contentEl.textContent = 'Error: ' + data.message;
                }
            }
        }

        typingIndicator.style.display = 'none';
    } catch (err) {
        typingIndicator.style.display = 'none';
        appendMessage('assistant', 'Connection error: ' + err.message);
    }
});

function appendMessage(role, content) {
    const div = document.createElement('div');
    div.className = 'message ' + role;
    if (role === 'assistant') {
        div.innerHTML = '<div class="content">' + (content ? marked.parse(content) : '') + '</div>';
    } else {
        div.textContent = content;
    }
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
}

async function loadDashboard() {
    try {
        const resp = await fetch('/api/dashboard');
        const data = await resp.json();

        // Render prioritized tasks
        const priEl = document.getElementById('prioritizedTasks');
        priEl.innerHTML = data.tasks.prioritized.length
            ? data.tasks.prioritized.map(t => taskHtml(t)).join('')
            : '<span class="text-muted">No prioritized tasks</span>';

        // Render unprioritized tasks
        const unpriEl = document.getElementById('unprioritizedTasks');
        unpriEl.innerHTML = data.tasks.unprioritized.length
            ? data.tasks.unprioritized.map(t => taskHtml(t)).join('')
            : '<span class="text-muted">No tasks</span>';

        // Render calendar events
        const calEl = document.getElementById('calendarEvents');
        calEl.innerHTML = data.events.length
            ? data.events.map(e => eventHtml(e)).join('')
            : '<span class="text-muted">No events today</span>';
    } catch (err) {
        console.error('Dashboard load failed:', err);
    }
}

function taskHtml(task) {
    const priorityColors = {1: 'secondary', 2: 'info', 3: 'warning', 4: 'danger'};
    const priorityLabels = {1: 'Low', 2: 'Med', 3: 'High', 4: 'Urgent'};
    const p = task.priority || 2;
    return `<div class="task-item ${task.status === 'completed' ? 'completed' : ''}">
        <span class="badge bg-${priorityColors[p]} priority-badge">${priorityLabels[p]}</span>
        ${task.title}
    </div>`;
}

function eventHtml(event) {
    return `<div class="event-item">
        <strong>${event.time || ''}</strong> ${event.title || event.subject || ''}
    </div>`;
}

// Load dashboard on page load
loadDashboard();
</script>
{% endblock %}
```

**Step 2: Add the `/chat` route and redirect `/` to it**

In `virtual_assistant/flask_app.py`, modify the `index` route (around line 147-151) to redirect to chat, and add a new chat route:

```python
@app.route("/")
@login_required
def index():
    """Redirect to chat page."""
    return redirect(url_for('chat'))

@app.route("/chat")
@login_required
def chat_page():
    """Displays the main chat interface."""
    return render_template('chat.html', user=current_user)
```

**Step 3: Verify the app starts**

```bash
poetry run flask run
```
Visit `http://localhost:5000/chat` and verify the layout renders (chat won't work without an API key, but the page should load).

**Step 4: Commit**

```bash
git add virtual_assistant/templates/chat.html virtual_assistant/flask_app.py
git commit -m "Add chat page template with dashboard panel"
```

---

### Task 7: Add user settings for LLM model selection

**Files:**
- Modify: `virtual_assistant/database/user.py` (add `llm_model` field)
- Modify: `virtual_assistant/flask_app.py` (save model in settings route)
- Modify: `virtual_assistant/chat/chat_routes.py` (use user's model)

**Step 1: Add `llm_model` column to User model**

In `virtual_assistant/database/user.py`, add after the `ai_instructions` field:
```python
llm_model = db.Column(db.String(100), nullable=True)  # e.g., 'gpt-4o', 'claude-sonnet-4-20250514'
```

**Step 2: Update `_get_model_for_user` in chat_routes.py**

```python
def _get_model_for_user(user):
    return user.llm_model or "gpt-4o"
```

**Step 3: Add model field to save_general_settings route in flask_app.py**

In the `save_general_settings` function, add after the AI instructions update:
```python
llm_model = request.form.get('llm_model')
if llm_model:
    current_user.llm_model = llm_model
```

**Step 4: Generate and apply migration**

```bash
poetry run flask db migrate -m "Add llm_model column to user"
poetry run flask db upgrade
```

**Step 5: Commit**

```bash
git add virtual_assistant/database/user.py virtual_assistant/flask_app.py virtual_assistant/chat/chat_routes.py migrations/
git commit -m "Add LLM model selection to user settings"
```

---

### Task 8: Wire up calendar integration in dashboard and tools

**Files:**
- Modify: `virtual_assistant/chat/chat_routes.py` (dashboard calendar)
- Modify: `virtual_assistant/chat/tools.py` (get_calendar tool)

**Step 1: Implement `_get_calendar` in tools.py**

Replace the placeholder `_get_calendar` function:

```python
import asyncio
from datetime import date, timedelta
from virtual_assistant.database.external_account import ExternalAccount
from virtual_assistant.meetings.calendar_provider_factory import CalendarProviderFactory


def _get_calendar(user_id, date=None):
    try:
        primary = ExternalAccount.query.filter_by(
            user_id=user_id, is_primary_calendar=True
        ).first()
        if not primary:
            return {"events": [], "message": "No primary calendar configured"}

        provider = CalendarProviderFactory.get_provider(primary.provider)
        loop = asyncio.new_event_loop()
        try:
            meetings = loop.run_until_complete(
                provider.get_meetings(primary.external_email, user_id)
            )
        finally:
            loop.close()

        events = []
        for m in meetings:
            events.append({
                "title": getattr(m, "subject", str(m)),
                "start": str(getattr(m, "start", "")),
                "end": str(getattr(m, "end", "")),
            })
        return {"events": events}
    except Exception as e:
        logger.exception(f"Error fetching calendar: {e}")
        return {"events": [], "error": str(e)}
```

**Step 2: Update dashboard endpoint to include calendar**

In `chat_routes.py`, update the `dashboard` function to call the calendar:

```python
@chat_bp.route("/api/dashboard", methods=["GET"])
@login_required
def dashboard():
    prioritized, unprioritized, completed = Task.get_user_tasks_by_list(current_user.id)

    tasks = {
        "prioritized": [t.to_dict() for t in prioritized],
        "unprioritized": [t.to_dict() for t in unprioritized],
        "completed": [t.to_dict() for t in (completed[:10] if completed else [])],
    }

    calendar_data = execute_tool("get_calendar", {}, current_user.id)
    events = calendar_data.get("events", [])

    return jsonify({"tasks": tasks, "events": events})
```

**Step 3: Verify manually**

Start the app, log in, and check `/api/dashboard` returns calendar events (if a primary calendar is configured).

**Step 4: Commit**

```bash
git add virtual_assistant/chat/tools.py virtual_assistant/chat/chat_routes.py
git commit -m "Wire up calendar integration in dashboard and chat tools"
```

---

### Task 9: End-to-end manual test and polish

**Step 1: Start the app and test the full flow**

```bash
poetry run flask run
```

- Log in
- Verify redirect to `/chat`
- Verify dashboard loads tasks and calendar
- Send a message like "What are my tasks?"
- Verify streaming response
- Send "Create a task called 'Test chatbot feature'"
- Verify task appears in dashboard
- Send "Mark that task as done"
- Verify dashboard updates

**Step 2: Fix any issues found during testing**

**Step 3: Commit any fixes**

```bash
git add -u
git commit -m "Polish chat UI and fix issues from end-to-end testing"
```

---

## Summary of new files

| File | Purpose |
|------|---------|
| `virtual_assistant/chat/__init__.py` | Package init |
| `virtual_assistant/chat/models.py` | Conversation + ChatMessage DB models |
| `virtual_assistant/chat/tools.py` | AI tool definitions + executor |
| `virtual_assistant/chat/chat_routes.py` | Chat API + dashboard endpoints |
| `virtual_assistant/templates/chat.html` | Chat + dashboard UI |
| `tests/test_chat_models.py` | Model tests |
| `tests/test_chat_tools.py` | Tool tests |
| `tests/test_chat_routes.py` | Route tests |

## Modified files

| File | Change |
|------|--------|
| `pyproject.toml` | Add litellm |
| `virtual_assistant/flask_app.py` | Register chat blueprint, redirect `/` to `/chat`, add chat route |
| `virtual_assistant/database/user.py` | Add `llm_model` column |

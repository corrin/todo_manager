import pytest
import uuid

from virtual_assistant.flask_app import create_app
from virtual_assistant.database.database import db
from virtual_assistant.database.task import Task
from virtual_assistant.database.user import User


@pytest.fixture()
def app(monkeypatch):
    # Patch Settings.DATABASE_URI before create_app so Database.init_app
    # picks up SQLite instead of the real MySQL URI.
    monkeypatch.setattr(
        "virtual_assistant.utils.settings.Settings.DATABASE_URI",
        "sqlite:///:memory:",
    )
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SERVER_NAME": "localhost",
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def user(app):
    with app.app_context():
        u = User(app_login="test@example.com")
        db.session.add(u)
        db.session.commit()
        # Return just the id to avoid DetachedInstanceError
        return type("UserRef", (), {"id": u.id})()


@pytest.fixture()
def sample_tasks(app, user):
    with app.app_context():
        task_ids = []
        for i, (title, status, priority) in enumerate([
            ("Buy groceries", "active", 2),
            ("Write report", "active", 3),
            ("Old task", "completed", 1),
        ]):
            t = Task(
                id=uuid.uuid4(),
                user_id=user.id,
                title=title,
                status=status,
                priority=priority,
                provider="sqlite",
                provider_task_id=str(uuid.uuid4()),
                task_user_email="test@example.com",
                content_hash="a" * 64,
                list_type="prioritized" if priority >= 2 else "unprioritized",
                position=i,
            )
            db.session.add(t)
            task_ids.append(t.id)
        db.session.commit()
        # Return lightweight refs to avoid detached instance errors
        return [type("TaskRef", (), {"id": tid})() for tid in task_ids]


class TestToolDefinitions:
    def test_tool_definitions_are_list(self):
        from virtual_assistant.chat.tools import TOOL_DEFINITIONS
        assert isinstance(TOOL_DEFINITIONS, list)
        assert len(TOOL_DEFINITIONS) >= 5

    def test_tool_definitions_have_valid_format(self):
        from virtual_assistant.chat.tools import TOOL_DEFINITIONS
        for tool in TOOL_DEFINITIONS:
            assert tool["type"] == "function"
            func = tool["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func
            assert func["parameters"]["type"] == "object"

    def test_expected_tool_names(self):
        from virtual_assistant.chat.tools import TOOL_DEFINITIONS
        names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
        assert "get_tasks" in names
        assert "complete_task" in names
        assert "create_task" in names
        assert "update_task" in names
        assert "get_calendar" in names


class TestGetTasks:
    def test_get_tasks_returns_tasks(self, app, user, sample_tasks):
        from virtual_assistant.chat.tools import execute_tool
        with app.app_context():
            result = execute_tool("get_tasks", {}, user.id)
            assert "tasks" in result
            assert len(result["tasks"]) >= 2  # at least the active ones

    def test_get_tasks_filter_by_status(self, app, user, sample_tasks):
        from virtual_assistant.chat.tools import execute_tool
        with app.app_context():
            result = execute_tool("get_tasks", {"status": "completed"}, user.id)
            assert all(t["status"] == "completed" for t in result["tasks"])

    def test_get_tasks_filter_by_priority(self, app, user, sample_tasks):
        from virtual_assistant.chat.tools import execute_tool
        with app.app_context():
            result = execute_tool("get_tasks", {"priority": 3}, user.id)
            assert all(t["priority"] == 3 for t in result["tasks"])


class TestCompleteTask:
    def test_complete_task_marks_done(self, app, user, sample_tasks):
        from virtual_assistant.chat.tools import execute_tool
        with app.app_context():
            active_task = sample_tasks[0]
            result = execute_tool("complete_task", {"task_id": str(active_task.id)}, user.id)
            assert result["success"] is True

            updated = db.session.get(Task, active_task.id)
            assert updated.status == "completed"

    def test_complete_task_not_found(self, app, user):
        from virtual_assistant.chat.tools import execute_tool
        with app.app_context():
            result = execute_tool("complete_task", {"task_id": str(uuid.uuid4())}, user.id)
            assert result["success"] is False
            assert "error" in result


class TestCreateTask:
    def test_create_task(self, app, user):
        from virtual_assistant.chat.tools import execute_tool
        with app.app_context():
            result = execute_tool("create_task", {
                "title": "New task from chat",
                "description": "Some description",
                "priority": 2,
            }, user.id)
            assert result["success"] is True
            assert "task" in result
            assert result["task"]["title"] == "New task from chat"
            assert result["task"]["provider"] == "sqlite"

    def test_create_task_minimal(self, app, user):
        from virtual_assistant.chat.tools import execute_tool
        with app.app_context():
            result = execute_tool("create_task", {"title": "Minimal task"}, user.id)
            assert result["success"] is True
            assert result["task"]["title"] == "Minimal task"


class TestUpdateTask:
    def test_update_task_modifies_fields(self, app, user, sample_tasks):
        from virtual_assistant.chat.tools import execute_tool
        with app.app_context():
            task = sample_tasks[0]
            result = execute_tool("update_task", {
                "task_id": str(task.id),
                "title": "Updated title",
                "priority": 4,
            }, user.id)
            assert result["success"] is True

            updated = db.session.get(Task, task.id)
            assert updated.title == "Updated title"
            assert updated.priority == 4

    def test_update_task_not_found(self, app, user):
        from virtual_assistant.chat.tools import execute_tool
        with app.app_context():
            result = execute_tool("update_task", {
                "task_id": str(uuid.uuid4()),
                "title": "Nope",
            }, user.id)
            assert result["success"] is False


class TestGetCalendar:
    def test_get_calendar_placeholder(self, app, user):
        from virtual_assistant.chat.tools import execute_tool
        with app.app_context():
            result = execute_tool("get_calendar", {}, user.id)
            assert "events" in result
            assert "message" in result


class TestUnknownTool:
    def test_unknown_tool_returns_error(self, app, user):
        from virtual_assistant.chat.tools import execute_tool
        with app.app_context():
            result = execute_tool("nonexistent_tool", {}, user.id)
            assert "error" in result

"""Chat API endpoints with SSE streaming support."""

import json

import litellm
from flask import Blueprint, Response, jsonify, request, stream_with_context
from flask_login import current_user, login_required

from virtual_assistant.chat.models import ChatMessage, Conversation
from virtual_assistant.chat.tools import TOOL_DEFINITIONS, execute_tool
from virtual_assistant.database.database import db
from virtual_assistant.database.task import Task
from virtual_assistant.utils.logger import logger

chat_bp = Blueprint("chat", __name__)

SYSTEM_PROMPT = (
    "You are Aligned, a task management assistant. You help users:\n"
    "- Break down complex tasks into smaller, actionable subtasks\n"
    "- Track progress by marking tasks complete\n"
    "- Prioritize and reorder their task list\n"
    "- Plan their day using their calendar and tasks\n\n"
    "Be concise and action-oriented. When a user mentions completing something, "
    "use the complete_task tool. When they want to add something, use create_task. "
    "Proactively suggest breaking down large tasks."
)

MUTATING_TOOLS = {"complete_task", "create_task", "update_task"}


def _build_messages(conversation_id, user_message_content):
    """Build the full messages list: system prompt + history + new user message."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if current_user.ai_instructions:
        messages[0]["content"] += f"\n\nAdditional instructions: {current_user.ai_instructions}"

    history = Conversation.get_history(conversation_id)
    messages.extend(history)

    messages.append({"role": "user", "content": user_message_content})
    return messages


def _get_model():
    """Get the LLM model from user settings or default."""
    return getattr(current_user, "llm_model", None) or "gpt-4o"


def _execute_tool_calls(tool_calls, user_id):
    """Execute tool calls and return results with metadata."""
    results = []
    for tc in tool_calls:
        func = tc.get("function", {}) if isinstance(tc, dict) else tc.function
        name = func.get("name", "") if isinstance(func, dict) else func.name
        args_str = func.get("arguments", "{}") if isinstance(func, dict) else func.arguments
        tc_id = tc.get("id", "") if isinstance(tc, dict) else tc.id

        try:
            arguments = json.loads(args_str)
        except (json.JSONDecodeError, TypeError):
            arguments = {}

        result = execute_tool(name, arguments, user_id)
        results.append(
            {
                "tool_call_id": tc_id,
                "name": name,
                "result": result,
                "is_mutating": name in MUTATING_TOOLS,
            }
        )
    return results


def _save_assistant_message(conversation, content, tool_calls_data=None):
    """Save the assistant's final message to the database."""
    msg = ChatMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=content,
        tool_calls=tool_calls_data,
        sequence=conversation.next_sequence(),
    )
    db.session.add(msg)
    db.session.commit()


def _save_tool_messages(conversation, tool_calls_raw, tool_results):
    """Save the assistant tool_calls message and tool result messages."""
    # Save assistant message with tool_calls
    tc_data = []
    for tc in tool_calls_raw:
        if isinstance(tc, dict):
            tc_data.append(tc)
        else:
            tc_data.append(
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
            )

    assistant_msg = ChatMessage(
        conversation_id=conversation.id,
        role="assistant",
        content="",
        tool_calls=tc_data,
        sequence=conversation.next_sequence(),
    )
    db.session.add(assistant_msg)
    db.session.commit()

    # Save each tool result as a message
    for tr in tool_results:
        tool_msg = ChatMessage(
            conversation_id=conversation.id,
            role="tool",
            content=json.dumps(tr["result"]),
            tool_call_id=tr["tool_call_id"],
            sequence=conversation.next_sequence(),
        )
        db.session.add(tool_msg)
        db.session.commit()


@chat_bp.route("/api/chat", methods=["POST"])
@login_required
def chat():
    """Main chat endpoint. Supports SSE streaming or JSON response."""
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "Message is required"}), 400

    api_key = current_user.ai_api_key
    if not api_key:
        return (
            jsonify({"error": "No API key configured. Go to Settings to add one."}),
            400,
        )

    # Get or create conversation
    conversation_id = data.get("conversation_id")
    if conversation_id:
        conversation = db.session.get(Conversation, conversation_id)
        if not conversation or conversation.user_id != current_user.id:
            return jsonify({"error": "Conversation not found"}), 404
    else:
        conversation = Conversation(user_id=current_user.id)
        db.session.add(conversation)
        db.session.commit()

    # Auto-title from first message
    if not conversation.title:
        conversation.title = message[:100]
        db.session.commit()

    # Save user message
    user_msg = ChatMessage(
        conversation_id=conversation.id,
        role="user",
        content=message,
        sequence=conversation.next_sequence(),
    )
    db.session.add(user_msg)
    db.session.commit()

    # Build messages for LLM
    messages = _build_messages(conversation.id, message)
    # Remove the duplicate user message we just appended — it's already in history
    # Actually, get_history includes the message we just saved, so don't append again.
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if current_user.ai_instructions:
        messages[0]["content"] += f"\n\nAdditional instructions: {current_user.ai_instructions}"
    messages.extend(Conversation.get_history(conversation.id))

    model = _get_model()

    # Check if client wants SSE streaming
    accept = request.headers.get("Accept", "")
    if "text/event-stream" in accept:
        return _stream_response(conversation, messages, model, api_key)
    else:
        return _json_response(conversation, messages, model, api_key)


def _json_response(conversation, messages, model, api_key):
    """Non-streaming JSON response with tool calling loop."""
    try:
        while True:
            response = litellm.completion(
                model=model,
                api_key=api_key,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                stream=False,
            )

            choice = response.choices[0]
            if choice.message.tool_calls:
                tool_results = _execute_tool_calls(choice.message.tool_calls, current_user.id)
                _save_tool_messages(conversation, choice.message.tool_calls, tool_results)

                # Add to messages for next iteration
                messages.append(
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in choice.message.tool_calls
                        ],
                    }
                )
                for tr in tool_results:
                    messages.append(
                        {
                            "role": "tool",
                            "content": json.dumps(tr["result"]),
                            "tool_call_id": tr["tool_call_id"],
                        }
                    )
                continue

            # No tool calls — we have the final response
            content = choice.message.content or ""
            _save_assistant_message(conversation, content)
            return jsonify(
                {
                    "content": content,
                    "conversation_id": str(conversation.id),
                }
            )

    except Exception as e:
        logger.exception(f"Error in chat endpoint: {e}")
        raise


def _stream_response(conversation, messages, model, api_key):
    """SSE streaming response with tool calling loop."""

    def generate():
        current_messages = list(messages)

        try:
            while True:
                response = litellm.completion(
                    model=model,
                    api_key=api_key,
                    messages=current_messages,
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

                    # Collect tool calls incrementally
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in collected_tool_calls:
                                collected_tool_calls[idx] = {
                                    "id": "",
                                    "function": {"name": "", "arguments": ""},
                                }
                            if tc.id:
                                collected_tool_calls[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    collected_tool_calls[idx]["function"]["name"] = tc.function.name
                                if tc.function.arguments:
                                    collected_tool_calls[idx]["function"]["arguments"] += tc.function.arguments

                # If tool calls were collected, execute them
                if collected_tool_calls:
                    tool_calls_list = [collected_tool_calls[i] for i in sorted(collected_tool_calls)]
                    tool_results = _execute_tool_calls(tool_calls_list, current_user.id)
                    _save_tool_messages(conversation, tool_calls_list, tool_results)

                    # Send tool call events
                    any_mutating = False
                    for tr in tool_results:
                        yield f"data: {json.dumps({'type': 'tool_call', 'name': tr['name'], 'result': tr['result']})}\n\n"
                        if tr["is_mutating"]:
                            any_mutating = True

                    if any_mutating:
                        yield f"data: {json.dumps({'type': 'dashboard_refresh'})}\n\n"

                    # Add to messages for next iteration
                    current_messages.append(
                        {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": tc["id"],
                                    "type": "function",
                                    "function": tc["function"],
                                }
                                for tc in tool_calls_list
                            ],
                        }
                    )
                    for tr in tool_results:
                        current_messages.append(
                            {
                                "role": "tool",
                                "content": json.dumps(tr["result"]),
                                "tool_call_id": tr["tool_call_id"],
                            }
                        )
                    continue

                # No tool calls — stream is complete
                _save_assistant_message(conversation, collected_content)
                yield f"data: {json.dumps({'type': 'done', 'conversation_id': str(conversation.id)})}\n\n"
                break

        except Exception as e:
            logger.exception(f"Error in streaming chat: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Conversation-Id": str(conversation.id),
        },
    )


@chat_bp.route("/api/dashboard", methods=["GET"])
@login_required
def dashboard():
    """Return current tasks and calendar state."""
    prioritized, unprioritized, completed = Task.get_user_tasks_by_list(current_user.id)

    calendar_data = execute_tool("get_calendar", {}, current_user.id)

    return jsonify(
        {
            "tasks": {
                "prioritized": [t.to_dict() for t in prioritized],
                "unprioritized": [t.to_dict() for t in unprioritized],
                "completed": [t.to_dict() for t in completed[:10]],
            },
            "events": calendar_data.get("events", []),
        }
    )

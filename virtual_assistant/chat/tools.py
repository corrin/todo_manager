"""OpenAI-format tool definitions and executor for task management."""

import uuid

from virtual_assistant.database.database import db
from virtual_assistant.database.task import Task

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_tasks",
            "description": "List the user's tasks, optionally filtered by status or priority.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["active", "completed"],
                        "description": "Filter tasks by status.",
                    },
                    "priority": {
                        "type": "integer",
                        "enum": [1, 2, 3, 4],
                        "description": "Filter tasks by priority (1=low, 2=medium, 3=high, 4=urgent).",
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
            "description": "Create a new task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title of the task.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description of the task.",
                    },
                    "priority": {
                        "type": "integer",
                        "enum": [1, 2, 3, 4],
                        "description": "Priority level (1=low, 2=medium, 3=high, 4=urgent).",
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
            "description": "Update an existing task's fields.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The UUID of the task to update.",
                    },
                    "title": {
                        "type": "string",
                        "description": "New title for the task.",
                    },
                    "description": {
                        "type": "string",
                        "description": "New description for the task.",
                    },
                    "priority": {
                        "type": "integer",
                        "enum": [1, 2, 3, 4],
                        "description": "New priority (1=low, 2=medium, 3=high, 4=urgent).",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "completed"],
                        "description": "New status for the task.",
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
            "description": "Get calendar events for a given date.",
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


def _get_tasks(arguments, user_id):
    """List tasks with optional filters."""
    query = Task.query.filter_by(user_id=user_id)

    status = arguments.get("status")
    if status:
        query = query.filter_by(status=status)

    priority = arguments.get("priority")
    if priority is not None:
        query = query.filter_by(priority=priority)

    tasks = query.order_by(Task.position).all()
    return {"tasks": [t.to_dict() for t in tasks]}


def _complete_task(arguments, user_id):
    """Mark a task as completed."""
    task_id = arguments.get("task_id")
    try:
        task = db.session.get(Task, uuid.UUID(task_id))
    except (ValueError, AttributeError):
        return {"success": False, "error": f"Invalid task ID: {task_id}"}

    if not task or task.user_id != user_id:
        return {"success": False, "error": "Task not found."}

    task.status = "completed"
    db.session.commit()
    return {"success": True, "task": task.to_dict()}


def _create_task(arguments, user_id):
    """Create a new task."""
    import hashlib
    import json

    title = arguments.get("title")
    description = arguments.get("description")
    priority = arguments.get("priority")

    content_hash = hashlib.sha256(
        json.dumps(
            {"title": title, "description": description, "priority": priority},
            sort_keys=True,
        ).encode()
    ).hexdigest()

    task = Task(
        id=uuid.uuid4(),
        user_id=user_id,
        title=title,
        description=description,
        priority=priority,
        status="active",
        provider="sqlite",
        provider_task_id=str(uuid.uuid4()),
        task_user_email="chat",
        content_hash=content_hash,
        list_type="unprioritized",
        position=0,
    )
    db.session.add(task)
    db.session.commit()
    return {"success": True, "task": task.to_dict()}


def _update_task(arguments, user_id):
    """Update an existing task."""
    task_id = arguments.get("task_id")
    try:
        task = db.session.get(Task, uuid.UUID(task_id))
    except (ValueError, AttributeError):
        return {"success": False, "error": f"Invalid task ID: {task_id}"}

    if not task or task.user_id != user_id:
        return {"success": False, "error": "Task not found."}

    for field in ("title", "description", "priority", "status"):
        if field in arguments:
            setattr(task, field, arguments[field])

    db.session.commit()
    return {"success": True, "task": task.to_dict()}


def _get_calendar(arguments, user_id):
    """Get calendar events for a given date."""
    import asyncio

    from virtual_assistant.database.external_account import ExternalAccount
    from virtual_assistant.meetings.calendar_provider_factory import (
        CalendarProviderFactory,
    )
    from virtual_assistant.utils.logger import logger

    try:
        primary = ExternalAccount.query.filter_by(user_id=user_id, is_primary_calendar=True).first()
        if not primary:
            return {"events": [], "message": "No primary calendar configured"}

        provider = CalendarProviderFactory.get_provider(primary.provider)
        loop = asyncio.new_event_loop()
        try:
            meetings = loop.run_until_complete(provider.get_meetings(primary.external_email, user_id))
        finally:
            loop.close()

        events = []
        for m in meetings:
            events.append(
                {
                    "title": getattr(m, "subject", str(m)),
                    "start": str(getattr(m, "start", "")),
                    "end": str(getattr(m, "end", "")),
                }
            )
        return {"events": events}
    except Exception as e:
        logger.exception(f"Error fetching calendar: {e}")
        return {"events": [], "error": str(e)}


_TOOL_HANDLERS = {
    "get_tasks": _get_tasks,
    "complete_task": _complete_task,
    "create_task": _create_task,
    "update_task": _update_task,
    "get_calendar": _get_calendar,
}


def execute_tool(tool_name, arguments, user_id):
    """Dispatch a tool call to the appropriate handler.

    Args:
        tool_name: Name of the tool to execute.
        arguments: Dictionary of arguments for the tool.
        user_id: The current user's database ID.

    Returns:
        Dictionary with the tool's result.
    """
    handler = _TOOL_HANDLERS.get(tool_name)
    if not handler:
        return {"error": f"Unknown tool: {tool_name}"}
    return handler(arguments, user_id)

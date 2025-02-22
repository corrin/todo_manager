from todoist_api_python.api import TodoistAPI
from flask import redirect, url_for
from datetime import datetime
from typing import List, Optional

from .task_provider import TaskProvider, Task
from virtual_assistant.utils.logger import logger


class TodoistProvider(TaskProvider):
    """Todoist implementation of the task provider interface."""

    INSTRUCTION_TASK_TITLE = "AI Instructions"

    def __init__(self):
        super().__init__()
        self.api = None

    def _get_provider_name(self) -> str:
        return "todoist"

    def _initialize_api(self, email):
        """Initialize or refresh the Todoist API client."""
        if self.api is None:
            credentials = self.get_credentials(email)
            if credentials:
                self.api = TodoistAPI(credentials.get("api_key"))

    def authenticate(self, email):
        """Check if we have valid credentials and return auth URL if needed."""
        credentials = self.get_credentials(email)
        
        if not credentials:
            logger.info(f"No Todoist credentials found for {email}")
            return self.provider_name, redirect(url_for('todoist_auth.setup_credentials'))
        
        # Test the credentials
        try:
            api = TodoistAPI(credentials.get("api_key"))
            api.get_projects()  # Simple API call to test credentials
            logger.debug(f"Todoist credentials valid for {email}")
            return None
        except Exception as e:
            logger.error(f"Todoist credentials invalid for {email}: {e}")
            return self.provider_name, redirect(url_for('todoist_auth.setup_credentials'))

    def get_tasks(self, email) -> List[Task]:
        """Get all tasks from Todoist."""
        self._initialize_api(email)
        if not self.api:
            raise Exception(f"No Todoist API client for {email}")

        try:
            todoist_tasks = self.api.get_tasks()
            tasks = []
            for t in todoist_tasks:
                # Skip the instruction task as it's handled separately
                if t.content == self.INSTRUCTION_TASK_TITLE:
                    continue
                
                # Convert Todoist task to our Task format
                due_date = None
                if t.due:
                    due_date = datetime.fromisoformat(t.due.datetime) if t.due.datetime else None

                task = Task(
                    id=t.id,
                    title=t.content,
                    project_id=t.project_id,
                    priority=t.priority,
                    due_date=due_date,
                    status="completed" if t.is_completed else "active",
                    is_instruction=False
                )
                tasks.append(task)
            
            logger.debug(f"Retrieved {len(tasks)} tasks for {email}")
            return tasks
        except Exception as e:
            logger.error(f"Error getting Todoist tasks: {e}")
            raise

    def get_ai_instructions(self, email) -> Optional[str]:
        """Get the AI instruction task content."""
        self._initialize_api(email)
        if not self.api:
            raise Exception(f"No Todoist API client for {email}")

        try:
            # Search for the instruction task
            tasks = self.api.get_tasks(filter=f"search:{self.INSTRUCTION_TASK_TITLE}")
            instruction_task = next((t for t in tasks if t.content == self.INSTRUCTION_TASK_TITLE), None)
            
            if instruction_task:
                logger.debug(f"Found AI instruction task for {email}")
                # The actual instructions are in the task description
                return instruction_task.description
            else:
                logger.warning(f"No AI instruction task found for {email}")
                return None
        except Exception as e:
            logger.error(f"Error getting AI instructions: {e}")
            raise

    def update_task_status(self, email, task_id: str, status: str) -> bool:
        """Update task completion status."""
        self._initialize_api(email)
        if not self.api:
            raise Exception(f"No Todoist API client for {email}")

        try:
            if status == "completed":
                self.api.close_task(task_id)
            else:
                self.api.reopen_task(task_id)
            logger.debug(f"Updated task {task_id} status to {status}")
            return True
        except Exception as e:
            logger.error(f"Error updating task status: {e}")
            raise

    def create_instruction_task(self, email, instructions: str) -> bool:
        """Create or update the AI instruction task."""
        self._initialize_api(email)
        if not self.api:
            raise Exception(f"No Todoist API client for {email}")

        try:
            # Check if instruction task exists
            tasks = self.api.get_tasks(filter=f"search:{self.INSTRUCTION_TASK_TITLE}")
            instruction_task = next((t for t in tasks if t.content == self.INSTRUCTION_TASK_TITLE), None)
            
            if instruction_task:
                # Update existing task
                self.api.update_task(
                    task_id=instruction_task.id,
                    description=instructions
                )
                logger.debug(f"Updated AI instruction task for {email}")
            else:
                # Create new task
                self.api.add_task(
                    content=self.INSTRUCTION_TASK_TITLE,
                    description=instructions
                )
                logger.debug(f"Created AI instruction task for {email}")
            
            return True
        except Exception as e:
            logger.error(f"Error managing instruction task: {e}")
            raise
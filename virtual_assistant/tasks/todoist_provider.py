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
            logger.info(f"[TODOIST] Retrieving tasks for {email}")
            
            # Get projects first to map project IDs to names
            projects = {}
            try:
                todoist_projects = self.api.get_projects()
                for p in todoist_projects:
                    projects[p.id] = p.name
                logger.debug(f"[TODOIST] Retrieved {len(projects)} projects for {email}")
            except Exception as e:
                logger.warning(f"[TODOIST] Error getting Todoist projects: {e}")
            
            # Get tasks
            todoist_tasks = self.api.get_tasks()
            logger.info(f"[TODOIST] Retrieved {len(todoist_tasks)} raw tasks from Todoist API")
            
            # Count completed and active tasks
            completed_count = 0
            active_count = 0
            
            tasks = []
            for t in todoist_tasks:
                # Skip the instruction task as it's handled separately
                if t.content == self.INSTRUCTION_TASK_TITLE:
                    continue
                
                # Convert Todoist task to our Task format
                due_date = None
                if t.due:
                    due_date = datetime.fromisoformat(t.due.datetime) if t.due.datetime else None

                # Get project name if available
                project_name = projects.get(t.project_id)
                
                is_completed = t.is_completed
                status = "completed" if is_completed else "active"
                
                if is_completed:
                    completed_count += 1
                    logger.debug(f"[TODOIST] Task {t.id} '{t.content}' is COMPLETED")
                else:
                    active_count += 1
                    logger.debug(f"[TODOIST] Task {t.id} '{t.content}' is ACTIVE")
                
                task = Task(
                    id=t.id,
                    title=t.content,
                    project_id=t.project_id,
                    priority=t.priority,
                    due_date=due_date,
                    status=status,
                    is_instruction=False,
                    parent_id=getattr(t, 'parent_id', None),
                    section_id=getattr(t, 'section_id', None),
                    project_name=project_name
                )
                tasks.append(task)
            
            logger.info(f"[TODOIST] Task summary for {email}: {len(tasks)} total tasks ({completed_count} completed, {active_count} active)")
            
            # Log all task IDs and statuses at once for easy comparison
            status_summary = {task.id: task.status for task in tasks}
            logger.debug(f"[TODOIST] Task status map: {status_summary}")
            
            return tasks
        except Exception as e:
            logger.error(f"[TODOIST] Error getting Todoist tasks: {e}")
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

        logger.info(f"[TODOIST] Attempting to update task {task_id} status to '{status}' for {email}")
        
        try:
            # First, check if the task exists by trying to get it
            try:
                task = self.api.get_task(task_id)
                # Task exists, check if status change is needed
                current_status = "completed" if task.is_completed else "active"
                logger.info(f"[TODOIST] Task {task_id} '{task.content}' current status: '{current_status}', requested status: '{status}'")
                
                if current_status == status:
                    # Task is already in requested status, no need to update
                    logger.info(f"[TODOIST] Task {task_id} already has status '{status}', no update needed")
                    return True
            except Exception as task_error:
                # If we can't get the task, it might be deleted or invalid
                error_msg = str(task_error).lower()
                if "not found" in error_msg or "404" in error_msg:
                    logger.warning(f"[TODOIST] Task {task_id} not found: {task_error}")
                    raise Exception(f"Task {task_id} not found in Todoist. It may have been deleted or synced incorrectly. Try refreshing your tasks.")
                # For other errors with task lookup, continue and try to update anyway
                logger.warning(f"[TODOIST] Could not verify task {task_id} existence: {task_error}. Attempting update anyway.")
            
            # Try to update the task status
            try:
                if status == "completed":
                    logger.info(f"[TODOIST] Marking task {task_id} as completed")
                    self.api.close_task(task_id)
                else:
                    logger.info(f"[TODOIST] Marking task {task_id} as active (reopening)")
                    self.api.reopen_task(task_id)
                logger.info(f"[TODOIST] Successfully updated task {task_id} status to '{status}'")
                return True
            except Exception as update_error:
                error_msg = str(update_error).lower()
                logger.error(f"[TODOIST] Error updating task status: {update_error}")
                # Handle common errors with better messages
                if "not found" in error_msg or "404" in error_msg:
                    raise Exception(f"Task {task_id} not found in Todoist. It may have been deleted or synced incorrectly. Try refreshing your tasks.")
                else:
                    raise update_error
                
        except Exception as e:
            # Check for common API errors and provide better messages
            error_msg = str(e).lower()
            
            if "rate limit" in error_msg or "429" in error_msg:
                logger.error(f"[TODOIST] Rate limit exceeded: {e}")
                raise Exception("Todoist API rate limit reached. Please wait a moment and try again.")
            elif "authentication" in error_msg or "unauthorized" in error_msg or "401" in error_msg:
                logger.error(f"[TODOIST] Authentication error: {e}")
                raise Exception("Todoist authentication error. Please check your API key in Settings.")
            elif "network" in error_msg or "timeout" in error_msg or "connection" in error_msg:
                logger.error(f"[TODOIST] Network error: {e}")
                raise Exception("Network error when connecting to Todoist. Please check your internet connection.")
            else:
                # If not a specific known error, log the original error and pass it along
                logger.error(f"[TODOIST] Error updating task status: {e}")
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
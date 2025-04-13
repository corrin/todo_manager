from todoist_api_python.api import TodoistAPI
from flask import redirect, url_for
from datetime import datetime
from typing import List, Optional, Dict, Any
from .task_provider import TaskProvider, Task
from virtual_assistant.database.task import TaskAccount
from virtual_assistant.database.user import User
from virtual_assistant.utils.logger import logger


class TodoistProvider(TaskProvider):
    """Todoist implementation of the task provider interface."""

    INSTRUCTION_TASK_TITLE = "AI Instructions"

    def __init__(self):
        super().__init__()
        self.api = None

    def _get_provider_name(self) -> str:
        return "todoist"

    # --- API Initialization ---

    def _initialize_api(self, user_id, task_user_email):
        """Initialize the Todoist API client using credentials from the database."""
        if self.api is None:
            logger.debug(f"Attempting to initialize Todoist API for user_id='{user_id}', task_user_email='{task_user_email}'")
            user = User.query.filter_by(id=user_id).first()
            if not user:
                 logger.error(f"Cannot initialize Todoist API: User not found for user_id '{user_id}'")
                 self.api = None
                 return
            # For Todoist, task_user_email is the user's email
            account = TaskAccount.get_account(user_id=user_id, provider_name=self.provider_name, task_user_email=task_user_email)
            if account and account.api_key:
                try:
                    self.api = TodoistAPI(account.api_key)
                    logger.debug(f"Successfully initialized Todoist API for user_id='{user_id}'")
                except Exception as e:
                    logger.error(f"Failed to initialize Todoist API for user_id='{user_id}' with stored key: {e}")
                    self.api = None
            else:
                 logger.warning(f"Could not initialize Todoist API: TaskAccount or API key not found in DB for user_id='{user_id}', provider='{self.provider_name}', task_user_email='{task_user_email}'")

    # --- Provider Methods ---

    # Signature matches abstract method in TaskProvider
    def authenticate(self, user_id, task_user_email):
        """Check if we have valid credentials in the database and return auth URL if needed."""
        logger.debug(f"Authenticating Todoist for user_id='{user_id}', task_user_email='{task_user_email}'")
        user = User.query.filter_by(id=user_id).first()
        if not user:
            logger.error(f"Cannot authenticate Todoist: User not found for user_id '{user_id}'")
            # Decide how to handle - maybe redirect to login or show error?
            # For now, treat as no credentials found.
            return self.provider_name, redirect(url_for('todoist_auth.setup_credentials'))
        # Get the account using the provided task_user_email
        account = TaskAccount.get_account(user_id=user_id, provider_name=self.provider_name, task_user_email=task_user_email)

        if not account or not account.api_key:
            logger.info(f"No valid Todoist credentials found in DB for user_id='{user_id}'. Redirecting to setup.")
            return self.provider_name, redirect(url_for('todoist_auth.setup_credentials'))

        # Test the stored credentials to ensure the API key is still valid
        try:
            api = TodoistAPI(account.api_key)
            api.get_projects() # Simple API call to test credentials
            logger.debug(f"Todoist credentials valid for user_id='{user_id}'")
            return None # Already authenticated
        except Exception as e:
            logger.error(f"Todoist credentials invalid for user_id='{user_id}': {e}. Redirecting to setup.")
            # Redirect to setup page if credentials are bad
            return self.provider_name, redirect(url_for('todoist_auth.setup_credentials'))

    # Signature matches abstract method in TaskProvider
    def get_tasks(self, user_id, task_user_email) -> List[Task]:
        """Get all tasks from Todoist."""
        self._initialize_api(user_id, task_user_email)
        if not self.api:
            raise Exception(f"Todoist API not initialized for user_id='{user_id}', task_user_email='{task_user_email}'. Check credentials.")

        try:
            # Log using both identifiers for clarity, even if API calls only use the key derived from them
            logger.info(f"[TODOIST] Retrieving tasks for user_id='{user_id}', task_user_email='{task_user_email}'")

            # Get projects first to map project IDs to names
            projects = {}
            try:
                todoist_projects = self.api.get_projects()
                for p in todoist_projects:
                    projects[p.id] = p.name
                logger.debug(f"[TODOIST] Retrieved {len(projects)} projects for user_id='{user_id}'")
            except Exception as e:
                logger.error(f"[TODOIST] Error getting Todoist projects: {e}")
                # Instead of silently continuing without project data, raise an exception
                raise Exception(f"Could not retrieve your Todoist projects: {e}")

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
                    # Handle potential date-only strings if datetime is None
                    due_date_str = t.due.datetime if t.due.datetime else t.due.date
                    try:
                        # Attempt to parse, assuming ISO format with potential Z
                        due_date = datetime.fromisoformat(due_date_str.replace("Z", "+00:00"))
                    except ValueError:
                         # Handle simple date string YYYY-MM-DD
                         try:
                             due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
                         except ValueError:
                             logger.warning(f"Could not parse Todoist due date: {due_date_str}")
                             due_date = None # Fallback if parsing fails


                # Get project name if available
                project_name = projects.get(t.project_id)

                is_completed = t.is_completed
                status = "completed" if is_completed else "active"

                if is_completed:
                    completed_count += 1
                else:
                    active_count += 1

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

            logger.info(f"[TODOIST] Task summary for user_id='{user_id}': {len(tasks)} total tasks ({completed_count} completed, {active_count} active)")

            return tasks
        except Exception as e:
            logger.error(f"[TODOIST] Error getting Todoist tasks for user_id='{user_id}': {e}")
            raise

    # Signature matches abstract method in TaskProvider
    def get_ai_instructions(self, user_id, task_user_email) -> Optional[str]:
        """Get the AI instruction task content."""
        self._initialize_api(user_id, task_user_email)
        if not self.api:
            raise Exception(f"Todoist API not initialized for user_id='{user_id}', task_user_email='{task_user_email}'. Check credentials.")

        try:
            # Search for the instruction task
            tasks = self.api.get_tasks(filter=f"search:{self.INSTRUCTION_TASK_TITLE}")
            instruction_task = next((t for t in tasks if t.content == self.INSTRUCTION_TASK_TITLE), None)

            if instruction_task:
                logger.debug(f"Found AI instruction task for user_id='{user_id}', task_user_email='{task_user_email}'")
                # The actual instructions are in the task description
                return instruction_task.description
            else:
                logger.warning(f"No AI instruction task found for user_id='{user_id}', task_user_email='{task_user_email}'")
                return None
        except Exception as e:
            logger.error(f"Error getting AI instructions for user_id='{user_id}', task_user_email='{task_user_email}': {e}")
            raise

    # Signature matches abstract method in TaskProvider
    def update_task_status(self, user_id, task_id, task_user_email=None, provider_task_id=None, status: str = None) -> bool:
        """Update task completion status."""
        # Look up the task to get provider_task_id and task_user_email
        from virtual_assistant.database.task import Task
        task = Task.query.filter_by(id=task_id, user_id=user_id).first()
        if not task:
            raise ValueError(f"Task with ID {task_id} not found")
            
        # Get the provider-specific information
        provider_task_id = task.provider_task_id
        task_user_email = task.task_user_email
        self._initialize_api(user_id, task_user_email)
        if not self.api:
             raise Exception(f"Todoist API not initialized for user_id='{user_id}', task_user_email='{task_user_email}'. Check credentials.")
        logger.info(f"[TODOIST] Attempting to update task (UUID: {task_id}, provider_task_id: {provider_task_id}) status to '{status}' for user_id='{user_id}', task_user_email='{task_user_email}'")

        
        try:
            # First, check if the task exists by trying to get it
            try:
                task = self.api.get_task(provider_task_id)
                # Task exists, check if status change is needed
                current_status = "completed" if task.is_completed else "active"
                logger.info(f"[TODOIST] Task (UUID: {task_id}, provider_task_id: {provider_task_id}) '{task.content}' current status: '{current_status}', requested status: '{status}'")
                
                if current_status == status:
                    # Task is already in requested status, no need to update
                    logger.info(f"[TODOIST] Task (UUID: {task_id}, provider_task_id: {provider_task_id}) already has status '{status}', no update needed")
                    return True
            except Exception as task_error:
                # If we can't get the task, it might be deleted or invalid
                error_msg = str(task_error).lower()
                if "not found" in error_msg or "404" in error_msg:
                    logger.warning(f"[TODOIST] Task (UUID: {task_id}, provider_task_id: {provider_task_id}) not found: {task_error}")
                    raise Exception(f"Task with provider_task_id {provider_task_id} not found in Todoist. It may have been deleted or synced incorrectly. Try refreshing your tasks.")
                # For other errors with task lookup, continue and try to update anyway
                logger.warning(f"[TODOIST] Could not verify task (UUID: {task_id}, provider_task_id: {provider_task_id}) existence: {task_error}. Attempting update anyway.")
            
            # Try to update the task status
            try:
                if status == "completed":
                    logger.info(f"[TODOIST] Marking task (UUID: {task_id}, provider_task_id: {provider_task_id}) as completed")
                    self.api.close_task(provider_task_id)
                else:
                    logger.info(f"[TODOIST] Marking task (UUID: {task_id}, provider_task_id: {provider_task_id}) as active (reopening)")
                    self.api.reopen_task(provider_task_id)
                logger.info(f"[TODOIST] Successfully updated task (UUID: {task_id}, provider_task_id: {provider_task_id}) status to '{status}'")
                return True
            except Exception as update_error:
                error_msg = str(update_error).lower()
                logger.error(f"[TODOIST] Error updating task status: {update_error}")
                # Handle common errors with better messages
                if "not found" in error_msg or "404" in error_msg:
                    raise Exception(f"Task {task_id} with provider_task_id {provider_task_id} not found in Todoist. It may have been deleted or synced incorrectly. Try refreshing your tasks.")
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
                logger.error(f"[TODOIST] Error updating task status for user_id='{user_id}', task_user_email='{task_user_email}': {e}")
                raise

    # Signature matches abstract method in TaskProvider
    def create_instruction_task(self, user_id, task_user_email, instructions: str) -> bool:
        """Create or update the AI instruction task."""
        self._initialize_api(user_id, task_user_email)
        if not self.api:
            raise Exception(f"Todoist API not initialized for user_id='{user_id}', task_user_email='{task_user_email}'. Check credentials.")

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
                logger.debug(f"Updated AI instruction task for user_id='{user_id}', task_user_email='{task_user_email}'")
            else:
                # Create new task
                self.api.add_task(
                    content=self.INSTRUCTION_TASK_TITLE,
                    description=instructions
                )
                logger.debug(f"Created AI instruction task for user_id='{user_id}', task_user_email='{task_user_email}'")
            
            return True
        except Exception as e:
            logger.error(f"Error managing instruction task for user_id='{user_id}', task_user_email='{task_user_email}': {e}")
            raise
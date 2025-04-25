from todoist_api_python.api import TodoistAPI
from flask import redirect, url_for
from datetime import datetime
from typing import List, Optional, Dict, Any
from .task_provider import TaskProvider, Task
from virtual_assistant.database.task import TaskAccount
from virtual_assistant.database.user import User
from virtual_assistant.utils.logger import logger
from virtual_assistant.database.task import TaskAccount

class TodoistProvider(TaskProvider):

    def get_task_accounts(self, user_id):
        """Get all Todoist task accounts for the specified user."""
        return TaskAccount.query.filter_by(
            user_id=user_id,
            provider_name=self.provider_name
        ).all()
    
    def update_task(self, user_id, task_id, task_data=None):
        """
        Updates a task in Todoist and syncs the changes.
        
        Args:
            user_id: The user's database ID
            task_id: The task's primary key
            task_data: Dictionary containing fields to update
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        if task_data is None:
            task_data = {}
        try:
            # Get task account for the specified user
            task_accounts = self.get_task_accounts(user_id)
            
            if not task_accounts:
                logger.error(f"No Todoist accounts found for user {user_id}")
                return False
            
            # For simplicity, use the first account (can be enhanced to determine the correct account)
            account = task_accounts[0]
            api_key = account.credentials.get('api_key')
            
            if not api_key:
                logger.error(f"No API key found for Todoist account {account.task_user_email}")
                return False
            
            # Initialize Todoist API
            from todoist_api_python.api import TodoistAPI
            api = TodoistAPI(api_key)
            
            # Prepare update arguments
            update_args = {}
            
            if title is not None:
                update_args['content'] = title
                
            if due_date is not None:
                # Convert to Todoist date format
                if due_date:  # Only if not empty string
                    update_args['due_date'] = due_date
                else:
                    # To clear the due date, we need to pass it differently
                    update_args['due_string'] = ''
            
            if priority is not None:
                # Todoist uses reverse priority (4=p1, 3=p2, 2=p3, 1=p4)
                # Convert our priority to Todoist's format
                todoist_priority = 5 - priority  # 1->4, 2->3, 3->2, 4->1
                update_args['priority'] = todoist_priority
            
            # Handle status updates separately
            if 'status' in task_data:
                try:
                    if task_data['status'] == "completed":
                        api.close_task(task_id)
                    else:
                        api.reopen_task(task_id)
                    logger.info(f"Updated Todoist task {task_id} status")
                except Exception as e:
                    logger.error(f"Failed to update Todoist task {task_id} status: {e}")
                    return False

            # Prepare update arguments for other fields
            update_args = {}
            for field in ['title', 'due_date', 'priority', 'description', 'comments']:
                if field in task_data:
                    update_args[field] = task_data[field]

            # Only update if we have changes
            if update_args:
                try:
                    api.update_task(task_id=task_id, **update_args)
                    logger.info(f"Updated Todoist task {task_id} fields: {list(update_args.keys())}")
                except Exception as e:
                    logger.error(f"Failed to update Todoist task {task_id}: {e}")
                    return False
            
            return True  # No changes to make or all changes succeeded
            
        except Exception as e:
            logger.exception(f"Error updating Todoist task {task_id}: {e}")
            return False
    """Todoist implementation of the task provider interface."""

    INSTRUCTION_TASK_TITLE = "AI Instructions"

    def __init__(self):
        super().__init__()

    def _get_provider_name(self) -> str:
        return "todoist"

    # --- API Initialization ---

    def _get_api(self, user_id, task_user_email):
        """Get a Todoist API client instance using credentials from the database."""
        logger.debug(f"Getting Todoist API for user_id='{user_id}', task_user_email='{task_user_email}'")
        user = User.query.filter_by(id=user_id).first()
        if not user:
            logger.error(f"Cannot get Todoist API: User not found for user_id '{user_id}'")
            return None
            
        account = TaskAccount.get_account(user_id=user_id, provider_name=self.provider_name, task_user_email=task_user_email)
        if account and account.api_key:
            try:
                return TodoistAPI(account.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Todoist API for user_id='{user_id}': {e}")
                return None
        else:
            logger.warning(f"No Todoist account found for user_id='{user_id}', provider='{self.provider_name}', task_user_email='{task_user_email}'")
            return None

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
        api = self._get_api(user_id, task_user_email)
        if not api:
            raise Exception(f"Could not get Todoist API for user_id='{user_id}', task_user_email='{task_user_email}'. Check credentials.")

        try:
            # Search for the instruction task
            tasks = api.get_tasks(filter=f"search:{self.INSTRUCTION_TASK_TITLE}")
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
    def update_task_status(self, user_id, task_id, status: str) -> bool:
        """Update task completion status."""
        # Look up the task to get provider_task_id
        from virtual_assistant.database.task import Task
        task = Task.query.filter_by(id=task_id, user_id=user_id).first()
        if not task:
            raise ValueError(f"Task with ID {task_id} not found")
            
        # Get the provider-specific information
        provider_task_id = task.provider_task_id
        task_user_email = task.task_user_email
        
        api = self._get_api(user_id, task_user_email)
        if not api:
             raise Exception(f"Could not get Todoist API for user_id='{user_id}'. Check credentials.")
        logger.info(f"[TODOIST] Updating task {task_id} (provider ID: {provider_task_id}) status to '{status}'")

        try:
            # First, check if the task exists by trying to get it
            try:
                task = api.get_task(provider_task_id)
                # Task exists, check if status change is needed
                current_status = "completed" if task.is_completed else "active"
                logger.info(f"[TODOIST] Task {task_id} current status: '{current_status}', requested status: '{status}'")
                
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
                    api.close_task(provider_task_id)
                else:
                    logger.info(f"[TODOIST] Marking task {task_id} as active (reopening)")
                    api.reopen_task(provider_task_id)
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
                logger.error(f"[TODOIST] Error updating task status for task {task_id}: {e}")
                raise

    # Signature matches abstract method in TaskProvider
    def create_instruction_task(self, user_id, task_user_email, instructions: str) -> bool:
        """Create or update the AI instruction task."""
        api = self._get_api(user_id, task_user_email)
        if not api:
            raise Exception(f"Could not get Todoist API for user_id='{user_id}', task_user_email='{task_user_email}'. Check credentials.")

        try:
            # Check if instruction task exists
            tasks = api.get_tasks(filter=f"search:{self.INSTRUCTION_TASK_TITLE}")
            instruction_task = next((t for t in tasks if t.content == self.INSTRUCTION_TASK_TITLE), None)
            
            if instruction_task:
                # Update existing task
                api.update_task(
                    task_id=instruction_task.id,
                    description=instructions
                )
                logger.debug(f"Updated AI instruction task for user_id='{user_id}', task_user_email='{task_user_email}'")
            else:
                # Create new task
                api.add_task(
                    content=self.INSTRUCTION_TASK_TITLE,
                    description=instructions
                )
                logger.debug(f"Created AI instruction task for user_id='{user_id}', task_user_email='{task_user_email}'")
            
            return True
        except Exception as e:
            logger.error(f"Error managing instruction task for user_id='{user_id}', task_user_email='{task_user_email}': {e}")
            raise
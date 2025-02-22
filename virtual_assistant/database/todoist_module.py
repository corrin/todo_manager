from todoist_api_python.api import TodoistAPI
from virtual_assistant.utils.user_manager import UserManager
from virtual_assistant.utils.logger import logger
from .database_module import DatabaseInterface


class TodoistModule(DatabaseInterface):
    def __init__(self):
        """Initialize Todoist client using the user's API token."""
        self.api = None
        self._initialize_api()

    def _initialize_api(self):
        """Initialize or refresh the Todoist API client."""
        token = UserManager.get_todoist_token()
        if not token:
            logger.warning("No Todoist token found for current user")
            return
        
        self.api = TodoistAPI(token)
        try:
            # Test the connection by getting projects
            self.api.get_projects()
            logger.info("Successfully connected to Todoist API")
        except Exception as e:
            logger.error(f"Failed to initialize Todoist API: {e}")
            self.api = None

    def get_tasks(self):
        """Get all active tasks."""
        if not self.api:
            logger.error("Todoist API not initialized")
            return []

        try:
            tasks = self.api.get_tasks()
            logger.debug(f"Retrieved {len(tasks)} tasks from Todoist")
            return tasks
        except Exception as e:
            logger.error(f"Error getting tasks from Todoist: {e}")
            return []

    def get_projects(self):
        """Get all projects."""
        if not self.api:
            logger.error("Todoist API not initialized")
            return []

        try:
            projects = self.api.get_projects()
            logger.debug(f"Retrieved {len(projects)} projects from Todoist")
            return projects
        except Exception as e:
            logger.error(f"Error getting projects from Todoist: {e}")
            return []

    def get_rules(self):
        """Get all tasks from the Rules project."""
        if not self.api:
            logger.error("Todoist API not initialized")
            return []

        try:
            # First find the Rules project
            projects = self.api.get_projects()
            rules_project = next((p for p in projects if p.name == "Rules"), None)
            
            if not rules_project:
                logger.warning("Rules project not found in Todoist")
                return []

            # Get all tasks from the Rules project
            tasks = self.api.get_tasks(project_id=rules_project.id)
            rules = [task for task in tasks if task.content.startswith("RULE:")]
            logger.debug(f"Retrieved {len(rules)} rules from Todoist")
            return rules
        except Exception as e:
            logger.error(f"Error getting rules from Todoist: {e}")
            return []

    def create_task(self, task_data):
        """Create a new task in Todoist."""
        if not self.api:
            logger.error("Todoist API not initialized")
            return None

        try:
            task = self.api.add_task(**task_data)
            logger.info(f"Created task: {task.content}")
            return task
        except Exception as e:
            logger.error(f"Error creating task in Todoist: {e}")
            return None

    def complete_task(self, task_id):
        """Mark a task as complete."""
        if not self.api:
            logger.error("Todoist API not initialized")
            return False

        try:
            self.api.close_task(task_id)
            logger.info(f"Completed task: {task_id}")
            return True
        except Exception as e:
            logger.error(f"Error completing task in Todoist: {e}")
            return False

    def reopen_task(self, task_id):
        """Reopen a completed task."""
        if not self.api:
            logger.error("Todoist API not initialized")
            return False

        try:
            self.api.reopen_task(task_id)
            logger.info(f"Reopened task: {task_id}")
            return True
        except Exception as e:
            logger.error(f"Error reopening task in Todoist: {e}")
            return False

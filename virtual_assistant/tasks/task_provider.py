from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
import os # Needed for path operations
import json # Needed for credential file handling
from virtual_assistant.database.user_manager import UserDataManager # Needed for user context (folder path)
from virtual_assistant.utils.logger import logger
# Settings is used by UserDataManager internally, no need to import here


@dataclass
class Task:
    """Represents a task from any task provider."""
    id: str
    title: str
    project_id: str
    priority: int
    due_date: Optional[datetime]
    status: str
    is_instruction: bool = False
    parent_id: Optional[str] = None
    section_id: Optional[str] = None
    project_name: Optional[str] = None


class TaskProvider(ABC):
    """Base class for task providers (Todoist, etc.)"""

    def __init__(self):
        self.provider_name = self._get_provider_name()

    @abstractmethod
    def _get_provider_name(self) -> str:
        """Return the name of this provider (e.g., 'todoist')"""
        pass

    # TODO: Refactor credential storage. File-based storage is used as a temporary measure
    # because CalendarAccount is unsuitable for non-OAuth keys (like Todoist API key).
    # Ideally, create a new DB model (e.g., ProviderCredential) to handle different credential types.

    # Implement file-based credential storage in the base class
    # Suitable for providers using simple keys (like Todoist API key)
    # OAuth providers (Google, O365) should override these methods.
    def get_credentials(self, app_login, task_user_email) -> Optional[Dict[str, Any]]:
        """Get task provider credentials from a user-specific file."""
        current_app_login = UserDataManager.get_current_user()
        if current_app_login != app_login:
             logger.warning(f"get_credentials called with app_login '{app_login}' which differs from current user context '{current_app_login}'")

        logger.debug(f"Retrieving {self.provider_name} credentials using context for '{current_app_login}', targeting file for task_user_email='{task_user_email}'")
        try:
            user_folder = UserDataManager.get_user_folder() # Uses current logged-in user context
        except ValueError as e:
             logger.error(f"Cannot get user folder for credentials: {e}")
             return None

        provider_folder = os.path.join(user_folder, self.provider_name)
        # Use a filename incorporating both identifiers for uniqueness
        # TODO: Improve filename sanitization if emails can contain unusual characters.
        safe_app_login = app_login.replace('@', '_at_').replace('.', '_dot_')
        safe_task_user_email = task_user_email.replace('@', '_at_').replace('.', '_dot_')
        filename = f"{safe_app_login}_{safe_task_user_email}_credentials.json"
        credentials_file = os.path.join(provider_folder, filename)

        if os.path.exists(credentials_file):
            try:
                with open(credentials_file, "r", encoding='utf-8') as file:
                    credentials = json.load(file)
                    logger.debug(f"{self.provider_name} credentials loaded for app_login='{app_login}', task_user_email='{task_user_email}' from {filename}")
                    return credentials
            except (json.JSONDecodeError, IOError) as e:
                 logger.error(f"Error reading credentials file {credentials_file}: {e}")
                 return None
        logger.warning(f"{self.provider_name} credentials file not found: {credentials_file}")
        return None

    def store_credentials(self, app_login, task_user_email, credentials):
        """Store task provider credentials in a user-specific file."""
        current_app_login = UserDataManager.get_current_user()
        if current_app_login != app_login:
             logger.warning(f"store_credentials called with app_login '{app_login}' which differs from current user context '{current_app_login}'")

        logger.debug(f"Storing {self.provider_name} credentials using context for '{current_app_login}', targeting file for task_user_email='{task_user_email}'")
        try:
            user_folder = UserDataManager.get_user_folder() # Uses current logged-in user context
        except ValueError as e:
             logger.error(f"Cannot get user folder for storing credentials: {e}")
             raise IOError(f"Cannot get user folder: {e}") from e

        provider_folder = os.path.join(user_folder, self.provider_name)

        try:
            os.makedirs(provider_folder, exist_ok=True)
        except OSError as e:
             logger.error(f"Cannot create provider folder {provider_folder}: {e}")
             raise IOError(f"Cannot create provider folder: {e}") from e

        # Use a filename incorporating both identifiers for uniqueness
        # TODO: Improve filename sanitization if emails can contain unusual characters.
        safe_app_login = app_login.replace('@', '_at_').replace('.', '_dot_')
        safe_task_user_email = task_user_email.replace('@', '_at_').replace('.', '_dot_')
        filename = f"{safe_app_login}_{safe_task_user_email}_credentials.json"
        credentials_file = os.path.join(provider_folder, filename)

        try:
            with open(credentials_file, "w", encoding='utf-8') as file:
                json.dump(credentials, file, indent=4)
            logger.debug(f"{self.provider_name} credentials stored for app_login='{app_login}', task_user_email='{task_user_email}' in {filename}")
        except IOError as e:
             logger.error(f"Error writing credentials file {credentials_file}: {e}")
             raise

    # --- Abstract methods for core provider functionality ---
    # Signatures updated to use app_login and task_user_email

    @abstractmethod
    def authenticate(self, app_login, task_user_email):
        """Authenticate with the task provider for the given user/account.

        Args:
            app_login: The application login identifier.
            task_user_email: The email associated with the task provider account.

        Returns:
            - None if already authenticated.
            - (provider_name, redirect_url) tuple if authentication/reauthorization is needed.
        """
        pass

    @abstractmethod
    def get_tasks(self, app_login, task_user_email) -> List[Task]:
        """Get all tasks for the user from the specified provider account.

        Args:
            app_login: The application login identifier.
            task_user_email: The email associated with the task provider account.

        Returns:
            List[Task]: List of tasks.

        Raises:
            Exception: If task retrieval fails.
        """
        pass

    @abstractmethod
    def get_ai_instructions(self, app_login, task_user_email) -> Optional[str]:
        """Get the AI instruction task content for the specified provider account.

        Args:
            app_login: The application login identifier.
            task_user_email: The email associated with the task provider account.

        Returns:
            Optional[str]: The instruction text, or None if not found.

        Raises:
            Exception: If instruction retrieval fails.
        """
        pass

    @abstractmethod
    def update_task_status(self, app_login, task_user_email, task_id: str, status: str) -> bool:
        """Update task completion status for the specified provider account.

        Args:
            app_login: The application login identifier.
            task_user_email: The email associated with the task provider account.
            task_id: The task identifier within the provider.
            status: The new status ('active' or 'completed').

        Returns:
            bool: True if update successful.

        Raises:
            Exception: If update fails.
        """
        pass
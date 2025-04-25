from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any
import os # Needed for path operations
import json # Needed for credential file handling
from virtual_assistant.database.user_manager import UserDataManager # Needed for user context (folder path)
from virtual_assistant.utils.logger import logger
from virtual_assistant.database.task import TaskAccount
from virtual_assistant.database.user import User
from virtual_assistant.database.database import db
# Settings is used by UserDataManager internally, no need to import here


@dataclass
class Task:
    """Represents a task from any task provider."""
    id: str  # Internal UUID
    title: str
    project_id: str
    priority: int
    due_date: Optional[datetime]
    status: str
    is_instruction: bool = False
    parent_id: Optional[str] = None
    section_id: Optional[str] = None
    project_name: Optional[str] = None
    provider_task_id: Optional[str] = None  # Provider's task ID


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
    def get_credentials(self, user_id: int, task_user_email: str) -> Optional[Dict[str, Any]]:
        """Get task provider credentials from the TaskAccount database model."""
        logger.debug(f"Retrieving {self.provider_name} credentials from DB for user_id='{user_id}', task_user_email='{task_user_email}'")

        user = User.query.filter_by(id=user_id).first()
        if not user:
            logger.error(f"User not found for user_id '{user_id}' when retrieving credentials.")
            return None

        # Use the provided task_user_email to find the specific account
        account = TaskAccount.get_account(user.id, self.provider_name, task_user_email)

        if account:
            # Construct credentials dictionary from model attributes
            credentials = {
                'api_key': account.api_key,
                'token': account.token,
                'refresh_token': account.refresh_token,
                'expires_at': account.expires_at,
                'scopes': account.scopes,
                'needs_reauth': account.needs_reauth,
                # Include identifiers for context if needed by caller
                'user_id': user_id,
                'task_user_email': task_user_email,
                'provider_name': self.provider_name
            }
            # Filter out None values to return only stored credentials
            credentials = {k: v for k, v in credentials.items() if v is not None}
            
            logger.debug(f"{self.provider_name} credentials retrieved from DB for user_id='{user_id}', task_user_email='{task_user_email}'")
            return credentials
        else:
            logger.warning(f"{self.provider_name} TaskAccount not found in DB for user_id='{user_id}', task_user_email='{task_user_email}'")
            return None

    def store_credentials(self, user_id: int, task_user_email: str, credentials: Dict[str, Any]):
        """Store task provider credentials in the TaskAccount database model."""
        logger.debug(f"Storing {self.provider_name} credentials to DB for user_id='{user_id}', task_user_email='{task_user_email}'")

        user = User.query.filter_by(id=user_id).first()
        if not user:
            logger.error(f"User not found for user_id '{user_id}' when storing credentials.")
            # Decide on error handling: raise exception or return failure?
            raise ValueError(f"User not found: {user_id}")

        try:
            # set_account handles both creation and update
            account = TaskAccount.set_account(
                user_id=user_id,
                provider_name=self.provider_name,
                task_user_email=task_user_email,
                credentials=credentials # Pass the dictionary directly
            )
            db.session.add(account) # Add to session (needed if new or updated)
            db.session.commit() # Commit the changes
            logger.debug(f"{self.provider_name} credentials stored in DB for user_id='{user_id}', task_user_email='{task_user_email}'")
        except Exception as e:
            db.session.rollback() # Rollback on error
            logger.error(f"Error storing {self.provider_name} credentials to DB for user_id='{user_id}', task_user_email='{task_user_email}': {e}")
            # Re-raise the exception to signal failure
            raise Exception(f"Database error storing credentials: {e}") from e

    # --- Abstract methods for core provider functionality ---
    # Signatures updated to use user_id and task_user_email

    @abstractmethod
    def authenticate(self, user_id, task_user_email):
        """Authenticate with the task provider for the given user/account.

        Args:
            user_id: The user's database ID.
            task_user_email: The email associated with the task provider account.

        Returns:
            - None if already authenticated.
            - (provider_name, redirect_url) tuple if authentication/reauthorization is needed.
        """
        pass

    @abstractmethod
    def get_tasks(self, user_id, task_user_email) -> List[Task]:
        """Get all tasks for the user from the specified provider account.

        Args:
            user_id: The user's database ID.
            task_user_email: The email associated with the task provider account.

        Returns:
            List[Task]: List of tasks.

        Raises:
            Exception: If task retrieval fails.
        """
        pass

    @abstractmethod
    def get_ai_instructions(self, user_id, task_user_email) -> Optional[str]:
        """Get the AI instruction task content for the specified provider account.

        Args:
            user_id: The user's database ID.
            task_user_email: The email associated with the task provider account.

        Returns:
            Optional[str]: The instruction text, or None if not found.

        Raises:
            Exception: If instruction retrieval fails.
        """
        pass

    @abstractmethod
    def update_task(self, user_id, task_id, task_data=None) -> bool:
        """Update multiple task properties.

        Args:
            user_id: The user's database ID.
            task_id: The task's primary key.
            task_data: Dictionary containing fields to update (e.g. {'title': 'New title', 'due_date': '2025-01-01'})

        Returns:
            bool: True if update successful.

        Raises:
            Exception: If update fails.
        """
        pass

    @abstractmethod
    def update_task_status(self, user_id, task_id, status: str) -> bool:
        """Update task completion status.

        Args:
            user_id: The user's database ID.
            task_id: The task's primary key.
            status: The new status ('active' or 'completed')

        Returns:
            bool: True if update successful.

        Raises:
            Exception: If update fails.
        """
        pass
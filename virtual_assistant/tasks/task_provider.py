from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from virtual_assistant.auth.user_manager import UserManager
from virtual_assistant.utils.logger import logger
import os
import json


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

    def get_credentials(self, email):
        """Get task provider credentials for the user."""
        logger.debug(f"Retrieving {self.provider_name} credentials for {email}")
        user_folder = UserManager.get_user_folder()
        provider_folder = os.path.join(user_folder, self.provider_name)
        credentials_file = os.path.join(provider_folder, f"{email}_credentials.json")

        if os.path.exists(credentials_file):
            with open(credentials_file, "r") as file:
                credentials = json.load(file)
                logger.debug(f"{self.provider_name} credentials loaded for {email}")
                return credentials
        logger.warning(f"{self.provider_name} credentials not found for {email}")
        return None

    def store_credentials(self, email, credentials):
        """Store task provider credentials for the user."""
        logger.debug(f"Storing {self.provider_name} credentials for {email}")
        user_folder = UserManager.get_user_folder()
        provider_folder = os.path.join(user_folder, self.provider_name)

        if not os.path.exists(provider_folder):
            os.makedirs(provider_folder)

        credentials_file = os.path.join(provider_folder, f"{email}_credentials.json")
        
        with open(credentials_file, "w") as file:
            json.dump(credentials, file)
        logger.debug(f"{self.provider_name} credentials stored for {email}")

    @abstractmethod
    def authenticate(self, email):
        """Authenticate with the task provider.
        Returns:
            - None if already authenticated
            - (provider_name, redirect_url) if authentication needed
        """
        pass

    @abstractmethod
    def get_tasks(self, email) -> List[Task]:
        """Get all tasks for the user.
        Args:
            email: The user's email
        Returns:
            List[Task]: List of tasks
        Raises:
            Exception: If task retrieval fails
        """
        pass

    @abstractmethod
    def get_ai_instructions(self, email) -> Optional[str]:
        """Get the AI instruction task content.
        Args:
            email: The user's email
        Returns:
            Optional[str]: The instruction text, or None if not found
        Raises:
            Exception: If instruction retrieval fails
        """
        pass

    @abstractmethod
    def update_task_status(self, email, task_id: str, status: str) -> bool:
        """Update task completion status.
        Args:
            email: The user's email
            task_id: The task identifier
            status: The new status
        Returns:
            bool: True if update successful
        Raises:
            Exception: If update fails
        """
        pass
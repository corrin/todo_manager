from abc import ABC, abstractmethod
from virtual_assistant.database.user_manager import UserDataManager
from virtual_assistant.utils.logger import logger
import os
import json


class AIProvider(ABC):
    """Base class for AI providers (OpenAI, Grok, etc.)"""

    def __init__(self):
        self.provider_name = self._get_provider_name()

    @abstractmethod
    def _get_provider_name(self) -> str:
        """Return the name of this provider (e.g., 'openai', 'grok')"""
        pass

    def get_credentials(self, email):
        """Get AI provider credentials for the user."""
        logger.debug(f"Retrieving {self.provider_name} credentials for {email}")
        user_folder = UserDataManager.get_user_folder()
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
        """Store AI provider credentials for the user."""
        logger.debug(f"Storing {self.provider_name} credentials for {email}")
        user_folder = UserDataManager.get_user_folder()
        provider_folder = os.path.join(user_folder, self.provider_name)

        if not os.path.exists(provider_folder):
            os.makedirs(provider_folder)

        credentials_file = os.path.join(provider_folder, f"{email}_credentials.json")
        
        with open(credentials_file, "w") as file:
            json.dump(credentials, file)
        logger.debug(f"{self.provider_name} credentials stored for {email}")

    @abstractmethod
    def authenticate(self, email):
        """Authenticate with the AI provider.
        Returns:
            - None if already authenticated
            - (provider_name, redirect_url) if authentication needed
        """
        pass

    @abstractmethod
    def generate_text(self, email, prompt):
        """Generate text using the AI provider.
        Args:
            email: The user's email
            prompt: The text prompt
        Returns:
            str: The generated text
        Raises:
            Exception: If generation fails
        """
        pass
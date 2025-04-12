from abc import ABC, abstractmethod
from virtual_assistant.utils.logger import logger
from virtual_assistant.database.user import User
from typing import Optional, Dict, Any
class AIProvider(ABC):
    """Base class for AI providers (OpenAI, Grok, etc.)"""

    def __init__(self):
        self.provider_name = self._get_provider_name()

    @abstractmethod
    def _get_provider_name(self) -> str:
        """Return the name of this provider (e.g., 'openai', 'grok')"""
        pass

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
from abc import ABC, abstractmethod
from virtual_assistant.utils.logger import logger
from virtual_assistant.database.user import User
from typing import Optional, Dict, Any
import uuid
class AIProvider(ABC):
    """Base class for AI providers (OpenAI, Grok, etc.)"""

    def __init__(self):
        self.provider_name = self._get_provider_name()

    @abstractmethod
    def _get_provider_name(self) -> str:
        """Return the name of this provider (e.g., 'openai', 'grok')"""
        pass

    @abstractmethod
    def authenticate(self, user_id):
        """Authenticate with the AI provider.
        Returns:
            - None if already authenticated
            - (provider_name, redirect_url) if authentication needed
        """
        pass

    @abstractmethod
    def generate_text(self, user_id, prompt):
        """Generate text using the AI provider.
        Args:
            user_id: The user's ID
            prompt: The text prompt
        Returns:
            str: The generated text
        Raises:
            Exception: If generation fails
        """
        pass
        
    def get_credentials(self, user_id) -> Optional[Dict[str, Any]]:
        """Get credentials for the specified user.
        
        Args:
            user_id: The user's ID
            
        Returns:
            Optional[Dict[str, Any]]: Credentials dictionary or None if not found
        """
        try:
            # Convert string ID to UUID if needed
            if isinstance(user_id, str):
                user_id = uuid.UUID(user_id)
                
            # Find user by ID
            user = User.query.filter_by(id=user_id).first()
            if not user:
                logger.warning(f"User not found with ID: {user_id}")
                return None
                
            if self.provider_name == "openai":
                if not user.openai_key:
                    return None
                return {
                    "api_key": user.openai_key,
                    "ai_instructions": user.ai_instructions
                }
            elif self.provider_name == "grok":
                if not user.grok_key:
                    return None
                return {
                    "api_key": user.grok_key,
                    "ai_instructions": user.ai_instructions
                }
            else:
                logger.warning(f"Unknown provider: {self.provider_name}")
                return None
        except Exception as e:
            logger.error(f"Error getting credentials: {e}")
            return None
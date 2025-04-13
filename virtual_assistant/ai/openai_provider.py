from .ai_provider import AIProvider
from virtual_assistant.utils.logger import logger
import openai
from flask import redirect, url_for


class OpenAIProvider(AIProvider):
    """OpenAI implementation of the AI provider interface."""

    def _get_provider_name(self) -> str:
        return "openai"

    def authenticate(self, user_id):
        """Check if we have valid credentials and return auth URL if needed."""
        credentials = self.get_credentials(user_id)
        
        if not credentials:
            logger.info(f"No OpenAI credentials found for user ID: {user_id}")
            return self.provider_name, redirect(url_for('openai_auth.setup_credentials'))
        
        # Test the credentials
        try:
            client = openai.OpenAI(api_key=credentials.get("api_key"))
            client.models.list()  # Simple API call to test credentials
            logger.debug(f"OpenAI credentials valid for user ID: {user_id}")
            return None
        except Exception as e:
            logger.error(f"OpenAI credentials invalid for user ID: {user_id}: {e}")
            return self.provider_name, redirect(url_for('openai_auth.setup_credentials'))

    def generate_text(self, user_id, prompt):
        """Generate text using OpenAI."""
        credentials = self.get_credentials(user_id)
        if not credentials:
            raise Exception(f"No OpenAI credentials found for user ID: {user_id}")

        try:
            client = openai.OpenAI(api_key=credentials.get("api_key"))
            
            # Get custom AI instructions if available
            ai_instructions = credentials.get("ai_instructions")
            system_message = "You are a helpful assistant in charge of my to-do list."
            
            # If user has custom AI instructions, use them
            if ai_instructions:
                system_message = ai_instructions
                
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": system_message,
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error generating text with OpenAI: {e}")
            raise
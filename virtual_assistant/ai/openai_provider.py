from .ai_provider import AIProvider
from virtual_assistant.utils.logger import logger
import openai
from flask import redirect, url_for


class OpenAIProvider(AIProvider):
    """OpenAI implementation of the AI provider interface."""

    def _get_provider_name(self) -> str:
        return "openai"

    def authenticate(self, email):
        """Check if we have valid credentials and return auth URL if needed."""
        credentials = self.get_credentials(email)
        
        if not credentials:
            logger.info(f"No OpenAI credentials found for {email}")
            return self.provider_name, redirect(url_for('openai_auth.setup_credentials'))
        
        # Test the credentials
        try:
            client = openai.OpenAI(api_key=credentials.get("api_key"))
            client.models.list()  # Simple API call to test credentials
            logger.debug(f"OpenAI credentials valid for {email}")
            return None
        except Exception as e:
            logger.error(f"OpenAI credentials invalid for {email}: {e}")
            return self.provider_name, redirect(url_for('openai_auth.setup_credentials'))

    def generate_text(self, email, prompt):
        """Generate text using OpenAI."""
        credentials = self.get_credentials(email)
        if not credentials:
            raise Exception(f"No OpenAI credentials found for {email}")

        try:
            client = openai.OpenAI(api_key=credentials.get("api_key"))
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant in charge of my to-do list.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error generating text with OpenAI: {e}")
            raise
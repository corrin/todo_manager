from virtual_assistant.database.user_manager import UserDataManager
from virtual_assistant.utils.logger import logger
from .openai_provider import OpenAIProvider
from .grok_provider import GrokProvider


class AIManager:
    """Manages multiple AI providers (OpenAI, Grok, etc.)"""

    def __init__(self):
        self.providers = {}
        self.provider_classes = {
            "openai": OpenAIProvider,
            "grok": GrokProvider,
        }
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize available AI providers."""
        for provider_name, provider_class in self.provider_classes.items():
            try:
                self.providers[provider_name] = provider_class()
                logger.debug(f"Initialized {provider_name} provider")
            except Exception as e:
                logger.error(f"Failed to initialize {provider_name} provider: {e}")

    def authenticate(self, email, provider_name=None):
        """Authenticate with specified or all providers.
        
        Args:
            email: User's email
            provider_name: Optional specific provider to authenticate with
        
        Returns:
            Dict of provider_name: auth_result pairs
        """
        auth_results = {}
        providers_to_check = (
            {provider_name: self.providers[provider_name]}
            if provider_name
            else self.providers
        )

        for name, provider in providers_to_check.items():
            try:
                result = provider.authenticate(email)
                if result:
                    auth_results[name] = result
                logger.debug(f"Authentication result for {name}: {result is not None}")
            except Exception as e:
                logger.error(f"Error authenticating with {name}: {e}")
                auth_results[name] = None

        return auth_results

    def generate_text(self, email, prompt, provider_name=None):
        """Generate text using specified or default provider.
        
        Args:
            email: User's email
            prompt: Text prompt
            provider_name: Optional specific provider to use
        
        Returns:
            Generated text
        """
        if provider_name and provider_name not in self.providers:
            raise ValueError(f"Unknown AI provider: {provider_name}")

        # If no provider specified, try them in order until one works
        providers_to_try = (
            [self.providers[provider_name]]
            if provider_name
            else self.providers.values()
        )

        last_error = None
        for provider in providers_to_try:
            try:
                return provider.generate_text(email, prompt)
            except Exception as e:
                last_error = e
                logger.error(f"Error generating text with {provider._get_provider_name()}: {e}")
                continue

        # If we get here, all providers failed
        raise Exception(f"All AI providers failed to generate text. Last error: {last_error}")

    def get_available_providers(self):
        """Get list of available provider names."""
        return list(self.providers.keys())

    def get_provider(self, provider_name):
        """Get specific provider instance."""
        return self.providers.get(provider_name)
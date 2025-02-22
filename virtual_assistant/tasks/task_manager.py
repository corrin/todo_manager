from virtual_assistant.utils.user_manager import UserManager
from virtual_assistant.utils.logger import logger
from .todoist_provider import TodoistProvider


class TaskManager:
    """Manages task providers (Todoist, etc.)"""

    def __init__(self):
        self.providers = {}
        self.provider_classes = {
            "todoist": TodoistProvider,
            # Add other providers here as needed
        }
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize available task providers."""
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

    def get_tasks(self, email, provider_name=None):
        """Get tasks from specified or default provider.
        
        Args:
            email: User's email
            provider_name: Optional specific provider to use
        
        Returns:
            List of tasks
        """
        if provider_name and provider_name not in self.providers:
            raise ValueError(f"Unknown task provider: {provider_name}")

        # For now, we just use the first provider (Todoist)
        # In future, we might combine tasks from multiple providers
        provider = (
            self.providers[provider_name]
            if provider_name
            else next(iter(self.providers.values()))
        )

        try:
            return provider.get_tasks(email)
        except Exception as e:
            logger.error(f"Error getting tasks: {e}")
            raise

    def get_ai_instructions(self, email, provider_name=None):
        """Get AI instructions from specified or default provider.
        
        Args:
            email: User's email
            provider_name: Optional specific provider to use
        
        Returns:
            str: The instruction text, or None if not found
        """
        if provider_name and provider_name not in self.providers:
            raise ValueError(f"Unknown task provider: {provider_name}")

        provider = (
            self.providers[provider_name]
            if provider_name
            else next(iter(self.providers.values()))
        )

        try:
            return provider.get_ai_instructions(email)
        except Exception as e:
            logger.error(f"Error getting AI instructions: {e}")
            raise

    def update_task_status(self, email, task_id, status, provider_name=None):
        """Update task status in specified or default provider.
        
        Args:
            email: User's email
            task_id: Task identifier
            status: New status
            provider_name: Optional specific provider to use
        
        Returns:
            bool: True if update successful
        """
        if provider_name and provider_name not in self.providers:
            raise ValueError(f"Unknown task provider: {provider_name}")

        provider = (
            self.providers[provider_name]
            if provider_name
            else next(iter(self.providers.values()))
        )

        try:
            return provider.update_task_status(email, task_id, status)
        except Exception as e:
            logger.error(f"Error updating task status: {e}")
            raise

    def create_instruction_task(self, email, instructions, provider_name=None):
        """Create or update the AI instruction task.
        
        Args:
            email: User's email
            instructions: The instruction text
            provider_name: Optional specific provider to use
        
        Returns:
            bool: True if successful
        """
        if provider_name and provider_name not in self.providers:
            raise ValueError(f"Unknown task provider: {provider_name}")

        provider = (
            self.providers[provider_name]
            if provider_name
            else next(iter(self.providers.values()))
        )

        try:
            return provider.create_instruction_task(email, instructions)
        except Exception as e:
            logger.error(f"Error creating instruction task: {e}")
            raise

    def get_available_providers(self):
        """Get list of available provider names."""
        return list(self.providers.keys())

    def get_provider(self, provider_name):
        """Get specific provider instance."""
        return self.providers.get(provider_name)
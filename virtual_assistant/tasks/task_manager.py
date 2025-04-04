from virtual_assistant.database.user_manager import UserDataManager
from virtual_assistant.utils.logger import logger
from .todoist_provider import TodoistProvider
from .outlook_task_provider import OutlookTaskProvider
from .google_task_provider import GoogleTaskProvider


class TaskManager:
    """Manages task providers (Todoist, Outlook, Google Tasks, etc.)"""

    def __init__(self):
        self.providers = {}
        self.provider_classes = {
            "todoist": TodoistProvider,
            "outlook": OutlookTaskProvider,
            "google_tasks": GoogleTaskProvider,
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

    def authenticate(self, app_login, task_user_email, provider_name=None):
        """Authenticate with specified or all providers for the given user/account.

        Args:
            app_login: The application login identifier.
            task_user_email: The email associated with the task provider account.
            provider_name: Optional specific provider to authenticate with.
        
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
                # Call provider authenticate with correct arguments
                if name == 'todoist':
                    # TodoistProvider.authenticate expects only app_login
                    result = provider.authenticate(app_login=app_login)
                else:
                    # Other providers (Outlook, Google) expect both
                    result = provider.authenticate(app_login=app_login, task_user_email=task_user_email)

                if result: # result is (provider_name, redirect_url) if auth needed
                    auth_results[name] = result
                logger.debug(f"Authentication result for {name} ({app_login}/{task_user_email}): {result is not None}")
            except Exception as e:
                logger.error(f"Error authenticating with {name} ({app_login}/{task_user_email}): {e}")
                auth_results[name] = None

        return auth_results

    def get_tasks(self, app_login, task_user_email, provider_name):
        """Get tasks from the specified provider for a given user and provider account.

        Args:
            app_login: The application login identifier (for credential lookup).
            task_user_email: The email associated with the task provider account.
            provider_name: The name of the specific provider to use.

        Returns:
            List of tasks obtained from the provider.

        Raises:
            ValueError: If the specified provider is not found.
            Exception: Propagates exceptions raised by the provider's get_tasks method.
        """
        # Get the provider instance; raises ValueError if not found.
        provider = self.get_provider(provider_name)

        try:
            # Call the specific provider's get_tasks method.
            # Assuming all provider methods will be updated to accept both arguments.
            return provider.get_tasks(app_login=app_login, task_user_email=task_user_email)
        except Exception as e:
            # Log provider-specific errors and re-raise
            logger.error(f"Error getting tasks from provider '{provider_name}' for user '{app_login}' / account '{task_user_email}': {e}")
            raise # Re-raise the original exception to be handled by the caller

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
        """Get specific provider instance.

        Args:
            provider_name: Name of the provider

        Returns:
            The provider instance

        Raises:
            ValueError: If the provider is not found.
        """
        provider = self.providers.get(provider_name)
        if provider is None:
            logger.warning(f"Attempted to get non-existent provider: {provider_name}")
            # Raise ValueError instead of a custom exception
            raise ValueError(f"Task provider '{provider_name}' not found or configured.")
        return provider
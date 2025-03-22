"""
Factory module for creating calendar provider instances.
This follows the factory pattern to centralize provider initialization.
"""
from virtual_assistant.utils.logger import logger
from virtual_assistant.meetings.google_calendar_provider import GoogleCalendarProvider
from virtual_assistant.meetings.o365_calendar_provider import O365CalendarProvider


class CalendarProviderFactory:
    """Factory class for calendar providers."""
    
    # Map of provider names to their respective classes
    _providers = {
        "google": GoogleCalendarProvider,
        "o365": O365CalendarProvider
    }
    
    @classmethod
    def get_provider(cls, provider_name):
        """
        Get a calendar provider instance by name.
        
        Args:
            provider_name (str): The name of the provider to get
            
        Returns:
            An instance of the requested provider, or None if not found
        """
        if not provider_name:
            logger.error("No provider name specified")
            return None
            
        provider_class = cls._providers.get(provider_name.lower())
        if not provider_class:
            logger.error(f"Unknown calendar provider: {provider_name}")
            return None
            
        try:
            provider = provider_class()
            logger.debug(f"Created {provider_name} calendar provider")
            return provider
        except Exception as e:
            logger.error(f"Error creating {provider_name} calendar provider: {str(e)}")
            return None
            
    @classmethod
    def get_providers(cls):
        """
        Get the names of all available providers.
        
        Returns:
            list: A list of provider names
        """
        return list(cls._providers.keys()) 
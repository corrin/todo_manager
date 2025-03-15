from abc import ABC, abstractmethod


class CalendarProvider(ABC):
    """Base class for calendar providers."""

    @abstractmethod
    def authenticate(self, email):
        """
        Authenticate with the calendar provider.
        
        Parameters:
            email (str): The email address to authenticate
            
        Returns:
            tuple: (credentials, auth_url) where auth_url is the URL to redirect to for auth
        """
        pass

    @abstractmethod
    def retrieve_tokens(self, callback_url):
        """
        Retrieve tokens from OAuth callback.
        
        Parameters:
            callback_url (str): The callback URL with auth code
            
        Returns:
            dict: The credential information
        """
        pass

    @abstractmethod
    async def get_meetings(self, email):
        """
        Get meetings for the given calendar email.
        
        Parameters:
            email (str): The email address to get meetings for
            
        Returns:
            list: List of meeting dictionaries
        """
        pass

    @abstractmethod
    async def create_busy_block(self, calendar_email, meeting_data, original_event_id):
        """
        Create a busy block in the calendar.
        
        Parameters:
            calendar_email (str): The email address to create the block for
            meeting_data (dict): The meeting data to use
            original_event_id (str): ID of the original event
            
        Returns:
            str: The ID of the created busy block
        """
        pass

    @abstractmethod
    def get_credentials(self, email):
        """
        Get credentials for the given email.
        
        Parameters:
            email (str): The email address to get credentials for
            
        Returns:
            dict: The credentials if found, None otherwise
        """
        pass

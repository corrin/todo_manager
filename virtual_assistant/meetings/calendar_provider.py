from abc import ABC, abstractmethod


class CalendarProvider(ABC):
    """Base class for calendar providers."""

    @abstractmethod
    def authenticate(self, user_id):
        """
        Authenticate with the calendar provider.
        
        Parameters:
            user_id (int): The ID of the app user.
            
        Returns:
            tuple: (credentials, auth_url) where auth_url is the URL to redirect to for auth
        """
        pass

    @abstractmethod
    def reauthenticate(self, calendar_email, user_id):
        """
        Reauthenticate an existing calendar connection.
        
        Parameters:
            calendar_email (str): The email address of the calendar account to reauthenticate.
            user_id (int): The ID of the app user.
            
        Returns:
            tuple: (credentials, auth_url) where auth_url is the URL to redirect to for auth
        """
        pass

    @abstractmethod
    def handle_oauth_callback(self, callback_url, user_id):
        """
        Handle the OAuth callback from the provider.
        
        Parameters:
            callback_url (str): The callback URL with authentication code
            user_id (int): The ID of the app user.
            
        Returns:
            The calendar email or credentials object (varies by provider)
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
    async def get_meetings(self, calendar_email, user_id):
        """
        Get meetings for the given calendar email.
        
        Parameters:
            calendar_email (str): The email address of the calendar to retrieve meetings from.
            user_id (int): The ID of the app user.
            
        Returns:
            list: List of meeting dictionaries
        """
        pass

    @abstractmethod
    async def create_busy_block(self, calendar_email, meeting_data, original_event_id, user_id):
        """
        Create a busy block in the calendar.
        
        Parameters:
            calendar_email (str): The email address to create the block for
            meeting_data (dict): The meeting data to use
            original_event_id (str): ID of the original event
            user_id (int): The ID of the app user.
            
        Returns:
            str: The ID of the created busy block
        """
        pass

    @abstractmethod
    def create_meeting(self, meeting_details, user_id):
        """
        Create a meeting in the calendar.
        
        Parameters:
            meeting_details (dict): Dictionary containing meeting details.
                Required keys vary by provider.
            user_id (int): The ID of the app user.
            
        Returns:
            The ID of the created meeting
        """
        pass

    @abstractmethod
    def get_credentials(self, calendar_email, user_id):
        """
        Get credentials for the given email.
        
        Parameters:
            calendar_email (str): The email address of the calendar to get credentials for.
            user_id (int): The ID of the app user.
            
        Returns:
            The credentials object if found
        """
        pass

    @abstractmethod
    def store_credentials(self, calendar_email, credentials, user_id):
        """
        Store credentials for the given calendar email.
        
        Parameters:
            calendar_email (str): The email address of the calendar account.
            credentials: The credentials to store.
            user_id (int): The ID of the app user.
            
        Returns:
            bool: True if successful
        """
        pass

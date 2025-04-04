from abc import ABC, abstractmethod


class CalendarProvider(ABC):
    """Base class for calendar providers."""

    @abstractmethod
    def authenticate(self, app_login):
        """
        Authenticate with the calendar provider.
        
        Parameters:
            app_login (str): The email address used to log into this app.
            
        Returns:
            tuple: (credentials, auth_url) where auth_url is the URL to redirect to for auth
        """
        pass

    @abstractmethod
    def reauthenticate(self, calendar_email, app_login):
        """
        Reauthenticate an existing calendar connection.
        
        Parameters:
            calendar_email (str): The email address of the calendar account to reauthenticate.
            app_login (str): The email address used to log into this app.
            
        Returns:
            tuple: (credentials, auth_url) where auth_url is the URL to redirect to for auth
        """
        pass

    @abstractmethod
    def handle_oauth_callback(self, callback_url, app_login):
        """
        Handle the OAuth callback from the provider.
        
        Parameters:
            callback_url (str): The callback URL with authentication code
            app_login (str): The email address used to log into this app.
            
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
    async def get_meetings(self, calendar_email, app_login):
        """
        Get meetings for the given calendar email.
        
        Parameters:
            calendar_email (str): The email address of the calendar to retrieve meetings from.
            app_login (str): The email address used to log into this app.
            
        Returns:
            list: List of meeting dictionaries
        """
        pass

    @abstractmethod
    async def create_busy_block(self, calendar_email, meeting_data, original_event_id, app_login):
        """
        Create a busy block in the calendar.
        
        Parameters:
            calendar_email (str): The email address to create the block for
            meeting_data (dict): The meeting data to use
            original_event_id (str): ID of the original event
            app_login (str): The email address used to log into this app.
            
        Returns:
            str: The ID of the created busy block
        """
        pass

    @abstractmethod
    def create_meeting(self, meeting_details, app_login):
        """
        Create a meeting in the calendar.
        
        Parameters:
            meeting_details (dict): Dictionary containing meeting details.
                Required keys vary by provider.
            app_login (str): The email address used to log into this app.
            
        Returns:
            The ID of the created meeting
        """
        pass

    @abstractmethod
    def get_credentials(self, calendar_email, app_login):
        """
        Get credentials for the given email.
        
        Parameters:
            calendar_email (str): The email address of the calendar to get credentials for.
            app_login (str): The email address used to log into this app.
            
        Returns:
            The credentials object if found
        """
        pass

    @abstractmethod
    def store_credentials(self, calendar_email, credentials, app_login):
        """
        Store credentials for the given calendar email.
        
        Parameters:
            calendar_email (str): The email address of the calendar account.
            credentials: The credentials to store.
            app_login (str): The email address used to log into this app.
            
        Returns:
            bool: True if successful
        """
        pass

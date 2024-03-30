# google_calendar_provider.py
from .calendar_provider import CalendarProvider
from virtual_assistant.utils.user_manager import UserManager
import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from utils.logger import logger
from utils.settings import Settings

class GoogleCalendarProvider(CalendarProvider):
    def __init__(self):
        self.client_id = Settings.GOOGLE_CLIENT_ID
        self.client_secret = Settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = Settings.GOOGLE_REDIRECT_URI
        self.scopes = Settings.GOOGLE_SCOPES
        logger.debug("Google Calendar Provider initialized")
        logger.debug(f"Google Calendar Provider: Client ID = {self.client_id}")
        logger.debug(f"Google Calendar Provider: Client Secret = {self.client_secret}")
        logger.debug(f"Google Calendar Provider: Redirect URI = {self.redirect_uri}")
        logger.debug(f"Google Calendar Provider: Scopes = {self.scopes}")

    def authenticate(self, email):
        credentials = self.get_credentials(email)

        if credentials and credentials.expired and credentials.refresh_token:
            # If credentials exist but are expired and have a refresh token, refresh them
            credentials.refresh(Request())
            self.store_credentials(email, credentials)

        if not credentials:
            # If credentials don't exist or are invalid, initiate the OAuth 2.0 flow
            flow = Flow.from_client_config(
                {
                    'web': {
                        'client_id': self.client_id,
                        'client_secret': self.client_secret,
                        'redirect_uris': [self.redirect_uri],
                        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                        'token_uri': 'https://oauth2.googleapis.com/token',
                    }
                },
                scopes=self.scopes,
                redirect_uri=self.redirect_uri
            )
            authorization_url, _ = flow.authorization_url(prompt='consent')
            return ("Google Calendar", authorization_url)

        return credentials

    def get_meetings(self, email):
        credentials = self.get_credentials(email)
        if credentials:
            service = build('calendar', 'v3', credentials=credentials)
            events_result = service.events().list(calendarId=email, singleEvents=True, orderBy='startTime').execute()
            events = events_result.get('items', [])
            return events
        else:
            print(f"No credentials found for email: {email}")
            return []

    def create_meeting(self, email, meeting_data):
        credentials = self.get_credentials(email)
        if credentials:
            service = build('calendar', 'v3', credentials=credentials)
            event = service.events().insert(calendarId=email, body=meeting_data).execute()
            print(f"Meeting created: {event.get('htmlLink')}")
        else:
            print(f"No credentials found for email: {email}")

    def get_credentials(self, email):
        # Retrieve the stored credentials for the email address from a file
        user_folder = UserManager.get_user_folder()
        credentials_file = os.path.join(user_folder, f"{email}_credentials.json")
        if os.path.exists(credentials_file):
            with open(credentials_file, "r") as file:
                credentials_data = json.load(file)
                credentials = Credentials.from_authorized_user_info(credentials_data)
                return credentials
        return None

    def store_credentials(self, email, credentials):
        # Store the credentials for the email address in a file
        user_folder = UserManager.get_user_folder()
        credentials_file = os.path.join(user_folder, f"{email}_credentials.json")
        credentials_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes
        }
        with open(credentials_file, "w") as file:
            json.dump(credentials_data, file)

# google_calendar_provider.py
from .calendar_provider import CalendarProvider
from ..utils.user_manager import UserManager
import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request


class GoogleCalendarProvider(CalendarProvider):
    def __init__(self):
        self.client_id = os.environ['GOOGLE_CLIENT_ID']
        self.client_secret = os.environ['GOOGLE_CLIENT_SECRET']
        self.redirect_uri = 'https://calendar-lakeland.pythonanywhere.com/meetings/google_authenticate'
        self.scopes = ['https://www.googleapis.com/auth/calendar']

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

            print(f"Please visit this URL to authorize the application: {authorization_url}")
            authorization_code = input("Enter the authorization code: ")

            flow.fetch_token(code=authorization_code)
            credentials = flow.credentials

            self.store_credentials(email, credentials)

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
        current_user = UserManager.get_current_user()
        if not current_user:
            raise ValueError("Current user not set. Please log in first.")
        user_dir = os.path.join("users", current_user)
        credentials_file = os.path.join(user_dir, f"{email}_credentials.json")
        if os.path.exists(credentials_file):
            with open(credentials_file, "r") as file:
                credentials_data = json.load(file)
                credentials = Credentials.from_authorized_user_info(credentials_data)
                return credentials
        return None

    def store_credentials(self, email, credentials):
        # Store the credentials for the email address in a file
        current_user = UserManager.get_current_user()
        if not current_user:
            raise ValueError("Current user not set. Please log in first.")
        user_dir = os.path.join("users", current_user)
        os.makedirs(user_dir, exist_ok=True)
        credentials_file = os.path.join(user_dir, f"{email}_credentials.json")
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
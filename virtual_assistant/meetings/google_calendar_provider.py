# google_calendar_provider.py
from .calendar_provider import CalendarProvider
from virtual_assistant.utils.user_manager import UserManager
from flask import redirect, session
import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from google.auth.transport.requests import Request
from virtual_assistant.utils.logger import logger
from virtual_assistant.utils.settings import Settings


class GoogleCalendarProvider(CalendarProvider):
    def __init__(self):
        self.client_id = Settings.GOOGLE_CLIENT_ID
        self.client_secret = Settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = Settings.GOOGLE_REDIRECT_URI
        self.scopes = Settings.GOOGLE_SCOPES
        self.provider_name = "google"
        logger.debug("Google Calendar Provider initialized")
        logger.debug(f"Client ID = {self.client_id}")
        logger.debug(f"Client Secret = {self.client_secret}")
        logger.debug(f"Redirect URI = {self.redirect_uri}")
        logger.debug(f"Scopes = {self.scopes}")

    def authenticate(self, email):
        credentials = self.get_credentials(email)

        if credentials and credentials.expired and credentials.refresh_token:
            logger.info(f"Refreshing expired credentials for {email}")
            try:
                credentials.refresh(Request())
                self.store_credentials(
                    email, credentials
                )  # Store refreshed credentials
                logger.info(f"Credentials refreshed and stored for {email}")
                return credentials
            except Exception as e:
                logger.error(f"Error refreshing credentials for {email}: {e}")
                # Handle the error, e.g., by initiating a new OAuth flow

        if not credentials or not credentials.valid:  # Check for valid credentials
            logger.info(f"Initiating new OAuth flow for {email}")
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "redirect_uris": [self.redirect_uri],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                },
                scopes=self.scopes,
                redirect_uri=self.redirect_uri,
            )
            authorization_url, state = flow.authorization_url(prompt="consent")
            session["oauth_state"] = state  # Store state for CSRF protection
            session["oauth_flow"] = flow  # Store flow for callback
            return self.provider_name, redirect(authorization_url)

        return credentials

    def handle_oauth_callback(self, callback_url):
        """Handle the OAuth callback from Google."""
        try:
            # Get the flow from session
            flow = session.get("oauth_flow")
            if not flow:
                logger.error("No OAuth flow found in session")
                return None

            # Fetch the token
            flow.fetch_token(authorization_response=callback_url)
            
            # Get credentials from flow
            credentials = flow.credentials
            
            # Clean up session
            session.pop("oauth_flow", None)
            session.pop("oauth_state", None)
            
            return credentials
        except Exception as e:
            logger.error(f"Error handling OAuth callback: {e}")
            return None

    def get_meetings(self, email):
        credentials = self.get_credentials(email)

        if not credentials:
            # Redirect to the OAuth route to start the authentication process
            return None

        # If we have credentials, proceed with API calls
        logger.info(f"Fetching meetings for {email}")
        try:
            service = build("calendar", "v3", credentials=credentials)
            events_result = (
                service.events()
                .list(calendarId="primary", singleEvents=True, orderBy="startTime")
                .execute()
            )
            events = events_result.get("items", [])
            logger.debug(f"Meetings fetched for {email}: {len(events)} meetings found")
            return events
        except HttpError as error:
            if error.resp.status in [401, 403]:
                # Credentials are expired or invalid, trigger re-authentication
                logger.warning(
                    f"Credentials expired or invalid for {email}. Triggering re-authentication."
                )
                return None
            else:
                logger.error(f"Error fetching meetings for {email}: {error}")
                return []
        except Exception as e:
            logger.error(f"Error fetching meetings for {email}: {e}")
            return []

    def create_meeting(self, email, meeting_data):
        credentials = self.get_credentials(email)
        if credentials:
            logger.info(f"Creating meeting for {email}")
            service = build("calendar", "v3", credentials=credentials)
            event = (
                service.events()
                .insert(calendarId="primary", body=meeting_data)
                .execute()
            )
            logger.info(f"Meeting created for {email}: {event.get('htmlLink')}")
        else:
            logger.warning(f"No credentials found for {email}")

    def get_credentials(self, email):
        logger.debug(f"Retrieving credentials for {email}")
        user_folder = UserManager.get_user_folder()
        provider_folder = os.path.join(user_folder, self.provider_name)
        credentials_file = os.path.join(provider_folder, f"{email}_credentials.json")

        if os.path.exists(credentials_file):
            with open(credentials_file, "r") as file:
                credentials_data = json.load(file)
                credentials = Credentials.from_authorized_user_info(credentials_data)
                logger.debug(f"Credentials loaded for {email}")
                return credentials
        logger.warning(f"Credentials file not found for {email}")
        return None

    def store_credentials(self, email, credentials):
        logger.debug(f"Storing credentials for {email}")
        user_folder = UserManager.get_user_folder()
        provider_folder = os.path.join(user_folder, self.provider_name)

        if not os.path.exists(provider_folder):
            os.makedirs(provider_folder)

        credentials_file = os.path.join(provider_folder, f"{email}_credentials.json")
        credentials_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
        }
        with open(credentials_file, "w") as file:
            json.dump(credentials_data, file)
        logger.debug(f"Credentials stored for {email}")

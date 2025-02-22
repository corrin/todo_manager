"""
Module for Google Calendar integration.
"""

import datetime
import json
import os

from flask import render_template, session
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from virtual_assistant.database.user_manager import UserDataManager
from virtual_assistant.meetings.calendar_provider import CalendarProvider
from virtual_assistant.utils.logger import logger
from virtual_assistant.utils.settings import Settings


class GoogleCalendarProvider(CalendarProvider):
    """
    Google Calendar Provider class for handling Google Calendar integration.
    """

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
        """
        Authenticate the user with the given email so we can access their calendar.

        This method checks for existing credentials, refreshes them if expired,
        and initiates a new authentication flow if necessary.

        Parameters:
            email (str): The email address of the user to authenticate.

        Returns:
            Credentials object if authentication is successful; None otherwise.
        """
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
            except Exception as error:
                logger.error(f"Error refreshing credentials for {email}: {error}")
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
            session["current_email"] = email  # Set current_email in the session
            return None, render_template(
                "authenticate_email.html",
                email=email,
                authorization_url=authorization_url,
            )

        return credentials, None

    def retrieve_tokens(self, callback_url):
        state = session.get("oauth_state")
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
            state=state,
        )
        flow.fetch_token(authorization_response=callback_url)
        credentials = flow.credentials
        return {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
        }

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
        """
        Retrieve a list of upcoming meetings for the given email address.

        Parameters:
            email (str): The email address to retrieve meetings for.

        Returns:
            A list of meeting dictionaries containing 'title', 'start', and 'end' keys.
        """
        try:
            credentials = UserDataManager.get_credentials(email)
            logger.debug(f"Credentials for {email}: {credentials}")

            if not credentials:
                logger.error(f"No credentials found for {email}")
                return []

            service = build("calendar", "v3", credentials=credentials)
            logger.debug(f"Calendar service built successfully for {email}")

            now = datetime.datetime.utcnow().isoformat() + "Z"  # "Z" indicates UTC time
            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=now,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            logger.debug(
                f"Events retrieved for {email}: {len(events_result.get('items', []))} events"
            )

            events = events_result.get("items", [])
            logger.debug(f"Events extracted for {email}: {len(events)} events")

            meetings = []
            for event in events:
                try:
                    meeting = {
                        "title": event.get("summary", ""),
                        "start": self.get_meeting_time(event.get("start", {})),
                        "end": self.get_meeting_time(event.get("end", {})),
                    }
                    meetings.append(meeting)
                except Exception as e:
                    logger.error(f"Error processing event: {event}")
                    logger.exception(e)

            logger.debug(f"Meetings processed for {email}: {len(meetings)} meetings")
            return meetings

        except HttpError as error:
            logger.error(
                f"An error occurred while retrieving meetings for {email}: {error}"
            )
            return []

        except Exception as e:
            logger.error(
                f"An unexpected error occurred while retrieving meetings for {email}"
            )
            logger.exception(e)
            return []

    def get_meeting_time(self, meeting_time):
        """
        Extract the meeting time from the given event data.

        Parameters:
            meeting_time (dict): The event data containing the meeting time.

        Returns:
            str: The meeting time in ISO format.
        """
        try:
            logger.debug(f"Meeting time: {meeting_time}")
            logger.debug(f"Type of meeting_time: {type(meeting_time)}")

            if isinstance(meeting_time, dict):
                logger.debug("Meeting time is a dictionary")
                date_time = meeting_time.get("dateTime")
                logger.debug(f"dateTime: {date_time}")

                date = meeting_time.get("date")
                logger.debug(f"date: {date}")

                if date_time:
                    logger.debug("Returning dateTime")
                    return date_time
                elif date:
                    logger.debug("Returning date")
                    return date
                else:
                    logger.debug("Returning empty string")
                    return ""
            else:
                logger.warning(f"Unexpected meeting time format: {meeting_time}")
                logger.debug("Converting meeting time to string")
                return str(meeting_time)
        except Exception as e:
            logger.error(f"Error getting meeting time: {meeting_time}")
            logger.exception(e)
            return ""

    def create_meeting(self, email, meeting_data):
        """
        Create a new meeting with the given data.

        Parameters:
            email (str): The email address of the meeting organizer.
            meeting_data (dict): The meeting data containing title, start, and end times.

        Returns:
            str: The meeting ID if created successfully; None otherwise.
        """
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
            return event.get("id")
        else:
            logger.warning(f"No credentials found for {email}")

    def get_credentials(self, email):
        """
        Retrieve the credentials for the given email address.

        Parameters:
            email (str): The email address to retrieve credentials for.

        Returns:
            Credentials object if found; None otherwise.
        """
        logger.debug(f"Retrieving credentials for {email}")
        user_folder = UserManager.get_user_folder()
        provider_folder = os.path.join(user_folder, self.provider_name)
        credentials_file = os.path.join(provider_folder, f"{email}_credentials.json")

        if os.path.exists(credentials_file):
            with open(credentials_file, "r", encoding="utf-8") as file:
                credentials_data = json.load(file)
                credentials = Credentials.from_authorized_user_info(credentials_data)
                logger.debug(f"Credentials loaded for {email}")
                return credentials

        logger.warning(f"Credentials file not found for {email}")
        return None

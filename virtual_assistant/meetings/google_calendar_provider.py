"""
Module for Google Calendar integration.
"""

import datetime
import json
import os
from datetime import datetime, timezone  

from flask import render_template, session
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from virtual_assistant.meetings.calendar_provider import CalendarProvider
from virtual_assistant.utils.logger import logger
from virtual_assistant.utils.settings import Settings
from virtual_assistant.database.calendar_account import CalendarAccount


class GoogleCalendarProvider(CalendarProvider):
    """
    Google Calendar Provider class for handling Google Calendar integration.
    """

    def __init__(self):
        self.client_id = Settings.GOOGLE_CLIENT_ID
        self.client_secret = Settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = Settings.GOOGLE_REDIRECT_URI
        self.scopes = [
            'openid',  # OpenID Connect scope
            'https://www.googleapis.com/auth/calendar',  # Calendar scope
            'https://www.googleapis.com/auth/userinfo.email'  # Email scope
        ]
        self.provider_name = "google"
        
        # Add this line to allow HTTPS
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
        
        # Keep these - useful for verifying config
        logger.debug("Google Calendar Provider initialized")
        logger.debug(f"Redirect URI = {self.redirect_uri}")

    def authenticate(self, calendar_email, force_new_auth=False):
        """
        Authenticate the user with the given calendar email so we can access their calendar.

        Parameters:
            calendar_email (str): The email address of the calendar to authenticate.
            force_new_auth (bool): If True, force a new authentication flow even if credentials exist.

        Returns:
            Credentials object if authentication is successful; None otherwise.
        """
        if not force_new_auth:
            credentials = self.get_credentials(calendar_email)

            if credentials and credentials.expired and credentials.refresh_token:
                logger.info(f"Refreshing expired credentials for {calendar_email}")
                try:
                    credentials.refresh(Request())
                    self.store_credentials(calendar_email, credentials)
                    logger.info(f"Credentials refreshed and stored for {calendar_email}")
                    return credentials, None
                except Exception as error:
                    logger.error(f"Error refreshing credentials for {calendar_email}: {error}")

            if credentials and credentials.valid:
                return credentials, None

        # Either force_new_auth is True or no valid credentials exist
        logger.info(f"Initiating new OAuth flow for {calendar_email}")
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
        authorization_url, state = flow.authorization_url(
            prompt="select_account",  # Force Google account picker
            access_type="offline"     # Get refresh token
        )
        
        # Store only serializable parts of the flow
        session["flow_state"] = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "scopes": self.scopes,
            "state": state
        }
        session["current_email"] = calendar_email
        return None, authorization_url

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
            # Get the flow state from session
            flow_state = session.get("flow_state")
            if not flow_state:
                logger.error("No OAuth flow state found in session")
                return None

            # Recreate the flow
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": flow_state["client_id"],
                        "client_secret": flow_state["client_secret"],
                        "redirect_uris": [flow_state["redirect_uri"]],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                },
                scopes=flow_state["scopes"],
                redirect_uri=flow_state["redirect_uri"],
                state=flow_state["state"]
            )
            
            # Fetch the token
            flow.fetch_token(authorization_response=callback_url)
            credentials = flow.credentials
            
            # Clean up session
            session.pop("flow_state", None)
            session.pop("current_email", None)
            
            return credentials
        except Exception as e:
            logger.error(f"Error handling OAuth callback: {e}")
            return None

    def get_meetings(self, calendar_email):
        """
        Retrieve a list of upcoming meetings for the given calendar email.

        Parameters:
            calendar_email (str): The email address of the calendar to retrieve meetings from.

        Returns:
            A list of meeting dictionaries containing 'title', 'start', and 'end' keys.
        """
        try:
            credentials = self.get_credentials(calendar_email)
            logger.debug(f"Credentials for {calendar_email}: {credentials}")

            if not credentials:
                logger.error(f"No credentials found for {calendar_email}")
                return []

            service = build("calendar", "v3", credentials=credentials)
            logger.debug(f"Calendar service built successfully for {calendar_email}")

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
                f"Events retrieved for {calendar_email}: {len(events_result.get('items', []))} events"
            )

            events = events_result.get("items", [])
            logger.debug(f"Events extracted for {calendar_email}: {len(events)} events")

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

            logger.debug(f"Meetings processed for {calendar_email}: {len(meetings)} meetings")
            return meetings

        except HttpError as error:
            logger.error(
                f"An error occurred while retrieving meetings for {calendar_email}: {error}"
            )
            return []

        except Exception as e:
            logger.error(
                f"An unexpected error occurred while retrieving meetings for {calendar_email}"
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

    def create_meeting(self, calendar_email, meeting_data):
        """
        Create a new meeting with the given data.

        Parameters:
            calendar_email (str): The email address of the calendar to create the meeting in.
            meeting_data (dict): The meeting data containing title, start, and end times.

        Returns:
            str: The meeting ID if created successfully; None otherwise.
        """
        credentials = self.get_credentials(calendar_email)
        if credentials:
            logger.info(f"Creating meeting for {calendar_email}")
            service = build("calendar", "v3", credentials=credentials)
            event = (
                service.events()
                .insert(calendarId="primary", body=meeting_data)
                .execute()
            )
            logger.info(f"Meeting created for {calendar_email}: {event.get('htmlLink')}")
            return event.get("id")
        else:
            logger.warning(f"No credentials found for {calendar_email}")

    def store_credentials(self, calendar_email, credentials):
        """Store credentials for the given calendar email."""
        try:
            from flask import session
            app_user_email = session.get('user_email')
            if not app_user_email:
                logger.error("No user email in session when storing credentials")
                return False

            credentials_data = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': ' '.join(credentials.scopes)  # Convert list to string
            }
            
            # Get existing account or create new one
            account = CalendarAccount.get_by_email_and_provider(calendar_email, self.provider_name)
            if not account:
                account = CalendarAccount(
                    calendar_email=calendar_email, 
                    app_user_email=app_user_email,
                    provider=self.provider_name, 
                    **credentials_data
                )
            else:
                # Update account with new credentials
                for key, value in credentials_data.items():
                    setattr(account, key, value)
                account.app_user_email = app_user_email  # Ensure this is set even on update
            
            account.last_sync = datetime.now(timezone.utc)
            account.save()
            logger.debug(f"Credentials stored in database for calendar {calendar_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing credentials: {e}")
            return False

    def get_credentials(self, calendar_email):
        """Retrieve credentials for the given calendar email."""
        account = CalendarAccount.get_by_email_and_provider(calendar_email, self.provider_name)
        if account:
            credentials = Credentials(
                token=account.token,
                refresh_token=account.refresh_token,
                token_uri=account.token_uri,
                client_id=account.client_id,
                client_secret=account.client_secret,
                scopes=account.scopes.split()  # Convert string back to list
            )
            logger.debug(f"Credentials loaded from database for {calendar_email} (app user: {account.app_user_email})")
            return credentials

        logger.warning(f"No Google credentials found for {calendar_email}")
        return None

    def get_google_email(self, credentials):
        """Get the email address of the Google account that was just authorized.
        
        This is the email address of the Google Calendar account that the user chose
        to connect, NOT necessarily the same as the app user's email. For example,
        if app user 'lakeland@gmail.com' authorizes their work calendar
        'work@company.com', this function will return 'work@company.com'.
        
        Args:
            credentials: The OAuth credentials returned from the Google authorization flow.
            
        Returns:
            str: The email address of the authorized Google Calendar account.
        """
        try:
            service = build('oauth2', 'v2', credentials=credentials)
            user_info = service.userinfo().get().execute()
            return user_info.get('email')
        except Exception as e:
            logger.error(f"Error getting Google account email from credentials: {e}")
            return None

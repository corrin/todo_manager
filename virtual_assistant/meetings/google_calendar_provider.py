"""
Module for Google Calendar integration.
"""

import datetime
import json
import os
from datetime import datetime, timezone  
import asyncio

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
            
        Raises:
            Exception: If token refresh fails or authentication cannot be established
        """
        if not force_new_auth:
            credentials = self.get_credentials(calendar_email)

            if credentials and credentials.expired and credentials.refresh_token:
                logger.info(f"Refreshing expired credentials for {calendar_email}")
                # Let errors propagate - don't swallow them
                credentials.refresh(Request())
                self.store_credentials(calendar_email, credentials)
                logger.info(f"Credentials refreshed and stored for {calendar_email}")
                return credentials, None

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
            prompt="consent",     # Force consent screen to ensure refresh token
            access_type="offline" # Get refresh token
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
            logger.debug("Handling OAuth callback with flow state")

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
            
            # Check if refresh token is missing - this can happen if the user has already
            # authorized this app and didn't revoke access
            if not credentials.refresh_token:
                logger.warning("❌ MISSING REFRESH TOKEN: Google didn't return a refresh token. This typically happens when the user has already authorized this app. If this is causing issues, have the user revoke access to this app in their Google account and try again.")
            
            # Clean up session
            session.pop("flow_state", None)
            session.pop("current_email", None)
            
            return credentials
        except Exception as e:
            logger.error(f"❌ AUTH ERROR: Error handling Google OAuth callback: {e}")
            raise Exception(f"Failed to complete Google authentication: {e}")

    async def get_meetings(self, calendar_email):
        """
        Retrieve a list of upcoming meetings for the given calendar email.

        Parameters:
            calendar_email (str): The email address of the calendar to retrieve meetings from.

        Returns:
            A list of meeting dictionaries containing:
            - title: The meeting title/summary
            - start: Start time in ISO format
            - end: End time in ISO format
            - id: The unique event ID
            - response_status: The user's response status (accepted/declined/needsAction/tentative)
            - is_organizer: Whether the user is the organizer
            - is_real_meeting: Whether the meeting has more than one attendee
            - is_synced_busy: Whether this is a synced busy block
            - location: The meeting location
            - attendee_info: String describing number of attendees
            
        Raises:
            Exception: If authentication fails or token is expired
        """
        # Run the synchronous API calls in a thread pool
        return await asyncio.get_event_loop().run_in_executor(
            None, self._get_meetings_sync, calendar_email
        )

    def _get_meetings_sync(self, calendar_email):
        """Synchronous implementation of get_meetings."""
        try:
            credentials = self.get_credentials(calendar_email)
            if not credentials:
                raise Exception("Authentication failed: Missing or invalid credentials")

            service = build("calendar", "v3", credentials=credentials)
            
            now = datetime.utcnow().isoformat() + "Z"  # "Z" indicates UTC time
            try:
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
            except HttpError as error:
                # Handle expired tokens or auth errors
                if "invalid_grant" in str(error) or "Invalid Credentials" in str(error) or "token expired" in str(error).lower():
                    logger.error(f"❌ AUTH ISSUE: Google token expired for {calendar_email}: {error}")
                    # Mark account as needing reauth
                    app_user_email = session.get('user_email')
                    account = CalendarAccount.get_by_email_provider_and_user(
                        calendar_email, self.provider_name, app_user_email
                    )
                    if account:
                        account.needs_reauth = True
                        account.save()
                    raise Exception(f"Token expired: {error}")
                else:
                    logger.error(f"❌ API ERROR: Google Calendar API error for {calendar_email}: {error}")
                    raise Exception(f"Google API error: {error}")

            events = events_result.get("items", [])
            logger.info(f"Retrieved {len(events)} events from Google Calendar for {calendar_email}")
            
            # Track counts for summary logging
            meetings_count = 0
            real_meetings_count = 0
            busy_blocks_count = 0
            
            meetings = []
            for event in events:
                meeting = self._handle_get_event(event, calendar_email)
                if meeting:
                    meetings.append(meeting)
                    meetings_count += 1
                    
                    # Count by type for summary
                    if meeting["is_real_meeting"]:
                        real_meetings_count += 1
                    if meeting["is_synced_busy"]:
                        busy_blocks_count += 1
                        
                    # Log a concise, meaningful summary for a few meetings as examples
                    if meetings_count <= 3:
                        meeting_type = "Meeting" if meeting["is_real_meeting"] else "Busy Block"
                        response_info = f"Response: {meeting['response_status']}" if meeting["is_real_meeting"] else ""
                        logger.info(f"📅 {meeting_type}: '{meeting['title']}' - {meeting['start']} to {meeting['end']} - {meeting['location']} - {meeting['attendee_info']} {response_info}")

            # Log a meaningful summary of processed meetings
            if meetings_count > 0:
                summary = f"Successfully processed {meetings_count} meetings for {calendar_email} "
                summary += f"({real_meetings_count} real meetings, {busy_blocks_count} busy blocks)"
                logger.info(summary)
            else:
                logger.info(f"No meetings found for {calendar_email} (empty calendar)")
                
            return meetings

        except HttpError as error:
            logger.error(f"Google API error while retrieving meetings for {calendar_email}: {error}")
            raise Exception(f"Google API error: {error}")

        except Exception as e:
            logger.error(f"Error retrieving meetings for {calendar_email}: {str(e)}")
            raise Exception(f"Error retrieving meetings: {str(e)}")

    def _handle_get_event(self, event, calendar_email):
        """
        Process a single event from Google Calendar.
        
        Parameters:
            event (dict): The event object from Google Calendar API
            calendar_email (str): The email address of the calendar
            
        Returns:
            dict: A dictionary containing the processed meeting data, or None if event should be skipped
        """
        # Get the user's response status
        attendees = event.get("attendees", [])
        user_response = "needsAction"  # Default if not found
        is_organizer = event.get("organizer", {}).get("email") == calendar_email

        # Look for this user's response in attendees
        for attendee in attendees:
            if attendee.get("email") == calendar_email:
                user_response = attendee.get("responseStatus", "needsAction")
                break

        # Check if this is a synced busy block
        description = event.get("description", "")
        is_synced_busy = "[SYNCED-BUSY]" in description

        # Only include events that either:
        # 1. Have more than one attendee (real meetings)
        # 2. Are synced busy blocks
        is_real_meeting = len(attendees) > 1
        
        # Get meeting details
        location = event.get("location", "No location")
        title = event.get("summary", "Untitled")
        
        # Extract meeting times - will raise ValueError if invalid
        start_time = self.get_meeting_time(event.get("start", {}))
        end_time = self.get_meeting_time(event.get("end", {}))
        
        # Get attendee info for logging
        attendee_info = ""
        if is_real_meeting:
            attendee_count = len(attendees)
            attendee_info = f"{attendee_count} attendees"
        
        if is_real_meeting or is_synced_busy:
            return {
                "id": event.get("id", ""),
                "title": title,
                "start": start_time,
                "end": end_time,
                "response_status": user_response,
                "is_organizer": is_organizer,
                "is_real_meeting": is_real_meeting,
                "is_synced_busy": is_synced_busy,
                "original_id": event.get("extendedProperties", {}).get("private", {}).get("original_event_id", ""),
                "location": location,
                "attendee_info": attendee_info
            }
        return None

    def get_meeting_time(self, meeting_time):
        """
        Extract the meeting time from the given event data.

        Parameters:
            meeting_time (dict): The event data containing the meeting time.

        Returns:
            str: The meeting time in ISO format.
            
        Raises:
            ValueError: If the meeting time data is missing or invalid.
        """
        if not meeting_time:
            raise ValueError("Meeting time data is missing")
            
        if not isinstance(meeting_time, dict):
            raise ValueError(f"Invalid meeting time format: expected dict, got {type(meeting_time).__name__}")
            
        date_time = meeting_time.get("dateTime")
        date = meeting_time.get("date")

        if date_time:
            return date_time
        elif date:
            return date
        else:
            raise ValueError("Meeting time missing both dateTime and date fields")

    async def create_busy_block(self, calendar_email, meeting_data, original_event_id):
        """
        Create a busy block in the calendar based on an existing meeting.

        Parameters:
            calendar_email (str): The email address of the calendar to create the block in.
            meeting_data (dict): The original meeting data.
            original_event_id (str): The ID of the original event this busy block is based on.

        Returns:
            str: The meeting ID if created successfully.
            
        Raises:
            Exception: If credentials are missing or API call fails
        """
        # Run the synchronous API calls in a thread pool
        return await asyncio.get_event_loop().run_in_executor(
            None, self._create_busy_block_sync, calendar_email, meeting_data, original_event_id
        )

    def _create_busy_block_sync(self, calendar_email, meeting_data, original_event_id):
        """Synchronous implementation of create_busy_block."""
        credentials = self.get_credentials(calendar_email)
        if not credentials:
            raise Exception(f"No credentials found for {calendar_email}")
            
        logger.info(f"Creating busy block for {calendar_email}")
        service = build("calendar", "v3", credentials=credentials)

        # Create a busy block event
        busy_event = {
            "summary": "Busy",
            "description": "[SYNCED-BUSY] This event was synced from another calendar.",
            "start": {"dateTime": meeting_data["start"]},
            "end": {"dateTime": meeting_data["end"]},
            "transparency": "opaque",  # Show as busy
            "visibility": "private",
            "extendedProperties": {
                "private": {
                    "original_event_id": original_event_id
                }
            }
        }

        event = (
            service.events()
            .insert(calendarId="primary", body=busy_event)
            .execute()
        )
        logger.info(f"Busy block created for {calendar_email}: {event.get('htmlLink')}")
        return event.get("id")

    def create_meeting(self, calendar_email, meeting_data):
        """
        Create a meeting in the calendar.

        Parameters:
            calendar_email (str): The email address of the calendar to create the meeting in.
            meeting_data (dict): The meeting data to use for creating the meeting.
                                 Should include at minimum: title, start, end, and attendees.

        Returns:
            str: The meeting ID if created successfully.
            
        Raises:
            Exception: If credentials are missing or API call fails
        """
        credentials = self.get_credentials(calendar_email)
        if not credentials:
            raise Exception(f"No credentials found for {calendar_email}")
            
        logger.info(f"Creating meeting for {calendar_email}")
        service = build("calendar", "v3", credentials=credentials)
        event = (
            service.events()
            .insert(calendarId="primary", body=meeting_data)
            .execute()
        )
        logger.info(f"Meeting created for {calendar_email}: {event.get('htmlLink')}")
        return event.get("id")

    def store_credentials(self, calendar_email, credentials):
        """Store credentials for the given calendar email."""
        app_user_email = session.get('user_email')
        if not app_user_email:
            logger.error("No user email in session when storing credentials")
            raise Exception("No user email in session - login required")

        credentials_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': ' '.join(credentials.scopes)
        }
        
        # Get existing account or create new one
        account = CalendarAccount.get_by_email_provider_and_user(
            calendar_email, self.provider_name, app_user_email
        )
        
        # Check if this is the first calendar account for this user
        existing_accounts = CalendarAccount.get_accounts_for_user(app_user_email)
        is_first_account = len(existing_accounts) == 0
        
        if not account:
            logger.info(f"Creating new calendar account for {calendar_email} ({self.provider_name}) for user {app_user_email}")
            account = CalendarAccount(
                calendar_email=calendar_email,
                app_user_email=app_user_email,
                provider=self.provider_name,
                is_primary=is_first_account,  # Set as primary if it's the first account
                **credentials_data
            )
        else:
            logger.info(f"Updating existing calendar account for {calendar_email} ({self.provider_name}) for user {app_user_email}")
            # Update account with new credentials
            for key, value in credentials_data.items():
                setattr(account, key, value)
        
        account.last_sync = datetime.now(timezone.utc)
        account.save()
        logger.debug(f"Credentials stored in database for calendar {calendar_email}")
        return True

    def get_credentials(self, calendar_email):
        """Retrieve credentials for the given calendar email."""
        app_user_email = session.get('user_email')
        account = CalendarAccount.get_by_email_provider_and_user(
            calendar_email, self.provider_name, app_user_email
        )
        if account:
            # Check if all required fields exist
            required_fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'client_secret', 'scopes']
            missing_fields = [field for field in required_fields if not getattr(account, field)]
            
            if missing_fields:
                logger.error(f"❌ AUTH ISSUE: Missing required credential fields for {calendar_email}: {missing_fields}")
                # Mark account as needing reauth
                account.needs_reauth = True
                account.save()
                return None
                
            try:
                credentials = Credentials(
                    token=account.token,
                    refresh_token=account.refresh_token,
                    token_uri=account.token_uri,
                    client_id=account.client_id,
                    client_secret=account.client_secret,
                    scopes=account.scopes.split()  # Convert string back to list
                )
                logger.debug(f"Credentials loaded from database for {calendar_email}")
                return credentials
            except Exception as e:
                logger.error(f"❌ AUTH ISSUE: Error creating credentials for {calendar_email}: {e}")
                # Mark account as needing reauth
                account.needs_reauth = True
                account.save()
                return None

        logger.error(f"❌ AUTH ISSUE: No Google credentials found for {calendar_email}")
        return None

    def get_google_email(self, credentials):
        """
        Get the email address of the Google account that was just authorized.
        
        This is the email address of the Google Calendar account that the user chose
        to connect, NOT necessarily the same as the app user's email. For example,
        if app user 'lakeland@gmail.com' authorizes their work calendar
        'work@company.com', this function will return 'work@company.com'.
        
        Args:
            credentials: The OAuth credentials returned from the Google authorization flow.
            
        Returns:
            str: The email address of the authorized Google Calendar account.
            
        Raises:
            ValueError: If the email address cannot be retrieved
        """
        if not credentials:
            logger.error("No credentials provided to get_google_email")
            raise ValueError("No credentials provided")
        
        try:
            service = build('oauth2', 'v2', credentials=credentials)
            user_info = service.userinfo().get().execute()
            email = user_info.get('email')
            
            if not email:
                logger.error(f"Email not found in Google account response: {user_info}")
                raise ValueError("Could not find email address in Google account information")
            
            return email
        except Exception as e:
            logger.error(f"Error getting Google account email from credentials: {e}")
            raise ValueError(f"Error retrieving Google account email: {e}")

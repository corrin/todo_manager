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

    def authenticate(self, app_login):
        """
        Initiate authentication to connect a new Google Calendar account.
        Used when the user wants to connect a calendar for the first time.

        Parameters:
            app_login (str): The email address used to log into this app. This is needed
                                  to associate the Google Calendar with the correct app user.

        Returns:
            tuple: (None, auth_url) - auth_url to redirect user to Google's consent screen
            
        Raises:
            Exception: If authentication cannot be established
        """
        # Always initiate a new OAuth flow - the calendar email will be retrieved after OAuth completes
        logger.info(f"Initiating Google OAuth flow for user {app_login}")
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
        
        # Store the app_login in session
        session["user_email"] = app_login
        
        return None, authorization_url
        
    def reauthenticate(self, calendar_email, app_login):
        """
        Reauthenticate an existing Google Calendar connection.
        Used when an existing connection needs to be refreshed.

        Parameters:
            calendar_email (str): The email address of the Google Calendar account to reauthenticate.
                                 This is the Google account email, not the app user's email.
            app_login (str): The email address used to log into this app. This is needed
                                 to associate the Google Calendar with the correct app user.

        Returns:
            tuple: (None, auth_url) - auth_url to redirect user to Google's consent screen
            
        Raises:
            Exception: If authentication cannot be established
        """
        logger.info(f"Reauthorizing Google Calendar {calendar_email} for user {app_login}")
        
        # Check if we have credentials that could be refreshed
        credentials = self.get_credentials(calendar_email, app_login)
        
        # If we have a refresh token, try to use it instead of doing full reauth
        if credentials and credentials.refresh_token:
            try:
                logger.info(f"Attempting to refresh token for {calendar_email}")
                credentials.refresh(Request())
                self.store_credentials(calendar_email, credentials, app_login)
                logger.info(f"Successfully refreshed token for {calendar_email}")
                return credentials, None
            except Exception as e:
                logger.error(f"Failed to refresh token for {calendar_email}: {e}")
                # Continue with full reauth
        
        # If we couldn't refresh or no refresh token, do full reauth
        # Set up a new OAuth flow for reauth
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
            access_type="offline", # Get refresh token
            login_hint=calendar_email  # Specify which account to authenticate
        )
        
        # Store flow state and user info in session
        session["flow_state"] = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "scopes": self.scopes,
            "state": state
        }
        
        # Store email details in session for the callback
        session["user_email"] = app_login
        session["reauth_calendar_email"] = calendar_email
        
        return None, authorization_url

    async def refresh_token(self, calendar_email, app_login):
        """
        Try to refresh the token using the refresh token.
        
        Parameters:
            calendar_email (str): The email address of the Google Calendar account.
            app_login (str): The email address used to log into this app.
            
        Returns:
            tuple: (credentials, None) if successful, (None, None) if failed
            
        Raises:
            Exception: If token refresh fails and should be handled by caller
        """
        account = CalendarAccount.get_by_email_provider_and_user(
            calendar_email, self.provider_name, app_login
        )
        
        if not account or not account.refresh_token:
            raise Exception(f"No refresh token available for {calendar_email}")
        
        logger.info(f"Attempting to refresh token for {calendar_email}")
        
        # Create a credentials object from stored credentials
        credentials = Credentials(
            token=account.token,
            refresh_token=account.refresh_token,
            token_uri=account.token_uri,
            client_id=account.client_id,
            client_secret=account.client_secret,
            scopes=account.scopes.split() if account.scopes else []
        )
        
        try:
            # Note: refresh() is synchronous, but we're wrapping it 
            # in an async method for API consistency
            credentials.refresh(Request())
            
            self.store_credentials(calendar_email, credentials, app_login)
            logger.info(f"Token refreshed for {calendar_email}")
            return credentials, None
        except Exception as e:
            error_msg = f"Token refresh failed: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

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

    def handle_oauth_callback(self, callback_url, app_login):
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
            
            return credentials
        except Exception as e:
            logger.error(f"❌ AUTH ERROR: Error handling Google OAuth callback: {e}")
            raise Exception(f"Failed to complete Google authentication: {e}")

    # This method is required by the CalendarProvider base class (which uses async methods)
    # but for Google, it's just a wrapper around our synchronous implementation
    async def get_meetings(self, calendar_email, app_login):
        """
        Async wrapper for get_meetings to conform to base class interface.
        This just calls the synchronous implementation in a thread pool.
        
        Parameters:
            calendar_email (str): The email address of the calendar to retrieve meetings from.
            app_login (str): The email address used to log into this app.

        Returns:
            A list of meeting dictionaries.
            
        Raises:
            Exception: If authentication fails or token is expired
        """
        # Run the synchronous implementation in a thread pool
        return await asyncio.get_event_loop().run_in_executor(
            None, self.get_meetings_sync, calendar_email, app_login
        )

    def get_meetings_sync(self, calendar_email, app_login):
        """Synchronous implementation of get_meetings."""
        try:
            credentials = self.get_credentials(calendar_email, app_login)
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
                    account = CalendarAccount.get_by_email_provider_and_user(
                        calendar_email, self.provider_name, app_login
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

    async def create_busy_block(self, calendar_email, meeting_data, original_event_id, app_login):
        """
        Create a busy block in the calendar based on an existing meeting.

        Parameters:
            calendar_email (str): The email address of the calendar to create the block in.
            meeting_data (dict): The original meeting data.
            original_event_id (str): The ID of the original event this busy block is based on.
            app_login (str): The email address used to log into this app.

        Returns:
            str: The meeting ID if created successfully.
            
        Raises:
            Exception: If credentials are missing or API call fails
        """
        # Run the synchronous API calls in a thread pool
        return await asyncio.get_event_loop().run_in_executor(
            None, self._create_busy_block_sync, calendar_email, meeting_data, original_event_id, app_login
        )

    def _create_busy_block_sync(self, calendar_email, meeting_data, original_event_id, app_login):
        """Synchronous implementation of create_busy_block."""
        credentials = self.get_credentials(calendar_email, app_login)
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

    def create_meeting(self, meeting_details, app_login):
        """
        Create a meeting in the calendar.

        Parameters:
            meeting_details (dict): Dictionary containing meeting details.
                Required keys: 'subject', 'start_time', 'end_time', 'calendar_email'
                Optional: 'description', 'location', 'attendees'
            app_login (str): The email address used to log into this app.

        Returns:
            str: The meeting ID if created successfully.
            
        Raises:
            Exception: If required parameters are missing or meeting creation fails.
        """
        # Extract required parameters
        calendar_email = meeting_details.get('calendar_email')
        if not calendar_email:
            raise Exception("Missing required parameter: calendar_email")
            
        subject = meeting_details.get('subject')
        if not subject:
            raise Exception("Missing required parameter: subject")
            
        start_time = meeting_details.get('start_time')
        if not start_time:
            raise Exception("Missing required parameter: start_time")
            
        end_time = meeting_details.get('end_time')
        if not end_time:
            raise Exception("Missing required parameter: end_time")

        credentials = self.get_credentials(calendar_email, app_login)
        if not credentials:
            raise Exception(f"No credentials found for {calendar_email}")
            
        logger.info(f"Creating meeting for {calendar_email}")
        service = build("calendar", "v3", credentials=credentials)
        event = (
            service.events()
            .insert(calendarId="primary", body=meeting_details)
            .execute()
        )
        logger.info(f"Meeting created for {calendar_email}: {event.get('htmlLink')}")
        return event.get("id")

    def store_credentials(self, calendar_email, credentials, app_login):
        """
        Store credentials for the given Google Calendar account.
        
        This associates the OAuth credentials with both the Google Calendar email
        and the app user's email, creating a link between them in the database.
        
        Parameters:
            calendar_email (str): The email address of the Google Calendar account.
                                 This is obtained from get_google_email().
            credentials: OAuth credentials object to store.
            app_login (str): The email address used to log into this app.
            
        Returns:
            bool: True if credentials were stored successfully.
            
        Raises:
            Exception: If provided parameters are invalid.
        """
        if not app_login:
            logger.error("No user email provided when storing credentials")
            raise Exception("app_login is required")

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
            calendar_email, self.provider_name, app_login
        )
        
        # Check if this is the first calendar account for this user
        existing_accounts = CalendarAccount.get_accounts_for_user(app_login)
        is_first_account = len(existing_accounts) == 0
        
        if not account:
            logger.info(f"Creating new calendar account for {calendar_email} ({self.provider_name}) for user {app_login}")
            account = CalendarAccount(
                calendar_email=calendar_email,
                app_login=app_login,
                provider=self.provider_name,
                is_primary=is_first_account,  # Set as primary if it's the first account
                **credentials_data
            )
        else:
            logger.info(f"Updating existing calendar account for {calendar_email} ({self.provider_name}) for user {app_login}")
            # Update account with new credentials
            for key, value in credentials_data.items():
                setattr(account, key, value)
        
        account.last_sync = datetime.now(timezone.utc)
        account.save()
        logger.debug(f"Credentials stored in database for calendar {calendar_email}")
        return True

    def get_credentials(self, calendar_email, app_login):
        """
        Retrieve credentials for the given Google Calendar account.
        
        This looks up the OAuth credentials associated with a specific Google Calendar
        account owned by the current app user.
        
        Parameters:
            calendar_email (str): The email address of the Google Calendar account.
                                 This is NOT the app_login, but the actual 
                                 Google account email.
            app_login (str): The email address used to log into this app.
                                 
        Returns:
            Credentials object if found and valid.
            
        Raises:
            Exception: In all error cases:
                      - If app_login is missing
                      - If no account is found for the calendar_email 
                      - If required credential fields are missing
                      - If there's an error creating credentials
        """
        if not app_login:
            error_msg = "No user email provided when getting credentials"
            logger.error(f"❌ AUTH ISSUE: {error_msg}")
            raise Exception(error_msg)
            
        account = CalendarAccount.get_by_email_provider_and_user(
            calendar_email, self.provider_name, app_login
        )
        if not account:
            error_msg = f"No Google credentials found for {calendar_email}"
            logger.error(f"❌ AUTH ISSUE: {error_msg}")
            raise Exception(error_msg)
            
        # Check if all required fields exist
        required_fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'client_secret', 'scopes']
        missing_fields = [field for field in required_fields if not getattr(account, field)]
        
        if missing_fields:
            error_msg = f"Missing required credential fields for {calendar_email}: {missing_fields}"
            logger.error(f"❌ AUTH ISSUE: {error_msg}")
            # Mark account as needing reauth
            account.needs_reauth = True
            account.save()
            raise Exception(error_msg)
            
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
            error_msg = f"Error creating credentials for {calendar_email}: {e}"
            logger.error(f"❌ AUTH ISSUE: {error_msg}")
            # Mark account as needing reauth
            account.needs_reauth = True
            account.save()
            raise Exception(error_msg)

    def get_google_email(self, credentials):
        """
        Get the email address of the Google account that was just authorized.
        
        This retrieves the email address of the specific Google Calendar account that 
        the user authorized through OAuth. This email is different from the app_login, 
        which is used to log into this app.
        
        For example, if a user logs into our app with 'lakeland@gmail.com' (app_login)
        but authorizes their work Google Calendar 'work@company.com', this function will 
        return 'work@company.com'.
        
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

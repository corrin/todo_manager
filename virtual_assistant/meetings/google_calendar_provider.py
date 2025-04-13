"""
Module for Google Calendar integration.
"""

import datetime
import json
import os
from datetime import datetime, timezone
import asyncio

from flask import render_template, session
from google.auth.transport.requests import Request, AuthorizedSession
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

    def authenticate(self, user_id):
        """
        Initiate authentication to connect a new Google Calendar account.
        Used when the user wants to connect a calendar for the first time.

        Parameters:
            user_id (int): The ID of the app user.

        Returns:
            tuple: (None, auth_url) - auth_url to redirect user to Google's consent screen

        Raises:
            Exception: If authentication cannot be established
        """
        # Always initiate a new OAuth flow - the calendar email will be retrieved after OAuth completes
        logger.info(f"Initiating Google OAuth flow for user ID {user_id}")
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

        # Store the user_id in session
        session["user_id"] = user_id

        return None, authorization_url

    def reauthenticate(self, calendar_email, user_id):
        """
        Reauthenticate an existing Google Calendar connection.
        Attempts to refresh the token first; if that fails or no refresh token exists,
        initiates the full OAuth flow to get new credentials.

        Parameters:
            calendar_email (str): The email address of the Google Calendar account to reauthenticate.
            user_id (int): The ID of the app user associated with this calendar account.

        Returns:
            tuple: (None, auth_url) - auth_url to redirect user to Google's consent screen
                   or (credentials, None) if token refresh was successful.

        Raises:
            Exception: If the OAuth flow setup fails. Token refresh errors are handled internally.
        """
        logger.info(f"Reauthorizing Google Calendar {calendar_email} for user ID {user_id}") # Use user_id in log

        # Check if we have credentials that could be refreshed
        credentials = self.get_credentials(calendar_email, user_id) # Use user_id

        # If we have a refresh token, try to use it instead of doing full reauth
        if credentials and credentials.refresh_token: # Check if credentials exist and have a refresh token
            try:
                logger.info(f"Attempting to refresh token for {calendar_email}")
                credentials.refresh(Request()) # Attempt to refresh the token
                self.store_credentials(calendar_email, credentials, user_id) # Update stored credentials on success
                logger.info(f"Successfully refreshed token for {calendar_email}")
                return credentials, None # Return refreshed credentials, no auth_url needed
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
        # session["app_login"] = app_login # No longer needed here, user_id is passed directly
        session["reauth_calendar_email"] = calendar_email

        return None, authorization_url

    async def refresh_token(self, calendar_email, user_id):
        """
        Try to refresh the token using the refresh token.

        Parameters:
            calendar_email (str): The email address of the Google Calendar account.
            user_id (int): The ID of the app user.

        Returns:
            tuple: (credentials, None) if successful, (None, None) if failed

        Raises:
            Exception: If token refresh fails and should be handled by caller
        """
        account = CalendarAccount.get_by_email_provider_and_user(
            calendar_email, self.provider_name, user_id # Use user_id
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

            self.store_credentials(calendar_email, credentials, user_id) # Use user_id
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

    def handle_oauth_callback(self, callback_url):
        """
        Handle the OAuth callback from Google after user consent.
        Uses the state stored in the session to recreate the OAuth flow
        and fetch the access and refresh tokens.

        Parameters:
            callback_url (str): The full callback URL received from Google containing the auth code and state.

        Returns:
            google.oauth2.credentials.Credentials: The obtained credentials object.
        """
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
    async def get_meetings(self, calendar_email, user_id):
        """
        Async wrapper for get_meetings to conform to base class interface.
        This just calls the synchronous implementation in a thread pool.

        Parameters:
            calendar_email (str): The email address of the calendar to retrieve meetings from.
            user_id (int): The ID of the app user.

        Returns:
            A list of meeting dictionaries.

        Raises:
            Exception: If authentication fails or token is expired
        """
        # Run the synchronous implementation in a thread pool
        return await asyncio.get_event_loop().run_in_executor(
            None, self.get_meetings_sync, calendar_email, user_id # Pass user_id
        )

    def get_meetings_sync(self, calendar_email, user_id):
        """Synchronous implementation of get_meetings."""
        try:
            credentials = self.get_credentials(calendar_email, user_id) # Use user_id
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
                        calendar_email, self.provider_name, user_id # Use user_id
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
        try:
            start_time = self.get_meeting_time(event.get("start", {}))
            end_time = self.get_meeting_time(event.get("end", {}))
        except ValueError as e:
             logger.warning(f"Skipping event '{title}' due to invalid time data: {e}")
             return None # Skip event if time data is invalid.


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

    def get_meeting_time(self, meeting_time_data):
        """
        Extract the meeting time from the given event data.

        Parameters:
            meeting_time_data (dict): The event data containing the meeting time.

        Returns:
            str: The meeting time in ISO format.

        Raises:
            ValueError: If the meeting time data is missing or invalid.
        """
        if not meeting_time_data:
            raise ValueError("Meeting time data is missing")

        if not isinstance(meeting_time_data, dict):
            raise ValueError(f"Invalid meeting time format: expected dict, got {type(meeting_time_data).__name__}")

        date_time = meeting_time_data.get("dateTime")
        date = meeting_time_data.get("date")

        if date_time:
            return date_time
        elif date:
            return date
        else:
            raise ValueError("Meeting time missing both dateTime and date fields")

    async def create_busy_block(self, calendar_email, meeting_data, original_event_id, user_id):
        """
        Create a busy block in the calendar based on an existing meeting.

        Parameters:
            calendar_email (str): The email address of the calendar to create the block in.
            meeting_data (dict): The original meeting data.
            original_event_id (str): The ID of the original event this busy block is based on.
            user_id (int): The ID of the app user.

        Returns:
            str: The meeting ID if created successfully.

        Raises:
            Exception: If credentials are missing or API call fails
        """
        # Run the synchronous API calls in a thread pool
        return await asyncio.get_event_loop().run_in_executor(
            None, self._create_busy_block_sync, calendar_email, meeting_data, original_event_id, user_id # Pass user_id
        )

    def _create_busy_block_sync(self, calendar_email, meeting_data, original_event_id, user_id):
        """Synchronous implementation of create_busy_block."""
        credentials = self.get_credentials(calendar_email, user_id) # Use user_id
        if not credentials:
            raise Exception(f"No credentials found for {calendar_email} (User ID: {user_id}) to create busy block.")

        logger.info(f"Creating busy block for '{meeting_data.get('title', 'Untitled')}' on {calendar_email} (User ID: {user_id})")
        service = build("calendar", "v3", credentials=credentials)

        # Construct the event body for the busy block.
        busy_event = {
            'summary': f"[BUSY] {meeting_data.get('title', 'Untitled')}",
            'description': f"[SYNCED-BUSY] Blocking time for event: {original_event_id}",
            'start': {'dateTime': meeting_data['start'], 'timeZone': 'UTC'}, # Assuming times are UTC ISO strings
            'end': {'dateTime': meeting_data['end'], 'timeZone': 'UTC'},
            'transparency': 'opaque', # Makes the block appear as "Busy"
            'extendedProperties': {
                'private': {
                    'original_event_id': original_event_id,
                    'sync_source': 'virtual_assistant_app' # Identify the source
                }
            }
        }

        try:
            # Insert the event into the user's primary calendar.
            event = (
                service.events()
                .insert(calendarId="primary", body=busy_event)
                .execute()
            )
            logger.info(f"Successfully created busy block event with ID: {event.get('id')}")
            return event.get("id")
        except HttpError as error:
            logger.error(f"Failed to create busy block for {calendar_email} (User ID: {user_id}): {error}")
            raise Exception(f"Google API error creating busy block: {error}")

    def create_meeting(self, meeting_details, user_id):
        """
        DEPRECATED/UNUSED? - Seems intended to create actual meetings, but uses app_login.
        Needs review and update to use user_id if still required.
        """
        # This method needs updating to use user_id instead of app_login
        # and likely needs calendar_email as well.
        # Example structure (needs refinement):
        # credentials = self.get_credentials(calendar_email, user_id)
        # if not credentials:
        #     raise Exception("Cannot create meeting: Authentication required.")
        # service = build("calendar", "v3", credentials=credentials)
        # event = { ... construct event body from meeting_details ... }
        # created_event = service.events().insert(calendarId='primary', body=event).execute()
        # return created_event.get('id')
        raise NotImplementedError("create_meeting needs to be updated to use user_id and potentially calendar_email.")


    def store_credentials(self, calendar_email, credentials, user_id):
        """
        Stores or updates Google Calendar credentials (tokens, etc.) in the database,
        associating them with the specified application user ID.

        Parameters:
            calendar_email (str): The email address associated with the Google Calendar account.
            credentials (google.oauth2.credentials.Credentials): The Credentials object containing tokens.
            user_id (int): The ID of the application user.

        Returns:
            CalendarAccount: The created or updated CalendarAccount database object.

        Raises:
            Exception: If there's an error saving the data to the database.
        """
        # Retrieve existing account or prepare to create a new one.
        account = CalendarAccount.get_by_email_provider_and_user(
            calendar_email, self.provider_name, user_id # Use user_id
        )

        # Prepare a dictionary with the credential data to be stored.
        credentials_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': ' '.join(credentials.scopes) # Store scopes as a space-separated string.
        }

        # Determine if this should be the primary account.
        # It becomes primary only if the user doesn't already have a primary account set.
        has_primary = CalendarAccount.query.filter_by(user_id=user_id, is_primary=True).first() is not None
        is_first_account = not has_primary # Set as primary if no other primary exists for this user.

        if not account:
            # Create a new CalendarAccount record if one doesn't exist.
            logger.info(f"Creating new calendar account for {calendar_email} ({self.provider_name}) for user ID {user_id}")
            account = CalendarAccount(
                user_id=user_id, # Associate with the correct app user ID.
                calendar_email=calendar_email,
                provider=self.provider_name,
                is_primary=is_first_account, # Set primary status based on check above.
                created_at=datetime.now(timezone.utc),
                **credentials_data # Populate with token data.
            )
        else:
            # Update the existing account record.
            logger.info(f"Updating existing calendar account for {calendar_email} ({self.provider_name}) for user ID {user_id}")
            for key, value in credentials_data.items():
                setattr(account, key, value)
            # Don't change primary status on update unless explicitly requested elsewhere.

        # Mark as not needing re-authorization since we just stored fresh credentials.
        account.needs_reauth = False
        account.last_sync = datetime.now(timezone.utc) # Update sync time (optional here, maybe better after successful API call)

        try:
            # Save the new or updated record to the database.
            account.save()
            logger.debug(f"Credentials stored/updated in database for calendar {calendar_email} (User ID: {user_id})")
        except Exception as e:
            logger.error(f"Error saving calendar account to database for {calendar_email} (User ID: {user_id}): {e}")
            # Consider rolling back the session if using Flask-SQLAlchemy's session management.
            # db.session.rollback()
            raise Exception(f"Error saving calendar account: {e}") # Re-raise the exception.

        return account # Return the persisted account object.

    def get_credentials(self, calendar_email, user_id):
        """
        Retrieves credentials for a specific Google Calendar account associated with an app user ID.
        Constructs a google.oauth2.credentials.Credentials object from data stored in the database.

        Parameters:
            calendar_email (str): The email address of the Google Calendar account.
            user_id (int): The ID of the application user.

        Returns:
            google.oauth2.credentials.Credentials: The constructed Credentials object if found and valid.

        Raises:
            Exception: If no account is found for the user_id and calendar_email,
                       or if required credential fields (like token or refresh_token) are missing.
        """
        # Retrieve the specific account record from the database.
        account = CalendarAccount.get_by_email_provider_and_user(
            calendar_email, self.provider_name, user_id # Use user_id
        )

        if not account: # Check if an account record was found.
            error_msg = f"No Google credentials found in database for {calendar_email} associated with user ID {user_id}"
            logger.error(f"❌ AUTH ISSUE: {error_msg}")
            raise Exception(error_msg) # Critical error if account doesn't exist.

        # Verify that essential credential fields are present in the database record.
        required_fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'client_secret', 'scopes']
        missing_fields = [field for field in required_fields if not getattr(account, field, None)]

        if missing_fields:
            error_msg = f"Missing required credential fields in database for {calendar_email} (User ID: {user_id}): {missing_fields}"
            logger.error(f"❌ AUTH ISSUE: {error_msg}")
            # Mark for re-authentication as the stored data is incomplete.
            account.needs_reauth = True
            account.save()
            raise Exception(error_msg) # Raise error as credentials cannot be constructed.

        try:
            # Construct the Credentials object using the data retrieved from the database.
            credentials = Credentials(
                token=account.token,
                refresh_token=account.refresh_token,
                token_uri=account.token_uri,
                client_id=account.client_id,
                client_secret=account.client_secret,
                scopes=account.scopes.split() # Convert space-separated string back to list.
            )
            # Optional: Check if the access token is expired and attempt refresh immediately.
            # if credentials.expired and credentials.refresh_token:
            #     try:
            #         logger.info(f"Access token expired for {calendar_email}, attempting refresh within get_credentials.")
            #         credentials.refresh(Request())
            #         self.store_credentials(calendar_email, credentials, user_id) # Store refreshed token
            #     except Exception as refresh_error:
            #         logger.error(f"Failed to auto-refresh expired token within get_credentials for {calendar_email}: {refresh_error}")
            #         account.needs_reauth = True
            #         account.save()
            #         raise Exception(f"Failed to refresh expired token: {refresh_error}")

            return credentials
        except Exception as e:
            # Catch potential errors during Credentials object creation.
            logger.error(f"Error creating Credentials object for {calendar_email} (User ID: {user_id}): {e}")
            raise Exception(f"Could not construct credentials: {e}")


    def get_google_email(self, credentials):
        """
        Retrieves the user's email address associated with the given Google credentials.
        Uses the Google People API (or UserInfo endpoint).

        Parameters:
            credentials (google.oauth2.credentials.Credentials): Valid Google credentials.

        Returns:
            str: The user's primary email address.

        Raises:
            Exception: If the email address cannot be retrieved.
        """
        try:
            # 1. Try getting email from the ID token first (most efficient)
            id_token_claims = credentials.id_token # If id_token is available (common with OpenID scope)
            if id_token_claims and 'email' in id_token_claims:
                 logger.debug(f"Retrieved email from ID token: {id_token_claims['email']}")
                 return id_token_claims['email']

            # 2. If not in ID token, call the standard UserInfo endpoint using google-auth transport
            logger.info("Email not found in ID token, calling UserInfo endpoint.")
            authed_session = AuthorizedSession(credentials)

            userinfo_response = authed_session.get(
                "https://openidconnect.googleapis.com/v1/userinfo"
            )
            userinfo_response.raise_for_status() 
            user_info = userinfo_response.json()

            if user_info and 'email' in user_info:
                logger.debug(f"Retrieved email from UserInfo endpoint: {user_info['email']}")
                return user_info['email']
            else:
                logger.error(f"Email not found in UserInfo response. Response: {user_info}")
                raise Exception("Email address not found in Google UserInfo response.")

        except Exception as e:
            logger.error(f"Error retrieving Google email: {e}")
            # Log the type of exception for better debugging
            logger.error(f"Exception type: {type(e).__name__}")
            raise Exception(f"Failed to retrieve Google email address: {e}")

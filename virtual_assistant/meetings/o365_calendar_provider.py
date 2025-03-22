# o365_calendar_provider.py
import os
import json
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
import uuid
from urllib.parse import quote, parse_qs
from asgiref.sync import async_to_sync
import logging

import msal
import requests
from flask import render_template, session
from msgraph import GraphServiceClient
from azure.identity import ClientSecretCredential
from msgraph.generated.users.item.calendar.events.events_request_builder import EventsRequestBuilder
from kiota_abstractions.base_request_configuration import RequestConfiguration
from azure.core.credentials import AccessToken as AzureAccessToken

from virtual_assistant.utils.logger import logger
from virtual_assistant.utils.settings import Settings
from virtual_assistant.database.calendar_account import CalendarAccount
from .calendar_provider import CalendarProvider

# Custom credential class that uses an existing access token
class AccessTokenCredential:
    def __init__(self, token):
        self.token = token
        
    def get_token(self, *scopes, **kwargs):
        # Return an access token in the format expected by the SDK
        
        # Ensure the token is not empty
        if not self.token:
            raise ValueError("Access token is empty")
            
        # Log the token length and first/last few characters for debugging
        token_length = len(self.token) if self.token else 0
        token_preview = ""
        if token_length > 10:
            token_preview = f"{self.token[:5]}...{self.token[-5:]}"
        logger.debug(f"Using access token of length {token_length}, preview: {token_preview}")
        
        # Return an Azure AccessToken with the token and an expiration time
        return AzureAccessToken(token=self.token, expires_on=int(time.time()) + 3600)

# Configure MSAL logging - set to INFO to reduce excessive debug logs
msal_logger = logging.getLogger('msal')
msal_logger.setLevel(logging.INFO)
# Make sure the handler is set to use our existing logger's handlers
for handler in logger.handlers:
    msal_logger.addHandler(handler)


class O365CalendarProvider(CalendarProvider):
    """Office 365 Calendar Provider class for handling O365 calendar integration."""
    
    provider_name = 'o365'
    
    def __init__(self):
        self.client_id = Settings.O365_CLIENT_ID
        self.client_secret = Settings.O365_CLIENT_SECRET
        self.redirect_uri = Settings.O365_REDIRECT_URI
        self.scopes = ["https://graph.microsoft.com/Calendars.ReadWrite"]  # For authorization code flow
        self.client_credential_scopes = ["https://graph.microsoft.com/.default"]  # For client credentials flow
        self.authority = "https://login.microsoftonline.com/common"
        self.app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret,
        )
        
        # Response status mapping between O365 and our internal format
        self.response_status_map = {
            "notResponded": "needsAction",
            "tentativelyAccepted": "tentative",
            "accepted": "accepted",
            "declined": "declined",
            None: "needsAction"
        }
        
        # Keep these - useful for verifying config
        logger.debug("O365 Calendar Provider initialized")
        logger.debug(f"Redirect URI = {self.redirect_uri}")
        
        # # Check if client secret is valid
        # self.check_client_secret_valid()
        
    def check_client_secret_valid(self):
        """Check if the client secret is valid by attempting to get a token using client credentials flow."""
        try:
            logger.debug("Checking if client secret is valid...")
            result = self.app.acquire_token_for_client(scopes=self.client_credential_scopes)
            
            if "access_token" in result:
                logger.debug("✅ Client secret is valid")
                return True
            else:
                error = result.get("error", "unknown_error")
                error_description = result.get("error_description", "Unknown error")
                logger.error(f"❌ Client secret validation failed: {error} - {error_description}")
                logger.debug(f"Full error response: {result}")
                return False
        except Exception as e:
            logger.error(f"❌ Error checking client secret: {str(e)}")
            logger.exception(e)
            return False

    def _map_response_status(self, o365_status):
        """Map O365 response status to our internal format."""
        return self.response_status_map.get(o365_status, "needsAction")

    def _get_extended_property(self, event, property_name):
        """Get an extended property value from an O365 event."""
        props = event.get("singleValueExtendedProperties", [])
        for prop in props:
            if f"Name {property_name}" in prop.get("id", ""):
                return prop.get("value")
        return ""

    def _format_event_time(self, time_obj):
        """Format O365 event time object to ISO string."""
        if not time_obj:
            raise ValueError("Meeting time data is missing")
            
        date_time = time_obj.get("dateTime")
        if not date_time:
            raise ValueError("Meeting time missing dateTime field")
            
        return date_time

    def authenticate(self, app_user_email):
        """
        Initiate authentication to connect a new O365 Calendar account.
        Used when the user wants to connect a calendar for the first time.
        
        Parameters:
            app_user_email (str): The email address used to log into this app.
            
        Returns:
            tuple: (None, auth_url) where auth_url is the URL to redirect to for auth
            
        Raises:
            ValueError: If app_user_email is not provided or authentication fails
        """
        # FAIL EARLY: Validate required parameters
        if not app_user_email:
            error_msg = "app_user_email is required for authentication"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        logger.info(f"Starting O365 authentication for user {app_user_email}")
        logger.debug(f"O365 client_id: {self.client_id}")
        logger.debug(f"O365 redirect_uri: {self.redirect_uri}")
        logger.debug(f"O365 scopes: {self.scopes}")
        logger.debug(f"O365 authority: {self.authority}")
        
        # Store the app user email in session for use in callback
        session['user_email'] = app_user_email
        
        # Generate state for CSRF protection
        state = str(uuid.uuid4())
        if not state:
            error_msg = "Failed to generate OAuth state"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        session['oauth_state'] = state
        logger.debug(f"Generated OAuth state: {state}")
        
        # Get auth URL from MSAL
        try:
            logger.debug("Calling MSAL get_authorization_request_url")
            auth_url = self.app.get_authorization_request_url(
                scopes=self.scopes,
                state=state,
                redirect_uri=self.redirect_uri,
                prompt="login"  # Force Microsoft to show the login screen
            )
            
            # FAIL EARLY: Verify auth URL was generated
            if not auth_url:
                error_msg = "Failed to generate authorization URL"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            logger.debug(f"Generated auth URL: {auth_url[:100]}...")
            return None, auth_url
        except Exception as e:
            error_msg = f"Error generating authorization URL: {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            raise ValueError(error_msg)
        
    async def refresh_token(self, calendar_email, app_user_email):
        """
        Try to refresh the token using the refresh token.
        
        Returns:
            tuple: (credentials, None) if successful, (None, None) if failed
            
        Raises:
            Exception: If token refresh fails and should be handled by caller
        """
        account = CalendarAccount.get_by_email_provider_and_user(
            calendar_email, self.provider_name, app_user_email
        )
        
        if not account or not account.refresh_token:
            raise Exception(f"No refresh token available for {calendar_email}")
        
        logger.info(f"Attempting to refresh token for {calendar_email}")
        
        # Use the O365 token endpoint to refresh
        token_url = f"{self.authority}/oauth2/v2.0/token"
        data = {
            'client_id': account.client_id,
            'client_secret': account.client_secret,
            'refresh_token': account.refresh_token,
            'grant_type': 'refresh_token'
        }
        
        response = requests.post(token_url, data=data)
        if response.status_code != 200:
            raise Exception(f"Token refresh failed with status {response.status_code}: {response.text}")
        
        new_tokens = response.json()
        if 'access_token' not in new_tokens:
            raise Exception(f"No access token in refresh response for {calendar_email}")
        
        credentials = {
            'token': new_tokens['access_token'],
            'refresh_token': new_tokens.get('refresh_token', account.refresh_token),
            'token_uri': account.token_uri,
            'client_id': account.client_id,
            'client_secret': account.client_secret,
            'scopes': account.scopes
        }
        
        self.store_credentials(calendar_email, credentials, app_user_email)
        logger.info(f"Token refreshed for {calendar_email}")
        return credentials, None
    
    def get_auth_url(self, calendar_email, app_user_email):
        """
        Get the authorization URL for full reauthentication.
        
        Returns:
            tuple: (None, auth_url) where auth_url is the URL to redirect to for auth
        """
        # Store account details in session for callback
        session['o365_calendar_email'] = calendar_email
        session['user_email'] = app_user_email
        
        # Generate state for CSRF protection
        state = str(uuid.uuid4())
        session['oauth_state'] = state
        
        # Get auth URL from MSAL
        auth_url = self.app.get_authorization_request_url(
            scopes=self.scopes,
            state=state,
            redirect_uri=self.redirect_uri,
            login_hint=calendar_email  # Specify which account to authenticate
        )
        
        logger.info(f"Created auth URL for {calendar_email}")
        return None, auth_url
    
    async def reauthenticate(self, calendar_email, app_user_email):
        """
        Reauthenticate an existing O365 Calendar connection.
        First tries to refresh the token, then falls back to full reauthentication if that fails.
        
        Parameters:
            calendar_email (str): The email address of the O365 Calendar account to reauthenticate.
                                 This is the actual O365 account email.
            app_user_email (str): The email address used to log into this app.
            
        Returns:
            tuple: (credentials, None) if token refresh successful,
                  (None, auth_url) if full reauth is needed
        """
        logger.info(f"Reauthorizing O365 Calendar {calendar_email} for user {app_user_email}")
        
        # First, try to refresh the token
        try:
            if CalendarAccount.get_by_email_provider_and_user(
                calendar_email, self.provider_name, app_user_email
            ) and CalendarAccount.get_by_email_provider_and_user(
                calendar_email, self.provider_name, app_user_email
            ).refresh_token:
                return await self.refresh_token(calendar_email, app_user_email)
        except Exception as e:
            logger.error(f"Token refresh failed: {str(e)}")
            # Fall back to full reauth
        
        # If refresh failed or was not possible, get auth URL for full reauth
        return self.get_auth_url(calendar_email, app_user_email)

    async def handle_oauth_callback(self, callback_url, app_user_email):
        """Handle the OAuth callback from O365."""
        logger.debug(f"O365 OAuth callback handling initiated with URL: {callback_url}")
        
        try:
            # Parse the URL to get query parameters
            parsed_url = urllib.parse.urlparse(callback_url)
            query_dict = urllib.parse.parse_qs(parsed_url.query)
            
            # Log all query parameters for debugging
            logger.debug(f"OAuth callback query parameters: {query_dict}")
            
            # FAIL EARLY: Check for required parameters
            if 'code' not in query_dict or not query_dict['code']:
                error_msg = "No authorization code received in callback"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            if 'state' not in query_dict or not query_dict['state']:
                error_msg = "No state parameter received in callback"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            # Extract values after validating existence
            code = query_dict['code'][0]
            received_state = query_dict['state'][0]
            logger.debug(f"Received authorization code: {code[:10]}...")
            logger.debug(f"Received state: {received_state}")
            
            # FAIL EARLY: Check for error in the callback
            if 'error' in query_dict:
                error = query_dict['error'][0]
                error_description = query_dict['error_description'][0] if 'error_description' in query_dict else 'No description'
                error_msg = f"OAuth error: {error} - {error_description}"
                logger.error(f"❌ AUTH ERROR: {error_msg}")
                raise ValueError(error_msg)
                
            # FAIL EARLY: Verify state exists in session
            expected_state = session.get('oauth_state')
            logger.debug(f"Expected state from session: {expected_state}")
            if not expected_state:
                error_msg = "No state found in session - security verification failed"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            # FAIL EARLY: Verify state matches
            if received_state != expected_state:
                error_msg = f"State mismatch error: expected {expected_state}, got {received_state}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Clean up the state from session
            session.pop('oauth_state', None)
            
            logger.debug("Attempting to acquire token by authorization code")
            # Get the tokens using MSAL with fail-early approach
            try:
                result = self.app.acquire_token_by_authorization_code(
                    code,
                    scopes=self.scopes,
                    redirect_uri=self.redirect_uri
                )
                logger.debug(f"Token acquisition result keys: {result.keys()}")
                
                # Verify token scopes
                if "scope" in result:
                    logger.info(f"Token scopes: {result['scope']}")
                    if "https://graph.microsoft.com/Calendars.ReadWrite" not in result['scope']:
                        logger.warning("Required scope 'Calendars.ReadWrite' is missing from token!")
                else:
                    logger.warning("No scope information in token response!")
            except Exception as token_error:
                logger.error(f"Exception during token acquisition: {str(token_error)}")
                logger.exception(token_error)
                raise ValueError(f"Failed to acquire token: {str(token_error)}")
            
            # FAIL EARLY: Verify token was received
            if "access_token" not in result:
                error_code = result.get('error', 'unknown_error')
                error_description = result.get('error_description', 'Unknown error')
                error_msg = f"Failed to obtain tokens: {error_code} - {error_description}"
                logger.error(f"❌ TOKEN ERROR: {error_msg}")
                logger.debug(f"Full token error response: {result}")
                raise ValueError(error_msg)
            
            logger.debug("Successfully acquired access token")
            if "refresh_token" in result:
                logger.debug("Refresh token also acquired")
            
            # Create credentials dictionary
            access_token = result["access_token"]
            token_length = len(access_token)
            logger.debug(f"Access token length from OAuth: {token_length}")
            
            credentials = {
                "token": access_token,
                "refresh_token": result.get("refresh_token"),
                "token_uri": f"{self.authority}/oauth2/v2.0/token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scopes": self.scopes
            }
            
            # Log credential keys for debugging
            logger.debug(f"Credential keys: {credentials.keys()}")
            
            # Verify we have valid tokens and ID token claims
            if "access_token" not in result or not result["access_token"]:
                raise ValueError("Missing or invalid access token")
                
            if "id_token_claims" not in result:
                raise ValueError("No ID token claims found - authentication may be incomplete")
                
            # Extract email from ID token claims
            claims = result["id_token_claims"]
            logger.debug(f"ID token claims: {claims}")
            
            if "preferred_username" not in claims:
                raise ValueError(f"No preferred_username in ID token claims. Available claims: {claims.keys()}")
                
            email = claims["preferred_username"]
            logger.info(f"Using email from ID token claims: {email}")
                
            # Store the credentials
            logger.debug(f"Storing credentials for {email}")
            self.store_credentials(email, credentials, app_user_email)
            
            # Explicitly set needs_reauth to False since we have a valid token
            account = CalendarAccount.get_by_email_provider_and_user(
                email, self.provider_name, app_user_email
            )
            if account:
                account.needs_reauth = False
                account.last_sync = datetime.now(timezone.utc)
                account.save()
                logger.debug(f"Updated account {email} to not need reauth")
            
            return email
            
        except Exception as e:
            logger.error(f"Error retrieving tokens: {str(e)}")
            raise Exception(f"Error retrieving tokens: {str(e)}")

    async def get_meetings(self, calendar_email, app_user_email):
        """
        Get meetings for the given calendar email.
        
        Parameters:
            calendar_email (str): The email address of the calendar to retrieve meetings from.
            app_user_email (str): The email address used to log into this app.

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
            
        Raises:
            Exception: If authentication fails, token is expired, or any other error occurs
        """
        credentials = self.get_credentials(calendar_email, app_user_email)
        if not credentials:
            # Account already marked as needing reauth in get_credentials
            raise Exception("Authentication failed: Missing or invalid credentials")
        # Log that we're using the user's access token
        logger.info(f"Using user's access token for {calendar_email}")

        try:
            # Use the get_authenticated_graph_client method which is already working
            client = self.get_authenticated_graph_client(credentials)
            
            if not client:
                raise Exception("Failed to create authenticated Graph client")

            # Get current time range
            now = datetime.utcnow()
            start_date = now.strftime("%Y-%m-%dT00:00:00Z")
            end_date = (now + timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")

            # Create query parameters
            query_params = EventsRequestBuilder.EventsRequestBuilderGetQueryParameters(
                select=["subject", "start", "end", "attendees", "organizer", "responseStatus", "id", "body", "singleValueExtendedProperties", "location"],
                filter=f"start/dateTime ge '{start_date}' and end/dateTime le '{end_date}'",
                expand=["singleValueExtendedProperties($filter=id eq 'String {00020329-0000-0000-C000-000000000046} Name original_event_id')"]
            )
            
            # Create request configuration
            request_config = EventsRequestBuilder.EventsRequestBuilderGetRequestConfiguration(
                query_parameters=query_params
            )
            
            # Use Graph API to get events - this is an async operation
            events = await client.users.by_user_id(calendar_email).calendar.events.get(
                request_configuration=request_config
            )

            if not events:
                logger.info(f"No events found for {calendar_email}")
                # Token is valid since API call succeeded
                account = CalendarAccount.get_by_email_provider_and_user(
                    calendar_email, self.provider_name, app_user_email
                )
                if account:
                    account.last_sync = datetime.now(timezone.utc)
                    account.needs_reauth = False
                    account.save()
                return []

            events_list = events.value if hasattr(events, 'value') else []
            logger.info(f"Retrieved {len(events_list)} events from O365 Calendar for {calendar_email}")
            
            # Track counts for summary logging
            meetings_count = 0
            real_meetings_count = 0
            busy_blocks_count = 0
            
            meetings = []
            for event in events_list:
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
                        logger.info(f"📅 O365 {meeting_type}: '{meeting['title']}' - {meeting['start']} to {meeting['end']} - {meeting['location']} - {meeting['attendee_info']} {response_info}")

            # Log a meaningful summary of processed meetings
            if meetings_count > 0:
                summary = f"Successfully processed {meetings_count} O365 meetings for {calendar_email} "
                summary += f"({real_meetings_count} real meetings, {busy_blocks_count} busy blocks)"
                logger.info(summary)
            else:
                logger.info(f"No meetings found in O365 calendar for {calendar_email} (empty calendar)")
            
            # Update last sync timestamp on successful API completion
            account = CalendarAccount.get_by_email_provider_and_user(
                calendar_email, self.provider_name, app_user_email
            )
            if account:
                account.last_sync = datetime.now(timezone.utc)
                account.needs_reauth = False
                account.save()
                
            return meetings

        except Exception as e:
            error_msg = str(e)
            # Check for auth issues including token expiration, permissions, conditional access
            if ("InvalidAuthenticationToken" in error_msg or 
                "token is expired" in error_msg.lower() or
                "AADSTS" in error_msg or
                "access has been blocked" in error_msg.lower() or
                "conditional access" in error_msg.lower() or
                "unauthorized" in error_msg.lower()):
                
                logger.error(f"❌ AUTH ISSUE: O365 authentication error for {calendar_email}: {error_msg}")
                # Mark account as needing reauth
                account = CalendarAccount.get_by_email_provider_and_user(
                    calendar_email, self.provider_name, app_user_email
                )
                if account:
                    account.needs_reauth = True
                    account.save()
                raise Exception(f"Authentication error: {error_msg}")
            else:
                logger.error(f"❌ API ERROR: O365 API error: {error_msg}")
                raise Exception(f"O365 API error: {error_msg}")

    def _handle_get_event(self, event, calendar_email):
        """
        Process a single event from O365 calendar.
        
        Parameters:
            event: The event object from O365 API
            calendar_email (str): The email address of the calendar
            
        Returns:
            dict: A dictionary containing the processed meeting data, or None if event should be skipped
        """
        # Get attendees and check if it's a real meeting (more than 1 attendee)
        attendees = event.attendees or []
        is_real_meeting = len(attendees) > 1
        
        # Get user's response status and organizer status
        is_organizer = event.organizer.email_address.address == calendar_email if event.organizer and event.organizer.email_address else False
        
        # Get response status from O365 format
        o365_response = None
        for attendee in attendees:
            if attendee.email_address.address == calendar_email:
                o365_response = attendee.status.response if attendee.status else None
                break
        user_response = self._map_response_status(o365_response)
        
        # Check if this is a synced busy block
        body = event.body.content if event.body else ""
        is_synced_busy = "[SYNCED-BUSY]" in body
        
        # Get meeting details
        location = event.location.display_name if event.location else "No location"
        title = event.subject or "Untitled"
        
        # Extract meeting times
        start_time = event.start.date_time
        end_time = event.end.date_time
        
        # Get attendee info for logging
        attendee_info = ""
        if is_real_meeting:
            attendee_count = len(attendees)
            attendee_info = f"{attendee_count} attendees"
        
        # Only include events that are either real meetings or synced busy blocks
        if is_real_meeting or is_synced_busy:
            return {
                "id": event.id,
                "title": title,
                "start": start_time,
                "end": end_time,
                "response_status": user_response,
                "is_organizer": is_organizer,
                "is_real_meeting": is_real_meeting,
                "is_synced_busy": is_synced_busy,
                "original_id": self._get_extended_property(event, "original_event_id"),
                "location": location,
                "attendee_info": attendee_info
            }
        return None

    async def create_busy_block(self, calendar_email, meeting_data, original_event_id, app_user_email):
        """
        Create a busy block in the calendar based on an existing meeting.

        Parameters:
            calendar_email (str): The email address of the calendar to create the block in.
            meeting_data (dict): The original meeting data.
            original_event_id (str): The ID of the original event this busy block is based on.
            app_user_email (str): The email address used to log into this app.

        Returns:
            str: The meeting ID if created successfully.
            
        Raises:
            Exception: If credentials are missing or API call fails
        """
        credentials = self.get_credentials(calendar_email, app_user_email)
        if not credentials:
            raise Exception(f"No credentials found for {calendar_email}")

        try:
            # Create Graph client using our updated authentication method
            client = self.get_authenticated_graph_client(credentials)
            if not client:
                raise ValueError("Failed to create authenticated Graph client")
            
            # Format the event data for O365
            event = {
                "subject": "Busy",
                "body": {
                    "contentType": "text",
                    "content": "[SYNCED-BUSY] This event was synced from another calendar."
                },
                "start": {
                    "dateTime": meeting_data["start"],
                    "timeZone": "UTC"
                },
                "end": {
                    "dateTime": meeting_data["end"],
                    "timeZone": "UTC"
                },
                "showAs": "busy",
                "sensitivity": "private",
                "singleValueExtendedProperties": [
                    {
                        "id": "String {00020329-0000-0000-C000-000000000046} Name original_event_id",
                        "value": original_event_id
                    }
                ]
            }
            
            # Create the event using Graph API - this is an async operation
            result = await client.users.by_user_id(calendar_email).calendar.events.post(
                body=event,
                request_configuration=EventsRequestBuilder.EventsRequestBuilderPostRequestConfiguration()
            )
            
            if not result:
                raise Exception("Failed to create busy block: No response from Graph API")
                
            logger.info(f"Busy block created for {calendar_email}: {result.id}")
            return result.id
            
        except Exception as e:
            error_msg = f"Failed to create busy block: {str(e)}"
            logger.error(f"❌ API ERROR: {error_msg}")
            raise Exception(error_msg)

    def create_meeting(self, meeting_details, app_user_email):
        """
        Create a meeting in the O365 calendar.
        
        Parameters:
            meeting_details (dict): Dictionary containing meeting details.
                Required keys: 'subject', 'start_time', 'end_time', 'calendar_email'
                Optional: 'description', 'location', 'attendees'
            app_user_email (str): The email address used to log into this app.
                
        Returns:
            dict: Dictionary with meeting details if successful.
            
        Raises:
            Exception: If required parameters are missing or meeting creation fails.
        """
        # Use a synchronous implementation to match the base class,
        # but internally use async_to_sync to call our async implementation
        return async_to_sync(self._create_meeting_async)(meeting_details, app_user_email)
    
    async def _create_meeting_async(self, meeting_details, app_user_email):
        """Async implementation of create_meeting."""
        # Verify required parameters
        required_params = ["subject", "start_time", "end_time", "calendar_email"]
        for param in required_params:
            if param not in meeting_details:
                error_msg = f"Missing required parameter: {param}"
                logger.error(error_msg)
                raise Exception(error_msg)

        calendar_email = meeting_details.get("calendar_email")
        # Get token information for the calendar
        credentials = self.get_credentials(calendar_email, app_user_email)
        if not credentials:
            error_msg = f"No credentials found for calendar: {calendar_email}"
            logger.error(error_msg)
            raise Exception(error_msg)

        # Create the Graph client
        graph_client = self.get_authenticated_graph_client(credentials)
        if not graph_client:
            error_msg = "Failed to authenticate with Graph API"
            logger.error(error_msg)
            raise Exception(error_msg)

        # Extract meeting details
        subject = meeting_details.get("subject")
        start_time = meeting_details.get("start_time")
        end_time = meeting_details.get("end_time")
        description = meeting_details.get("description", "")
        location = meeting_details.get("location", "")
        attendees = meeting_details.get("attendees", [])

        # Validate time data types
        if start_time is None or end_time is None:
            error_msg = "Start time and end time must not be None"
            logger.error(error_msg)
            raise Exception(error_msg)

        # Convert times to ISO format if they are datetime objects
        if isinstance(start_time, datetime):
            start_time = start_time.isoformat()
        elif not isinstance(start_time, str):
            error_msg = f"Invalid start_time type: expected datetime or str, got {type(start_time).__name__}"
            logger.error(error_msg)
            raise Exception(error_msg)
            
        if isinstance(end_time, datetime):
            end_time = end_time.isoformat()
        elif not isinstance(end_time, str):
            error_msg = f"Invalid end_time type: expected datetime or str, got {type(end_time).__name__}"
            logger.error(error_msg)
            raise Exception(error_msg)

        # Create the event content
        new_event = {
            "subject": subject,
            "body": {"contentType": "HTML", "content": description},
            "start": {"dateTime": start_time, "timeZone": "UTC"},
            "end": {"dateTime": end_time, "timeZone": "UTC"},
        }

        # Add location if provided
        if location:
            new_event["location"] = {"displayName": location}

        # Add attendees if provided
        if attendees:
            new_event["attendees"] = []
            for attendee in attendees:
                attendee_email = attendee.get("email", "")
                if attendee_email:
                    new_event["attendees"].append(
                        {
                            "emailAddress": {"address": attendee_email},
                            "type": "required",
                        }
                    )

        try:
            # Use the new SDK style to create the event
            result = await graph_client.users.by_user_id(calendar_email).calendar.events.post(
                body=new_event,
                request_configuration=EventsRequestBuilder.EventsRequestBuilderPostRequestConfiguration()
            )
            
            if result:
                logger.info(f"Meeting created successfully in O365: {result.id}")
                
                # Format the response
                response = {
                    "id": result.id,
                    "subject": result.subject,
                    "start_time": result.start.date_time if result.start else None,
                    "end_time": result.end.date_time if result.end else None,
                    "organizer": result.organizer.email_address.address if result.organizer and result.organizer.email_address else None,
                    "meeting_link": result.web_url,
                    "provider": "o365",
                }
                return response
            else:
                error_msg = "Failed to create event: Empty response from Graph API"
                logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Error creating meeting in O365: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def store_credentials(self, calendar_email, credentials, app_user_email):
        """
        Store credentials for the given calendar email.
        
        Parameters:
            calendar_email (str): The email address of the calendar account.
            credentials (dict): The credentials to store.
            app_user_email (str): The email address used to log into this app.
            
        Raises:
            Exception: If storing credentials fails for any reason
        """
        if not app_user_email:
            error_msg = "No user email provided when storing credentials" 
            logger.error(error_msg)
            raise Exception(error_msg)

        # Validate and prepare scopes
        if 'scopes' not in credentials:
            logger.error("Missing 'scopes' in credentials")
            raise Exception("Missing required 'scopes' field in credentials")
        elif not isinstance(credentials['scopes'], (list, str)):
            logger.error(f"Invalid type for 'scopes': {type(credentials['scopes'])}")
            raise Exception(f"Expected 'scopes' to be list or string, got {type(credentials['scopes'])}")
        
        # Convert list scopes to string for storage
        if isinstance(credentials['scopes'], list):
            credentials['scopes'] = ' '.join(credentials['scopes'])
            
        # Validate token exists
        if 'access_token' in credentials:
            credentials['token'] = credentials.pop('access_token')
        elif 'token' not in credentials:
            logger.error("No token found in credentials")
            raise Exception("Missing required token in credentials")
        
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
                **credentials
            )
        else:
            logger.info(f"Updating existing calendar account for {calendar_email} ({self.provider_name}) for user {app_user_email}")
            # Update account with new credentials
            for key, value in credentials.items():
                setattr(account, key, value)
            account.app_user_email = app_user_email  # Ensure this is set even on update
        
        account.last_sync = datetime.now(timezone.utc)
        account.save()
        logger.debug(f"O365 credentials stored in database for calendar {calendar_email}")
        return True

    def get_credentials(self, calendar_email, app_user_email):
        """
        Retrieve credentials for the given calendar email.
        
        Parameters:
            calendar_email (str): The email address of the calendar to get credentials for.
            app_user_email (str): The email address used to log into this app.
            
        Returns:
            dict: Credential dictionary if found and valid
            
        Raises:
            Exception: In all error cases:
                     - If app_user_email is missing
                     - If no account is found for the calendar_email 
                     - If required credential fields are missing
                     - If account is already marked as needing reauth
        """
        if not app_user_email:
            error_msg = "No user email provided when getting credentials"
            logger.error(f"❌ AUTH ISSUE: {error_msg}")
            raise Exception(error_msg)
            
        account = CalendarAccount.get_by_email_provider_and_user(
            calendar_email, self.provider_name, app_user_email
        )
        if not account:
            error_msg = f"No O365 credentials found for {calendar_email}"
            logger.error(f"❌ AUTH ISSUE: {error_msg}")
            raise Exception(error_msg)
        
        # If account is already marked as needing reauth, don't try to use it
        if account.needs_reauth:
            error_msg = f"Account {calendar_email} is already marked as needing reauthorization"
            logger.error(f"❌ AUTH ISSUE: {error_msg}")
            raise Exception(error_msg)
            
        # Check for token which is required for authentication
        if not account.token:
            error_msg = f"Missing access token for {calendar_email}"
            logger.error(f"❌ AUTH ISSUE: {error_msg}")
            # Mark account as needing reauth
            account.needs_reauth = True
            account.save()
            raise Exception(error_msg)
            
        # Check for fields needed for token refresh
        refresh_fields = ['refresh_token', 'token_uri', 'client_id', 'client_secret']
        missing_refresh_fields = [field for field in refresh_fields if not getattr(account, field)]
        
        if missing_refresh_fields:
            logger.warning(f"Missing fields for token refresh for {calendar_email}: {missing_refresh_fields}")
            # We don't fail here since immediate authentication can still work with just the token
            
        credentials = {
            'token': account.token,  # Keep as token
            'refresh_token': account.refresh_token,
            'token_uri': account.token_uri,
            'client_id': account.client_id,
            'client_secret': account.client_secret,
            'scopes': account.scopes.split() if account.scopes else []  # Convert string back to list
        }
        logger.debug(f"O365 credentials loaded from database for {calendar_email}")
        return credentials

    async def get_o365_email(self, credentials):
        """
        Get the user's email address from the Microsoft Graph API.
        
        Parameters:
            credentials (dict): The credentials dictionary containing the access token.
            
        Returns:
            str: The user's email address.
            
        Raises:
            Exception: If the API call fails or no email is returned.
        """
        if not credentials:
            error_msg = "No credentials provided to get O365 email"
            logger.error(error_msg)
            raise Exception(error_msg)
            
        try:
            # Use our updated authentication method
            client = self.get_authenticated_graph_client(credentials)
            if not client:
                raise ValueError("Failed to create authenticated Graph client")
            user = await client.me.get()
            
            if not user:
                error_msg = "No user data returned from Graph API"
                logger.error(error_msg)
                raise Exception(error_msg)
                
            user_email = user.user_principal_name
            
            if not user_email:
                error_msg = "User email not found in Graph API response"
                logger.error(error_msg)
                raise Exception(error_msg)
                
            logger.info(f"Successfully retrieved O365 email: {user_email}")
            return user_email
            
        except Exception as e:
            error_msg = f"Error getting O365 email: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def get_authenticated_graph_client(self, credentials):
        """
        Create an authenticated Microsoft Graph client using the user's access token.
        
        Parameters:
            credentials (dict): The credentials dictionary for authentication.
            
        Returns:
            GraphServiceClient: The authenticated Graph client object.
            
        Raises:
            Exception: If no token is found in credentials or authentication fails.
        """
        if not credentials or "token" not in credentials:
            error_msg = "No valid credentials provided for Graph client"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        try:
            # Log token information for debugging
            token = credentials.get("token", "")
            token_length = len(token) if token else 0
            logger.debug(f"Token length in get_authenticated_graph_client: {token_length}")
            
            if not token:
                logger.error("Token is empty in get_authenticated_graph_client")
                raise ValueError("Access token is empty")
            
            # Create a credential using the user's access token
            credential = AccessTokenCredential(token)
            
            # Use delegated permission scopes
            scopes = self.scopes
            logger.debug(f"Using scopes: {scopes}")
            
            # Create and return the Graph client with the credential and scopes
            logger.debug("Creating GraphServiceClient with credential and scopes")
            graph_client = GraphServiceClient(credential, scopes)
            logger.debug("GraphServiceClient created successfully")
            return graph_client
        except Exception as e:
            error_msg = f"Error creating Graph client: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def retrieve_tokens(self, callback_url):
        """
        Parse the callback URL and retrieve tokens from OAuth flow.
        Required by CalendarProvider ABC.
        
        Parameters:
            callback_url (str): The full callback URL received from O365.
            
        Returns:
            dict: The credentials dictionary containing access and refresh tokens.
            
        Raises:
            Exception: If token retrieval fails.
        """
        # Parse the URL to get query parameters
        parsed_url = urllib.parse.urlparse(callback_url)
        query_dict = urllib.parse.parse_qs(parsed_url.query)
        
        # Get the authorization code
        code = query_dict.get('code', [None])[0]
        if not code:
            error_msg = "No authorization code received in callback"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # Get the tokens using MSAL
        result = self.app.acquire_token_by_authorization_code(
            code,
            scopes=self.scopes,
            redirect_uri=self.redirect_uri
        )
        
        if "access_token" not in result:
            error_msg = f"Failed to obtain tokens: {result.get('error_description', 'Unknown error')}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # Create credentials dictionary
        credentials = {
            "token": result["access_token"],
            "refresh_token": result.get("refresh_token"),
            "token_uri": f"{self.authority}/oauth2/v2.0/token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scopes": self.scopes
        }
        
        return credentials

    def initiate_auth_flow(self, redirect_uri, app_user_email):
        """
        Initiate the O365 OAuth authentication flow.
        
        Parameters:
            redirect_uri (str): The URI to redirect to after authentication.
            app_user_email (str): The email address used to log into this app.
            
        Returns:
            tuple: (None, auth_url) where auth_url is the authorization URL to redirect the user to.
            
        Raises:
            Exception: If the flow cannot be initiated or parameters are invalid.
        """
        # Validate redirect_uri
        if not redirect_uri:
            error_msg = "No redirect URI provided for authentication flow"
            logger.error(error_msg)
            raise Exception(error_msg)
            
        logger.debug(f"Initiating O365 auth flow with redirect URI: {redirect_uri}")
        
        # Store the app user email in session
        session['user_email'] = app_user_email
            
        try:
            # Create the authorization flow
            flow = self.app.initiate_auth_code_flow(
                scopes=self.scopes.split(),
                redirect_uri=redirect_uri,
            )
            
            # Store the flow state in the session
            session["flow"] = flow
            
            # Return the authorization URL
            logger.info("O365 auth flow initiated successfully")
            return None, flow["auth_uri"]
        except Exception as e:
            error_msg = f"Error initiating O365 auth flow: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

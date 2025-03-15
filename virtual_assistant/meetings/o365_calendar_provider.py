# o365_calendar_provider.py
import os
import json
import urllib.parse
from datetime import datetime, timedelta, timezone
import uuid
from urllib.parse import quote, parse_qs

import msal
import requests
from flask import render_template, session
from msgraph import GraphServiceClient
from azure.identity import ClientSecretCredential

from virtual_assistant.utils.logger import logger
from virtual_assistant.utils.settings import Settings
from virtual_assistant.database.calendar_account import CalendarAccount
from .calendar_provider import CalendarProvider


class O365CalendarProvider(CalendarProvider):
    """Office 365 Calendar Provider class for handling O365 calendar integration."""
    
    provider_name = 'o365'
    
    def __init__(self):
        self.client_id = Settings.O365_CLIENT_ID
        self.client_secret = Settings.O365_CLIENT_SECRET
        self.redirect_uri = Settings.O365_REDIRECT_URI
        self.scopes = ["https://graph.microsoft.com/Calendars.ReadWrite"]  # MSAL will handle reserved scopes automatically
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

    def authenticate(self, calendar_email, app_user_email=None):
        """
        Initiate O365 authentication flow.
        
        Parameters:
            calendar_email (str): The email address of the calendar to authenticate
            app_user_email (str): The email address of the app user
            
        Returns:
            tuple: (None, auth_url) where auth_url is the URL to redirect to for auth
        """
        logger.info(f"Starting O365 authentication for {calendar_email}")
        
        # Store the calendar email in session for use in callback
        session['o365_calendar_email'] = calendar_email
        session['user_email'] = app_user_email
        
        # Generate state for CSRF protection
        state = str(uuid.uuid4())
        session['oauth_state'] = state
        
        # Get auth URL from MSAL
        auth_url = self.app.get_authorization_request_url(
            scopes=self.scopes,
            state=state,
            redirect_uri=self.redirect_uri
        )
        
        return None, auth_url

    async def handle_oauth_callback(self, callback_url):
        """Handle the OAuth callback from O365."""
        logger.debug(f"O365 OAuth callback handling initiated with URL: {callback_url}")
        
        try:
            # Parse the URL to get query parameters
            parsed_url = urllib.parse.urlparse(callback_url)
            query_dict = urllib.parse.parse_qs(parsed_url.query)
            
            # Get the authorization code and state
            code = query_dict.get('code', [None])[0]
            received_state = query_dict.get('state', [None])[0]
            
            if not code:
                error_msg = "No authorization code received in callback"
                logger.error(error_msg)
                raise Exception(error_msg)
                
            # Verify state matches to prevent CSRF
            expected_state = session.get('oauth_state')
            if not expected_state:
                error_msg = "No state found in session"
                logger.error(error_msg)
                raise Exception(error_msg)
                
            if received_state != expected_state:
                error_msg = f"State mismatch error: expected {expected_state}, got {received_state}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Clean up the state from session
            session.pop('oauth_state', None)
            
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
            
            # Get the user's email using Graph API
            credential = ClientSecretCredential(
                tenant_id="common",
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            client = GraphServiceClient(credentials=credential)
            user = await client.me.get()
            email = user.mail or user.user_principal_name
            
            if not email:
                raise Exception("Could not retrieve email from O365 account")
                
            # Store the credentials
            self.store_credentials(email, credentials)
            
            return email
            
        except Exception as e:
            logger.error(f"Error retrieving tokens: {str(e)}")
            raise Exception(f"Error retrieving tokens: {str(e)}")

    async def get_meetings(self, calendar_email):
        """
        Get meetings for the given calendar email.
        
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
            
        Raises:
            Exception: If authentication fails, token is expired, or any other error occurs
        """
        credentials = self.get_credentials(calendar_email)
        if not credentials:
            # Account already marked as needing reauth in get_credentials
            raise Exception("Authentication failed: Missing or invalid credentials")

        # Create credential object for Graph client
        credential = ClientSecretCredential(
            tenant_id="common",  # Use "common" for multi-tenant apps
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"]
        )

        try:
            # Create Graph client
            client = GraphServiceClient(credentials=credential)

            # Get current time range
            now = datetime.utcnow()
            start_date = now.strftime("%Y-%m-%dT00:00:00Z")
            end_date = (now + timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")

            # Use Graph API to get events - this is an async operation
            events = await client.users[calendar_email].calendar.events.get(
                params={
                    "$select": "subject,start,end,attendees,organizer,responseStatus,id,body,singleValueExtendedProperties,location",
                    "$filter": f"start/dateTime ge '{start_date}' and end/dateTime le '{end_date}'",
                    "$expand": "singleValueExtendedProperties($filter=id eq 'String {00020329-0000-0000-C000-000000000046} Name original_event_id')"
                }
            )

            if not events:
                logger.info(f"No events found for {calendar_email}")
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
                
            return meetings

        except Exception as e:
            error_msg = str(e)
            # Check for token expiration
            if "InvalidAuthenticationToken" in error_msg or "token is expired" in error_msg.lower():
                logger.error(f"❌ AUTH ISSUE: O365 token expired for {calendar_email}")
                # Mark account as needing reauth
                app_user_email = session.get('user_email')
                account = CalendarAccount.get_by_email_provider_and_user(
                    calendar_email, self.provider_name, app_user_email
                )
                if account:
                    account.needs_reauth = True
                    account.save()
                raise Exception(f"Token expired: {error_msg}")
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
        credentials = self.get_credentials(calendar_email)
        if not credentials:
            raise Exception(f"No credentials found for {calendar_email}")

        # Create credential object for Graph client
        credential = ClientSecretCredential(
            tenant_id="common",  # Use "common" for multi-tenant apps
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"]
        )

        try:
            # Create Graph client
            client = GraphServiceClient(credentials=credential)
            
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
            result = await client.users[calendar_email].calendar.events.post(
                body=event
            )
            
            if not result:
                raise Exception("Failed to create busy block: No response from Graph API")
                
            logger.info(f"Busy block created for {calendar_email}: {result.id}")
            return result.id
            
        except Exception as e:
            error_msg = f"Failed to create busy block: {str(e)}"
            logger.error(f"❌ API ERROR: {error_msg}")
            raise Exception(error_msg)

    def create_meeting(self, meeting_details):
        """
        Create a meeting in the O365 calendar.
        
        Parameters:
            meeting_details (dict): Dictionary containing meeting details.
                Required keys: 'subject', 'start_time', 'end_time', 'calendar_email'
                Optional: 'description', 'location', 'attendees'
                
        Returns:
            dict: Dictionary with meeting details if successful.
            
        Raises:
            Exception: If required parameters are missing or meeting creation fails.
        """
        # Verify required parameters
        required_params = ["subject", "start_time", "end_time", "calendar_email"]
        for param in required_params:
            if param not in meeting_details:
                error_msg = f"Missing required parameter: {param}"
                logger.error(error_msg)
                raise Exception(error_msg)

        calendar_email = meeting_details.get("calendar_email")
        # Get token information for the calendar
        credentials = self.get_credentials(calendar_email)
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
            # Post the new event to the user's calendar
            result = graph_client.post(
                f"/users/{calendar_email}/calendar/events", data=new_event
            )
            if result:
                created_event = result.json()
                logger.info(f"Meeting created successfully in O365: {created_event.get('id')}")
                
                # Format the response
                response = {
                    "id": created_event.get("id"),
                    "subject": created_event.get("subject"),
                    "start_time": created_event.get("start", {}).get("dateTime"),
                    "end_time": created_event.get("end", {}).get("dateTime"),
                    "organizer": created_event.get("organizer", {})
                    .get("emailAddress", {})
                    .get("address"),
                    "meeting_link": created_event.get("webLink"),
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

    def store_credentials(self, calendar_email, credentials):
        """
        Store credentials for the given calendar email.
        
        Parameters:
            calendar_email (str): The email address of the calendar account.
            credentials (dict): The credentials to store.
            
        Raises:
            Exception: If storing credentials fails for any reason
        """
        app_user_email = session.get('user_email')
        if not app_user_email:
            logger.error("No user email in session when storing credentials")
            raise Exception("No user email in session - login required")

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

    def get_credentials(self, calendar_email):
        """
        Retrieve credentials for the given calendar email.
        
        Parameters:
            calendar_email (str): The email address of the calendar to get credentials for.
            
        Returns:
            dict: Credential dictionary if found and valid
            
        Raises:
            Exception: If credentials are missing required fields
        """
        app_user_email = session.get('user_email')
        account = CalendarAccount.get_by_email_provider_and_user(
            calendar_email, self.provider_name, app_user_email
        )
        if not account:
            error_msg = f"No O365 credentials found for {calendar_email}"
            logger.error(f"❌ AUTH ISSUE: {error_msg}")
            return None
            
        # Check if required fields exist
        required_fields = ['token', 'token_uri', 'client_id', 'client_secret']
        missing_fields = [field for field in required_fields if not getattr(account, field)]
        
        if missing_fields:
            error_msg = f"Missing required O365 credential fields for {calendar_email}: {missing_fields}"
            logger.error(f"❌ AUTH ISSUE: {error_msg}")
            # Mark account as needing reauth
            account.needs_reauth = True
            account.save()
            return None
            
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
            
        # Create credential object for Graph client
        credential = ClientSecretCredential(
            tenant_id="common",  # Use "common" for multi-tenant apps
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"]
        )
        
        try:
            # Create Graph client and make request - this is an async operation
            client = GraphServiceClient(credentials=credential)
            user = await client.users.me.get()
            
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
        Create an authenticated Microsoft Graph client.
        
        Parameters:
            credentials (dict): The credentials dictionary for authentication.
            
        Returns:
            GraphServiceClient: The authenticated Graph client object.
            
        Raises:
            Exception: If no token is found in credentials or authentication fails.
        """
        if not credentials:
            error_msg = "No credentials provided for Graph client authentication"
            logger.error(error_msg)
            raise Exception(error_msg)
            
        # Check for token in credentials
        if "token" not in credentials:
            error_msg = "No token found in credentials"
            logger.error(error_msg)
            raise Exception(error_msg)
            
        try:
            # Create credential object
            credential = ClientSecretCredential(
                tenant_id="common",  # Use "common" for multi-tenant apps
                client_id=credentials["client_id"],
                client_secret=credentials["client_secret"]
            )
            
            # Create and return the Graph client
            graph_client = GraphServiceClient(credential)
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

    def initiate_auth_flow(self, redirect_uri):
        """
        Initiate the O365 OAuth authentication flow.
        
        Parameters:
            redirect_uri (str): The URI to redirect to after authentication.
            
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

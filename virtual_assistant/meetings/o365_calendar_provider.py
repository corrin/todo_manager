# o365_calendar_provider.py
import os
import json
import urllib.parse
from datetime import datetime, timedelta

import msal
import requests
from flask import render_template, session

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
        self.scopes = ["Calendars.ReadWrite"]
        self.authority = "https://login.microsoftonline.com/common"
        self.app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret,
        )

    def authenticate(self, calendar_email):
        """
        Authenticate the user with the given calendar email.
        
        Parameters:
            calendar_email (str): The email address of the calendar to authenticate.
        """
        cache = msal.SerializableTokenCache()
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret,
            token_cache=cache,
        )

        accounts = app.get_accounts(username=calendar_email)
        if accounts:
            result = app.acquire_token_silent(scopes=self.scopes, account=accounts[0])
            if "access_token" in result:
                return result["access_token"], None

        # Initiate the auth code flow
        flow = app.initiate_auth_code_flow(
            scopes=self.scopes, redirect_uri=self.redirect_uri
        )
        session["flow"] = flow
        session["current_email"] = calendar_email

        return None, flow["auth_uri"]

    def retrieve_tokens(self, callback_url):
        # Parse the authorization code from the callback URL
        logger.debug(f"O365 retrieve tokens called with callback: {callback_url}")
        query_dict = urllib.parse.parse_qs(urllib.parse.urlparse(callback_url).query)
        auth_code = query_dict.get("code", [""])[
            0
        ]  # Taking the first element of the list
        received_state = query_dict.get("state", [""])[
            0
        ]  # Taking the first element of the list

        if not auth_code:
            logger.error("Authorization code not found in the callback URL")
            return None

        # Retrieve flow data from the session
        flow = session.get("flow", {})
        if not flow:
            logger.error("Authentication flow data not found in session")
            return None

        # Security check for state value
        if flow.get("state") != received_state:
            logger.error(
                f"State mismatch error: expected {flow.get('state')}, got {received_state}"
            )
            return None

        # Adjust query_dict to the expected format by MSAL
        corrected_query_dict = {key: values[0] for key, values in query_dict.items()}

        # Complete the token acquisition process using MSAL
        result = self.app.acquire_token_by_auth_code_flow(flow, corrected_query_dict)
        if "access_token" in result:
            access_token = result["access_token"]
            refresh_token = result.get("refresh_token", None)
            expires_in = result.get(
                "expires_in", 3600
            )  # Default to 1 hour if not specified
            expiration_time = datetime.utcnow() + timedelta(seconds=expires_in)

            credentials = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expiration_time": expiration_time.isoformat(),
                "token_uri": f"{self.authority}/oauth2/v2.0/token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scopes": self.scopes,
            }
            return credentials
        else:
            logger.error(f"Failed to obtain tokens: {result.get('error_description')}")
            return None

    def get_meetings(self, calendar_email):
        """
        Get meetings for the given calendar email.
        
        Parameters:
            calendar_email (str): The email address of the calendar to retrieve meetings from.
        """
        try:
            credentials = self.get_credentials(calendar_email)
            if not credentials:
                logger.error(f"No credentials found for {calendar_email}")
                return []

            access_token = credentials.get("access_token")
            if not access_token:
                logger.error(f"No access token found in credentials for {calendar_email}")
                return []

            endpoint = "https://graph.microsoft.com/v1.0/me/events"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Prefer": 'outlook.timezone="UTC"',
            }

            now = datetime.utcnow()
            start_date = now.strftime("%Y-%m-%dT00:00:00Z")
            end_date = (now + timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")

            params = {
                "$select": "subject,start,end",
                "$filter": f"start/dateTime ge '{start_date}' and end/dateTime le '{end_date}'",
            }

            response = requests.get(endpoint, headers=headers, params=params)
            if response.status_code != 200:
                logger.error(f"Failed to get meetings: {response.text}")
                return []

            events_result = response.json()
            meetings = []
            for event in events_result.get("value", []):
                try:
                    meeting = {
                        "title": event.get("subject", ""),
                        "start": event.get("start", {}).get("dateTime", ""),
                        "end": event.get("end", {}).get("dateTime", ""),
                    }
                    meetings.append(meeting)
                except Exception as e:
                    logger.error(f"Error processing event: {event}")
                    logger.exception(e)

            return meetings

        except Exception as e:
            logger.error(f"Error getting meetings for {calendar_email}")
            logger.exception(e)
            return []

    def create_meeting(self, calendar_email, event_data):
        """
        Create a meeting for the given calendar email.
        
        Parameters:
            calendar_email (str): The email address of the calendar to create the meeting in.
            event_data (dict): The meeting data to create.
        """
        try:
            credentials = self.get_credentials(calendar_email)
            if not credentials:
                logger.error(f"No credentials found for {calendar_email}")
                return False

            access_token = credentials.get("access_token")
            if not access_token:
                logger.error(f"No access token found in credentials for {calendar_email}")
                return False

            endpoint = "https://graph.microsoft.com/v1.0/me/events"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            response = requests.post(endpoint, headers=headers, json=event_data)
            if response.status_code == 201:
                logger.info(f"Meeting created for {calendar_email}")
                return True
            else:
                logger.error(f"Failed to create meeting: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error creating meeting for {calendar_email}")
            logger.exception(e)
            return False

    def store_credentials(self, calendar_email, credentials, app_user_email):
        """
        Store credentials for the given calendar email.
        
        Parameters:
            calendar_email (str): The email address of the calendar account.
            credentials (dict): The credentials to store.
            app_user_email (str): The email address of the app user who owns this calendar.
        """
        # Get existing account or create new one
        account = CalendarAccount.get_by_email_and_provider(calendar_email, self.provider_name)
        if not account:
            account = CalendarAccount(
                calendar_email=calendar_email,
                app_user_email=app_user_email,
                provider=self.provider_name,
                **credentials
            )
        else:
            # Update account with new credentials
            for key, value in credentials.items():
                setattr(account, key, value)
        
        account.last_sync = datetime.utcnow()
        account.save()
        logger.debug(f"O365 credentials stored in database for calendar {calendar_email}")

    def get_credentials(self, calendar_email):
        """
        Retrieve credentials for the given calendar email.
        
        Parameters:
            calendar_email (str): The email address of the calendar to get credentials for.
        """
        account = CalendarAccount.get_by_email_and_provider(calendar_email, self.provider_name)
        if account:
            credentials = {
                'token': account.token,
                'refresh_token': account.refresh_token,
                'token_uri': account.token_uri,
                'client_id': account.client_id,
                'client_secret': account.client_secret,
                'scopes': account.scopes.split()  # Convert string back to list
            }
            logger.debug(f"O365 credentials loaded from database for {calendar_email}")
            return credentials

        logger.warning(f"No O365 credentials found for {calendar_email}")
        return None

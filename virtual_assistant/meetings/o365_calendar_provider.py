# o365_calendar_provider.py
import os
import json
import urllib.parse
from datetime import datetime, timedelta

import msal
import requests
from flask import render_template, session

from virtual_assistant.utils.logger import logger
from virtual_assistant.utils.user_manager import UserManager
from .calendar_provider import CalendarProvider


class O365CalendarProvider(CalendarProvider):
    """Office 365 Calendar Provider class for handling O365 calendar integration."""
    
    provider_name = 'o365'
    
    def __init__(self):
        self.client_id = os.environ["MICROSOFT_CLIENT_ID"]
        self.client_secret = os.environ["MICROSOFT_CLIENT_SECRET"]
        self.redirect_uri = "https://virtualassistant-lakeland.pythonanywhere.com/meetings/o365_authenticate"
        self.scopes = ["Calendars.ReadWrite"]
        self.authority = "https://login.microsoftonline.com/common"
        self.app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret,
        )

    def authenticate(self, email):
        cache = msal.SerializableTokenCache()
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret,
            token_cache=cache,
        )

        accounts = app.get_accounts(username=email)
        if accounts:
            result = app.acquire_token_silent(scopes=self.scopes, account=accounts[0])
            if "access_token" in result:
                return result["access_token"], None

        # Initiate the auth code flow
        flow = app.initiate_auth_code_flow(
            scopes=self.scopes, redirect_uri=self.redirect_uri
        )
        session["flow"] = flow
        session["current_email"] = email

        return None, render_template(
            "authenticate_email.html",
            email=email,
            authorization_url=flow["auth_uri"],
        )

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

    def get_meetings(self, email, access_token):
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

        events_result = requests.get(endpoint, headers=headers, params=params).json()

        meetings = []
        for event in events_result["value"]:
            meeting = {
                "title": event["subject"],
                "start": event["start"]["dateTime"],
                "end": event["end"]["dateTime"],
            }
            meetings.append(meeting)

        return meetings

    def create_meeting(self, email, access_token, event_data):
        endpoint = "https://graph.microsoft.com/v1.0/me/events"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        response = requests.post(endpoint, headers=headers, json=event_data)
        if response.status_code == 201:
            return True
        else:
            return False

    def store_credentials(self, email, credentials):
        """Store credentials for the given email."""
        provider_folder = UserManager.get_provider_folder(self.provider_name, email)
        credentials_file = os.path.join(provider_folder, f"{email}_credentials.json")
        
        with open(credentials_file, "w", encoding="utf-8") as file:
            json.dump(credentials, file)
        logger.debug(f"O365 credentials stored for {email}")

    def get_credentials(self, email):
        """Retrieve credentials for the given email."""
        provider_folder = UserManager.get_provider_folder(self.provider_name, email)
        credentials_file = os.path.join(provider_folder, f"{email}_credentials.json")
        
        if os.path.exists(credentials_file):
            with open(credentials_file, "r", encoding="utf-8") as file:
                credentials = json.load(file)
                logger.debug(f"O365 credentials loaded for {email}")
                return credentials
        
        logger.warning(f"No O365 credentials found for {email}")
        return None

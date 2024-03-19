# meetings/meetings_routes.py
from flask import Blueprint, request
import os
from google_auth_oauthlib.flow import Flow

meetings_bp = Blueprint('meetings', __name__)

@meetings_bp.route('/google_authenticate')
def google_authenticate():
    # Handle the Google OAuth 2.0 callback
    client_config = {
        'web': {
            'client_id': os.environ['GOOGLE_CLIENT_ID'],
            'client_secret': os.environ['GOOGLE_CLIENT_SECRET'],
            'redirect_uris': ['https://calendar-lakeland.pythonanywhere.com/meetings/google_authenticate'],
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
        }
    }
    flow = Flow.from_client_config(client_config, scopes=['https://www.googleapis.com/auth/calendar'])
    authorization_code = request.args.get('code')
    flow.fetch_token(code=authorization_code)
    credentials = flow.credentials
    email = get_email_from_credentials(credentials)
    store_credentials(email, credentials)
    return "Google authentication successful!"

@meetings_bp.route('/o365_authenticate')
def o365_authenticate():
    # Handle the Office 365 OAuth 2.0 callback
    authorization_code = request.args.get('code')
    # Exchange the authorization code for access token and refresh token
    credentials = flow.fetch_token(code=authorization_code)
    # Store the credentials for the authenticated email address
    email = get_email_from_credentials(credentials)
    store_credentials(email, credentials)
    return "Office 365 authentication successful!"

def get_email_from_credentials(credentials):
    # Extract the email address from the authenticated credentials
    # You may need to make an additional API call to retrieve the email address
    # Example: https://docs.microsoft.com/en-us/graph/api/user-get?view=graph-rest-1.0
    pass

def store_credentials(email, credentials):
    # Store the credentials for the email address
    # You can use a database or file storage to persist the credentials
    pass
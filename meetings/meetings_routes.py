# meetings/meetings_routes.py
from flask import Blueprint, request
from google_auth_oauthlib.flow import Flow
from virtual_assistant.utils.logger import logger
from virtual_assistant.flask_app import app  # Import the app instance
import utils.settings # import , GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, GOOGLE_SCOPES

meetings_bp = Blueprint('meetings', __name__, url_prefix='/meetings')

@meetings_bp.route('/google_authenticate', methods=['GET'])
def google_authenticate():
    # Handle the Google OAuth 2.0 callback
    client_config = {
        'web': {
            'client_id': utils.settings.GOOGLE_CLIENT_ID,
            'client_secret': utils.settings.GOOGLE_CLIENT_SECRET,
            'redirect_uris': [utils.settings.GOOGLE_REDIRECT_URI],
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
        }
    }
    scopes = utils.settings.GOOGLE_SCOPES
    redirect_uri = client_config['web']['redirect_uris'][0]

    code = request.args.get('code')
    if code:
        flow = Flow.from_client_config(client_config, scopes=scopes, redirect_uri=redirect_uri)
        try:
            flow.fetch_token(code=code, redirect_uri=redirect_uri)
            credentials = flow.credentials
            provider = app.calendar_manager.providers.get("Google Calendar")  # Access the provider instance from the app instance
            if provider:
                email = request.args.get('state')
                provider.store_credentials(email, credentials)
                return "Google authentication successful!"
            else:
                return "Google Calendar provider not found", 500
        except Exception as e:
            logger.error(f"Error fetching token: {e}")  # Use the imported logger
            return f"Error fetching token: {e}", 500
        else:
            return "Missing code parameter", 400

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
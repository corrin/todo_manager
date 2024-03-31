# meetings/meetings_routes.py
from your_google_oauth_library import (
    build_oauth_flow,
)  # Placeholder, replace with actual import
from flask import Blueprint, request, render_template, jsonify
from flask import redirect, url_for

from google_auth_oauthlib.flow import Flow
from virtual_assistant.utils.logger import logger
from utils.settings import Settings

meetings_bp = Blueprint("meetings", __name__, url_prefix="/meetings")


@meetings_bp.route("/google_authenticate", methods=["GET"])
def google_authenticate():
    # Handle the Google OAuth 2.0 callback
    client_config = {
        "web": {
            "client_id": Settings.GOOGLE_CLIENT_ID,
            "client_secret": Settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": Settings.GOOGLE_REDIRECT_URI,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    scopes = Settings.GOOGLE_SCOPES
    redirect_uri = client_config["web"]["redirect_uri"]

    logger.debug(f"Google Authenticate - Redirect URI: {redirect_uri}")
    logger.debug(f"Google Authenticate - Client Config: {client_config}")

    code = request.args.get("code")
    if code:
        flow = Flow.from_client_config(
            client_config, scopes=scopes, redirect_uri=redirect_uri
        )
        logger.debug(f"Google Authenticate - Flow: {flow}")
        try:
            flow.fetch_token(code=code)
            credentials = flow.credentials
            logger.debug(f"Google Authenticate - Credentials: {credentials}")
            provider = meetings_bp.calendar_manager.providers.get("google")
            if provider:
                email = request.args.get("state")
                provider.store_credentials(email, credentials)
                return "Google authentication successful!"
            else:
                return "Google Calendar provider not found", 500
        except Exception as e:
            logger.error(f"Error fetching token: {e}")  # Use the imported logger
            return f"Error fetching token: {e}", 500
    else:
        return "Missing code parameter", 400


@meetings_bp.route("/o365_authenticate")
def o365_authenticate():
    # Handle the Office 365 OAuth 2.0 callback
    client_config = {
        "web": {
            "client_id": Settings.O365_CLIENT_ID,
            "client_secret": Settings.O365_CLIENT_SECRET,
            "redirect_uris": [Settings.O365_REDIRECT_URI],
            "auth_uri": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "token_uri": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        }
    }
    scopes = Settings.O365_SCOPES
    redirect_uri = client_config["web"]["redirect_uris"][0]

    authorization_code = request.args.get("code")
    if authorization_code:
        flow = Flow.from_client_config(
            client_config, scopes=scopes, redirect_uri=redirect_uri
        )
        try:
            flow.fetch_token(code=authorization_code)
            credentials = flow.credentials
            email = get_email_from_credentials(credentials)
            store_credentials(email, credentials)
            return "Office 365 authentication successful!"
        except Exception as e:
            logger.error(f"Error fetching token: {e}")
            return f"Error fetching token: {e}", 500
    else:
        return "Missing authorization code", 400


@meetings_bp.route("/start_oauth")
def start_oauth():
    flow = (
        build_oauth_flow()
    )  # Build your OAuth flow here, specifics depend on the library you're using
    authorization_url, _ = flow.authorization_url(
        prompt="consent", access_type="offline"
    )

    return redirect(authorization_url)


@meetings_bp.route("/oauth_callback")
def oauth_callback():
    # Code to handle the callback, exchange the authorization code for tokens, and store them

    # After handling the callback, you might redirect to a simple page that closes the popup
    return redirect(url_for("meetings.close_popup"))


def get_email_from_credentials(credentials):
    # Extract the email address from the authenticated credentials
    # You may need to make an additional API call to retrieve the email address
    # Example: https://docs.microsoft.com/en-us/graph/api/user-get?view=graph-rest-1.0
    pass


def store_credentials(email, credentials):
    # Store the credentials for the email address
    # You can use a database or file storage to persist the credentials
    pass


@meetings_bp.route("/debug/<email>")
def debug_meetings(email):
    try:
        meetings = meetings_bp.calendar_manager.get_meetings(email)
        return render_template("meetings.html", meetings=meetings, email=email)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def init_app(calendar_manager):
    meetings_bp.calendar_manager = calendar_manager
    return meetings_bp

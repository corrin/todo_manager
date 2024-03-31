from flask import (
    Blueprint,
    request,
    redirect,
    url_for,
    session,
    render_template,
    jsonify,
)
from virtual_assistant.meetings.google_calendar_provider import GoogleCalendarProvider

# Import O365CalendarProvider similarly when ready
from virtual_assistant.utils.logger import logger

meetings_bp = Blueprint("meetings", __name__, url_prefix="/meetings")


@meetings_bp.route("/start_oauth/<provider>")
def start_oauth(provider):
    logger.info(f"Starting OAuth flow for provider: {provider}")
    if provider == "google":
        # Instantiate the provider class
        google_provider = GoogleCalendarProvider()
        # Call the authenticate method which should handle initiating OAuth flow if needed
        result = google_provider.authenticate(request.args.get("email"))
        if isinstance(result, tuple):
            # Assuming the authenticate method returns a tuple with provider name and authorization URL
            _, authorization_url = result
            return redirect(authorization_url)
        return redirect(
            url_for("meetings.debug_meetings", email=request.args.get("email"))
        )
    else:
        logger.error(f"OAuth flow for provider {provider} is not supported")
        return "Provider not supported", 400


@meetings_bp.route("/oauth_callback")
def oauth_callback():
    # This example assumes 'google' provider for simplicity
    provider = session.get("oauth_provider", "google")
    if provider == "google":
        google_provider = GoogleCalendarProvider()

        # Assuming the authorization response is handled within the provider
        credentials = google_provider.handle_oauth_callback(request.url)
        if credentials:
            user_email = session.get("user_email")  # Make sure this is set correctly
            google_provider.store_credentials(user_email, credentials)
            logger.info(f"New credentials stored for {user_email}")
            return redirect(url_for("meetings.debug_meetings", email=user_email))
        else:
            logger.error("Failed to obtain credentials from OAuth callback")
            return "Authentication failed", 500
    else:
        logger.error("Invalid provider in OAuth callback")
        return "Invalid provider", 400


@meetings_bp.route("/debug/<email>")
def debug_meetings(email):
    # Use the appropriate provider based on the email or another identifier
    google_provider = GoogleCalendarProvider()
    try:
        meetings = google_provider.get_meetings(email)
        return render_template("meetings.html", meetings=meetings, email=email)
    except Exception as e:
        logger.error(f"Error in debug_meetings for {email}: {e}")
        return jsonify({"error": str(e)}), 500


def init_app(calendar_manager):
    # Assuming calendar_manager is an object that may be used for additional setup or functionality
    meetings_bp.calendar_manager = calendar_manager
    logger.info("Meetings Blueprint initialized with calendar manager")
    return meetings_bp

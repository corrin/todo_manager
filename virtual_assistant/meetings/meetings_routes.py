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
from virtual_assistant.utils.logger import logger

meetings_bp = Blueprint("meetings", __name__, url_prefix="/meetings")


@meetings_bp.route("/google_authenticate")
def google_authenticate():
    """Handle Google OAuth callback."""
    google_provider = GoogleCalendarProvider()
    
    try:
        # Get the user's email from session
        email = session.get("user_email")
        if not email:
            logger.error("No user email in session")
            return redirect(url_for("login"))
        
        # Handle the callback
        credentials = google_provider.handle_oauth_callback(request.url)
        
        if credentials:
            # Store the credentials
            google_provider.store_credentials(email, credentials)
            logger.info(f"Google Calendar credentials stored for {email}")
            return redirect(url_for("main_app"))
        else:
            logger.error("Failed to get credentials from OAuth callback")
            return "Authentication failed", 500
            
    except Exception as e:
        logger.error(f"Error in Google OAuth callback: {e}")
        return f"Error: {str(e)}", 500


@meetings_bp.route("/debug/<email>")
def debug_meetings(email):
    """Debug endpoint to test calendar access."""
    google_provider = GoogleCalendarProvider()
    try:
        meetings = google_provider.get_meetings(email)
        return render_template("meetings.html", meetings=meetings, email=email)
    except Exception as e:
        logger.error(f"Error in debug_meetings for {email}: {e}")
        return jsonify({"error": str(e)}), 500


def init_app(calendar_manager):
    """Initialize the meetings blueprint."""
    meetings_bp.calendar_manager = calendar_manager
    logger.info("Meetings Blueprint initialized with calendar manager")
    return meetings_bp

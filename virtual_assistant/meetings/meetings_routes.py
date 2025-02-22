"""
Meetings Blueprint routes and functionality.
"""

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from virtual_assistant.meetings.google_calendar_provider import GoogleCalendarProvider
from virtual_assistant.utils.logger import logger

meetings_bp = Blueprint("meetings", __name__, url_prefix="/meetings")

providers = {
    "google": GoogleCalendarProvider,
    "o365": O365CalendarProvider,
}


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
        logger.info("Meetings for %s: %s", email, meetings)
        return render_template("meetings.html", meetings=meetings, email=email)
    except Exception as error:
        logger.error("Error in debug_meetings for %s: %s", email, error)
        return jsonify({"error": str(error)}), 500


@meetings_bp.route("/sync")
def sync_meetings():
    # Retrieve meetings for all accounts
    # Commented out because this is closer to pseudocode
    # Also this is gogole specfic and it should be getting hte provider
    # meetings_by_account = {}
    # for email in UserManager.get_email_addresses():
    #     meetings = google_provider.get_meetings(email)
    #     meetings_by_account[email] = meetings

    # # Split meetings into master and clone meetings for each account
    # master_meetings_by_account = {}
    # clone_meetings_by_account = {}
    # for email, meetings in meetings_by_account.items():
    #     master_meetings = []
    #     clone_meetings = []
    #     for meeting in meetings:
    #         if "(Clone)" in meeting["title"]:
    #             clone_meetings.append(meeting)
    #         else:
    #             master_meetings.append(meeting)
    #     master_meetings_by_account[email] = master_meetings
    #     clone_meetings_by_account[email] = clone_meetings

    # # Sync meetings across accounts
    # for email, master_meetings in master_meetings_by_account.items():
    #     for master_meeting in master_meetings:
    #         for other_email in UserManager.get_email_addresses():
    #             if other_email != email:
    #                 clone_meeting = find_clone_meeting(
    #                     master_meeting, clone_meetings_by_account[other_email]
    #                 )
    #                 if clone_meeting:
    #                     # Update clone meeting if details differ
    #                     if not is_same_meeting(master_meeting, clone_meeting):
    #                         update_meeting(other_email, clone_meeting, master_meeting)
    #                 else:
    #                     # Create new clone meeting
    #                     create_clone_meeting(other_email, master_meeting)

    # # Delete orphaned clone meetings
    # for email, clone_meetings in clone_meetings_by_account.items():
    #     for clone_meeting in clone_meetings:
    #         master_meeting = find_master_meeting(
    #             clone_meeting, master_meetings_by_account
    #         )
    #         if not master_meeting:
    #             delete_meeting(email, clone_meeting)

    # return "Meetings synced successfully"
    # # Delete orphaned clone meetings
    # for email, clone_meetings in clone_meetings_by_account.items():
    #     for clone_meeting in clone_meetings:
    #         master_meeting = find_master_meeting(
    #             clone_meeting, master_meetings_by_account
    #         )
    #         if not master_meeting:
    #             delete_meeting(email, clone_meeting)

    return "Meetings synced successfully"


def init_app(calendar_manager):
    """Initialize the meetings blueprint."""
    meetings_bp.calendar_manager = calendar_manager
    logger.info("Meetings Blueprint initialized with calendar manager")
    return meetings_bp

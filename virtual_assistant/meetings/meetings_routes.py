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

from virtual_assistant.database.user_manager import UserDataManager
from virtual_assistant.meetings.google_calendar_provider import GoogleCalendarProvider
from virtual_assistant.meetings.o365_calendar_provider import O365CalendarProvider
from virtual_assistant.utils.logger import logger

meetings_bp = Blueprint("meetings", __name__, url_prefix="/meetings")

providers = {
    "google": GoogleCalendarProvider,
    "o365": O365CalendarProvider,
}


@meetings_bp.route("/start_oauth/<provider>")
def start_oauth(provider):
    """
    Start the OAuth flow for the specified provider.

    Args:
        provider (str): The provider for which to start the OAuth flow.

    Returns:
        Response: Redirect to the provider's authorization URL or an error message.
    """
    logger.info("Starting OAuth flow for provider: %s", provider)
    if provider == "google":
        google_provider = GoogleCalendarProvider()
        result = google_provider.authenticate(request.args.get("email"))
        if isinstance(result, tuple):
            _, authorization_url = result
            return redirect(authorization_url)
        return redirect(
            url_for("meetings.debug_meetings", email=request.args.get("email"))
        )
    logger.error("OAuth flow for provider %s is not supported", provider)
    return "Provider not supported", 400


@meetings_bp.route("/google_authenticate")
@meetings_bp.route("/o365_authenticate")
def oauth_callback():
    """
    Handle the OAuth callback from the provider.

    Returns:
        Response: Redirect to the debug meetings page or an error message.
    """
    current_email = session.get("current_email")
    provider_key = UserDataManager.get_provider_for_email(current_email)
    logger.debug(f"Available providers: {providers}")
    logger.debug(f"Provider key: {provider_key}")
    provider_class = providers.get(provider_key)

    if not provider_class:
        logger.error("Invalid provider for the current email address")
        return f"Invalid provider for {current_email}", 400

    provider_instance = provider_class()
    credentials = provider_instance.retrieve_tokens(request.url)

    if not credentials:
        logger.error("Failed to obtain credentials from OAuth callback")
        return "Failed to obtain credentials", 500

    UserManager.save_credentials(current_email, credentials)
    logger.info("New credentials stored for %s", current_email)

    return "Authentication successful. Credentials stored.", 200


@meetings_bp.route("/debug/<email>")
def debug_meetings(email):
    """
    Debug endpoint to retrieve meetings for a given email.  Tests that we are
    logged in to the calendar.

    Args:
        email (str): The email address for which to retrieve meetings.

    Returns:
        Response: Rendered template with the meetings or an error message.
    """
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
    """
    Initialize the Meetings Blueprint with the given calendar manager.

    Args:
        calendar_manager: The calendar manager object.

    Returns:
        Blueprint: The initialized Meetings Blueprint.
    """
    meetings_bp.calendar_manager = calendar_manager
    logger.info("Meetings Blueprint initialized with calendar manager")
    return meetings_bp

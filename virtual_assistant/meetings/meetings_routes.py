"""
Meetings Blueprint routes and functionality.
"""

from datetime import datetime, timezone, UTC
from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from virtual_assistant.meetings.google_calendar_provider import GoogleCalendarProvider
from virtual_assistant.meetings.o365_calendar_provider import O365CalendarProvider
from virtual_assistant.utils.logger import logger
from virtual_assistant.utils.user_manager import UserManager
from virtual_assistant.database.calendar_account import CalendarAccount
from virtual_assistant.utils.settings import Settings

meetings_bp = Blueprint("meetings", __name__, url_prefix="/meetings")

providers = {
    "google": GoogleCalendarProvider,
    "o365": O365CalendarProvider,
}

@meetings_bp.route("/manage_calendar_accounts")
def manage_calendar_accounts():
    """Redirect to settings page for calendar management."""
    return redirect(url_for('settings'))

@meetings_bp.route("/remove_calendar_account", methods=["POST"])
def remove_calendar_account():
    """Remove a calendar account."""
    try:
        email = session.get("user_email")
        if not email:
            logger.error("No user email in session")
            return redirect(url_for("login"))
        
        provider_name = request.form.get("provider")
        calendar_email = request.form.get("email")
        
        if provider_name not in providers:
            flash("Invalid calendar provider.", "error")
            return redirect(url_for("settings"))
        
        # Remove from database first
        if calendar_email:
            logger.debug(f"Attempting to delete calendar account: {calendar_email} ({provider_name})")
            
            # Verify account exists before deletion
            existing = CalendarAccount.query.filter_by(
                calendar_email=calendar_email,
                provider=provider_name,
                app_user_email=email
            ).first()
            
            if existing:
                logger.debug(f"Found existing account to delete: {existing.calendar_email}")
                CalendarAccount.delete_by_email_and_provider(calendar_email, provider_name, email)
                logger.info(f"Successfully deleted calendar account from database: {calendar_email} ({provider_name})")
                
                # Verify deletion
                verify = CalendarAccount.query.filter_by(
                    calendar_email=calendar_email,
                    provider=provider_name,
                    app_user_email=email
                ).first()
                if verify:
                    logger.error(f"Account still exists after deletion attempt: {calendar_email}")
                    raise Exception("Failed to delete account from database")
                
                # Try to remove credentials if possible
                try:
                    provider = providers[provider_name]()
                    if hasattr(provider, 'remove_credentials'):
                        provider.remove_credentials(calendar_email)
                except Exception as cred_error:
                    logger.warning(f"Could not remove credentials: {cred_error}")
                    # Continue anyway as the database entry is removed
                
                flash(f"Successfully removed {provider_name} calendar account.", "success")
            else:
                logger.warning(f"Account not found for deletion: {calendar_email} ({provider_name})")
                flash("Calendar account not found.", "warning")
        else:
            flash("Calendar email not provided.", "error")
        
    except Exception as e:
        logger.error(f"Error removing calendar account: {e}")
        flash("An error occurred while removing the calendar account.", "error")
        db.session.rollback()
    
    return redirect(url_for("settings"))

@meetings_bp.route("/reauth_calendar_account")
def reauth_calendar_account():
    """Reauthorize a calendar account."""
    try:
        email = session.get("user_email")
        if not email:
            logger.error("No user email in session")
            return redirect(url_for("login"))
        
        provider_name = request.args.get("provider")
        if provider_name not in providers:
            flash("Invalid calendar provider.", "error")
            return redirect(url_for("meetings.manage_calendar_accounts"))
        
        provider = providers[provider_name]()
        _, auth_page = provider.authenticate(email)
        
        if auth_page:
            return auth_page
        
        flash("Account already authorized.", "info")
        return redirect(url_for("meetings.manage_calendar_accounts"))
        
    except Exception as e:
        logger.error(f"Error reauthorizing calendar account: {e}")
        flash("An error occurred while reauthorizing the calendar account.", "error")
        return redirect(url_for("meetings.manage_calendar_accounts"))


@meetings_bp.route("/authenticate_google_calendar")
def authenticate_google_calendar():
    """Initiate Google Calendar authentication."""
    try:
        logger.info("Starting Google Calendar authentication")
        email = session.get("user_email")
        logger.debug(f"User email from session: {email}")
        
        if not email:
            logger.error("No user email in session")
            return redirect(url_for("login"))
        
        provider = GoogleCalendarProvider()
        logger.debug("Calling provider.authenticate with force_new_auth=True")
        credentials, auth_url = provider.authenticate(email, force_new_auth=True)
        logger.debug(f"Got auth_url: {auth_url}")
        
        if auth_url:
            logger.info(f"Redirecting to Google auth URL: {auth_url}")
            return redirect(auth_url)
        
        logger.error("Failed to get authentication URL")
        flash("Unable to initiate Google Calendar authentication.", "error")
        return redirect(url_for("meetings.manage_calendar_accounts"))
        
    except Exception as e:
        logger.error(f"Error initiating Google Calendar auth: {e}", exc_info=True)
        flash("An error occurred while setting up Google Calendar.", "error")
        return redirect(url_for("meetings.manage_calendar_accounts"))

@meetings_bp.route("/authenticate_o365_calendar")
def authenticate_o365_calendar():
    """Initiate O365 Calendar authentication."""
    try:
        email = session.get("user_email")
        if not email:
            logger.error("No user email in session")
            return redirect(url_for("login"))
        
        provider = O365CalendarProvider()
        _, auth_url = provider.authenticate(email)
        
        if auth_url:
            return redirect(auth_url)
        
        flash("Account already authorized.", "info")
        return redirect(url_for("meetings.manage_calendar_accounts"))
        
    except Exception as e:
        logger.error(f"Error initiating O365 Calendar auth: {e}")
        flash("An error occurred while setting up Office 365 Calendar.", "error")
        return redirect(url_for("meetings.manage_calendar_accounts"))

@meetings_bp.route("/google_authenticate")
def google_authenticate():
    """Handle Google OAuth callback."""
    logger.debug(f"Google Calendar OAuth callback received for URL: {request.url}")
    
    google_provider = GoogleCalendarProvider()
    provider="google"
    try:
        app_user_email = session.get("user_email")
        if not app_user_email:
            logger.error("No user email in session")
            return redirect(url_for("login"))
        
        credentials = google_provider.handle_oauth_callback(request.url)
        if not credentials:
            raise ValueError("Failed to get credentials from OAuth callback")

        if credentials:
            # Get the actual Google account email
            calendar_account_email = google_provider.get_google_email(credentials)
            if not calendar_account_email:
                logger.error("Could not get Google account email")
                flash("Failed to get Google account information.", "error")
                return redirect(url_for("settings"))
            
            logger.info(f"Google Calendar credentials received for account: {calendar_account_email}")
            
            # Check if this Google account is already connected to this app user
            existing_account = CalendarAccount.query.filter_by(
                app_user_email=app_user_email,
                calendar_email=calendar_account_email,
                provider=provider
            ).first()
            
            if existing_account:
                flash(f"You have already connected this Google account.", "info")
                return redirect(url_for("settings"))
            
            # Store credentials under the Google account email
            # This will create or update the calendar account in the database
            if not google_provider.store_credentials(calendar_account_email, credentials):
                logger.error("Failed to store credentials")
                flash("Failed to store Google Calendar credentials.", "error")
                return redirect(url_for("settings"))
            
            flash(f"Google Calendar {calendar_account_email} connected successfully.", "success")
            return redirect(url_for("settings"))
        else:
            logger.error("Failed to get credentials from OAuth callback")
            flash("Failed to connect Google Calendar.", "error")
            return redirect(url_for("settings"))
            
    except Exception as e:
        logger.error(f"Error in Google OAuth callback: {e}", exc_info=True)
        flash(f"Error connecting Google Calendar: {str(e)}", "error")
        return redirect(url_for("settings"))


@meetings_bp.route("/o365_authenticate")
def o365_authenticate():
    """Handle O365 OAuth callback."""
    o365_provider = O365CalendarProvider()
    
    try:
        # Get the user's email from session
        email = session.get("user_email")
        if not email:
            logger.error("No user email in session")
            return redirect(url_for("login"))
        
        # Handle the callback
        credentials = o365_provider.retrieve_tokens(request.url)
        
        if credentials:
            # Store the credentials
            o365_provider.store_credentials(email, credentials)
            logger.info(f"O365 Calendar credentials stored for {email}")
            flash("Office 365 Calendar connected successfully.", "success")
            return redirect(url_for("meetings.manage_calendar_accounts"))
        else:
            logger.error("Failed to get O365 credentials from OAuth callback")
            flash("Failed to connect Office 365 Calendar.", "error")
            return redirect(url_for("meetings.manage_calendar_accounts"))
            
    except Exception as e:
        logger.error(f"Error in O365 OAuth callback: {e}")
        flash(f"Error connecting Office 365 Calendar: {str(e)}", "error")
        return redirect(url_for("meetings.manage_calendar_accounts"))

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
    meetings_by_account = {}
    for account in UserManager.get_accounts():
        provider = providers[account.provider]()
        meetings = provider.get_meetings(account.email)
        meetings_by_account[account.email] = meetings

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

    return "Meetings synced successfully"

@meetings_bp.route("/test")
def test_route():
    logger.info("Test route hit")
    return "Test route working"

def init_app(calendar_manager):
    """Initialize the meetings blueprint."""
    meetings_bp.calendar_manager = calendar_manager
    logger.info("Meetings Blueprint initialized with calendar manager")
    return meetings_bp

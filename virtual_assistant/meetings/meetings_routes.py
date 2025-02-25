"""
Meetings Blueprint routes and functionality.
"""

from datetime import datetime
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

meetings_bp = Blueprint("meetings", __name__, url_prefix="/meetings")

providers = {
    "google": GoogleCalendarProvider,
    "o365": O365CalendarProvider,
}

@meetings_bp.route("/manage_calendar_accounts")
def manage_calendar_accounts():
    """Display the calendar accounts management page."""
    try:
        email = session.get("user_email")
        if not email:
            logger.error("No user email in session")
            return redirect(url_for("login"))

        # Get all calendar accounts for the user
        calendar_accounts = []
        for provider_name, provider_class in providers.items():
            provider = provider_class()
            credentials = provider.get_credentials(email)
            if credentials:
                # Check if credentials are valid/active
                is_active = True
                if hasattr(credentials, 'expired'):
                    is_active = not credentials.expired
                
                # Get last sync time from database
                account = CalendarAccount.get_by_email_and_provider(email, provider_name)
                last_sync = account.last_sync if account else None
                
                calendar_accounts.append({
                    'provider': provider_name,
                    'email': email,
                    'last_sync': last_sync.strftime('%Y-%m-%d %H:%M:%S') if last_sync else None,
                    'is_active': is_active
                })
        
        return render_template('manage_calendar_accounts.html', calendar_accounts=calendar_accounts)
    
    except Exception as e:
        logger.error(f"Error in manage_calendar_accounts: {e}")
        flash("An error occurred while loading calendar accounts.", "error")
        return redirect(url_for("main_app"))

@meetings_bp.route("/remove_calendar_account", methods=["POST"])
def remove_calendar_account():
    """Remove a calendar account."""
    try:
        email = session.get("user_email")
        if not email:
            logger.error("No user email in session")
            return redirect(url_for("login"))
        
        provider_name = request.form.get("provider")
        if provider_name not in providers:
            flash("Invalid calendar provider.", "error")
            return redirect(url_for("meetings.manage_calendar_accounts"))
        
        # Remove credentials
        provider = providers[provider_name]()
        UserManager.remove_provider_folder(provider_name, email)
        
        # Remove from database
        CalendarAccount.delete_by_email_and_provider(email, provider_name)
        
        flash(f"Successfully removed {provider_name} calendar account.", "success")
        
    except Exception as e:
        logger.error(f"Error removing calendar account: {e}")
        flash("An error occurred while removing the calendar account.", "error")
    
    return redirect(url_for("meetings.manage_calendar_accounts"))

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
        email = session.get("user_email")
        if not email:
            logger.error("No user email in session")
            return redirect(url_for("login"))
        
        provider = GoogleCalendarProvider()
        _, auth_url = provider.authenticate(email)
        
        if auth_url:
            return redirect(auth_url)
        
        flash("Account already authorized.", "info")
        return redirect(url_for("meetings.manage_calendar_accounts"))
        
    except Exception as e:
        logger.error(f"Error initiating Google Calendar auth: {e}")
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
            flash("Google Calendar connected successfully.", "success")
            return redirect(url_for("meetings.manage_calendar_accounts"))
        else:
            logger.error("Failed to get credentials from OAuth callback")
            flash("Failed to connect Google Calendar.", "error")
            return redirect(url_for("meetings.manage_calendar_accounts"))
            
    except Exception as e:
        logger.error(f"Error in Google OAuth callback: {e}")
        flash(f"Error connecting Google Calendar: {str(e)}", "error")
        return redirect(url_for("meetings.manage_calendar_accounts"))


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

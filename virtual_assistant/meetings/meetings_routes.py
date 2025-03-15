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
from google.auth.exceptions import RefreshError
from asgiref.sync import async_to_sync
from virtual_assistant.meetings.google_calendar_provider import GoogleCalendarProvider
from virtual_assistant.meetings.o365_calendar_provider import O365CalendarProvider
from virtual_assistant.utils.logger import logger
from virtual_assistant.utils.user_manager import UserManager
from virtual_assistant.database.calendar_account import CalendarAccount
from virtual_assistant.utils.settings import Settings
from virtual_assistant.database.database import db
from functools import wraps
from google.auth.credentials import Credentials
from google.auth.transport.requests import Request
import requests

meetings_bp = Blueprint("meetings", __name__, url_prefix="/meetings")

providers = {
    "google": GoogleCalendarProvider,
    "o365": O365CalendarProvider,
}

def handle_token_expiry(account, error):
    """Handle token expiry by marking account for reauthorization."""
    if isinstance(error, RefreshError) or "token expired" in str(error).lower():
        logger.warning(f"Token expired for {account.calendar_email} ({account.provider})")
        # Mark account as needing reauth
        account.needs_reauth = True
        db.session.commit()
        return {
            'error': 'Token expired',
            'needs_reauth': True,
            'reauth_url': url_for(
                f'meetings.authenticate_{account.provider}_calendar',
                _external=True
            )
        }
    return {'error': str(error)}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        app_user_email = session.get('user_email')
        if not app_user_email:
            logger.error("No user email in session")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"error": "Not logged in"}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@meetings_bp.route("/manage_calendar_accounts")
@login_required
def manage_calendar_accounts():
    """Redirect to settings page for calendar management."""
    return redirect(url_for('settings'))

@meetings_bp.route("/set_primary_account", methods=["POST"])
def set_primary_account():
    """Set a calendar account as the primary account."""
    try:
        email = session.get("user_email")
        if not email:
            logger.error("No user email in session")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"success": False, "error": "Not logged in"}), 401
            return redirect(url_for("login"))
        
        provider = request.form.get("provider")
        calendar_email = request.form.get("email")
        
        if not provider or not calendar_email:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"success": False, "error": "Invalid request"}), 400
            flash("Invalid request. Provider and email are required.", "error")
            return render_template("error.html", error="Provider and email are required", title="Invalid Request")
        
        # Set the account as primary
        success = CalendarAccount.set_as_primary(calendar_email, provider, email)
        
        if success:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"success": True})
            flash(f"Set {calendar_email} as your primary calendar account.", "success")
            return redirect(url_for("settings"))
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"success": False, "error": "Failed to set primary account"}), 500
            flash("Failed to set primary calendar account.", "error")
            return render_template("error.html", error="Failed to set primary calendar account", title="Operation Failed")
            
    except Exception as e:
        logger.error(f"Error setting primary calendar account: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": False, "error": str(e)}), 500
        flash("An error occurred while setting the primary calendar account.", "error")
        return render_template("error.html", error=str(e), title="Operation Failed")

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
            return render_template("error.html", error="Invalid calendar provider", title="Invalid Request")
        
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
                
                # Check if this is the primary account
                was_primary = existing.is_primary
                
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
                
                # If this was the primary account, set another account as primary if one exists
                if was_primary:
                    remaining_accounts = CalendarAccount.get_accounts_for_user(email)
                    if remaining_accounts:
                        # Set the first remaining account as primary
                        first_account = remaining_accounts[0]
                        CalendarAccount.set_as_primary(
                            first_account.calendar_email,
                            first_account.provider,
                            email
                        )
                        logger.info(f"Set {first_account.calendar_email} as new primary account after deleting primary")
                
                flash(f"Successfully removed {provider_name} calendar account.", "success")
                return redirect(url_for("settings"))
            else:
                logger.warning(f"Account not found for deletion: {calendar_email} ({provider_name})")
                flash("Calendar account not found.", "warning")
                return render_template("error.html", error="Calendar account not found", title="Account Error")
        else:
            flash("Calendar email not provided.", "error")
            return render_template("error.html", error="Calendar email not provided", title="Invalid Request")
        
    except Exception as e:
        logger.error(f"Error removing calendar account: {e}")
        flash("An error occurred while removing the calendar account.", "error")
        db.session.rollback()
        return render_template("error.html", error=str(e), title="Operation Failed")

@meetings_bp.route("/reauth_calendar_account")
def reauth_calendar_account():
    """Reauthorize a calendar account."""
    try:
        app_user_email = session.get("user_email")
        if not app_user_email:
            logger.error("No user email in session")
            return redirect(url_for("login"))
        
        provider_name = request.args.get("provider")
        calendar_email = request.args.get("email")
        
        if provider_name not in providers:
            flash("Invalid calendar provider.", "error")
            return render_template("error.html", error="Invalid calendar provider", title="Invalid Request")
        
        if not calendar_email:
            flash("Calendar email not provided.", "error")
            return render_template("error.html", error="Calendar email not provided", title="Invalid Request")
        
        provider = providers[provider_name]()
        _, auth_url = provider.authenticate(calendar_email, app_user_email=app_user_email)
        
        if auth_url:
            # Instead of returning the auth_url, redirect to it
            return redirect(auth_url)
        
        flash("Account already authorized.", "info")
        return redirect(url_for("meetings.manage_calendar_accounts"))
        
    except Exception as e:
        logger.error(f"Error reauthorizing calendar account: {e}")
        flash("An error occurred while reauthorizing the calendar account.", "error")
        return render_template("error.html", error=str(e), title="Authentication Error")


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
@login_required
def google_authenticate():
    """Handle Google OAuth callback."""
    logger.debug(f"Google Calendar OAuth callback received for URL: {request.url}")
    
    google_provider = GoogleCalendarProvider()
    provider="google"
    
    app_user_email = session.get("user_email")
    if not app_user_email:
        logger.error("No user email in session")
        return redirect(url_for("login"))
    
    try:
        credentials = google_provider.handle_oauth_callback(request.url)
        if not credentials:
            raise ValueError("Failed to get credentials from OAuth callback")
    
        # Get the actual Google account email
        calendar_account_email = google_provider.get_google_email(credentials)
        
        logger.info(f"Google Calendar credentials received for account: {calendar_account_email}")
        
        # Check if this Google account is already connected to this app user
        existing_account = CalendarAccount.query.filter_by(
            app_user_email=app_user_email,
            calendar_email=calendar_account_email,
            provider=provider
        ).first()
        
        # Store/update credentials
        google_provider.store_credentials(calendar_account_email, credentials)
        
        # Verify credentials work by attempting to get meetings
        google_provider.get_meetings(calendar_account_email)
        
        # Update account status
        if existing_account:
            existing_account.needs_reauth = False
            existing_account.last_sync = datetime.now(timezone.utc)
            db.session.commit()
            flash(f"Successfully reauthorized Google Calendar for {calendar_account_email}.", "success")
        else:
            flash(f"Google Calendar {calendar_account_email} connected successfully.", "success")
        
        return redirect(url_for("meetings.sync_meetings"))
        
    except Exception as e:
        logger.error(f"❌ AUTH ERROR: Error in google_authenticate: {e}")
        flash(f"Failed to connect Google Calendar: {str(e)}", "error")
        return render_template("error.html", error=str(e), title="Authentication Error")


@meetings_bp.route("/o365_authenticate")
@login_required
def o365_authenticate():
    """Handle O365 OAuth callback."""
    logger.info(f"O365 authenticate route called with URL: {request.url}")
    
    o365_provider = O365CalendarProvider()
    
    app_user_email = session.get("user_email")
    if not app_user_email:
        logger.error("No user email in session")
        return redirect(url_for("login"))
    
    try:
        # Handle the callback synchronously by wrapping the async call
        calendar_email = async_to_sync(o365_provider.handle_oauth_callback)(request.url)
        if not calendar_email:
            logger.error("Failed to complete O365 authentication - no email returned")
            flash("Failed to connect Office 365 Calendar.", "error")
            return redirect(url_for("meetings.sync_meetings"))

        # Check if this account already exists
        existing_account = CalendarAccount.query.filter_by(
            app_user_email=app_user_email,
            calendar_email=calendar_email,
            provider='o365'
        ).first()
        
        # Update account status
        if existing_account:
            existing_account.needs_reauth = False
            existing_account.last_sync = datetime.now(timezone.utc)
            db.session.commit()
            flash(f"Successfully reauthorized Office 365 Calendar for {calendar_email}.", "success")
        else:
            flash("Office 365 Calendar connected successfully.", "success")
        
        return redirect(url_for("meetings.sync_meetings"))
        
    except Exception as e:
        logger.error(f"❌ AUTH ERROR in o365_authenticate: {str(e)}")
        flash(f"Failed to connect Office 365 Calendar: {str(e)}", "error")
        return render_template("error.html", error=str(e), title="Authentication Error")

@meetings_bp.route("/debug/<email>")
@login_required
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
@login_required
def sync_meetings():
    """Sync meetings from all connected calendars."""
    app_user_email = session.get('user_email')
    
    results = {
        'success': [],
        'errors': [],
        'needs_reauth': [],
        'status': 'success',
        'message': ''
    }
    
    accounts = CalendarAccount.get_accounts_for_user(app_user_email)
    if not accounts:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'No calendar accounts found'}), 404
        flash('No calendar accounts found', 'error')
        return render_template("error.html", error="No calendar accounts found", title="No Accounts")
    
    for account in accounts:
        if getattr(account, 'needs_reauth', False):
            # Skip accounts already marked as needing reauth
            logger.warning(f"⚠️ SKIPPING SYNC: Account {account.calendar_email} already needs reauthorization")
            results['needs_reauth'].append({
                'email': account.calendar_email,
                'provider': account.provider,
                'reason': 'Account previously marked as needing reauthorization',
                'reauth_url': url_for(
                    f'meetings.authenticate_{account.provider}_calendar',
                    _external=True
                )
            })
            results['status'] = 'needs_reauth'
            continue
                
        logger.info(f"Attempting to sync {account.provider} calendar for {account.calendar_email}")
        provider = providers[account.provider]()
        
        try:
            # Handle both sync and async get_meetings calls
            if account.provider == 'o365':
                meetings = async_to_sync(provider.get_meetings)(account.calendar_email)
            else:
                meetings = provider.get_meetings(account.calendar_email)
            
            # Only log as a success if we get here (no exceptions were thrown)
            success_info = {
                'email': account.calendar_email,
                'provider': account.provider,
                'meetings_count': len(meetings)
            }
            results['success'].append(success_info)
            
            if not meetings:
                logger.info(f"No meetings found for {account.calendar_email} (empty calendar)")
            else:
                logger.info(f"Successfully synced {len(meetings)} meetings for {account.calendar_email}")
                
        except Exception as e:
            error_msg = str(e)
            
            # Process authentication errors
            if ("token expired" in error_msg.lower() or 
                "authentication failed" in error_msg.lower() or 
                "invalid credentials" in error_msg.lower() or
                "missing refresh token" in error_msg.lower() or
                "auth" in error_msg.lower() and "fail" in error_msg.lower()):
                
                logger.warning(f"⚠️ AUTH ISSUE: Token expired or authentication failed for {account.calendar_email}: {error_msg}")
                
                # Mark account as needing reauth if not already done
                account.needs_reauth = True
                db.session.commit()
                
                # Check for specific missing fields
                required_fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'client_secret', 'scopes']
                missing_fields = [field for field in required_fields if not getattr(account, field)]
                
                reason = "Authentication failed"
                if "missing refresh token" in error_msg.lower():
                    reason = "Missing refresh token - try revoking app access in your Google account settings and reconnect"
                elif missing_fields:
                    reason = f"Missing required fields: {', '.join(missing_fields)}"
                elif "expired" in error_msg.lower():
                    reason = "Token has expired"
                    
                results['needs_reauth'].append({
                    'email': account.calendar_email,
                    'provider': account.provider,
                    'error': error_msg,
                    'reason': reason,
                    'reauth_url': url_for(
                        f'meetings.refresh_{account.provider}_calendar',
                        calendar_email=account.calendar_email,
                        _external=True
                    ) if account.refresh_token else url_for(
                        f'meetings.authenticate_{account.provider}_calendar',
                        _external=True
                    )
                })
                results['status'] = 'needs_reauth'
            else:
                logger.error(f"❌ ERROR: Error syncing {account.provider} calendar ({account.calendar_email}): {error_msg}")
                results['errors'].append({
                    'email': account.calendar_email,
                    'provider': account.provider,
                    'error': error_msg
                })
                results['status'] = 'error'
    
    # Set overall status message
    if results['needs_reauth']:
        reauth_details = [f"{a['email']} ({a['provider']}) - {a.get('reason', 'Unknown reason')}" 
                         for a in results['needs_reauth']]
        results['message'] = f"Some accounts need reauthorization:\n" + "\n".join(reauth_details)
        
    elif not results['success'] and results['errors']:
        results['message'] = 'All calendar syncs failed'
        
    elif results['errors']:
        results['message'] = 'Some calendar syncs failed'
        
    else:
        results['message'] = 'All calendars synced successfully'

    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(results)

    # For error cases in normal requests, show error page
    if results['status'] == 'error' or results['status'] == 'needs_reauth':
        return render_template(
            'error.html',
            error=results['message'],
            title="Calendar Sync Error",
            details=results
        )

    # For success cases, show meetings page
    return render_template(
        'meetings.html',
        sync_results=results,
        title="Calendar Sync Results"
    )

@meetings_bp.route("/test")
def test_route():
    logger.info("Test route hit")
    return "Test route working"

@meetings_bp.route("/refresh_google_calendar/<calendar_email>")
@login_required
def refresh_google_calendar(calendar_email):
    """Refresh Google Calendar token."""
    try:
        app_user_email = session.get("user_email")
        if not app_user_email:
            logger.error("No user email in session")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"error": "Not logged in"}), 401
            return redirect(url_for("login"))
            
        # Get the account
        account = CalendarAccount.get_by_email_provider_and_user(
            calendar_email, "google", app_user_email
        )
        if not account:
            logger.error(f"No Google calendar account found for {calendar_email}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"error": "Account not found"}), 404
            flash("Calendar account not found.", "error")
            return render_template("error.html", error="Calendar account not found", title="Account Error")
            
        # Try to refresh using existing refresh token
        provider = GoogleCalendarProvider()
        credentials = Credentials(
            token=account.token,
            refresh_token=account.refresh_token,
            token_uri=account.token_uri,
            client_id=account.client_id,
            client_secret=account.client_secret,
            scopes=account.scopes.split()
        )
        
        if not credentials.refresh_token:
            logger.error(f"No refresh token for {calendar_email}, need full reauth")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    "error": "No refresh token available",
                    "needs_full_auth": True,
                    "auth_url": url_for("meetings.authenticate_google_calendar", _external=True)
                }), 401
            return redirect(url_for("meetings.authenticate_google_calendar"))
            
        try:
            credentials.refresh(Request())
            provider.store_credentials(calendar_email, credentials)
            account.needs_reauth = False
            account.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"success": True})
            flash("Successfully refreshed Google Calendar access.", "success")
            return redirect(url_for("meetings.sync_meetings"))
            
        except Exception as e:
            logger.error(f"Error refreshing token for {calendar_email}: {e}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    "error": "Failed to refresh token",
                    "needs_full_auth": True,
                    "auth_url": url_for("meetings.authenticate_google_calendar", _external=True)
                }), 401
            return redirect(url_for("meetings.authenticate_google_calendar"))
            
    except Exception as e:
        logger.error(f"Error in refresh_google_calendar: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": str(e)}), 500
        flash("An error occurred while refreshing calendar access.", "error")
        return render_template("error.html", error=str(e), title="Refresh Error")

@meetings_bp.route("/refresh_o365_calendar/<calendar_email>")
@login_required
def refresh_o365_calendar(calendar_email):
    """Refresh O365 Calendar token."""
    try:
        app_user_email = session.get("user_email")
        if not app_user_email:
            logger.error("No user email in session")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"error": "Not logged in"}), 401
            return redirect(url_for("login"))
            
        # Get the account
        account = CalendarAccount.get_by_email_provider_and_user(
            calendar_email, "o365", app_user_email
        )
        if not account:
            logger.error(f"No O365 calendar account found for {calendar_email}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"error": "Account not found"}), 404
            flash("Calendar account not found.", "error")
            return render_template("error.html", error="Calendar account not found", title="Account Error")
            
        # Try to refresh using existing refresh token
        provider = O365CalendarProvider()
        if not account.refresh_token:
            logger.error(f"No refresh token for {calendar_email}, need full reauth")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    "error": "No refresh token available",
                    "needs_full_auth": True,
                    "auth_url": url_for("meetings.authenticate_o365_calendar", _external=True)
                }), 401
            return redirect(url_for("meetings.authenticate_o365_calendar"))
            
        try:
            # Use the O365 token endpoint to refresh
            token_url = f"{provider.authority}/oauth2/v2.0/token"
            data = {
                'client_id': account.client_id,
                'client_secret': account.client_secret,
                'refresh_token': account.refresh_token,
                'grant_type': 'refresh_token'
            }
            response = requests.post(token_url, data=data)
            if response.status_code == 200:
                new_tokens = response.json()
                credentials = {
                    'token': new_tokens['access_token'],
                    'refresh_token': new_tokens.get('refresh_token', account.refresh_token),
                    'token_uri': account.token_uri,
                    'client_id': account.client_id,
                    'client_secret': account.client_secret,
                    'scopes': account.scopes
                }
                provider.store_credentials(calendar_email, credentials)
                account.needs_reauth = False
                account.save()
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({"success": True})
                flash("Successfully refreshed Office 365 Calendar access.", "success")
                return redirect(url_for("meetings.sync_meetings"))
            else:
                logger.error(f"Failed to refresh O365 token: {response.text}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        "error": "Failed to refresh token",
                        "needs_full_auth": True,
                        "auth_url": url_for("meetings.authenticate_o365_calendar", _external=True)
                    }), 401
                return redirect(url_for("meetings.authenticate_o365_calendar"))
                
        except Exception as e:
            logger.error(f"Error refreshing token for {calendar_email}: {e}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    "error": "Failed to refresh token",
                    "needs_full_auth": True,
                    "auth_url": url_for("meetings.authenticate_o365_calendar", _external=True)
                }), 401
            return redirect(url_for("meetings.authenticate_o365_calendar"))
            
    except Exception as e:
        logger.error(f"Error in refresh_o365_calendar: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": str(e)}), 500
        flash("An error occurred while refreshing calendar access.", "error")
        return render_template("error.html", error=str(e), title="Refresh Error")

def init_app(calendar_manager):
    """Initialize the meetings blueprint."""
    meetings_bp.calendar_manager = calendar_manager
    logger.info("Meetings Blueprint initialized with calendar manager")
    return meetings_bp

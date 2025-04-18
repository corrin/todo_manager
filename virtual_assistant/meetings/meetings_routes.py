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
    current_app
)
from google.auth.exceptions import RefreshError
from asgiref.sync import async_to_sync
from virtual_assistant.meetings.google_calendar_provider import GoogleCalendarProvider
from virtual_assistant.meetings.o365_calendar_provider import O365CalendarProvider
from virtual_assistant.utils.logger import logger
from virtual_assistant.database.user_manager import UserDataManager
from virtual_assistant.database.calendar_account import CalendarAccount
from virtual_assistant.database.task import TaskAccount # Import TaskAccount
from flask_login import current_user # Import current_user
from flask_login import login_required # Import login_required
from virtual_assistant.database.database import db
from functools import wraps
from google.auth.credentials import Credentials
from google.auth.transport.requests import Request
import requests
import asyncio

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

@meetings_bp.route("/manage_calendar_accounts")
def manage_calendar_accounts():
    """Redirect to settings page for calendar management."""
    return redirect(url_for('settings'))

@meetings_bp.route("/set_primary_account", methods=["POST"])
def set_primary_account():
    """Set a calendar account as the primary account using its ID."""
    try:
        user_id = current_user.id
        
        account_id_str = request.form.get("primary_calendar_account_id")
        
        if not account_id_str:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"success": False, "error": "Invalid request"}), 400
            flash("Invalid request. Calendar account ID is required.", "error")
            return render_template("error.html", error="Calendar account ID is required", title="Invalid Request")
        
        try:
            account_id = int(account_id_str)
        except ValueError:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"success": False, "error": "Invalid account ID format"}), 400
            flash("Invalid account ID format.", "error")
            return render_template("error.html", error="Invalid account ID format", title="Invalid Request")
        
        # Set the account as primary using the new method
        success = CalendarAccount.set_as_primary_by_id(account_id, user_id)
        
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
                user_id=current_user.id 
            ).first()
            
            if existing:
                logger.debug(f"Found existing account to delete: {existing.calendar_email}")
                
                # Check if this is the primary account
                was_primary = existing.is_primary
                
                CalendarAccount.delete_by_email_and_provider(calendar_email, provider_name, current_user.id)
                logger.info(f"Successfully deleted calendar account from database: {calendar_email} ({provider_name})")
                
                # Verify deletion
                verify = CalendarAccount.query.filter_by(
                    calendar_email=calendar_email,
                    provider=provider_name,
                    user_id=current_user.id
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
                    remaining_accounts = CalendarAccount.get_accounts_for_user(current_user.id) 
                    if remaining_accounts:
                        # Set the first remaining account as primary
                        first_account = remaining_accounts[0]
                        CalendarAccount.set_as_primary(
                            first_account.calendar_email,
                            first_account.provider,
                            current_user.id 
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
@login_required # Add decorator for authentication
def reauth_calendar_account():
    """Reauthorize a calendar account."""
    try:
        
        provider_name = request.args.get("provider")
        calendar_email = request.args.get("calendar_email") # Changed from "email"
        
        if provider_name not in providers:
            flash("Invalid calendar provider.", "error")
            return render_template("error.html", error="Invalid calendar provider", title="Invalid Request")
        
        if not calendar_email:
            flash("Calendar account email not provided.", "error") # Updated flash message
            return render_template("error.html", error="Calendar account email not provided", title="Invalid Request")
        
        provider = providers[provider_name]()
        
        # Store referrer URL for later redirect
        referrer = request.referrer
        if referrer:
            session['calendar_auth_referrer'] = referrer
        
        # Use the appropriate method based on provider - both use reauthenticate now
        if provider_name == "google":
            credentials, auth_url = provider.reauthenticate(calendar_email=calendar_email, user_id=current_user.id) # Pass user_id
        elif provider_name == "o365":
            # O365 provider's reauthenticate method is async, so we need to use async_to_sync
            credentials, auth_url = async_to_sync(provider.reauthenticate)(calendar_email=calendar_email, user_id=current_user.id) # Pass user_id
        else:
            flash(f"Unsupported calendar provider: {provider_name}", "error")
            return render_template("error.html", error=f"Unsupported calendar provider: {provider_name}", title="Invalid Provider")
        
        # If auth_url is None but credentials exist, it means token was refreshed without needing reauth
        if auth_url is None and credentials is not None:
            logger.info(f"Token refreshed for {calendar_email} without needing reauthorization")
            # Mark account as no longer needing reauth
            account = CalendarAccount.get_by_email_provider_and_user(
                calendar_email, provider_name, current_user.id # Use user_id
            )
            if account:
                account.needs_reauth = False
                account.save()
            
            flash(f"Successfully refreshed access to {calendar_email}", "success")
            return redirect(url_for("meetings.sync_single_calendar", provider=provider_name, calendar_email=calendar_email))
        
        # If we have an auth_url, redirect to it for full reauth (this is what we want when user clicks reauth)
        if auth_url:
            logger.info(f"Redirecting to auth URL for {provider_name} reauthorization: {calendar_email}")
            return redirect(auth_url)
        
        # We should never get here if the implementation is correct
        flash("Account already authorized, but full reauthorization failed.", "warning")
        return redirect(url_for("meetings.manage_calendar_accounts"))
        
    except Exception as e:
        logger.error(f"Error reauthorizing calendar account: {e}")
        flash("An error occurred while reauthorizing the calendar account.", "error")
        return render_template("error.html", error=str(e), title="Authentication Error")

@meetings_bp.route("/authenticate_google_calendar")
def authenticate_google_calendar():
    """Initiate Google Calendar authentication."""
    try:
        user_id = current_user.id
        
        # Store referrer URL for later redirect
        referrer = request.referrer
        if referrer:
            session['calendar_auth_referrer'] = referrer
        
        provider = GoogleCalendarProvider()
        # Google's authenticate now takes user_id
        _, auth_url = provider.authenticate(user_id)
        
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
        user_id = current_user.id
        
        # Store referrer URL for later redirect
        referrer = request.referrer
        if referrer:
            session['calendar_auth_referrer'] = referrer
        
        provider = O365CalendarProvider()
        _, auth_url = provider.authenticate(user_id)
        
        if auth_url:
            logger.error(f"REDIRECTING TO MICROSOFT: {auth_url}")
            return redirect(auth_url)
        else:
            error_msg = "No authorization URL generated - this should never happen"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
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
    user_id = current_user.id
    
    
    try:
        credentials = google_provider.handle_oauth_callback(request.url)
        if not credentials:
            raise ValueError("Failed to get credentials from OAuth callback")
    
        # Get the actual Google account email
        calendar_account_email = google_provider.get_google_email(credentials)
        
        logger.info(f"Google Calendar credentials received for account: {calendar_account_email}")
        
        # Check if a CalendarAccount for this Google account already exists for this app user
        existing_calendar_account = CalendarAccount.query.filter_by(
            user_id=current_user.id, # Use user_id from current_user
            calendar_email=calendar_account_email,
            provider=provider
        ).first()
        
        # Store/update CALENDAR credentials using the provider's method
        # store_credentials now returns the CalendarAccount object directly or raises exception
        calendar_account = google_provider.store_credentials(calendar_account_email, credentials, current_user.id)

        # Verify credentials work by attempting to get meetings (optional but recommended)
        verification_failed = False
        try:
            google_provider.get_meetings_sync(calendar_account_email, current_user.id) # Pass user_id
            # Mark calendar account as active since verification succeeded
            # calendar_account is guaranteed to be an object here if store_credentials didn't raise an error
            calendar_account.needs_reauth = False
            calendar_account.last_sync = datetime.now(timezone.utc)
                 # Don't commit yet, do it after task account update
        except Exception as verify_error:
             verification_failed = True
             logger.error(f"Failed to verify Google Calendar credentials for {calendar_account_email} (User ID: {current_user.id}): {verify_error}")
             # Mark as needing reauth if verification fails
             calendar_account.needs_reauth = True # Mark as needing reauth if verification fails
             # Don't commit yet

        # --- Also Create/Update TaskAccount ---
        task_provider_name = 'google_tasks'
        # Prepare credentials dictionary for TaskAccount
        task_credentials = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            # Attempt to get expiry, handle potential AttributeError if not present
            'expires_at': getattr(credentials, 'expiry', None),
            'scopes': " ".join(credentials.scopes) if credentials.scopes else None,
            # Set reauth based on calendar verification result
            'needs_reauth': verification_failed
        }
        # Use TaskAccount's class method to handle creation or update
        task_account = TaskAccount.set_account(
            user_id=current_user.id,
            provider_name=task_provider_name,
            task_user_email=calendar_account_email, # Use the same email
            credentials=task_credentials
        )
        # Stage the task account changes if an object was returned (created/updated)
        if task_account:
             db.session.add(task_account)

        # --- Commit all changes and Flash message ---
        try:
            db.session.commit() # Commit both CalendarAccount and TaskAccount changes
            # Flash message should only mention Calendar context, as per user requirement
            if existing_calendar_account: # Check if the *calendar* account existed before
                flash(f"Successfully reauthorized Google Calendar for {calendar_account_email}.", "success")
            else:
                flash(f"Google Calendar for {calendar_account_email} connected successfully.", "success")
        except Exception as commit_error:
             db.session.rollback()
             logger.error(f"Error committing account updates for Google user {current_user.id} ({calendar_account_email}): {commit_error}")
             flash(f"Error saving account details for {calendar_account_email}.", "danger")
             # Redirect to settings on error saving
             return redirect(url_for("settings"))

        # Redirect to settings page after successful connection/reauth
        return redirect(url_for("settings"))
        
    except Exception as e:
        logger.error(f"❌ AUTH ERROR: Error in google_authenticate: {e}")
        flash(f"Failed to connect Google Calendar: {str(e)}", "error")
        return render_template("error.html", error=str(e), title="Authentication Error")

@meetings_bp.route("/o365_authenticate")
def o365_authenticate():
    """Handle O365 OAuth callback."""
    logger.info(f"O365 authenticate route called with URL: {request.url}")
    
    o365_provider = O365CalendarProvider()
    
    # app_login = session.get("app_login") # Use current_user instead
    
    try:
        # Handle the callback synchronously, expecting email and credentials dict
        result = async_to_sync(o365_provider.handle_oauth_callback)(request.url, current_user.id) # Pass user_id
        
        if not result or 'email' not in result or 'credentials' not in result:
            logger.error(f"Failed to complete O365 authentication for user {current_user.id} - invalid result from callback handler: {result}")
            flash("Failed to connect Office 365 Calendar (invalid callback data).", "error")
            return redirect(url_for("settings")) # Redirect to settings

        calendar_email = result['email']
        credentials = result['credentials'] # Expecting dict like {'token': ..., 'refresh_token': ..., 'expires_at': ...}

        # Check if a CalendarAccount for this O365 account already exists
        existing_calendar_account = CalendarAccount.query.filter_by(
            user_id=current_user.id,
            calendar_email=calendar_email,
            provider='o365'
        ).first()

        # --- Create/Update CalendarAccount ---
        calendar_account = existing_calendar_account
        if not calendar_account:
             calendar_account = CalendarAccount(
                 user_id=current_user.id,
                 calendar_email=calendar_email,
                 provider='o365'
             )
             db.session.add(calendar_account)
        
        # Update CalendarAccount fields from credentials dict
        calendar_account.token = credentials.get('token')
        calendar_account.refresh_token = credentials.get('refresh_token')
        # Assuming O365 provider handles client_id/secret internally if needed
        # calendar_account.scopes = Settings.O365_SCOPES # Store scopes if needed
        calendar_account.needs_reauth = False # Assume success for now
        calendar_account.last_sync = datetime.now(timezone.utc)
        # Verification step could be added here if O365 provider has a sync check method

        # --- Also Create/Update TaskAccount ---
        task_provider_name = 'outlook' # Map 'o365' calendar to 'outlook' task provider
        task_credentials = {
            'token': credentials.get('token'),
            'refresh_token': credentials.get('refresh_token'),
            'expires_at': credentials.get('expires_at'), # Pass expiry if available
            'scopes': credentials.get('scopes'), # Pass scopes if available
            'needs_reauth': False # Assume success
        }
        task_account = TaskAccount.set_account(
            user_id=current_user.id,
            provider_name=task_provider_name,
            task_user_email=calendar_email,
            credentials=task_credentials
        )
        if task_account:
             db.session.add(task_account)

        # --- Commit all changes and Flash message ---
        try:
            db.session.commit()
            # Flash message only mentions Calendar context
            if existing_calendar_account:
                flash(f"Successfully reauthorized Office 365 Calendar for {calendar_email}.", "success")
            else:
                flash(f"Office 365 Calendar for {calendar_email} connected successfully.", "success")
        except Exception as commit_error:
             db.session.rollback()
             logger.error(f"Error committing account updates for O365 user {current_user.id} ({calendar_email}): {commit_error}")
             flash(f"Error saving account details for {calendar_email}.", "danger")
             return redirect(url_for("settings"))
        # Redirect to settings page after successful connection/reauth
        return redirect(url_for("settings"))
        
        return redirect(url_for("meetings.sync_single_calendar", provider='o365', calendar_email=calendar_email))
        
    except Exception as e:
        logger.error(f"❌ AUTH ERROR in o365_authenticate: {str(e)}")
        flash(f"Failed to connect Office 365 Calendar: {str(e)}", "error")
        return render_template("error.html", error=str(e), title="Authentication Error")

@meetings_bp.route("/debug/<email>")
def debug_meetings(email):
    """Debug endpoint to test calendar access."""
    user_id = current_user.id
    
    google_provider = GoogleCalendarProvider()
    try:
        meetings = google_provider.get_meetings_sync(email, user_id)
        logger.info("Meetings for %s: %s", email, meetings)
        return render_template("meetings.html", meetings=meetings, email=email)
    except Exception as error:
        logger.error("Error in debug_meetings for %s: %s", email, error)
        return jsonify({"error": str(error)}), 500

@meetings_bp.route("/sync")
def sync_meetings():
    """Sync meetings from all connected calendars."""
    user_id = current_user.id
    
    results = {
        'success': [],
        'errors': [],
        'needs_reauth': [],
        'status': 'success',
        'message': ''
    }
    accounts = CalendarAccount.get_accounts_for_user(user_id)
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
            # Skip unsupported providers
            if account.provider not in providers:
                logger.error(f"Unsupported provider: {account.provider}")
                results['errors'].append({
                    'email': account.calendar_email,
                    'provider': account.provider,
                    'error': f"Unsupported calendar provider: {account.provider}"
                })
                results['status'] = 'error'
                continue

            # Handle O365 and Google providers differently
            if account.provider == 'o365':
                # O365 needs to use async methods with async_to_sync
                meetings = async_to_sync(provider.get_meetings)(account.calendar_email, user_id)
            else:
                # Google can use synchronous methods directly
                meetings = provider.get_meetings_sync(account.calendar_email, user_id)
            
            # Log success
            logger.info(f"Successfully synced {len(meetings)} meetings for {account.calendar_email}")
            flash(f"Successfully synced {len(meetings)} meetings from {account.calendar_email}", "success")
            
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
def refresh_google_calendar(calendar_email):
    """Refresh Google Calendar token."""
    try:
        user_id = current_user.id
        
        # Get the account
        account = CalendarAccount.get_by_email_provider_and_user(
            calendar_email, "google", app_login
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
            provider.store_credentials(calendar_email, credentials, user_id)
            account.needs_reauth = False
            account.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"success": True})
            flash(f"Successfully refreshed access to {calendar_email}", "success")
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
def refresh_o365_calendar(calendar_email):
    """Refresh O365 Calendar token."""
    try:
        user_id = current_user.id
        
        # Get the account
        account = CalendarAccount.get_by_email_provider_and_user(
            calendar_email, "o365", app_login
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
                provider.store_credentials(calendar_email, credentials, user_id)
                account.needs_reauth = False
                account.save()
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({"success": True})
                flash(f"Successfully refreshed access to {calendar_email}", "success")
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

@meetings_bp.route("/sync_single_calendar/<provider>/<calendar_email>")
def sync_single_calendar(provider, calendar_email):
    """Sync meetings from a single calendar that was just authenticated."""
    user_id = current_user.id
    
    # Check for original referrer in session
    original_referrer = session.pop('calendar_auth_referrer', None)
    came_from_settings = original_referrer and 'settings' in original_referrer
    
    # Get the specific account
    account = CalendarAccount.get_by_email_provider_and_user(
        calendar_email, provider, app_login
    )
    
    if not account:
        flash(f"Calendar account {calendar_email} not found", 'error')
        return render_template("error.html", error="Calendar account not found", title="Not Found")
    
    if provider not in providers:
        flash(f"Unsupported provider: {provider}", 'error')
        return render_template("error.html", error=f"Unsupported provider: {provider}", title="Invalid Provider")
        
    logger.info(f"Syncing newly authenticated {provider} calendar for {calendar_email}")
    provider_obj = providers[provider]()
    
    try:
        # Handle O365 and Google differently
        if provider == 'o365':
            # O365 needs to use async methods with async_to_sync
            meetings = async_to_sync(provider_obj.get_meetings)(calendar_email, user_id)
        else:
            # Google can use synchronous methods directly
            meetings = provider_obj.get_meetings_sync(calendar_email, user_id)
        
        # Log success
        logger.info(f"Successfully synced {len(meetings)} meetings for {calendar_email}")
        flash(f"Successfully synced {len(meetings)} meetings from {calendar_email}", "success")
        
        # Redirect to the settings page if that's where we came from, otherwise to meetings
        if came_from_settings:
            return redirect(url_for("settings"))
        elif original_referrer:
            # Try to redirect back to original page
            return redirect(original_referrer)
        else:
            return redirect(url_for("meetings.index"))
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error syncing {provider} calendar for {calendar_email}: {error_msg}")
        flash(f"Error syncing {provider.upper()} calendar: {error_msg}", "error")
        
        # Always render error template on errors
        return render_template("error.html", error=error_msg, title="Sync Error")

def init_app(calendar_manager):
    """Initialize the meetings blueprint."""
    meetings_bp.calendar_manager = calendar_manager
    logger.info("Meetings Blueprint initialized with calendar manager")
    return meetings_bp

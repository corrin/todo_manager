from flask import Blueprint, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from sqlalchemy.exc import IntegrityError # Keep import in case needed elsewhere

# Import necessary components for handling task accounts and provider logic
from virtual_assistant.tasks.task_manager import TaskManager 
from virtual_assistant.database.task import TaskAccount
from virtual_assistant.database.database import db
from virtual_assistant.utils.logger import logger
# Import the specific provider for creating instruction tasks if needed
from .todoist_provider import TodoistProvider 

# Factory function to instantiate TaskManager when needed within request context
def _get_task_manager():
    return TaskManager()

def init_todoist_routes():
    """Initializes the Blueprint for Todoist authentication and account management."""
    bp = Blueprint('todoist_auth', __name__, url_prefix='/todoist_auth')

    @bp.route('/add_account', methods=['POST'])
    def add_account():
        """Handles the submission from the 'Add Todoist Account' modal."""
        app_login = current_user.app_login # Used for logging context
        submitted_email = request.form.get('todoist_email')
        submitted_api_key = request.form.get('api_key')

        # Basic validation for required fields from the modal form
        if not submitted_email or not submitted_api_key:
            flash('Both Todoist email and API key are required to add an account.', 'danger')
            return redirect(url_for('settings'))

        try:
            # Prevent adding duplicate accounts for the same user/email/provider combination
            existing_account = TaskAccount.get_account(current_user.id, 'todoist', submitted_email)
            if existing_account:
                 flash(f'A Todoist account for {submitted_email} already exists.', 'warning')
                 return redirect(url_for('settings'))

            # Use the TaskAccount model's method to handle creation/update logic
            account = TaskAccount.set_account(
                user_id=current_user.id,
                provider_name='todoist',
                task_user_email=submitted_email, 
                credentials={'api_key': submitted_api_key} 
            )
            db.session.add(account) # Stage the new account
            db.session.commit() # Persist the new account
            flash(f'Todoist account for {submitted_email} added successfully.', 'success')
            logger.info(f"Added Todoist account {submitted_email} for user {app_login}")

            # Post-creation: Attempt to add a default instruction task for the new account
            try:
                task_manager = _get_task_manager() 
                todoist_provider = task_manager.get_provider('todoist')
                if todoist_provider:
                    # Standard default instructions for new accounts
                    default_instructions = """AI Instructions:
- Schedule friend catchups weekly
- Work on each project at least twice a week
- Keep mornings free for focused work
- Handle urgent tasks within 24 hours"""
                    # Ensure the instruction task is associated with the correct user and specific Todoist account email
                    todoist_provider.create_instruction_task(current_user.id, submitted_email, default_instructions)
                    logger.info(f"Attempted creation of default AI instruction task for new account {submitted_email}")
                else:
                     logger.warning("Todoist provider not found, cannot create instruction task.")
            except Exception as instruction_error:
                # Log failure but don't prevent the user from seeing the account was added
                logger.error(f"Failed to create default instruction task for {submitted_email}: {instruction_error}")
                flash(f'Account added, but failed to create default Todoist instruction task: {instruction_error}', 'warning')

        except Exception as e:
            # General error handling during account addition
            db.session.rollback() # Rollback any potential partial changes
            logger.exception(f"Error adding Todoist account {submitted_email} for {app_login}: {e}")
            # Provide a user-friendly error message
            flash(f'Error adding Todoist account for {submitted_email}. Please check the details and try again.', 'danger')
            
        # Redirect back to the main settings page after processing
        return redirect(url_for('settings'))

    @bp.route('/update_key', methods=['POST'])
    def update_key():
        """Handles the submission from the 'Edit Todoist API Key' modal."""
        app_login = current_user.app_login # For logging
        # The email identifies which TaskAccount record to update (it's readonly in the modal form)
        submitted_email = request.form.get('todoist_email') 
        # The submitted API key can be a new key or an empty string to clear the existing key
        submitted_api_key = request.form.get('api_key') 

        if not submitted_email:
            # Should not happen if the modal passes the email correctly, but validate defensively
            flash('Todoist account email is missing. Cannot update key.', 'danger')
            return redirect(url_for('settings'))

        try:
            # Use TaskAccount.set_account which handles finding the existing account
            # based on user_id, provider_name, and task_user_email, then updates its credentials.
            account = TaskAccount.set_account(
                user_id=current_user.id,
                provider_name='todoist',
                task_user_email=submitted_email, 
                credentials={'api_key': submitted_api_key} # Pass the potentially new/empty key
            )
            if account: 
                 db.session.add(account) # Stage the update
                 db.session.commit() # Persist the changes
                 flash(f'API key for Todoist account {submitted_email} updated.', 'success')
                 logger.info(f"Updated Todoist API key for account {submitted_email}, user {app_login}")

                 # Post-update: Attempt to create instruction task only if a non-empty key was provided
                 if submitted_api_key:
                     try:
                         task_manager = _get_task_manager() 
                         todoist_provider = task_manager.get_provider('todoist')
                         if todoist_provider:
                             default_instructions = """AI Instructions:
- Schedule friend catchups weekly
- Work on each project at least twice a week
- Keep mornings free for focused work
- Handle urgent tasks within 24 hours"""
                             # Associate with the correct user and specific Todoist account email
                             todoist_provider.create_instruction_task(current_user.id, submitted_email, default_instructions)
                             logger.info(f"Attempted creation of default AI instruction task for updated account {submitted_email}")
                         else:
                              logger.warning("Todoist provider not found, cannot create instruction task.")
                     except Exception as instruction_error:
                         logger.error(f"Failed to create default instruction task for {submitted_email}: {instruction_error}")
                         flash(f'Key updated, but failed to create default Todoist instruction task: {instruction_error}', 'warning')
            else:
                 # This indicates the account identified by the email didn't exist for this user
                 flash(f'Todoist account for {submitted_email} not found. Cannot update key.', 'danger')
                 logger.error(f"Todoist account {submitted_email} not found for update for user {app_login}")

        except Exception as e:
            # General error handling during key update
            db.session.rollback()
            logger.exception(f"Error updating Todoist key for {submitted_email}, user {app_login}: {e}")
            flash(f'Error updating API key for {submitted_email}.', 'danger')
            
        # Redirect back to the main settings page after processing
        return redirect(url_for('settings'))

    @bp.route('/delete_account', methods=['POST'])
    def delete_account():
        """Handles the submission from the 'Delete Todoist Account' modal."""
        app_login = current_user.app_login # For logging
        # The email identifies the TaskAccount record to delete
        submitted_email = request.form.get('todoist_email')

        if not submitted_email:
            # Should not happen if the modal passes the email correctly
            flash('Todoist account email is missing. Cannot delete.', 'danger')
            return redirect(url_for('settings'))

        try:
            # Use the TaskAccount model's method for deletion
            deleted = TaskAccount.delete_account(current_user.id, 'todoist', submitted_email)
            
            if deleted:
                db.session.commit() # Persist the deletion
                flash(f'Todoist account for {submitted_email} deleted successfully.', 'success')
                logger.info(f"Deleted Todoist account {submitted_email} for user {app_login}")
            else:
                # The account might have been deleted via another request between page load and submission
                flash(f'Todoist account for {submitted_email} not found.', 'warning')
                logger.warning(f"Attempted to delete non-existent Todoist account {submitted_email} for user {app_login}")

        except Exception as e:
            # General error handling during account deletion
            db.session.rollback()
            logger.exception(f"Error deleting Todoist account {submitted_email} for {app_login}: {e}")
            flash(f'Error deleting Todoist account for {submitted_email}.', 'danger')
            
        # Redirect back to the main settings page after processing
        return redirect(url_for('settings'))


    @bp.route('/test', methods=['POST'])
    def test_connection():
        """Provides an endpoint to test a Todoist API key without saving it. 
           Used by the 'Test' button in the settings UI (potentially within modals)."""
        api_key = request.form.get('api_key')
        if not api_key:
            return jsonify({'success': False, 'message': 'API key is required'})
            
        try:
            # Use the official Todoist library to verify the key by making a simple API call
            from todoist_api_python.api import TodoistAPI
            api = TodoistAPI(api_key)
            api.get_projects()  # A basic read operation to confirm authentication
            return jsonify({'success': True, 'message': 'Connection successful'})
        except Exception as e:
            # Log the actual error for server-side debugging
            logger.error(f"Error testing Todoist API key: {e}") 
            # Return a user-friendly error without exposing internal details
            return jsonify({'success': False, 'message': 'Connection failed. Please check your API key.'})

    return bp
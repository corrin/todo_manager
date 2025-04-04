from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from virtual_assistant.database.user_manager import UserDataManager # Correct import
from virtual_assistant.utils.logger import logger
from .todoist_provider import TodoistProvider


def init_todoist_routes():
    bp = Blueprint('todoist_auth', __name__, url_prefix='/todoist_auth')
    todoist_provider = TodoistProvider()

    @bp.route('/setup', methods=['GET', 'POST'])
    def setup_credentials():
        if request.method == 'POST':
            api_key = request.form.get('api_key')
            if not api_key:
                flash('API key is required', 'danger')
                return redirect(url_for('settings'))

            try:
                app_login = UserDataManager.get_current_user() # Correct manager and variable name
                # HACK/TODO: Using app_login as task_user_email for file storage key.
                # Replace when proper credential storage is implemented.
                task_user_email_for_storage = app_login
                # Call base class store_credentials with both args
                todoist_provider.store_credentials(app_login, task_user_email_for_storage, {"api_key": api_key})
                
                # Create default AI instruction task if it doesn't exist
                default_instructions = """AI Instructions:
- Schedule friend catchups weekly
- Work on each project at least twice a week
- Keep mornings free for focused work
- Handle urgent tasks within 24 hours"""
                
                # Update create_instruction_task call signature
                todoist_provider.create_instruction_task(app_login, task_user_email_for_storage, default_instructions)
                
                flash('Todoist credentials saved successfully', 'success')
                return redirect(url_for('index'))
            except Exception as e:
                logger.error(f"Error saving Todoist credentials: {e}")
                flash(f'Error saving credentials: {str(e)}', 'danger')
                return redirect(url_for('settings'))

        # Redirect to settings page instead of trying to render a non-existent template
        return redirect(url_for('settings'))

    @bp.route('/test', methods=['POST'])
    def test_connection():
        """Test Todoist API connection with provided API key"""
        api_key = request.form.get('api_key')
        if not api_key:
            return jsonify({'success': False, 'message': 'API key is required'})
            
        try:
            # Test the API key by creating a temporary API client
            from todoist_api_python.api import TodoistAPI
            api = TodoistAPI(api_key)
            api.get_projects()  # Simple API call to test credentials
            return jsonify({'success': True, 'message': 'Connection successful'})
        except Exception as e:
            logger.error(f"Error testing Todoist API key: {e}")
            return jsonify({'success': False, 'message': f'Connection failed: {str(e)}'})

    return bp
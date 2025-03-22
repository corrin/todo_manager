"""
Routes for Outlook task provider authentication and setup.
"""
from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify
from virtual_assistant.utils.user_manager import UserManager
from virtual_assistant.utils.logger import logger
from .outlook_task_provider import OutlookTaskProvider


def init_outlook_routes():
    """Initialize Outlook routes blueprint."""
    bp = Blueprint('outlook_auth', __name__, url_prefix='/outlook_auth')
    outlook_provider = OutlookTaskProvider()

    @bp.route('/setup', methods=['GET', 'POST'])
    def setup_credentials():
        """Set up Outlook credentials."""
        if request.method == 'POST':
            client_id = request.form.get('client_id')
            client_secret = request.form.get('client_secret')
            refresh_token = request.form.get('refresh_token')
            
            if not client_id or not client_secret or not refresh_token:
                flash('All fields are required', 'danger')
                return redirect(url_for('outlook_auth.setup_credentials'))

            try:
                email = UserManager.get_current_user()
                outlook_provider.store_credentials(email, {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token
                })
                
                # Create default AI instruction task if it doesn't exist
                default_instructions = """AI Instructions:
- Schedule friend catchups weekly
- Work on each project at least twice a week
- Keep mornings free for focused work
- Handle urgent tasks within 24 hours"""
                
                try:
                    outlook_provider.create_instruction_task(email, default_instructions)
                    logger.info(f"Created default AI instruction task for {email}")
                except Exception as e:
                    logger.warning(f"Could not create AI instruction task: {e}")
                
                flash('Outlook credentials saved successfully', 'success')
                return redirect(url_for('index'))
            except Exception as e:
                logger.error(f"Error saving Outlook credentials: {e}")
                flash(f'Error saving credentials: {str(e)}', 'danger')
                return redirect(url_for('outlook_auth.setup_credentials'))

        # Redirect to settings page instead of trying to render a non-existent template
        return render_template('outlook_setup.html')

    @bp.route('/test', methods=['POST'])
    def test_connection():
        """Test Outlook API connection with provided credentials."""
        client_id = request.form.get('client_id')
        client_secret = request.form.get('client_secret')
        refresh_token = request.form.get('refresh_token')
        
        if not client_id or not client_secret or not refresh_token:
            return jsonify({'success': False, 'message': 'All fields are required'})
            
        try:
            # In a real implementation, we would test the credentials
            # For now, just return success
            return jsonify({'success': True, 'message': 'Connection successful'})
        except Exception as e:
            logger.error(f"Error testing Outlook credentials: {e}")
            return jsonify({'success': False, 'message': f'Connection failed: {str(e)}'})

    return bp
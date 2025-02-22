from flask import Blueprint, request, render_template, redirect, url_for, flash
from virtual_assistant.utils.user_manager import UserManager
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
                flash('API key is required')
                return redirect(url_for('todoist_auth.setup_credentials'))

            try:
                email = UserManager.get_current_user()
                todoist_provider.store_credentials(email, {"api_key": api_key})
                
                # Create default AI instruction task if it doesn't exist
                default_instructions = """AI Instructions:
- Schedule friend catchups weekly
- Work on each project at least twice a week
- Keep mornings free for focused work
- Handle urgent tasks within 24 hours"""
                
                todoist_provider.create_instruction_task(email, default_instructions)
                
                flash('Todoist credentials saved successfully')
                return redirect(url_for('main_app'))
            except Exception as e:
                logger.error(f"Error saving Todoist credentials: {e}")
                flash('Error saving credentials')
                return redirect(url_for('todoist_auth.setup_credentials'))

        return render_template('todoist_setup.html')

    return bp
from flask import Blueprint, render_template, redirect, url_for, flash, request
from virtual_assistant.utils.user_manager import UserManager
from virtual_assistant.utils.logger import logger
from .sqlite_provider import SQLiteTaskProvider

def init_sqlite_routes():
    """Initialize routes for SQLite storage setup and task management."""
    bp = Blueprint('sqlite_auth', __name__, url_prefix='/sqlite_auth')
    sqlite_provider = SQLiteTaskProvider()

    @bp.route('/setup', methods=['GET'])
    def setup_storage():
        """Handle SQLite storage setup."""
        try:
            email = UserManager.get_current_user()
            
            # Try to initialize storage
            sqlite_provider.authenticate(email)
            
            # Create default AI instruction task
            default_instructions = """AI Instructions:
- Schedule friend catchups weekly
- Work on each project at least twice a week
- Keep mornings free for focused work
- Handle urgent tasks within 24 hours"""
            
            sqlite_provider.create_instruction_task(email, default_instructions)
            
            flash('SQLite storage initialized successfully')
            return redirect(url_for('main_app'))
        except Exception as e:
            logger.error(f"Error initializing SQLite storage: {e}")
            flash('Error initializing storage')
            return redirect(url_for('sqlite_auth.setup_storage'))

    @bp.route('/tasks', methods=['GET'])
    def show_tasks():
        """Show all tasks from SQLite storage."""
        try:
            email = UserManager.get_current_user()
            tasks = sqlite_provider.get_tasks(email)
            return render_template('sqlite_tasks.html', tasks=tasks)
        except Exception as e:
            logger.error(f"Error showing tasks: {e}")
            flash('Error showing tasks')
            return redirect(url_for('main_app'))

    @bp.route('/add_task', methods=['POST'])
    def add_task():
        """Add a new task to SQLite storage."""
        try:
            email = UserManager.get_current_user()
            title = request.form['title']
            description = request.form['description']
            
            sqlite_provider.create_task(email, title, description)
            
            flash('Task added successfully')
            return redirect(url_for('sqlite_auth.show_tasks'))
        except Exception as e:
            logger.error(f"Error adding task: {e}")
            flash('Error adding task')
            return redirect(url_for('sqlite_auth.show_tasks'))

    return bp
import os
import json
import threading
import asyncio
from flask import request, session, make_response, jsonify, flash, send_from_directory
from flask import Flask, render_template, redirect, url_for
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
from virtual_assistant.utils.settings import Settings
from virtual_assistant.utils.logger import logger

import jinja2

from virtual_assistant.tasks.task_manager import TaskManager
from virtual_assistant.tasks.task_provider import Task
from virtual_assistant.tasks.task_hierarchy import TaskHierarchy
from virtual_assistant.ai.ai_manager import AIManager
from virtual_assistant.ai.auth_routes import init_ai_routes
from virtual_assistant.tasks.todoist_routes import init_todoist_routes
from virtual_assistant.tasks.sqlite_routes import init_sqlite_routes
from virtual_assistant.tasks.task_routes import init_task_routes
from virtual_assistant.meetings.google_calendar_provider import GoogleCalendarProvider
from virtual_assistant.meetings.meetings_routes import init_app, providers
from virtual_assistant.database.database import Database
from virtual_assistant.database.database_routes import database_bp
from virtual_assistant.database.calendar_account import CalendarAccount
from virtual_assistant.auth.user_auth import setup_login_manager
from virtual_assistant.tasks.token_refresh import start_token_refresh_scheduler
from virtual_assistant.meetings.calendar_provider_factory import CalendarProviderFactory


def create_task_manager():
    # Factory function to create the task manager
    return TaskManager()


def create_ai_manager():
    # Factory function to create the AI manager
    return AIManager()


def create_calendar_provider():
    # Factory function to create the calendar provider
    calendar_provider = CalendarProviderFactory.get_provider("google")
    logger.debug("Calendar Provider created using factory")
    return calendar_provider


def create_app():
    app = Flask(__name__)
    
    # Configure SQLAlchemy
    app.config['SQLALCHEMY_DATABASE_URI'] = Settings.DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database
    Database.init_app(app)
    
    # Initialize Flask-Login
    setup_login_manager(app)

    # Initialize managers
    task_manager = create_task_manager()
    ai_manager = create_ai_manager()
    calendar_provider = create_calendar_provider()

    # Register blueprints
    app.register_blueprint(init_ai_routes(), url_prefix="/ai_auth")
    app.register_blueprint(init_todoist_routes(), url_prefix="/todoist_auth")
    app.register_blueprint(init_sqlite_routes(), url_prefix="/sqlite_auth")
    app.register_blueprint(init_task_routes())
    app.register_blueprint(init_app(calendar_provider), url_prefix="/meetings")
    app.register_blueprint(database_bp, url_prefix="/database")
    
    app.secret_key = Settings.FLASK_SECRET_KEY
    app.config['SERVER_NAME'] = Settings.SERVER_NAME

    template_dir = os.path.join(app.root_path, "assets")
    app.jinja_loader = jinja2.FileSystemLoader(template_dir)
    
    # Start the token refresh scheduler in a background thread
    def run_token_refresh_scheduler():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with app.app_context():
            loop.run_until_complete(start_token_refresh_scheduler())
    
    token_refresh_thread = threading.Thread(
        target=run_token_refresh_scheduler, 
        daemon=True
    )
    token_refresh_thread.start()
    logger.info("Started token refresh scheduler in background thread")

    @app.context_processor
    def inject_user():
        user_email = session.get('user_email')
        if not user_email:
            user_email = request.cookies.get('user_email')
        return dict(user_email=user_email, Settings=Settings)

    @app.errorhandler(Exception)
    def handle_error(e):
        logger.error(f"Unhandled exception: {str(e)}")
        return render_template('error.html', error=str(e)), 500

    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(
            os.path.join(app.root_path, 'assets'),
            'favicon.ico', mimetype='image/vnd.microsoft.icon'
        )

    return app


app = create_app()

@app.before_request
def load_user_from_cookie():
    user_email = request.cookies.get('user_email')
    if user_email and 'user_email' not in session:
        session['user_email'] = user_email


@app.route("/")
def index():
    # Check if the user is logged in
    if 'user_email' not in session:
        return redirect(url_for('login'))  # Redirect to login page

    user_email = session.get('user_email')
    return render_template('index.html', user_email=user_email)


@app.route('/settings', methods=['GET'])
def settings():
    # Check if the user is logged in
    if 'user_email' not in session:
        return redirect(url_for('login'))

    user_email = session.get('user_email')
    
    # Get calendar accounts data
    calendar_accounts = CalendarAccount.get_accounts_for_user(user_email)
    accounts_data = []
    
    for account in calendar_accounts:
        accounts_data.append({
            'provider': account.provider,
            'email': account.calendar_email,
            'last_sync': account.last_sync.strftime('%Y-%m-%d %H:%M:%S') if account.last_sync else None,
            'needs_reauth': account.needs_reauth,
            'is_primary': account.is_primary
        })
    
    # Load user configuration
    user_folder = os.path.join(Settings.USERS_FOLDER, user_email)
    config_file = os.path.join(user_folder, 'config.json')
    config = {}
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
        except Exception as e:
            logger.error(f"Error loading user config: {e}")
    
    # Check if Todoist API key exists
    todoist_api_key_exists = False
    task_manager = create_task_manager()
    todoist_provider = task_manager.get_provider('todoist')
    if todoist_provider:
        credentials = todoist_provider.get_credentials(user_email)
        if credentials and 'api_key' in credentials:
            todoist_api_key_exists = True

    return render_template(
        'settings.html',
        user_email=user_email,
        calendar_accounts=accounts_data,
        config=config,
        todoist_api_key_exists=todoist_api_key_exists
    )

@app.route('/settings', methods=['POST'])
def save_settings():
    if 'user_email' not in session:
        return redirect(url_for('login'))

    user_email = session.get('user_email')
    try:
        # Get form data
        task_provider = request.form.get('task_provider')
        ai_provider = request.form.get('ai_provider')
        openai_key = request.form.get('openai_key')
        grok_key = request.form.get('grok_key')
        todoist_api_key = request.form.get('api_key')

        # Save provider selections
        user_folder = os.path.join(Settings.USERS_FOLDER, user_email)
        config_file = os.path.join(user_folder, 'config.json')
        
        config = {
            'task_provider': task_provider,
            'ai_provider': ai_provider
        }
        
        # Save API keys if provided
        if openai_key:
            config['openai_key'] = openai_key
        if grok_key:
            config['grok_key'] = grok_key

        # Ensure user directory exists
        os.makedirs(user_folder, exist_ok=True)
        
        # Save configuration
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
            
        # Handle Todoist API key if provided
        if todoist_api_key:
            # Use the task manager to handle Todoist credentials
            task_manager = create_task_manager()
            todoist_provider = task_manager.get_provider('todoist')
            
            if todoist_provider:
                todoist_provider.store_credentials(user_email, {"api_key": todoist_api_key})
                
                # Create default AI instruction task if it doesn't exist
                default_instructions = """AI Instructions:
- Schedule friend catchups weekly
- Work on each project at least twice a week
- Keep mornings free for focused work
- Handle urgent tasks within 24 hours"""
                
                try:
                    todoist_provider.create_instruction_task(user_email, default_instructions)
                    logger.info(f"Created default AI instruction task for {user_email}")
                except Exception as e:
                    logger.warning(f"Could not create AI instruction task: {e}")
            
        # Get the action parameter
        action = request.form.get('action')
        
        flash('Configuration saved successfully', 'success')
        logger.info(f"Configuration updated for user {user_email}")
        
        # Check if user wants to return home after saving
        if action == 'save_and_return':
            return redirect(url_for('index'))
        
    except Exception as e:
        flash(f'Error saving configuration: {str(e)}', 'danger')
        logger.error(f"Error saving configuration for {user_email}: {e}")
    
    return redirect(url_for('settings'))


@app.route('/tasks')
def tasks():
    """Display the user's tasks from Todoist."""
    if 'user_email' not in session:
        return redirect(url_for('login'))

    user_email = session.get('user_email')
    task_manager = create_task_manager()
    
    try:
        # Try to authenticate with Todoist
        auth_results = task_manager.authenticate(user_email, provider_name='todoist')
        
        # If authentication is needed, redirect to the auth URL
        if 'todoist' in auth_results and auth_results['todoist']:
            provider_name, redirect_url = auth_results['todoist']
            return redirect_url
        
        # Get tasks from Todoist
        tasks = task_manager.get_tasks(user_email, provider_name='todoist')
        
        # Create a task hierarchy to organize tasks
        hierarchy = TaskHierarchy(tasks)
        flattened_tasks = hierarchy.get_flattened_tasks()
        
        return render_template('tasks.html', flattened_tasks=flattened_tasks)
    
    except Exception as e:
        logger.error(f"Error getting tasks: {e}")
        return render_template('tasks.html', error=str(e))


@app.route('/sync_todoist')
def sync_todoist():
    """Sync Todoist tasks."""
    if 'user_email' not in session:
        return redirect(url_for('login'))

    user_email = session.get('user_email')
    task_manager = create_task_manager()
    
    try:
        # Try to authenticate with Todoist
        auth_results = task_manager.authenticate(user_email, provider_name='todoist')
        
        # If authentication is needed, redirect to the auth URL
        if 'todoist' in auth_results and auth_results['todoist']:
            provider_name, redirect_url = auth_results['todoist']
            return redirect_url
        
        # Get tasks from Todoist to refresh the cache
        tasks = task_manager.get_tasks(user_email, provider_name='todoist')
        
        # Create a task hierarchy to get a better count of tasks
        hierarchy = TaskHierarchy(tasks)
        flattened_tasks = hierarchy.get_flattened_tasks()
        
        flash(f'Successfully synced {len(tasks)} Todoist tasks', 'success')
        logger.info(f"Successfully synced {len(tasks)} Todoist tasks for {user_email}")
        
        # Redirect to the tasks page to show the synced tasks
        return redirect(url_for('tasks'))
    
    except Exception as e:
        logger.error(f"Error syncing Todoist tasks: {e}")
        flash(f'Error syncing Todoist tasks: {str(e)}', 'error')
        return redirect(url_for('tasks'))


@app.route('/tasks/<task_id>/status', methods=['POST'])
def update_task_status(task_id):
    """Update a task's status (completed/active)."""
    if 'user_email' not in session:
        return redirect(url_for('login'))

    user_email = session.get('user_email')
    status = request.form.get('status')
    
    if not status:
        flash('Status is required', 'danger')
        return redirect(url_for('tasks'))
    
    task_manager = create_task_manager()
    
    try:
        task_manager.update_task_status(user_email, task_id, status, provider_name='todoist')
        flash(f'Task status updated to {status}', 'success')
    except Exception as e:
        logger.error(f"Error updating task status: {e}")
        flash(f'Error updating task status: {str(e)}', 'danger')
    
    return redirect(url_for('tasks'))


@app.route("/logout")
def logout():
    session.pop('user_email', None)
    response = make_response(redirect(url_for('login')))
    response.delete_cookie('user_email')
    return response


@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        logger.info(f"Google Client ID being used: {Settings.GOOGLE_CLIENT_ID}")
    
    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email')
        
        if email:
            # Create user folder if it doesn't exist
            user_folder = os.path.join(Settings.USERS_FOLDER, email)
            if not os.path.exists(user_folder):
                os.makedirs(user_folder)
                logger.info(f"Created user folder for {email}")

            # Set both cookie and session
            response = make_response(jsonify({'success': True}))
            response.set_cookie('user_email', email)
            session['user_email'] = email
            return response
        
        return jsonify({'success': False, 'error': 'Email required'}), 400
        
    return render_template('login.html')


# This allows the file to work both in development and production
if __name__ == '__main__':
    # Development server
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)

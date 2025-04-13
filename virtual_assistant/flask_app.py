import os
import json
import threading
import asyncio
from flask import request, make_response, jsonify, flash, send_from_directory
from flask import Flask, render_template, redirect, url_for
from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError # Keep for potential use elsewhere

# Load environment variables
load_dotenv()
from virtual_assistant.utils.settings import Settings
from virtual_assistant.utils.logger import logger

import jinja2

# Import necessary components from other modules
from virtual_assistant.tasks.task_manager import TaskManager # Needed for create_task_manager factory
from virtual_assistant.ai.ai_manager import AIManager # Needed for create_ai_manager factory
from virtual_assistant.ai.auth_routes import init_ai_routes
from virtual_assistant.tasks.todoist_routes import init_todoist_routes
from virtual_assistant.tasks.task_routes import init_task_routes
from virtual_assistant.schedule.schedule_routes import init_schedule_routes
from virtual_assistant.meetings.meetings_routes import init_app as init_meetings_app # Renamed to avoid conflict
from virtual_assistant.database.database import Database, db
from virtual_assistant.database.database_routes import database_bp
from virtual_assistant.database.calendar_account import CalendarAccount
from virtual_assistant.database.user import User
from virtual_assistant.database.task import TaskAccount # Needed for settings GET route
from virtual_assistant.auth.user_auth import setup_login_manager
from virtual_assistant.tasks.token_refresh import start_token_refresh_scheduler
from virtual_assistant.meetings.calendar_provider_factory import CalendarProviderFactory
from flask_login import login_user, logout_user, login_required, current_user


# --- Factory Functions ---
# These create instances when needed, promoting better separation

def create_task_manager():
    return TaskManager()

def create_ai_manager():
    return AIManager()

def create_calendar_provider():
    # Consider making the provider type configurable if needed later
    calendar_provider = CalendarProviderFactory.get_provider("google") 
    logger.debug("Calendar Provider created using factory")
    return calendar_provider

# --- App Creation ---

def create_app():
    app = Flask(__name__)
    
    # --- Configuration ---
    app.config['SQLALCHEMY_DATABASE_URI'] = Settings.DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.secret_key = Settings.FLASK_SECRET_KEY
    # SERVER_NAME might be needed for url_for generation in background tasks or emails
    app.config['SERVER_NAME'] = Settings.SERVER_NAME 

    # --- Initialization ---
    Database.init_app(app)
    setup_login_manager(app)

    # --- Blueprints ---
    app.register_blueprint(init_ai_routes(), url_prefix="/ai_auth")
    app.register_blueprint(init_todoist_routes(), url_prefix="/todoist_auth")
    app.register_blueprint(init_task_routes())
    app.register_blueprint(init_schedule_routes())  # This now registers API endpoints at /api/schedule
    # Pass the factory function to init_app for meetings
    app.register_blueprint(init_meetings_app(create_calendar_provider), url_prefix="/meetings")
    app.register_blueprint(database_bp, url_prefix="/database")
    
    # --- Template and Static Files ---
    template_dir = os.path.join(app.root_path, "templates")
    app.jinja_loader = jinja2.FileSystemLoader(template_dir)
    app.static_folder = os.path.join(app.root_path, "static")
    app.static_url_path = "/static"
    
    # --- Background Scheduler ---
    def run_token_refresh_scheduler():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with app.app_context(): 
            loop.run_until_complete(start_token_refresh_scheduler())
    
    token_refresh_thread = threading.Thread(
        target=run_token_refresh_scheduler, 
        daemon=True
    )
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        token_refresh_thread.start()
        logger.info("Started token refresh scheduler in background thread")
    else:
        logger.info("Skipping token refresh scheduler start (not main Werkzeug process)")

    # --- Error Handling ---
    @app.errorhandler(Exception)
    def handle_error(e):
        logger.exception(f"Unhandled exception: {str(e)}") 
        error_message = str(e) if app.debug else "An unexpected error occurred."
        # Rollback session in case of error during request handling
        db.session.rollback() 
        return render_template('error.html', error=error_message), 500

    # --- Favicon Route ---
    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(
            os.path.join(app.root_path, 'static'),
            'favicon.ico', mimetype='image/vnd.microsoft.icon'
        )
        
    return app

# --- Create App Instance ---
app = create_app()

# --- Core Routes ---

@app.route("/")
@login_required 
def index():
    """Displays the main application page for logged-in users."""
    return render_template('index.html', user=current_user)

@app.route("/new-user")
def new_user():
    """Displays the welcome page for new or logged-out users."""
    return render_template('new_user.html')

@app.route('/settings', methods=['GET'])
@login_required
def settings():
    """Displays the settings page, fetching necessary account information."""
    app_login = current_user.app_login 
    
    # --- Get Calendar Accounts ---
    # Fetch CalendarAccount records directly for the calendar section
    calendar_accounts = CalendarAccount.query.filter_by(user_id=current_user.id).order_by(CalendarAccount.calendar_email).all()
    # Prepare data for template display if needed (or pass objects directly if template handles it)
    calendar_accounts_data_for_template = []
    for account in calendar_accounts:
        calendar_accounts_data_for_template.append({
            'id': account.id, # Pass ID if needed by template logic (e.g., modals)
            'provider': account.provider,
            'email': account.calendar_email, # Use the correct email field
            'last_sync': account.last_sync.strftime('%Y-%m-%d %H:%M:%S') if account.last_sync else None,
            'needs_reauth': account.needs_reauth,
            'calendar_is_primary': account.is_primary # This is for the CALENDAR primary
        })

    # --- Get Task Accounts ---
    # Fetch ALL TaskAccount records (Todoist, Google, O365) for the task provider section
    task_accounts_db = TaskAccount.query.filter_by(user_id=current_user.id).order_by(TaskAccount.provider_name, TaskAccount.task_user_email).all()
    # Prepare task account data for template
    task_accounts_data_for_template = []
    for account in task_accounts_db:
        task_accounts_data_for_template.append({
            'id': account.id,
            'provider_name': account.provider_name,
            'task_user_email': account.task_user_email,
            'api_key': bool(account.api_key), # Pass boolean indicating if key is set
            'token': bool(account.token), # Pass boolean indicating if token is set
            'needs_reauth': account.needs_reauth,
            'task_is_primary': account.is_primary # This is for the TASK primary
        })

    # Pass the separate lists to the template
    return render_template(
        'settings.html',
        user=current_user,
        calendar_accounts=calendar_accounts_data_for_template, # Pass calendar-specific data/objects
        task_accounts=task_accounts_data_for_template # Pass transformed task data
    )

@app.route('/save_general_settings', methods=['POST'])
@login_required 
def save_general_settings():
    """Saves general application settings (AI provider, API keys, etc.)."""
    app_login = current_user.app_login 
    try:
        # Update general User model fields from form (AI provider, API keys, AI instructions)
        current_user.ai_provider = request.form.get('ai_provider', current_user.ai_provider)
        
        # Only update keys if non-empty value is provided in the form
        openai_key_form = request.form.get('openai_key')
        grok_key_form = request.form.get('grok_key')
        
        # Update only if the form field exists and has a value (protects against accidental clearing)
        if 'openai_key' in request.form and openai_key_form:
             current_user.openai_key = openai_key_form
        if 'grok_key' in request.form and grok_key_form:
             current_user.grok_key = grok_key_form
             # Always update AI instructions (can be empty to clear)
             current_user.ai_instructions = request.form.get('ai_instructions', '')
             
             # Update schedule slot duration
             slot_duration = request.form.get('schedule_slot_duration')
             if slot_duration in ['30', '60', '120']:
                 current_user.schedule_slot_duration = int(slot_duration)
             
        
        db.session.add(current_user) # Stage user changes
        db.session.commit() # Commit general settings changes
        
        flash('General settings saved successfully.', 'success')
        logger.info(f"General settings updated for user {app_login}")

    except Exception as e:
        db.session.rollback() 
        logger.exception(f"Error saving general settings for {app_login}: {e}") 
        flash(f'Error saving general settings: {str(e)}', 'danger')

    # Always redirect back to settings page
    return redirect(url_for('settings')) 

@app.route("/logout")
@login_required 
def logout():
    """Logs the user out."""
    logout_user()
    flash('You have been successfully logged out.', 'info') 
    response = make_response(redirect(url_for('new_user')))
    return response

@app.route("/login", methods=['GET', 'POST'])
def login():
    """Handles user login (GET displays form, POST processes credentials)."""
    if request.method == 'GET':
        # Pass settings needed by the login template (e.g., Google Client ID)
        return render_template('login.html', Settings=Settings) 
    
    # POST request handling
    data = request.get_json()
    if not data or 'email' not in data:
         return jsonify({'success': False, 'error': 'Email required'}), 400
         
    app_login = data.get('email') 
    
    try:
        user = User.query.filter_by(app_login=app_login).first()
        
        if not user:
            user = User(app_login=app_login) 
            db.session.add(user)             
            db.session.commit()              
            logger.info(f"Created new user: {app_login}")
        else:
            logger.info(f"Found existing user: {app_login}")

        login_user(user) # Handles session creation via Flask-Login
        return jsonify({'success': True})

    except Exception as e:
         db.session.rollback()
         logger.exception(f"Error during login for {app_login}: {e}")
         return jsonify({'success': False, 'error': 'An internal error occurred during login.'}), 500


# --- Main Execution ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    # Use debug=True based on environment variable for auto-reloading etc.
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG') == '1')

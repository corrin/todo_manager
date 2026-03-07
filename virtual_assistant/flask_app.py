import os
import json
import threading
import asyncio
from flask import request, make_response, jsonify, flash, send_from_directory
from flask import Flask, render_template, redirect, url_for
from flask_migrate import Migrate
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
from virtual_assistant.database.external_account import ExternalAccount
from virtual_assistant.database.user import User
from virtual_assistant.auth.user_auth import setup_login_manager
from virtual_assistant.tasks.token_refresh import start_token_refresh_scheduler
from virtual_assistant.meetings.calendar_provider_factory import CalendarProviderFactory
from flask_login import login_user, logout_user, login_required, current_user, LoginManager


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
    migrate = Migrate(app, db)
    login_manager = setup_login_manager(app)
    
    # Global auth check - require login for all routes by default
    @app.before_request
    def require_login():
        # List of endpoints that don't require auth
        public_endpoints = [
            'login',
            'new_user',
            'about',
            'static',  # Allow static files
            'favicon'  # Allow favicon
        ]
        
        # Skip auth check for public endpoints
        if request.endpoint in public_endpoints:
            return
            
        # Skip auth check if user is already authenticated
        if current_user.is_authenticated:
            return
            
        # Otherwise redirect to login
        return redirect(url_for('login', next=request.path))

    # --- Blueprints ---
    app.register_blueprint(init_ai_routes(), url_prefix="/ai_auth")
    app.register_blueprint(init_todoist_routes(), url_prefix="/todoist_auth")
    app.register_blueprint(init_task_routes())  # Register comprehensive task routes
    app.register_blueprint(init_schedule_routes())  # This now registers API endpoints at /api/schedule
    # Pass the factory function to init_app for meetings
    app.register_blueprint(init_meetings_app(create_calendar_provider), url_prefix="/meetings")
    app.register_blueprint(database_bp, url_prefix="/database")

    from virtual_assistant.chat.chat_routes import chat_bp
    app.register_blueprint(chat_bp)
    
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
    """Redirect to chat page."""
    return redirect(url_for('chat_page'))

@app.route("/chat")
@login_required
def chat_page():
    """Displays the main chat interface."""
    return render_template('chat.html', user=current_user)

@app.route("/new-user")
def new_user():
    """Displays the welcome page for new or logged-out users."""
    return render_template('new_user.html')

@app.route("/about")
def about():
    """Displays the about page (no login required)."""
    return render_template('about.html')

@app.route('/settings', methods=['GET'])
@login_required
def settings():
    """Displays the settings page, fetching necessary account information."""
    app_login = current_user.app_login

    all_ext_accounts = ExternalAccount.query.filter_by(
        user_id=current_user.id
    ).order_by(ExternalAccount.provider, ExternalAccount.external_email).all()

    external_accounts = []
    for ext_account in all_ext_accounts:
        external_accounts.append({
            'id': ext_account.id,
            'provider': ext_account.provider,
            'email': ext_account.external_email,
            'has_calendar': ext_account.use_for_calendar,
            'has_tasks': ext_account.use_for_tasks,
            'calendar_is_primary': ext_account.is_primary_calendar,
            'task_is_primary': ext_account.is_primary_tasks,
            'api_key': bool(ext_account.api_key),
            'token': bool(ext_account.token),
            'needs_reauth': ext_account.needs_reauth,
            'last_sync': ext_account.last_sync.strftime('%Y-%m-%d %H:%M:%S') if ext_account.last_sync else None,
        })

    return render_template(
        'settings.html',
        user=current_user,
        external_accounts=external_accounts
    )

@app.route('/save_general_settings', methods=['POST'])
@login_required 
def save_general_settings():
    """Saves general application settings (AI provider, API keys, etc.)."""
    app_login = current_user.app_login 
    try:
        # Update general User model fields from form (API keys, AI instructions)
        # Only update keys if non-empty value is provided in the form
        ai_api_key_form = request.form.get('ai_api_key')

        # Update only if the form field exists and has a value (protects against accidental clearing)
        if 'ai_api_key' in request.form and ai_api_key_form:
             current_user.ai_api_key = ai_api_key_form

        # Always update AI instructions (can be empty to clear)
        current_user.ai_instructions = request.form.get('ai_instructions', '')

        # Update LLM model
        llm_model = request.form.get('llm_model')
        if llm_model:
            current_user.llm_model = llm_model

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

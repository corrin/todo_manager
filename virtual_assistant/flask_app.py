import os
import json
from flask import request, session, make_response, jsonify, flash
from flask import Flask, render_template, redirect, url_for
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
from virtual_assistant.utils.settings import Settings
from virtual_assistant.utils.logger import logger

import jinja2

from tasks.task_manager import TaskManager
from ai.ai_manager import AIManager
from ai.auth_routes import init_ai_routes
from tasks.todoist_routes import init_todoist_routes
from tasks.sqlite_routes import init_sqlite_routes
from meetings.google_calendar_provider import GoogleCalendarProvider
from meetings.meetings_routes import init_app


def create_task_manager():
    # Factory function to create the task manager
    return TaskManager()


def create_ai_manager():
    # Factory function to create the AI manager
    return AIManager()


def create_calendar_provider():
    # Factory function to create the calendar provider
    calendar_provider = GoogleCalendarProvider()
    logger.debug(f"Calendar Provider created")
    return calendar_provider


def create_app():
    app = Flask(__name__)

    # Initialize managers
    task_manager = create_task_manager()
    ai_manager = create_ai_manager()
    calendar_provider = create_calendar_provider()

    # Register blueprints
    app.register_blueprint(init_ai_routes(), url_prefix="/ai_auth")
    app.register_blueprint(init_todoist_routes(), url_prefix="/todoist_auth")
    app.register_blueprint(init_sqlite_routes(), url_prefix="/sqlite_auth")
    app.register_blueprint(init_app(calendar_provider), url_prefix="/meetings")
    
    app.secret_key = Settings.FLASK_SECRET_KEY

    template_dir = os.path.join(app.root_path, "assets")
    app.jinja_loader = jinja2.FileSystemLoader(template_dir)

    @app.context_processor
    def inject_user():
        user_email = session.get('user_email')
        if not user_email:
            user_email = request.cookies.get('user_email')
        return dict(user_email=user_email, Settings=Settings)

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


@app.route("/config", methods=['GET'])
def config():
    # Check if the user is logged in
    if 'user_email' not in session:
        return redirect(url_for('login'))  # Redirect to login page

    user_email = session.get('user_email')
    return render_template('config.html', user_email=user_email)

@app.route("/save_config", methods=['POST'])
def save_config():
    if 'user_email' not in session:
        return redirect(url_for('login'))

    user_email = session.get('user_email')
    try:
        # Get form data
        task_provider = request.form.get('task_provider')
        ai_provider = request.form.get('ai_provider')
        openai_key = request.form.get('openai_key')
        grok_key = request.form.get('grok_key')

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
            
        flash('Configuration saved successfully')
        logger.info(f"Configuration updated for user {user_email}")
        
        # Check if user wants to return home after saving
        action = request.form.get('action')
        if action == 'save_and_return':
            return redirect(url_for('index'))
        
    except Exception as e:
        flash(f'Error saving configuration: {str(e)}')
        logger.error(f"Error saving configuration for {user_email}: {e}")
    
    return redirect(url_for('config'))


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

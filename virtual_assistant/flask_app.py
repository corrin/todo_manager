import os
from flask import Flask, render_template, redirect, url_for
from virtual_assistant.utils.user_manager import UserManager
from virtual_assistant.utils.settings import Settings
from virtual_assistant.utils.logger import logger
from virtual_assistant.initial_setup import initial_setup

import jinja2

from tasks.task_manager import TaskManager
from ai.ai_manager import AIManager
from ai.auth_routes import init_ai_routes
from tasks.todoist_routes import init_todoist_routes
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
    app.register_blueprint(init_app(calendar_provider), url_prefix="/meetings")
    
    app.secret_key = Settings.FLASK_SECRET_KEY

    template_dir = os.path.join(app.root_path, "assets")
    app.jinja_loader = jinja2.FileSystemLoader(template_dir)

    return app


app = create_app()


@app.route("/")
def main_app():
    auth_instructions = {}
    current_user = UserManager.get_current_user()
    
    # Check task provider authentication
    task_manager = create_task_manager()
    task_auth_results = task_manager.authenticate(current_user)
    for provider, result in task_auth_results.items():
        if result:
            provider_name, auth_url = result
            auth_instructions[f"{provider}_task"] = (provider_name, auth_url)

    # Check AI provider authentication
    ai_manager = create_ai_manager()
    ai_auth_results = ai_manager.authenticate(current_user)
    for provider, result in ai_auth_results.items():
        if result:
            provider_name, auth_url = result
            auth_instructions[f"{provider}_ai"] = (provider_name, auth_url)

    # Check calendar authentication
    calendar_provider = create_calendar_provider()
    email = UserManager.get_current_user()
    logger.debug(f"Authenticating email: {email}")
    instructions = calendar_provider.authenticate(email)
    if instructions:
        logger.debug(f"Received instructions: {instructions}")
        provider, auth_url = instructions
        auth_instructions[email] = (provider, auth_url)
    else:
        logger.debug(f"No instructions received for email: {email}")

    if auth_instructions:
        logger.debug(f"Rendering auth_instructions: {auth_instructions}")
        return render_template("auth_instructions.html", instructions=auth_instructions)
    else:
        logger.debug("No authentication instructions received")
        return "Authentication process initiated. Check the console for further instructions."


@app.route("/initial_setup")
def initial_setup_route():
    result = initial_setup()
    return result


# Set up the default user
UserManager.set_current_user("lakeland@gmail.com")


# This allows the file to work both in development and production
if __name__ == '__main__':
    # Development server
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
else:
    # Production server (pythonanywhere) will import app
    pass

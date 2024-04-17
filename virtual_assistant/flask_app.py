"""
Flask application module for the Virtual Assistant.
This application is for syncing calendars and scheduling tasks
"""

import os
from flask import Flask, render_template, request, redirect, url_for
from flask_login import (
    #    LoginManager,
    #    UserMixin,
    #    login_user,
    #    login_required,
    #    logout_user,
    current_user,
)

import jinja2
from datetime import timedelta

from virtual_assistant.users.user_auth import setup_login_manager

from virtual_assistant.utils.user_manager import UserManager
from virtual_assistant.utils.settings import Settings
from virtual_assistant.initial_setup import initial_setup
from virtual_assistant.database.todoist_module import TodoistModule
from virtual_assistant.ai.openai_module import OpenAIModule
from virtual_assistant.meetings.meetings_routes import meetings_bp, providers


def create_database_module():
    """
    Factory function to create the appropriate database module based on
    configuration.  Not currently used.  The goal is this is hwo tasks get
    stored so they are remembered.

    Returns:
        TodoistModule: An instance of the TodoistModule.
    """
    return TodoistModule()


def require_login():
    # List of routes that don't require authentication
    open_routes = ["/login", "/privacy", "/tos"]
    if not current_user.is_authenticated and request.path not in open_routes:
        return redirect(url_for("auth.login"))  # Redirect to the login page


def create_ai_module():
    """
    Factory function to create the appropriate AI module based on configuration.
    Not currently used.  Goal is this allows you to chat with your calendar.

    Returns:
        OpenAIModule: An instance of the OpenAIModule.
    """
    return OpenAIModule()


def create_app():
    """
    Create and configure the Flask application.

    Returns:
        Flask: The configured Flask application.
    """
    flask_app = Flask(__name__)

    # Setup Flask-Login
    setup_login_manager(flask_app)

    flask_app.before_request(require_login)

    flask_app.config["SESSION_COOKIE_SECURE"] = True
    flask_app.config["SESSION_COOKIE_HTTPONLY"] = True
    flask_app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=14)

    ai_module = create_ai_module()

    flask_app.register_blueprint(ai_module.blueprint, url_prefix="/openai")
    flask_app.register_blueprint(meetings_bp, url_prefix="/meetings")
    flask_app.secret_key = Settings.FLASK_SECRET_KEY

    template_dir = os.path.join(flask_app.root_path, "assets")
    flask_app.jinja_loader = jinja2.FileSystemLoader(template_dir)

    return flask_app


app = create_app()


@app.route("/")
def main_app():
    """
    Main route for the Virtual Assistant application.
    Don't call this yet - this is what you're supposed to call once the
    components are working

    Returns:
        str: The rendered HTML template with the list of meetings.
    """
    email_addresses = UserManager.get_email_addresses()
    meetings = []
    for email, provider_key in email_addresses.items():
        provider_class = providers.get(provider_key)
        if provider_class:
            provider_instance = provider_class()
            user_meetings = provider_instance.get_meetings(email)
            meetings.extend(user_meetings)
    return render_template("meetings.html", meetings=meetings)


@app.route("/initial_setup")
def initial_setup_route():
    """
    Route for performing the initial setup.  To be called just once.

    Returns:
        str: The result of the initial setup.
    """
    result = initial_setup()
    return result


@app.route("/initial_setup_complete")
def initial_setup_complete_route():
    return "Initial setup complete. You can now use the application."


@app.route("/terms")
def terms_of_service():
    return render_template("tos.html")


@app.route("/privacy")
def privacy_statement():
    return render_template("privacy.html")


# Authenticate the email addresses stored in the CalendarManager
# Removed - we want the user to log in instead
# UserManager.set_current_user("lakeland@gmail.com")

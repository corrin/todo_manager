import os

import jinja2
from flask import Flask, current_app, render_template
from flask_login import login_required

from virtual_assistant.ai.openai_module import OpenAIModule
from virtual_assistant.auth.google_auth import GoogleAuth
from virtual_assistant.auth.user_auth import setup_login_manager
from virtual_assistant.database.database import Database
from virtual_assistant.database.todoist_module import TodoistModule
from virtual_assistant.meetings.meetings_routes import meetings_bp, providers
from virtual_assistant.new_user import new_user
from virtual_assistant.utils.logger import logger
from virtual_assistant.utils.settings import Settings
from virtual_assistant.utils.user_manager import UserManager


def create_database_module():
    """Factory function to create the appropriate database module."""
    logger.info("Creating database module")
    return TodoistModule()


def create_ai_module():
    """Factory function to create the AI module."""
    logger.info("Creating AI module")
    return OpenAIModule()


def login():
    logger.info("Logging in!")
    with current_app.app_context():
        google_auth = GoogleAuth(current_app)
        logger.info("Logging in")
        return google_auth.authenticate()


def authorize():
    logger.info("Authorize called")
    with current_app.app_context():
        google_auth = GoogleAuth(current_app)
        logger.info("Authorizing")
        return google_auth.authorize()


@login_required
def main_app():
    """Display meetings; requires user to be logged in."""
    logger.info("Displaying meetings")
    calendar_accounts = UserManager.get_calendar_accounts()
    meetings = []
    for email, provider_key in calendar_accounts.items():
        provider_class = providers.get(provider_key)
        if provider_class:
            provider_instance = provider_class()
            user_meetings = provider_instance.get_meetings(email)
            meetings.extend(user_meetings)
    return render_template("meetings.html", meetings=meetings)


def new_user_route():
    logger.info("Creating new user")
    return new_user()


def new_user_complete_route():
    logger.info("New user setup complete")
    return "New user setup complete. You can now use the application."


def terms_of_service():
    logger.info("Displaying terms of service")
    return render_template("tos.html")


def privacy_statement():
    logger.info("Displaying privacy statement")
    return render_template("privacy.html")


def app(script_name=None, config=None):
    application = Flask(__name__)
    application.secret_key = Settings.FLASK_SECRET_KEY
    application.config["SQLALCHEMY_DATABASE_URI"] = Settings.DATABASE_URI
    application.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    application.config["SERVER_NAME"] = Settings.SERVER_NAME
    application.config["APPLICATION_ROOT"] = "/"
    application.config["PREFERRED_URL_SCHEME"] = "https"

    logger.info(f"Database URI: {Settings.DATABASE_URI}")

    # If there's a config dictionary provided, update the configuration
    if isinstance(config, dict):
        application.config.update(config)

    setup_login_manager(application)
    Database.init_app(app)

    application.add_url_rule("/login", "login", login)
    application.add_url_rule("/authorize", "authorize", authorize)
    application.add_url_rule("/", "main_app", main_app)
    application.add_url_rule("/new_user", "new_user_route", new_user)
    application.add_url_rule(
        "/new_user_complete",
        "new_user_complete_route",
        lambda: "Setup complete. You can now use the application.",
    )
    application.add_url_rule("/terms", "terms_of_service", terms_of_service)
    application.add_url_rule("/privacy", "privacy_statement", privacy_statement)

    ai_module = create_ai_module()
    # db_module = create_database_module()

    if ai_module and hasattr(ai_module, "blueprint"):
        application.register_blueprint(ai_module.blueprint, url_prefix="/openai")
    else:
        logger.error("AI module or its blueprint is not properly initialized.")

    if meetings_bp:
        application.register_blueprint(meetings_bp, url_prefix="/meetings")
    else:
        logger.error("Meetings blueprint is not initialized.")

    if database_bp:
        application.register_blueprint(database_bp, url_prefix="/database")
    else:
        logger.error("Database blueprint is not initialized.")

    template_dir = os.path.join(application.root_path, "assets")
    if os.path.exists(template_dir):
        application.jinja_loader = jinja2.FileSystemLoader(template_dir)
    else:
        logger.error(f"Template directory {template_dir} does not exist.")

    logger.info("Application initialized")
    logger.info(f"Returning application instance: {application}")

    return application

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import login_required
import jinja2

from virtual_assistant.auth.google_auth import GoogleAuth
from virtual_assistant.users.user_auth import setup_login_manager
from virtual_assistant.utils.user_manager import UserManager
from virtual_assistant.utils.settings import Settings
from virtual_assistant.database.todoist_module import TodoistModule
from virtual_assistant.ai.openai_module import OpenAIModule
from virtual_assistant.meetings.meetings_routes import meetings_bp, providers

# Initialize SQLAlchemy
db = SQLAlchemy()


def create_database_module():
    """Factory function to create the appropriate database module."""
    return TodoistModule()


def create_ai_module():
    """Factory function to create the AI module."""
    return OpenAIModule()


def login(google_auth):
    return google_auth.authenticate()


def authorize(google_auth):
    return google_auth.authorize()


@login_required
def main_app():
    """Display meetings; requires user to be logged in."""
    email_addresses = UserManager.get_email_addresses()
    meetings = []
    for email, provider_key in email_addresses.items():
        provider_class = providers.get(provider_key)
        if provider_class:
            provider_instance = provider_class()
            user_meetings = provider_instance.get_meetings(email)
            meetings.extend(user_meetings)
    return render_template("meetings.html", meetings=meetings)


def new_user_route():
    """Route for new user setup."""
    result = initial_setup()
    return result


def new_user_complete_route():
    return "New user setup complete. You can now use the application."


def terms_of_service():
    return render_template("tos.html")


def privacy_statement():
    return render_template("privacy.html")


def create_app():
    app = Flask(__name__)
    app.secret_key = Settings.FLASK_SECRET_KEY
    app.config["SQLALCHEMY_DATABASE_URI"] = Settings.DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    setup_login_manager(app)
    google_auth = GoogleAuth(app)

    app.add_url_rule("/login", "login", login(google_auth))
    app.add_url_rule("/authorize", "authorize", authorize(google_auth))
    app.add_url_rule("/", "main_app", main_app)
    app.add_url_rule("/new_user", "new_user_route", new_user)
    app.add_url_rule(
        "/new_user_complete",
        "new_user_complete_route",
        lambda: "Setup complete. You can now use the application.",
    )
    app.add_url_rule("/terms", "terms_of_service", terms_of_service)
    app.add_url_rule("/privacy", "privacy_statement", privacy_statement)

    ai_module = create_ai_module()
    app.register_blueprint(ai_module.blueprint, url_prefix="/openai")
    app.register_blueprint(meetings_bp, url_prefix="/meetings")

    template_dir = os.path.join(app.root_path, "assets")
    app.jinja_loader = jinja2.FileSystemLoader(template_dir)

    return app

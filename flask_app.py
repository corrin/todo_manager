import platform
import pkg_resources  # part of setuptools
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from utils.user_manager import UserManager

load_dotenv()  # take environment variables from .env.

from database.todoist_module import TodoistModule
from ai.openai_module import OpenAIModule
from meetings.calendar_manager import CalendarManager
from meetings.meetings_routes import meetings_bp

app = Flask(__name__)

def create_database_module():
    # Factory function to create the appropriate database module based on configuration
    return TodoistModule()

def create_ai_module():
    # Factory function to create the appropriate AI module based on configuration
    return OpenAIModule()

def create_calendar_module():
    # Factory function to create the appropriate calendar module based on configuration
    return CalendarManager()

ai_module = create_ai_module()
calendar_manager = create_calendar_module()

app.register_blueprint(ai_module.blueprint, url_prefix='/openai')
app.register_blueprint(meetings_bp, url_prefix='/meetings')

@app.route('/')
def main_app():
    for email in calendar_manager.email_providers:
        calendar_manager.authenticate(email)
    return 'Authentication process initiated. Check the console for further instructions.'

@app.route('/versions')
def show_versions():
    python_version = platform.python_version()
    installed_packages = ['Flask', 'requests']  # Add any packages you've installed in the venv
    versions_info = f"Python Version: {python_version}\n"

    for package in installed_packages:
        version = pkg_resources.get_distribution(package).version
        versions_info += f"{package} Version: {version}\n"

    return versions_info

# Authenticate the email addresses stored in the CalendarManager

UserManager.set_current_user('lakeland@gmail.com')

if __name__ == '__main__':
    app.run()
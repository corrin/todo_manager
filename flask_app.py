import os
import platform # Used in the hello world style 'version' call
import pkg_resources  # part of setuptools
from flask import Flask, render_template
#from flask import request, jsonify
from virtual_assistant.utils.user_manager import UserManager
import jinja2


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
template_dir = os.path.join(app.root_path, 'assets')
app.jinja_loader = jinja2.FileSystemLoader(template_dir)

app.register_blueprint(ai_module.blueprint, url_prefix='/openai')
app.register_blueprint(meetings_bp, url_prefix='/meetings')

# In flask_app.py
from utils.logger import logger

@app.route('/')
def main_app():
    auth_instructions = {}
    for email in calendar_manager.email_providers:
        logger.debug(f"Authenticating email: {email}")
        instructions = calendar_manager.authenticate(email)
        if instructions:
            logger.debug(f"Received instructions: {instructions}")
            provider, auth_url = instructions
            auth_instructions[email] = (provider, auth_url)
        else:
            logger.debug(f"No instructions received for email: {email}")

    if auth_instructions:
        logger.debug(f"Rendering auth_instructions: {auth_instructions}")
        return render_template('auth_instructions.html', instructions=auth_instructions)
    else:
        logger.debug("No authentication instructions received")
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
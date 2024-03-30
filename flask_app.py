import os
from flask import Flask, render_template
from virtual_assistant.utils.user_manager import UserManager
import jinja2
from utils.logger import logger

from database.todoist_module import TodoistModule
from ai.openai_module import OpenAIModule
from meetings.calendar_manager import CalendarManager
from meetings.meetings_routes import init_app

def create_database_module():
    # Factory function to create the appropriate database module based on configuration
    return TodoistModule()

def create_ai_module():
    # Factory function to create the appropriate AI module based on configuration
    return OpenAIModule()

def create_calendar_module():
    # Factory function to create the appropriate calendar module based on configuration
    calendar_manager = CalendarManager()
    logger.debug(f"Calendar Manager created: {calendar_manager}")
    logger.debug(f"Calendar Manager providers: {calendar_manager.providers}")
    return calendar_manager

def create_app():
    app = Flask(__name__)

    ai_module = create_ai_module()
    calendar_manager = create_calendar_module()

    app.register_blueprint(ai_module.blueprint, url_prefix='/openai')
    app.register_blueprint(init_app(calendar_manager), url_prefix='/meetings')

    template_dir = os.path.join(app.root_path, 'assets')
    app.jinja_loader = jinja2.FileSystemLoader(template_dir)

    return app

app = create_app()

@app.route('/')
def main_app():
    auth_instructions = {}
    calendar_manager = create_calendar_module()

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

# Authenticate the email addresses stored in the CalendarManager
UserManager.set_current_user('lakeland@gmail.com')
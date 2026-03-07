# utils/settings.py
import os
from dotenv import load_dotenv
from virtual_assistant.utils.logger import logger

# Load environment variables from the .env file
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
logger.info(f"Loading .env from: {env_path}")
load_dotenv(env_path)

class Settings:
    # Project settings
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    USERS_FOLDER = os.path.join(PROJECT_ROOT, "users")
    # DATABASE_PATH = os.path.join(PROJECT_ROOT, "data", "virtual_assistant.db") # Old SQLite path
    # DATABASE_URI = f"sqlite:///{DATABASE_PATH}" # Old SQLite URI
    DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI") # Read from environment

    # Ensure users folder exists
    os.makedirs(USERS_FOLDER, exist_ok=True)

    # Google Calendar API settings
    GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
    GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
    GOOGLE_REDIRECT_URI = os.environ["GOOGLE_REDIRECT_URI"]
    GOOGLE_SCOPES = ["https://www.googleapis.com/auth/calendar"]

    # Office 365 Calendar API settings
    O365_CLIENT_ID = os.environ["O365_CLIENT_ID"]
    O365_CLIENT_SECRET = os.environ["O365_CLIENT_SECRET"]
    O365_REDIRECT_URI = os.environ["O365_REDIRECT_URI"]
    O365_SCOPES = ["Calendars.ReadWrite"]

    # Flask settings
    FLASK_SECRET_KEY = os.environ["FLASK_SECRET_KEY"]
    SERVER_NAME = os.environ["SERVER_NAME"]

    @classmethod
    def validate_settings(cls):
        """Validate that all required environment variables are set."""
        required_vars = {
            'GOOGLE_CLIENT_ID': 'Google Calendar client ID',
            'GOOGLE_CLIENT_SECRET': 'Google Calendar client secret',
            'GOOGLE_REDIRECT_URI': 'Google Calendar redirect URI',
            'O365_CLIENT_ID': 'Office 365 client ID',
            'O365_CLIENT_SECRET': 'Office 365 client secret',
            'O365_REDIRECT_URI': 'Office 365 redirect URI',
            'FLASK_SECRET_KEY': 'Flask secret key',
            'SERVER_NAME': 'Server name',
            'SQLALCHEMY_DATABASE_URI': 'SQLAlchemy Database URI'
        }

        missing_vars = []
        for var, description in required_vars.items():
            if not os.environ.get(var):
                missing_vars.append(f"{description} ({var})")

        if missing_vars:
            error_msg = "Missing required environment variables:\n- " + "\n- ".join(missing_vars)
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info("All required environment variables are set")

# Validate settings on module import
Settings.validate_settings()

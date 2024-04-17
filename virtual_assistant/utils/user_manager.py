# user_manager.py
import os
import json
from google.oauth2.credentials import Credentials
from flask_login import login_user, logout_user, current_user

from virtual_assistant.utils.settings import Settings
from virtual_assistant.utils.logger import logger
from virtual_assistant.users.user import User


class UserManager:
    current_user = None
    user_calendar_accounts = {}

    @classmethod
    def get_current_user(cls):
        return cls.current_user

    @classmethod
    def login(cls, email):
        """Log in a user by setting the session and UserManager's current user."""
        user = User(email)
        login_user(user, remember=True)
        cls.current_user = email
        logger.info(f"User {email} logged in.")

    @classmethod
    def logout(cls):
        """Log out the current user."""
        if current_user.is_authenticated:
            logger.info(f"Logging out user {current_user.id}")
            logout_user()
            cls.current_user = None

    @classmethod
    def get_user_folder(cls):
        if not cls.current_user:
            raise ValueError("Current user not set. Please log in first.")
        user_folder = os.path.join(Settings.USERS_FOLDER, cls.current_user)
        os.makedirs(
            user_folder, exist_ok=True
        )  # Create the user folder if it doesn't exist
        return user_folder

    @classmethod
    def get_calendar_accounts_file(cls):
        user_folder = cls.get_user_folder()
        return os.path.join(user_folder, "email_addresses.json")

    @classmethod
    def load_calendar_accounts(cls):
        calendar_accounts_file = cls.get_calendar_accounts_file()
        logger.debug(f"Loading calendar accounts from file: {calendar_accounts_file}")
        if os.path.exists(calendar_accounts_file):
            with open(calendar_accounts_file, "r") as file:
                cls.user_calendar_accounts = json.load(file)
        else:
            cls.user_calendar_accounts = {}
        logger.debug(f"Loaded calendar accounts: {cls.user_calendar_accounts}")

    @classmethod
    def get_calendar_accounts(cls):
        return cls.user_calendar_accounts

    @classmethod
    def get_provider_for_email(cls, email):
        logger.debug(f"Getting provider for email: {email}")
        logger.debug(f"Current user_calendar_accounts: {cls.user_calendar_accounts}")
        provider = cls.user_calendar_accounts.get(email)
        logger.debug(f"Retrieved provider: {provider}")
        return provider

    @classmethod
    def save_calendar_accounts(cls, calendar_accounts):
        cls.user_calendar_accounts = calendar_accounts
        calendar_accounts_file = cls.get_calendar_accounts_file()
        with open(calendar_accounts_file, "w") as file:
            json.dump(calendar_accounts, file)
        logger.debug(f"Saved calendar accounts: {cls.user_calendar_accounts}")

    @classmethod
    def save_credentials(cls, email, credentials):
        user_folder = cls.get_user_folder()
        credentials_file = os.path.join(user_folder, f"{email}_credentials.json")
        with open(credentials_file, "w", encoding="utf-8") as file:
            json.dump(credentials, file)
        logger.debug(f"Credentials stored for {email}")

    @classmethod
    def get_credentials(cls, email):
        user_folder = cls.get_user_folder()
        credentials_file = os.path.join(user_folder, f"{email}_credentials.json")

        if os.path.exists(credentials_file):
            with open(credentials_file, "r", encoding="utf-8") as file:
                credentials_data = json.load(file)
                credentials = Credentials.from_authorized_user_info(credentials_data)
                return credentials

        return None

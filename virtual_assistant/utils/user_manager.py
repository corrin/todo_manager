import json
import os

from flask_login import current_user, login_user, logout_user
from google.oauth2.credentials import Credentials

from virtual_assistant.database.base import db
from virtual_assistant.database.user import User
from virtual_assistant.utils.logger import logger
from virtual_assistant.utils.settings import Settings

"""
User Manager class
"""


class UserManager:
    """
    Handles user authentication and management
    """

    current_user = None
    user_calendar_accounts = {}

    @classmethod
    def get_current_user(cls) -> str:
        """
        Get the current user

        Returns:
            str: The current user's email
        """
        return cls.current_user

    @classmethod
    def login(cls, email: str):
        """
        Log in a user by setting the session and UserManager's current user.

        Args:
            email (str): The user's email
        """
        user = User(email)
        login_user(user, remember=True)
        cls.current_user = email
        logger.info(f"User {email} logged in.")

    @classmethod
    def logout(cls):
        """
        Log out the current user.
        """
        if current_user.is_authenticated:
            logger.info(f"Logging out user {current_user.id}")
            logout_user()
            cls.current_user = None

    @classmethod
    def get_user_folder(cls) -> str:
        """
        Get the user's folder path

        Returns:
            str: The user's folder path
        """
        if not cls.current_user:
            raise ValueError("Current user not set. Please log in first.")
        user_folder = os.path.join(Settings.USERS_FOLDER, cls.current_user)
        os.makedirs(
            user_folder, exist_ok=True
        )  # Create the user folder if it doesn't exist
        return user_folder

    @classmethod
    def get_calendar_accounts_file(cls) -> str:
        """
        Get the calendar accounts file path

        Returns:
            str: The calendar accounts file path
        """
        user_folder = cls.get_user_folder()
        return os.path.join(user_folder, "email_addresses.json")

    @classmethod
    def load_calendar_accounts(cls):
        """
        Load the calendar accounts from the file
        """
        calendar_accounts_file = cls.get_calendar_accounts_file()
        logger.debug(f"Loading calendar accounts from file: {calendar_accounts_file}")
        if os.path.exists(calendar_accounts_file):
            with open(calendar_accounts_file, "r") as file:
                cls.user_calendar_accounts = json.load(file)
        else:
            cls.user_calendar_accounts = {}
        logger.debug(f"Loaded calendar accounts: {cls.user_calendar_accounts}")

    @classmethod
    def get_calendar_accounts(cls) -> dict:
        """
        Get the calendar accounts

        Returns:
            dict: The calendar accounts
        """
        return cls.user_calendar_accounts

    @classmethod
    def get_provider_for_email(cls, email: str) -> str:
        """
        Get the provider for the given email

        Args:
            email (str): The email

        Returns:
            str: The provider
        """
        logger.debug(f"Getting provider for email: {email}")
        logger.debug(f"Current user_calendar_accounts: {cls.user_calendar_accounts}")
        provider = cls.user_calendar_accounts.get(email)
        logger.debug(f"Retrieved provider: {provider}")
        return provider

    @classmethod
    def save_calendar_accounts(cls, calendar_accounts: dict):
        """
        Save the calendar accounts to the file

        Args:
            calendar_accounts (dict): The calendar accounts
        """
        cls.user_calendar_accounts = calendar_accounts
        calendar_accounts_file = cls.get_calendar_accounts_file()
        with open(calendar_accounts_file, "w") as file:
            json.dump(calendar_accounts, file)
        logger.debug(f"Saved calendar accounts: {cls.user_calendar_accounts}")

    @classmethod
    def save_credentials(cls, email: str, credentials: dict):
        """
        Save the credentials for the given email

        Args:
            email (str): The email
            credentials (dict): The credentials
        """
        user_folder = cls.get_user_folder()
        credentials_file = os.path.join(user_folder, f"{email}_credentials.json")
        with open(credentials_file, "w", encoding="utf-8") as file:
            json.dump(credentials, file)
        logger.debug(f"Credentials stored for {email}")

    @classmethod
    def get_credentials(cls, email: str) -> Credentials:
        """
        Get the credentials for the given email

        Args:
        email (str): The email

        Returns:
        Credentials: The credentials
        """
        user_folder = cls.get_user_folder()
        credentials_file = os.path.join(user_folder, f"{email}_credentials.json")

        if os.path.exists(credentials_file):
            with open(credentials_file, "r", encoding="utf-8") as file:
                credentials_data = json.load(file)
                credentials = Credentials.from_authorized_user_info(credentials_data)
                return credentials

        return None

    @staticmethod
    def create_user(user_info):
        """
        Create a new user based on the OAuth user info.

        Parameters:
        user_info (dict): The dictionary containing user information

        Returns:
        User: The newly created user object
        """
        user = User(email=user_info["email"])
        # Set other necessary fields from user_info
        db.session.add(user)
        db.session.commit()
        return user

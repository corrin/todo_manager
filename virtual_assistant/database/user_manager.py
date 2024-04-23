import json
import os

from flask_login import current_user, login_user, logout_user
from google.oauth2.credentials import Credentials

from virtual_assistant.database.calendar_account import CalendarAccount
from virtual_assistant.database.database import Database
from virtual_assistant.database.user import User
from virtual_assistant.utils.logger import logger
from virtual_assistant.utils.settings import Settings


class UserDataManager(Database):
    """
    Manages user data and interactions with the database.
    """

    current_user = None
    user_calendar_accounts = {}

    @classmethod
    def get_current_user(cls):
        """Get the current user's email."""
        return cls.current_user

    @classmethod
    def login(cls, email):
        """Log in a user and set the current user."""
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
        """Get the user's folder path."""
        if not cls.current_user:
            raise ValueError("Current user not set. Please log in first.")
        user_folder = os.path.join(Settings.USERS_FOLDER, cls.current_user)
        os.makedirs(user_folder, exist_ok=True)
        return user_folder

    @classmethod
    def get_calendar_accounts_file(cls):
        """Get the calendar accounts file path (legacy)."""
        user_folder = cls.get_user_folder()
        return os.path.join(user_folder, "email_addresses.json")

    @classmethod
    def load_calendar_accounts(cls):
        """Load calendar accounts from the database."""
        if not cls.current_user:
            raise ValueError("Current user not set. Please log in first.")
        calendar_accounts = (
            cls._db.session.query(CalendarAccount)
            .filter_by(user_id=cls.current_user)
            .all()
        )
        cls.user_calendar_accounts = {
            account.email_address: account.provider for account in calendar_accounts
        }
        logger.debug(f"Loaded calendar accounts: {cls.user_calendar_accounts}")

    @classmethod
    def get_calendar_accounts(cls):
        """Get the calendar accounts associated with the current user."""
        return cls.user_calendar_accounts

    @classmethod
    def get_provider_for_email(cls, email):
        """Get the provider for the given email."""
        logger.debug(f"Getting provider for email: {email}")
        logger.debug(f"Current user_calendar_accounts: {cls.user_calendar_accounts}")
        provider = cls.user_calendar_accounts.get(email)
        logger.debug(f"Retrieved provider: {provider}")
        return provider

    @classmethod
    def save_calendar_account(cls, email_address, provider, credentials):
        """Save a calendar account to the database."""
        if not cls.current_user:
            raise ValueError("Current user not set. Please log in first.")
        calendar_account = CalendarAccount(
            user_id=cls.current_user,
            email_address=email_address,
            provider=provider,
            credentials=credentials,
        )
        cls._db.session.add(calendar_account)
        cls._db.session.commit()
        logger.debug(f"Calendar account saved for {email_address}")

    @classmethod
    def save_credentials(cls, email, credentials):
        """Save the credentials for the given email and provider."""
        provider = cls.get_provider_for_email(email)
        if provider:
            cls.save_calendar_account(email, provider, credentials)
        else:
            logger.warning(f"No provider found for email: {email}")

    @classmethod
    def get_credentials(cls, email):
        """Retrieve the credentials for the given email and provider from the database."""
        if not cls.current_user:
            raise ValueError("Current user not set. Please log in first.")
        calendar_account = (
            cls._db.session.query(CalendarAccount)
            .filter_by(user_id=cls.current_user, email_address=email)
            .first()
        )
        if calendar_account:
            logger.debug(f"Credentials loaded for {email}")
            return Credentials.from_authorized_user_info(
                calendar_account.authentication_credentials
            )
        else:
            logger.warning(f"Credentials not found for {email}")
            return None

    @staticmethod
    def create_user(email):
        """Create a new user in the database."""
        user = User(email=email)
        Database.add(user)
        Database.commit()
        return user

import json
import os

from flask_login import current_user, login_user, logout_user
from google.oauth2.credentials import Credentials

from virtual_assistant.database.calendar_account import CalendarAccount
from virtual_assistant.database.database import Database, db
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
    def login(cls, app_login):
        """Log in a user and set the current user."""
        user = User(app_login)
        login_user(user, remember=True)
        cls.current_user = app_login
        logger.info(f"User {app_login} logged in.")

    @classmethod
    def logout(cls):
        """Log out the current user."""
        if current_user.is_authenticated:
            logger.info(f"Logging out user {current_user.app_login}")
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
            db.session.query(CalendarAccount)
            .filter_by(app_login=cls.current_user)
            .all()
        )
        cls.user_calendar_accounts = {
            account.calendar_email: account.provider for account in calendar_accounts
        }
        logger.debug(f"Loaded calendar accounts: {cls.user_calendar_accounts}")

    @classmethod
    def get_calendar_accounts(cls):
        """Get the calendar accounts associated with the current user."""
        return cls.user_calendar_accounts

    @classmethod
    def get_provider_for_email(cls, calendar_email):
        """Get the provider for the given calendar email."""
        # TODO: This code technically has a bug and should not exist
        # It is possible for multiple providers for one email
        logger.debug(f"Getting provider for calendar email: {calendar_email}")
        logger.debug(f"Current user_calendar_accounts: {cls.user_calendar_accounts}")
        provider = cls.user_calendar_accounts.get(calendar_email)
        logger.debug(f"Retrieved provider: {provider}")
        return provider

    @classmethod
    def save_calendar_account(cls, calendar_email, provider, credentials):
        """Save a calendar account to the database."""
        if not cls.current_user:
            raise ValueError("Current user not set. Please log in first.")
        calendar_account = CalendarAccount(
            app_login=cls.current_user,
            calendar_email=calendar_email,
            provider=provider,
            token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_uri=credentials.token_uri,
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
            scopes=','.join(credentials.scopes) if credentials.scopes else None
        )
        db.session.add(calendar_account)
        db.session.commit()
        logger.debug(f"Calendar account saved for {calendar_email}")

    @classmethod
    def save_credentials(cls, calendar_email, credentials):
        """Save the credentials for the given calendar email and provider."""
        provider = cls.get_provider_for_email(calendar_email)
        if provider:
            cls.save_calendar_account(calendar_email, provider, credentials)
        else:
            logger.warning(f"No provider found for calendar email: {calendar_email}")

    @classmethod
    def get_calendar_credentials(cls, calendar_email):
        """Retrieve the credentials for the given calendar account."""
        if not cls.current_user:
            raise ValueError("Current user not set. Please log in first.")
        
        # Find the calendar account for this user and calendar email
        calendar_account = (
            db.session.query(CalendarAccount)
            .filter_by(app_login=cls.current_user, calendar_email=calendar_email)
            .first()
        )
        
        if calendar_account:
            logger.debug(f"Credentials loaded for calendar: {calendar_email}")
            # Create a credentials object from the stored fields
            credentials_info = {
                'token': calendar_account.token,
                'refresh_token': calendar_account.refresh_token,
                'token_uri': calendar_account.token_uri,
                'client_id': calendar_account.client_id,
                'client_secret': calendar_account.client_secret,
                'scopes': calendar_account.scopes.split(',') if calendar_account.scopes else []
            }
            return Credentials.from_authorized_user_info(credentials_info)
        else:
            logger.warning(f"Credentials not found for calendar: {calendar_email}")
            return None

    @staticmethod
    def create_user(app_login):
        """Create a new user in the database."""
        user = User(app_login=app_login)
        db.session.add(user)
        db.session.commit()
        return user

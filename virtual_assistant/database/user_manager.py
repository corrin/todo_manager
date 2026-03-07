from flask_login import current_user, login_user, logout_user

from virtual_assistant.database.database import Database, db
from virtual_assistant.database.user import User
from virtual_assistant.utils.logger import logger


class UserDataManager(Database):
    """
    Manages user data and interactions with the database.
    """

    current_user = None
    user_external_accounts = {}

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

    @staticmethod
    def create_user(app_login):
        """Create a new user in the database."""
        user = User(app_login=app_login)
        db.session.add(user)
        db.session.commit()
        return user

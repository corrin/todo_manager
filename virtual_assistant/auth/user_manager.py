import os
from flask import session
from virtual_assistant.utils.settings import Settings
from virtual_assistant.utils.logger import logger

class UserManager:
    """
    Manages user authentication state and user-specific storage.
    Part of the authentication system to handle user sessions
    and their associated data storage.
    """
    @staticmethod
    def get_current_user():
        """Get the current user's email from the session."""
        return session.get('user_email')

    @staticmethod
    def get_user_folder():
        """Get the current user's storage folder path."""
        user_email = UserManager.get_current_user()
        if not user_email:
            raise ValueError("Current user not set. Please log in first.")
        
        user_folder = os.path.join(Settings.USERS_FOLDER, user_email)
        os.makedirs(user_folder, exist_ok=True)
        return user_folder
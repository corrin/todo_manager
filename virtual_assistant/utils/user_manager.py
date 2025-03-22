import os
from flask import session
from virtual_assistant.utils.settings import Settings
from virtual_assistant.utils.logger import logger

# ############################################################################################
# DEPRECATION NOTICE: This module is marked for removal in a future version.
# All code should begin migrating away from file-based credential storage.
# Future versions will use database credential storage with proper encryption.
# ############################################################################################

class UserManager:
    """
    Handles user session state and folder management.
    Each provider manages its own storage in the user's folder.
    """
    @staticmethod
    def get_current_user():
        """Get the current user's email from the session."""
        return session.get('user_email')

    @staticmethod
    def get_user_folder(email=None):
        """Get a user's folder path. Uses current user if email not provided."""
        if not email:
            email = UserManager.get_current_user()
            if not email:
                raise ValueError("No user email provided or found in session")
        
        user_folder = os.path.join(Settings.USERS_FOLDER, email)
        os.makedirs(user_folder, exist_ok=True)
        logger.debug(f"Using folder for user {email}: {user_folder}")
        return user_folder

    @staticmethod
    def get_provider_folder(provider_name, email=None):
        """Get a provider's folder within the user's folder."""
        user_folder = UserManager.get_user_folder(email)
        provider_folder = os.path.join(user_folder, provider_name)
        os.makedirs(provider_folder, exist_ok=True)
        return provider_folder
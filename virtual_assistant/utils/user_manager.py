# user_manager.py
import os
import json

from utils.settings import Settings
from flask import session


class UserManager:
    @classmethod
    def get_current_user(cls):
        return session.get('user_email')

    @classmethod
    def set_current_user(cls, username):
        session['user_email'] = username

    @classmethod
    def get_user_folder(cls):
        current_user = cls.get_current_user()
        if not current_user:
            raise ValueError("Current user not set. Please log in first.")
        user_folder = os.path.join(Settings.USERS_FOLDER, current_user)
        if not os.path.exists(user_folder):
            os.makedirs(user_folder, exist_ok=True)  # Create the user folder if it doesn't exist
            logger.info(f"Created user folder for {current_user}")
        return user_folder

    @classmethod
    def get_email_addresses_file(cls):
        user_folder = cls.get_user_folder()
        return os.path.join(user_folder, "email_addresses.json")

    @classmethod
    def get_email_addresses(cls):
        email_addresses_file = cls.get_email_addresses_file()
        if os.path.exists(email_addresses_file):
            with open(email_addresses_file, "r") as file:
                return json.load(file)
        else:
            return {}

    @classmethod
    def save_email_addresses(cls, email_addresses):
        email_addresses_file = cls.get_email_addresses_file()
        with open(email_addresses_file, "w") as file:
            json.dump(email_addresses, file)

    @classmethod
    def get_todoist_token(cls):
        """Get the Todoist API token for the current user."""
        user_folder = cls.get_user_folder()
        token_file = os.path.join(user_folder, "todoist_token")
        if os.path.exists(token_file):
            with open(token_file, "r") as file:
                return file.read().strip()
        return None

    @classmethod
    def save_todoist_token(cls, token):
        """Save the Todoist API token for the current user."""
        user_folder = cls.get_user_folder()
        token_file = os.path.join(user_folder, "todoist_token")
        with open(token_file, "w") as file:
            file.write(token)

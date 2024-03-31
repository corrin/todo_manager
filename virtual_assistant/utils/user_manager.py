# user_manager.py
import os
import json

from utils.settings import Settings


class UserManager:
    __current_user = None

    @classmethod
    def get_current_user(cls):
        return cls.__current_user

    @classmethod
    def set_current_user(cls, username):
        cls.__current_user = username

    @classmethod
    def get_user_folder(cls):
        current_user = cls.get_current_user()
        if not current_user:
            raise ValueError("Current user not set. Please log in first.")
        user_folder = os.path.join(Settings.USERS_FOLDER, current_user)
        os.makedirs(
            user_folder, exist_ok=True
        )  # Create the user folder if it doesn't exist
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

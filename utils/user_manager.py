# user_manager.py
import os
from utils.settings import Settings

class UserManager:
    __current_user = None

    @classmethod
    def get_current_user(cls):
        return cls.__current_user

    @classmethod
    def set_current_user(cls, email):
        cls.__current_user = email

    @classmethod
    def get_user_folder(cls):
        current_user = cls.get_current_user()
        if not current_user:
            raise ValueError("Current user not set. Please log in first.")
        user_folder = os.path.join(Settings.USERS_FOLDER, current_user)
        os.makedirs(user_folder, exist_ok=True)  # Create the user folder if it doesn't exist
        return user_folder

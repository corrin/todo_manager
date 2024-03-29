# user_manager.py
class UserManager:
    __current_user = None

    @classmethod
    def get_current_user(cls):
        return cls.__current_user

    @classmethod
    def set_current_user(cls, email):
        cls.__current_user = email

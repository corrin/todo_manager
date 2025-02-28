from flask_login import UserMixin
from virtual_assistant.database.database import db


class User(UserMixin, db.Model):
    app_user_email = db.Column(db.String(120), primary_key=True)  # Use app_user_email as primary key
    calendar_accounts = db.relationship("CalendarAccount", backref="user", lazy=True)
    
    def __init__(self, app_user_email):
        self.app_user_email = app_user_email
    
    def __repr__(self):
        return f"<User {self.app_user_email}>"

    def get_id(self):
        """Override to return the user identifier for Flask-Login"""
        return self.app_user_email

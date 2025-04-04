from flask_login import UserMixin
from virtual_assistant.database.database import db


class User(UserMixin, db.Model):
    app_login = db.Column(db.String(120), primary_key=True)  # Use app_login as primary key
    calendar_accounts = db.relationship("CalendarAccount", backref="user", lazy=True)
    
    def __init__(self, app_login):
        self.app_login = app_login
    
    def __repr__(self):
        return f"<User {self.app_login}>"

    def get_id(self):
        """Override to return the user identifier for Flask-Login"""
        return self.app_login

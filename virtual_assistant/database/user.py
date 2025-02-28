from flask_login import UserMixin
from virtual_assistant.database.database import db


class User(UserMixin, db.Model):
    id = db.Column(db.String(120), primary_key=True)  # Use email as primary key
    username = db.Column(db.String(80), unique=True, nullable=False)
    calendar_accounts = db.relationship("CalendarAccount", backref="user", lazy=True)

    def __repr__(self):
        return f"<User {self.username}>"

    def get_id(self):
        """Override to return the user identifier for Flask-Login"""
        return self.id

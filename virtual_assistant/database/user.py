from flask_login import UserMixin
from sqlalchemy.orm import relationship # Added relationship
from virtual_assistant.database.database import db


class User(UserMixin, db.Model):
    app_login = db.Column(db.String(120), primary_key=True)  # Use app_login as primary key
    # Define relationships using back_populates for bidirectional linking
    calendar_accounts = relationship("CalendarAccount", back_populates="user", lazy=True, cascade="all, delete-orphan")
    # Relationship to TaskAccount model for storing API keys etc. for task providers
    task_accounts = relationship("TaskAccount", back_populates="user", lazy=True, cascade="all, delete-orphan")
    
    def __init__(self, app_login):
        self.app_login = app_login
    
    def __repr__(self):
        return f"<User {self.app_login}>"

    def get_id(self):
        """Override to return the user identifier for Flask-Login"""
        return self.app_login

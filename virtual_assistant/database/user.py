from flask_login import UserMixin
from sqlalchemy.orm import relationship # Added relationship
from virtual_assistant.database.database import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    app_login = db.Column(db.String(120), unique=True, index=True, nullable=False) # User's login identifier for this app

    # User-specific configuration (previously in config.json)
    ai_provider = db.Column(db.String(50), nullable=True) # e.g., 'openai', 'grok'. 
    openai_key = db.Column(db.Text, nullable=True) 
    grok_key = db.Column(db.Text, nullable=True)

    # Define relationships using back_populates for bidirectional linking
    calendar_accounts = relationship("CalendarAccount", back_populates="user", lazy=True, cascade="all, delete-orphan")
    # Relationship to TaskAccount model for storing API keys etc. for task providers
    task_accounts = relationship("TaskAccount", back_populates="user", lazy=True, cascade="all, delete-orphan")
    def __init__(self, app_login):
        self.app_login = app_login
        # id is auto-generated
    
    def __repr__(self):
        return f"<User id={self.id} app_login={self.app_login}>"

    def get_id(self):
        """Override to return the user identifier for Flask-Login"""
        return self.id

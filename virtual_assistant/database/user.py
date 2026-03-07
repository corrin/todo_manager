from flask_login import UserMixin
from sqlalchemy.orm import relationship # Added relationship
import uuid
from sqlalchemy import BINARY, TypeDecorator
from virtual_assistant.database.database import db

# Custom UUID type for MySQL
class MySQLUUID(TypeDecorator):
    impl = BINARY(16)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)
        return value.bytes

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(bytes=value)


class User(UserMixin, db.Model):
    id = db.Column(MySQLUUID, primary_key=True, default=uuid.uuid4)
    app_login = db.Column(db.String(120), unique=True, index=True, nullable=False) # User's login identifier for this app

    # User-specific configuration (previously in config.json)
    ai_provider = db.Column(db.String(50), nullable=True) # e.g., 'openai'
    openai_key = db.Column(db.Text, nullable=True)
    ai_instructions = db.Column(db.Text, nullable=True) # Custom AI instructions for the user
    schedule_slot_duration = db.Column(db.Integer, default=60) # Schedule slot duration in minutes (30, 60, or 120)
    llm_model = db.Column(db.String(100), nullable=True)  # e.g., 'gpt-4o', 'claude-sonnet-4-20250514'

    # Define relationships using back_populates for bidirectional linking
    external_accounts = relationship("ExternalAccount", back_populates="user", lazy=True, cascade="all, delete-orphan")
    def __init__(self, app_login):
        self.app_login = app_login
        # id is auto-generated
    
    def __repr__(self):
        return f"<User id={self.id} app_login={self.app_login}>"

    def get_id(self):
        """Override to return the user identifier for Flask-Login"""
        return str(self.id)

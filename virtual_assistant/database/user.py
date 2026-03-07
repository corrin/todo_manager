import uuid
from typing import Optional

from flask_login import UserMixin
from sqlalchemy import BINARY, String, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship

from virtual_assistant.database.database import Base


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


class User(UserMixin, Base):
    __tablename__ = "app_user"
    id: Mapped[uuid.UUID] = mapped_column(MySQLUUID, primary_key=True, default=uuid.uuid4)
    app_login: Mapped[str] = mapped_column(String(120), unique=True, index=True)  # User's login identifier for this app

    # User-specific configuration (previously in config.json)
    ai_api_key: Mapped[Optional[str]] = mapped_column(default=None)
    ai_instructions: Mapped[Optional[str]] = mapped_column(default=None)  # Custom AI instructions for the user
    schedule_slot_duration: Mapped[Optional[int]] = mapped_column(
        default=60
    )  # Schedule slot duration in minutes (30, 60, or 120)
    llm_model: Mapped[Optional[str]] = mapped_column(
        String(100), default=None
    )  # e.g., 'gpt-4o', 'claude-sonnet-4-20250514'

    # Define relationships using back_populates for bidirectional linking
    external_accounts = relationship(
        "ExternalAccount",
        back_populates="user",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def __init__(self, app_login):
        self.app_login = app_login
        # id is auto-generated

    def __repr__(self):
        return f"<User id={self.id} app_login={self.app_login}>"

    def get_id(self):
        """Override to return the user identifier for Flask-Login"""
        return str(self.id)

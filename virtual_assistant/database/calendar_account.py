from datetime import datetime, timezone
from sqlalchemy import and_

from virtual_assistant.database.database import db
from virtual_assistant.utils.logger import logger


class CalendarAccount(db.Model):
    """Model for storing calendar account credentials and metadata."""
    
    id = db.Column(db.Integer, primary_key=True)
    calendar_email = db.Column(db.String(120), nullable=False)  # The specific calendar account email (e.g. google account email)
    app_user_email = db.Column(db.String(120), db.ForeignKey('user.app_user_email'), nullable=False)  # The app user's email (foreign key to User)
    provider = db.Column(db.String(50), nullable=False)  # 'google' or 'o365'
    token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text)
    token_uri = db.Column(db.String(200))
    client_id = db.Column(db.String(200))
    client_secret = db.Column(db.String(200))
    scopes = db.Column(db.Text)
    last_sync = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (db.UniqueConstraint('calendar_email', 'provider', 'app_user_email', name='_calendar_email_provider_app_user_email_uc'),)

    def __init__(self, calendar_email, provider, **kwargs):
        self.calendar_email = calendar_email
        self.provider = provider
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        return f"<CalendarAccount {self.calendar_email} ({self.provider})>"

    @classmethod
    def get_by_email_and_provider(cls, calendar_email, provider):
        """Get calendar account by calendar email and provider."""
        return cls.query.filter_by(calendar_email=calendar_email, provider=provider).first()
        
    @classmethod
    def get_by_email_provider_and_user(cls, calendar_email, provider, app_user_email):
        """Get calendar account by calendar email, provider, and app user email."""
        return cls.query.filter_by(
            calendar_email=calendar_email,
            provider=provider,
            app_user_email=app_user_email
        ).first()

    @classmethod
    def get_accounts_for_user(cls, app_user_email):
        """Get all calendar accounts for a specific app user."""
        return cls.query.filter_by(app_user_email=app_user_email).all()

    def save(self):
        """Save the calendar account to the database."""
        db.session.add(self)
        db.session.commit()

    @classmethod
    def delete_by_email_and_provider(cls, calendar_email, provider, app_user_email):
        """Delete calendar account by calendar email, provider, and app user email."""
        account = cls.get_by_email_provider_and_user(calendar_email, provider, app_user_email)
        if not account:
            raise ValueError(f"No calendar account found for {calendar_email} ({provider}) for user {app_user_email}")
        
        db.session.delete(account)
        db.session.commit()

    def update_last_sync(self):
        """Update the last sync timestamp."""
        self.last_sync = datetime.now(timezone.utc)
        db.session.commit()

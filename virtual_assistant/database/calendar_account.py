from datetime import datetime, timezone
from sqlalchemy import and_

from virtual_assistant.database.database import db
from virtual_assistant.utils.logger import logger


class CalendarAccount(db.Model):
    """Model for storing calendar account credentials and metadata."""
    
    id = db.Column(db.Integer, primary_key=True)
    calendar_email = db.Column(db.String(120), nullable=False)  # The specific calendar account email (e.g. google account email)
    app_user_email = db.Column(db.String(120), nullable=False)  # The app user's email
    provider = db.Column(db.String(50), nullable=False)  # 'google' or 'o365'
    token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text)
    token_uri = db.Column(db.String(200))
    client_id = db.Column(db.String(200))
    client_secret = db.Column(db.String(200))
    scopes = db.Column(db.Text)
    last_sync = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (db.UniqueConstraint('calendar_email', 'provider', name='_calendar_email_provider_uc'),)

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
    def get_accounts_for_user(cls, app_user_email):
        """Get all calendar accounts for a specific app user."""
        return cls.query.filter_by(app_user_email=app_user_email).all()

    def save(self):
        """Save the calendar account to the database."""
        db.session.add(self)
        db.session.commit()

    @classmethod
    def delete_by_email_and_provider(cls, calendar_email, provider):
        """Delete calendar account by calendar email and provider."""
        account = cls.get_by_email_and_provider(calendar_email, provider)
        if account:
            db.session.delete(account)
            db.session.commit()

    def update_last_sync(self):
        """Update the last sync timestamp."""
        try:
            self.last_sync = datetime.now(timezone.utc)
            db.session.commit()
            logger.info(f"Updated last sync for {self.calendar_email} ({self.provider})")
            return True
        except Exception as e:
            logger.error(f"Error updating last sync: {e}")
            db.session.rollback()
            return False

from datetime import datetime, timezone
from sqlalchemy import and_, update
from sqlalchemy.orm import relationship
import uuid

from virtual_assistant.database.database import db
from virtual_assistant.database.user import MySQLUUID
from virtual_assistant.utils.logger import logger


class CalendarAccount(db.Model):
    """Model for storing calendar account credentials and metadata."""
    
    __tablename__ = 'calendar_account'
    
    id = db.Column(MySQLUUID, primary_key=True, default=uuid.uuid4)
    calendar_email = db.Column(db.String(255), nullable=False)  # The specific calendar account email (e.g. google account email)
    user_id = db.Column(MySQLUUID, db.ForeignKey('user.id'), nullable=False)
    provider = db.Column(db.String(50), nullable=False)  # 'google' or 'o365'
    token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text)
    token_uri = db.Column(db.String(255))
    client_id = db.Column(db.String(255))
    client_secret = db.Column(db.String(255))
    scopes = db.Column(db.Text)
    is_primary = db.Column(db.Boolean, default=False)  # Whether this is the user's primary calendar account
    last_sync = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    needs_reauth = db.Column(db.Boolean, nullable=False, default=False)

    # Define the relationship to the User model
    user = relationship("User", back_populates="calendar_accounts")

    __table_args__ = (
        db.UniqueConstraint('user_id', 'calendar_email', 'provider',
                          name='uq_calendar_account_user_id_provider'),
    )

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
    def get_by_email_provider_and_user(cls, calendar_email, provider, user_id):
        """Get calendar account by calendar email, provider, and user ID."""
        return cls.query.filter_by(
            calendar_email=calendar_email,
            provider=provider,
            user_id=user_id
        ).first()

    @classmethod
    def get_accounts_for_user(cls, user_id):
        """Get all calendar accounts for a specific user."""
        return cls.query.filter_by(user_id=user_id).all()

    def save(self):
        """Save the calendar account to the database."""
        db.session.add(self)
        db.session.commit()

    @classmethod
    def delete_by_email_and_provider(cls, calendar_email, provider, user_id):
        """Delete calendar account by calendar email, provider, and user ID."""
        account = cls.get_by_email_provider_and_user(calendar_email, provider, user_id)
        if not account:
            raise ValueError(f"No calendar account found for {calendar_email} ({provider}) for user ID {user_id}")
        
        db.session.delete(account)
        db.session.commit()

    def update_last_sync(self):
        """Update the last sync timestamp."""
        self.last_sync = datetime.now(timezone.utc)
        db.session.commit()
        
    @classmethod
    def set_as_primary(cls, calendar_email, provider, user_id):
        """Set a calendar account as the primary account for a user.
        
        This will unset any other account that was previously set as primary.
        
        Args:
            calendar_email: The email of the calendar account to set as primary
            provider: The provider of the calendar account
            user_id: The ID of the app user
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # First, unset any existing primary account for this user
            db.session.execute(
                update(cls)
                .where(cls.user_id == user_id)
                .values(is_primary=False)
            )
            
            # Then set the specified account as primary
            account = cls.get_by_email_provider_and_user(
                calendar_email, provider, user_id
            )
            if account:
                account.is_primary = True
                db.session.commit()
                logger.info(f"Set {calendar_email} ({provider}) as primary calendar for user ID {user_id}")
                return True
            else:
                logger.error(f"Account not found: {calendar_email} ({provider}) for user ID {user_id}")
                return False
        except Exception as e:
            logger.error(f"Error setting primary calendar account: {e}")
            db.session.rollback()
            return False
            
    @classmethod
    def set_as_primary_by_id(cls, account_id, user_id):
        """Set a calendar account as the primary account for a user using the account ID.
        
        This will unset any other account that was previously set as primary.
        
        Args:
            account_id: The ID of the calendar account to set as primary
            user_id: The ID of the app user
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # First, unset any existing primary account for this user
            db.session.execute(
                update(cls)
                .where(cls.user_id == user_id)
                .values(is_primary=False)
            )
            
            # Then set the specified account as primary
            account = cls.query.filter_by(id=account_id, user_id=user_id).first()
            if account:
                account.is_primary = True
                db.session.commit()
                logger.info(f"Set calendar account ID {account_id} as primary for user ID {user_id}")
                return True
            else:
                logger.error(f"Calendar account ID {account_id} not found for user ID {user_id}")
                return False
        except Exception as e:
            logger.error(f"Error setting primary calendar account: {e}")
            db.session.rollback()
            return False
            
    @classmethod
    def get_primary_account(cls, user_id):
        """Get the primary calendar account for a user.
        
        If no account is explicitly set as primary, returns the first account found.
        
        Args:
            user_id: The ID of the app user
            
        Returns:
            CalendarAccount: The primary calendar account, or None if no accounts exist
        """
        # First try to find an account explicitly set as primary
        primary = cls.query.filter_by(
            user_id=user_id,
            is_primary=True
        ).first()
        
        if primary:
            return primary
            
        # If no account is explicitly set as primary, return the first account
        return cls.query.filter_by(user_id=user_id).first()
        
    @classmethod
    def get_accounts_by_last_sync(cls, older_than=None):
        """Get calendar accounts that were last synced before the given time.
        
        Args:
            older_than: datetime, only return accounts last synced before this time
            
        Returns:
            list: List of CalendarAccount objects matching the criteria
        """
        if older_than is None:
            return cls.query.all()
            
        return cls.query.filter(
            cls.last_sync < older_than
        ).all()

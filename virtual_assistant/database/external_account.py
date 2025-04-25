from datetime import datetime, timezone
from sqlalchemy import and_, update
from sqlalchemy.orm import relationship
import uuid

from virtual_assistant.database.database import db
from virtual_assistant.database.user import MySQLUUID
from virtual_assistant.utils.logger import logger


class ExternalAccount(db.Model):
    """Model for managing all external service accounts (Google, O365, Todoist)."""
    
    __tablename__ = 'external_account'
    
    id = db.Column(MySQLUUID, primary_key=True, default=uuid.uuid4)
    account_email = db.Column(db.String(255), nullable=False)
    user_id = db.Column(MySQLUUID, db.ForeignKey('user.id'), nullable=False)
    provider = db.Column(db.String(50), nullable=False)  # 'google', 'o365', 'todoist'
    token = db.Column(db.Text)  # For OAuth access tokens
    api_key = db.Column(db.Text)  # For API key authentication
    refresh_token = db.Column(db.Text)
    token_uri = db.Column(db.String(255))
    client_id = db.Column(db.String(255))
    client_secret = db.Column(db.String(255))
    scopes = db.Column(db.Text)
    is_primary_calendar = db.Column(db.Boolean, default=False)
    is_primary_tasks = db.Column(db.Boolean, default=False)
    last_sync = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    needs_reauth = db.Column(db.Boolean, nullable=False, default=False)
    use_for_calendar = db.Column(db.Boolean, nullable=False, default=False)
    use_for_tasks = db.Column(db.Boolean, nullable=False, default=False)
    
    # Relationships
    user = relationship("User", back_populates="external_accounts")
    
    def __init__(self, account_email, provider, **kwargs):
        self.account_email = account_email
        self.provider = provider
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        return f"<ExternalAccount {self.account_email} ({self.provider})>"

    @classmethod
    def get_by_email_and_provider(cls, account_email, provider):
        """Get account by email and provider."""
        return cls.query.filter_by(account_email=account_email, provider=provider).first()
        
    @classmethod
    def get_by_email_provider_and_user(cls, account_email, provider, user_id):
        """Get account by email, provider, and user ID."""
        return cls.query.filter_by(
            account_email=account_email,
            provider=provider,
            user_id=user_id
        ).first()

    @classmethod
    def get_accounts_for_user(cls, user_id):
        """Get all accounts for a specific user."""
        return cls.query.filter_by(user_id=user_id).all()

    def save(self):
        """Save the account to the database."""
        db.session.add(self)
        db.session.commit()

    @classmethod
    def delete_by_email_and_provider(cls, account_email, provider, user_id):
        """Delete account by email, provider, and user ID."""
        account = cls.get_by_email_provider_and_user(account_email, provider, user_id)
        if not account:
            raise ValueError(f"No account found for {account_email} ({provider}) for user ID {user_id}")
        
        db.session.delete(account)
        db.session.commit()

    def update_last_sync(self):
        """Update the last sync timestamp."""
        self.last_sync = datetime.now(timezone.utc)
        db.session.commit()
        
    @classmethod
    def set_as_primary(cls, account_email, provider, user_id, account_type):
        """Set an account as the primary account for a user for either calendar or tasks.
        
        Args:
            account_email: Email of the account
            provider: Provider name ('google', 'o365', 'todoist')
            user_id: User ID
            account_type: Must be either 'calendar' or 'tasks'
        """
        if account_type not in ('calendar', 'tasks'):
            logger.error(f"Invalid account_type: {account_type}")
            raise ValueError("account_type must be 'calendar' or 'tasks'")

        account = cls.get_by_email_provider_and_user(account_email, provider, user_id)
        if not account:
            logger.error(f"Account not found: {account_email} ({provider}) for user ID {user_id}")
            raise ValueError("Account not found")

        try:
            # Unset existing primary account of this type
            if account_type == 'calendar':
                db.session.execute(
                    update(cls)
                    .where(cls.user_id == user_id)
                    .values(is_primary_calendar=False)
                )
                account.is_primary_calendar = True
            else:
                db.session.execute(
                    update(cls)
                    .where(cls.user_id == user_id)
                    .values(is_primary_tasks=False)
                )
                account.is_primary_tasks = True

            db.session.commit()
            logger.info(f"Set {account_email} ({provider}) as primary {account_type} account for user ID {user_id}")
        except Exception as e:
            logger.error(f"Error setting primary {account_type} account: {e}")
            db.session.rollback()
            raise
            
    @classmethod
    def get_primary_account(cls, user_id, account_type):
        """Get the primary account for a user for either calendar or tasks.
        
        Args:
            user_id: User ID
            account_type: Must be either 'calendar' or 'tasks'
        """
        if account_type not in ('calendar', 'tasks'):
            raise ValueError("account_type must be 'calendar' or 'tasks'")

        if account_type == 'calendar':
            return cls.query.filter_by(
                user_id=user_id,
                is_primary_calendar=True
            ).first()
        else:
            return cls.query.filter_by(
                user_id=user_id,
                is_primary_tasks=True
            ).first()
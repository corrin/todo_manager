import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, update
from sqlalchemy.orm import relationship

from virtual_assistant.database.database import db
from virtual_assistant.database.user import MySQLUUID
from virtual_assistant.utils.logger import logger

# Maps task provider names (used in task routes/providers) to ExternalAccount provider names
TASK_PROVIDER_MAP = {"todoist": "todoist", "google_tasks": "google", "outlook": "o365"}
# Reverse mapping: ExternalAccount provider names to task provider names
PROVIDER_TO_TASK = {"todoist": "todoist", "google": "google_tasks", "o365": "outlook"}


class ExternalAccount(db.Model):
    """Model for managing all external service accounts (Google, O365, Todoist)."""

    __tablename__ = "external_account"

    id = db.Column(MySQLUUID, primary_key=True, default=uuid.uuid4)
    external_email = db.Column(db.String(255), nullable=False)
    user_id = db.Column(MySQLUUID, db.ForeignKey("app_user.id"), nullable=False)
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
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    expires_at = db.Column(db.DateTime, nullable=True)
    needs_reauth = db.Column(db.Boolean, nullable=False, default=False)
    use_for_calendar = db.Column(db.Boolean, nullable=False, default=False)
    use_for_tasks = db.Column(db.Boolean, nullable=False, default=False)

    # Relationships
    user = relationship("User", back_populates="external_accounts")

    def __init__(self, external_email, provider, **kwargs):
        self.external_email = external_email
        self.provider = provider
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        return f"<ExternalAccount {self.external_email} ({self.provider})>"

    @classmethod
    def get_by_email_and_provider(cls, external_email, provider):
        """Get account by email and provider."""
        return cls.query.filter_by(external_email=external_email, provider=provider).first()

    @classmethod
    def get_by_email_provider_and_user(cls, external_email, provider, user_id):
        """Get account by email, provider, and user ID."""
        return cls.query.filter_by(external_email=external_email, provider=provider, user_id=user_id).first()

    @classmethod
    def get_accounts_for_user(cls, user_id):
        """Get all accounts for a specific user."""
        return cls.query.filter_by(user_id=user_id).all()

    def save(self):
        """Save the account to the database."""
        db.session.add(self)
        db.session.commit()

    @classmethod
    def delete_by_email_and_provider(cls, external_email, provider, user_id):
        """Delete account by email, provider, and user ID."""
        account = cls.get_by_email_provider_and_user(external_email, provider, user_id)
        if not account:
            raise ValueError(f"No account found for {external_email} ({provider}) for user ID {user_id}")

        db.session.delete(account)
        db.session.commit()

    def update_last_sync(self):
        """Update the last sync timestamp."""
        self.last_sync = datetime.now(timezone.utc)
        db.session.commit()

    @classmethod
    def set_as_primary(cls, external_email, provider, user_id, account_type):
        """Set an account as the primary account for a user for either calendar or tasks.

        Args:
            external_email: Email of the account
            provider: Provider name ('google', 'o365', 'todoist')
            user_id: User ID
            account_type: Must be either 'calendar' or 'tasks'
        """
        if account_type not in ("calendar", "tasks"):
            logger.error(f"Invalid account_type: {account_type}")
            raise ValueError("account_type must be 'calendar' or 'tasks'")

        account = cls.get_by_email_provider_and_user(external_email, provider, user_id)
        if not account:
            logger.error(f"Account not found: {external_email} ({provider}) for user ID {user_id}")
            raise ValueError("Account not found")

        try:
            # Unset existing primary account of this type
            if account_type == "calendar":
                db.session.execute(update(cls).where(cls.user_id == user_id).values(is_primary_calendar=False))
                account.is_primary_calendar = True
            else:
                db.session.execute(update(cls).where(cls.user_id == user_id).values(is_primary_tasks=False))
                account.is_primary_tasks = True

            db.session.commit()
            logger.info(f"Set {external_email} ({provider}) as primary {account_type} account for user ID {user_id}")
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
        if account_type not in ("calendar", "tasks"):
            raise ValueError("account_type must be 'calendar' or 'tasks'")

        if account_type == "calendar":
            return cls.query.filter_by(user_id=user_id, is_primary_calendar=True).first()
        else:
            return cls.query.filter_by(user_id=user_id, is_primary_tasks=True).first()

    # --- Task Account helper methods (replacing TaskAccount model) ---

    @classmethod
    def get_task_account(cls, user_id, provider_name, task_user_email):
        """Get a task account by resolving the task provider name to ExternalAccount provider.

        Args:
            user_id: The user's database ID
            provider_name: Task provider name ('todoist', 'google_tasks', 'outlook')
            task_user_email: The email/identifier for the account
        """
        ea_provider = TASK_PROVIDER_MAP.get(provider_name, provider_name)
        return cls.query.filter_by(
            user_id=user_id,
            provider=ea_provider,
            external_email=task_user_email,
            use_for_tasks=True,
        ).first()

    @classmethod
    def set_task_account(cls, user_id, provider_name, task_user_email, credentials):
        """Create or update a task account on ExternalAccount.

        Args:
            user_id: The user's database ID
            provider_name: Task provider name ('todoist', 'google_tasks', 'outlook')
            task_user_email: The email/identifier for the account
            credentials: Dict with keys like 'api_key', 'token', 'refresh_token', 'expires_at', 'scopes', 'needs_reauth'

        Returns:
            ExternalAccount: The created/updated account (caller should commit)
        """
        ea_provider = TASK_PROVIDER_MAP.get(provider_name, provider_name)

        account = cls.query.filter_by(user_id=user_id, provider=ea_provider, external_email=task_user_email).first()

        if not account:
            account = cls(external_email=task_user_email, provider=ea_provider, user_id=user_id)
            db.session.add(account)

        # Update credential fields
        account.api_key = credentials.get("api_key", account.api_key)
        account.token = credentials.get("token", account.token)
        account.refresh_token = credentials.get("refresh_token", account.refresh_token)
        account.expires_at = credentials.get("expires_at", account.expires_at)
        account.scopes = credentials.get("scopes", account.scopes)
        account.needs_reauth = credentials.get("needs_reauth", False)
        account.use_for_tasks = True

        # Auto-set as primary tasks if no primary exists
        has_primary = cls.query.filter_by(user_id=user_id, is_primary_tasks=True).first() is not None
        if not has_primary:
            account.is_primary_tasks = True
            logger.info(f"Setting {ea_provider} account for user {user_id} as primary tasks (no primary exists)")

        return account

    @classmethod
    def delete_task_account(cls, user_id, provider_name, task_user_email):
        """Delete a task account. If also used for calendar, just clear use_for_tasks.

        Args:
            user_id: The user's database ID
            provider_name: Task provider name ('todoist', 'google_tasks', 'outlook')
            task_user_email: The email/identifier for the account

        Returns:
            bool: True if found and handled
        """
        ea_provider = TASK_PROVIDER_MAP.get(provider_name, provider_name)
        account = cls.query.filter_by(user_id=user_id, provider=ea_provider, external_email=task_user_email).first()

        if not account:
            return False

        if account.use_for_calendar:
            # Keep the row but disable tasks
            account.use_for_tasks = False
            account.is_primary_tasks = False
        else:
            db.session.delete(account)

        return True

    @classmethod
    def get_task_accounts_for_user(cls, user_id):
        """Get all active task accounts for a user.

        Returns accounts that have use_for_tasks=True and are not needing reauth,
        with appropriate credentials present.
        """
        return (
            cls.query.filter(
                cls.user_id == user_id,
                cls.use_for_tasks == True,
                cls.needs_reauth == False,
                db.or_(
                    db.and_(cls.provider == "todoist", cls.api_key != None),
                    db.and_(cls.provider.in_(["google", "o365"]), cls.token != None),
                ),
            )
            .order_by(cls.provider, cls.external_email)
            .all()
        )

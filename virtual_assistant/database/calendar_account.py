from datetime import datetime
from sqlalchemy import Column, ForeignKey, Integer, String, DateTime
from sqlalchemy import and_

from virtual_assistant.database.database import Database
from virtual_assistant.utils.logger import logger


class CalendarAccount(Database.Model):
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    email_address = Column(String(120), nullable=False)
    provider = Column(String(50), nullable=False)
    authentication_credentials = Column(String, nullable=False, json=True)
    last_sync = Column(DateTime, nullable=True)

    def __init__(self, user_id, email_address, provider, credentials):
        self.user_id = user_id
        self.email_address = email_address
        self.provider = provider
        self.authentication_credentials = credentials
        self.last_sync = None

    def __repr__(self):
        return f"<CalendarAccount {self.email_address}>"

    @classmethod
    def get_by_email_and_provider(cls, email, provider):
        """Get a calendar account by email and provider."""
        try:
            return cls.query.filter(
                and_(
                    cls.email_address == email,
                    cls.provider == provider
                )
            ).first()
        except Exception as e:
            logger.error(f"Error getting calendar account: {e}")
            return None

    @classmethod
    def delete_by_email_and_provider(cls, email, provider):
        """Delete a calendar account by email and provider."""
        try:
            account = cls.get_by_email_and_provider(email, provider)
            if account:
                Database.session.delete(account)
                Database.session.commit()
                logger.info(f"Deleted calendar account for {email} ({provider})")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting calendar account: {e}")
            Database.session.rollback()
            return False

    def update_last_sync(self):
        """Update the last sync timestamp."""
        try:
            self.last_sync = datetime.utcnow()
            Database.session.commit()
            logger.info(f"Updated last sync for {self.email_address} ({self.provider})")
            return True
        except Exception as e:
            logger.error(f"Error updating last sync: {e}")
            Database.session.rollback()
            return False

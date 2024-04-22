from sqlalchemy import Column, ForeignKey, Integer, String

from virtual_assistant.database.database import Database


class CalendarAccount(Database.Model):
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    email_address = Column(String(120), nullable=False)
    provider = Column(String(50), nullable=False)
    authentication_credentials = Column(String, nullable=False, json=True)

    def __init__(self, user_id, email_address, provider, credentials):
        self.user_id = user_id
        self.email_address = email_address
        self.provider = provider
        self.authentication_credentials = credentials

    def __repr__(self):
        return f"<CalendarAccount {self.email_address}>"

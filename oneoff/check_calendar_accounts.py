"""
One-off script to check the current calendar accounts in the database.
"""

import os
import sys

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from virtual_assistant.database.database import db
from virtual_assistant.database.calendar_account import CalendarAccount
from virtual_assistant.utils.settings import Settings
from flask import Flask

def main():
    """Check the current calendar accounts in the database."""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = Settings.DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    
    with app.app_context():
        print('Current calendar accounts:')
        accounts = CalendarAccount.query.all()
        for account in accounts:
            print(f'- {account.calendar_email} ({account.provider}) for user {account.app_user_email}')

if __name__ == '__main__':
    main()
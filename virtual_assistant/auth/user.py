from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask import Flask

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(UserMixin, db.Model):
    id = db.Column(db.String(120), primary_key=True)  # Use email as primary key
    username = db.Column(db.String(80), unique=True, nullable=False)
    calendar_accounts = db.Column(db.String(500))  # JSON string of calendar accounts

    def __repr__(self):
        return f'<User {self.username}>'

    @property
    def calendar_account_list(self):
        import json
        try:
            return json.loads(self.calendar_accounts)
        except (TypeError, ValueError):
            return []

    @calendar_account_list.setter
    def calendar_account_list(self, accounts):
        import json
        self.calendar_accounts = json.dumps(accounts)

    def get_id(self):
        """Override to return the user identifier for Flask-Login"""
        return self.id

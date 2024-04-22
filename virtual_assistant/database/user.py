from flask import Flask
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class User(UserMixin, db.Model):
    id = db.Column(db.String(120), primary_key=True)  # Use email as primary key
    username = db.Column(db.String(80), unique=True, nullable=False)
    calendar_accounts = db.relationship('CalendarAccount', backref='user', lazy=True)

    def __repr__(self):
        return f"<User {self.username}>"

    def get_id(self):
        """Override to return the user identifier for Flask-Login"""
        return self.id
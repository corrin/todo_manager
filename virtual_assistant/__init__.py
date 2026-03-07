from flask import Flask
from flask_migrate import Migrate

from virtual_assistant.database.database import db

migrate = Migrate()


def create_app():
    """Application factory for virtual assistant"""
    app = Flask(__name__)
    app.config.from_pyfile("settings.py")

    db.init_app(app)
    migrate.init_app(app, db)

    return app

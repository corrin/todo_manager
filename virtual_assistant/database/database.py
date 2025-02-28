# db_setup.py
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from flask_migrate import Migrate

from virtual_assistant.utils.logger import logger

# Create a single, centralized SQLAlchemy instance
db = SQLAlchemy()
migrate = Migrate()

class Database:
    """
    Database singleton class that wraps SQLAlchemy functionality.
    """
    _instance = None
    # Class-level attributes to expose SQLAlchemy components
    Model = db.Model
    session = db.session
    
    def __init__(self):
        if Database._instance is not None:
            raise Exception("This class is a singleton!")
        else:
            Database._instance = self
            self._db = db  # Use the shared SQLAlchemy instance

    def test_sqlite(self):
        logger.info("Test SQLite called")
        try:
            result = db.session.execute(text("SELECT 1"))
            for row in result:
                logger.info(f"Database test result: {row}")
            return "Database connected!"
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return f"Database connection failed: {e}"

    def __repr__(self):
        return f"Database(instance={self._db})"

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()  # Create an instance if one doesn't exist
        return cls._instance

    @classmethod
    def init_app(cls, app):
        """Initialize the database with the Flask app"""
        from virtual_assistant.utils.settings import Settings
        import os
        
        # Ensure the database directory exists
        db_dir = os.path.dirname(Settings.DATABASE_URI.replace('sqlite:///', ''))
        os.makedirs(db_dir, exist_ok=True)
        
        # Configure SQLAlchemy
        app.config['SQLALCHEMY_DATABASE_URI'] = Settings.DATABASE_URI
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Initialize database and migrations
        db.init_app(app)
        migrate.init_app(app, db)

    def add(self, model):
        db.session.add(model)

    def commit(self):
        db.session.commit()

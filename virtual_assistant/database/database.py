# db_setup.py
from flask import Blueprint
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text

from virtual_assistant.utils.logger import logger


class Database:
    
    _instance = None

    def __init__(self):
        if Database._instance is not None:
            raise Exception("This class is a singleton!")
        else:
            Database._instance = self
            self._db = SQLAlchemy()
            self.blueprint = Blueprint("database", __name__, url_prefix="/database")


    def test_sqlite(self):
        logger.info("Test SQLite called")
        try:
            result = self._db.session.execute(text("SELECT 1"))
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
        return cls._instance
    
    @staticmethod
    def init_app(app):
        database = Database()
        database._db.init_app(app)
        database.blueprint.route("/test_sqlite", methods=["GET"])(database.test_sqlite)
        app.register_blueprint(database.blueprint)


    def add(self, model):
        self._db.session.add(model)

    def commit(self):
        self._db.session.commit()

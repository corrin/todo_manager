import os

from sqlalchemy import create_engine, text

from virtual_assistant.utils.logger import logger

# Get database URI from environment
db_uri = os.getenv("SQLALCHEMY_DATABASE_URI")

try:
    engine = create_engine(db_uri)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        logger.info(f"Database connection successful: {result.scalar()}")
except Exception as e:
    logger.error(f"Database connection failed: {e}")
    raise

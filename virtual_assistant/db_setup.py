# db_setup.py
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from models import Base

engine = create_engine("sqlite:///virtual_assistant.db")
Base.metadata.create_all(engine)  # Assuming your models are defined in 'models.py'

if __name__ == "__main__":
    Base.metadata.create_all(engine)
    print("Database setup complete.")

# db/user_storage.py
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from virtual_assistant.database.user import Base, User

engine = create_engine("sqlite:///virtual_assistant.db")
Base.metadata.create_all(engine)

db_session = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, bind=engine)
)


def store_user_data(user_data):
    user = User(id=user_data["id"], username=user_data["username"])
    db_session.add(user)
    db_session.commit()


def get_user_data(user_id):
    return db_session.query(User).get(user_id)

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
engine = create_engine(os.getenv("SQLALCHEMY_DATABASE_URI"))
with engine.connect() as conn:
    result = conn.execute(text("SHOW TABLES"))
    print("Existing tables:")
    for row in result:
        print(row[0])

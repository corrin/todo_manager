import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('SQLALCHEMY_DATABASE_URI'))
with engine.connect() as conn:
    result = conn.execute(text('SHOW TABLES'))
    print("Existing tables:")
    for row in result:
        print(row[0])
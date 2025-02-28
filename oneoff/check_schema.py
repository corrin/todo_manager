import os
import sys

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from virtual_assistant.flask_app import app
from virtual_assistant.database.database import db
from sqlalchemy import inspect

with app.app_context():
    inspector = inspect(db.engine)
    print('Tables:', inspector.get_table_names())
    
    for table in inspector.get_table_names():
        print(f'\nTable: {table}')
        print('Columns:')
        for column in inspector.get_columns(table):
            print(f'  {column}')
        
        print('Foreign Keys:')
        for fk in inspector.get_foreign_keys(table):
            print(f'  {fk}')
        
        print('Constraints:')
        for constraint in inspector.get_unique_constraints(table):
            print(f'  {constraint}')
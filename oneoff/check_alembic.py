from virtual_assistant.flask_app import app
from virtual_assistant.database.database import db

with app.app_context():
    result = db.session.execute('SELECT version_num FROM alembic_version')
    print("Current migration version:")
    for row in result:
        print(row[0])
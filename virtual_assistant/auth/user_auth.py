from flask_login import LoginManager

from virtual_assistant.database.user import User
from virtual_assistant.database.database import db

# Instantiate the LoginManager
login_manager = LoginManager()
# Set the view function name for login. Unauthenticated users attempting
# to access @login_required routes will be redirected here.
login_manager.login_view = "new_user"


def setup_login_manager(app):
    login_manager.init_app(app)


# User loader callback. This is called by Flask-Login to reload the user object
# from the user ID stored in the session.
@login_manager.user_loader
def load_user(user_id):
    # Since user_id is just the primary key of our user table, use it directly.
    return User.query.get(int(user_id))

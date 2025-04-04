from flask_login import LoginManager

from virtual_assistant.database.user import User
from virtual_assistant.database.database import db

# Instantiate the LoginManager
login_manager = LoginManager()
login_manager.login_view = "login"  # This should redirect to your login route


def setup_login_manager(app):
    login_manager.init_app(app)


# Define the user loader function directly in the module scope
@login_manager.user_loader
def load_user(app_login):
    # Check if the user exists in the database
    user = User.query.filter_by(app_login=app_login).first()
    
    # If the user doesn't exist, create it
    if not user:
        user = User(app_login)
        db.session.add(user)
        db.session.commit()
    return user

from flask_login import LoginManager
from virtual_assistant.users.user import User  # Adjust the import path as necessary

# Instantiate the LoginManager
login_manager = LoginManager()
login_manager.login_view = 'login'  # This should redirect to your login route

def setup_login_manager(app):
    login_manager.init_app(app)

# Define the user loader function directly in the module scope
@login_manager.user_loader
def load_user(user_id):
    # All authenticated Google users are valid
    return User(user_id)

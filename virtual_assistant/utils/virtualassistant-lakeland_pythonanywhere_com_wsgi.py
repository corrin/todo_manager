# This file contains the WSGI configuration required to serve up your
# web application at http://<your-username>.pythonanywhere.com/
# It works by setting the variable 'application' to a WSGI handler of some
# description.
#
# The below has been auto-generated for your Flask project


import sys
import os

# add your project directory to the sys.path
project_home = "/home/lakeland/virtual_assistant"
if project_home not in sys.path:
    sys.path = [project_home] + sys.path


# Activate the virtual environment
# Path to the virtualenv you want to use
activate_env = os.path.expanduser(
    "/home/lakeland/.virtualenvs/virtual_assistant/bin/activate_this.py"
)
# Execute the script to activate the virtual environment
with open(activate_env) as file_:
    exec(file_.read(), dict(__file__=activate_env))

# Path to your .env file
env_path = "/home/lakeland/virtual_assistant/.env"

# Check if the .env file exists
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            # Parse each line as an environment variable
            if "=" in line:
                # Remove leading/trailing whitespace, split by first '=', and strip each part
                key, value = map(str.strip, line.split("=", 1))
                os.environ[key] = value


# import flask app but need to call it "application" for WSGI to work
from flask_app import app as application  # noqa

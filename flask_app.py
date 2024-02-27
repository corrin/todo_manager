import platform
import pkg_resources  # part of setuptools
from flask import Flask

from dotenv import load_dotenv
load_dotenv()  # take environment variables from .env.

from openai_module import openai_blueprint


app = Flask(__name__)
app.register_blueprint(openai_blueprint, url_prefix='/openai')



@app.route('/')
def hello_world():
    return 'Hello from Flask!'

@app.route('/versions')
def show_versions():
    python_version = platform.python_version()
    installed_packages = ['Flask', 'requests']  # Add any packages you've installed in the venv
    versions_info = f"Python Version: {python_version}\n"

    for package in installed_packages:
        version = pkg_resources.get_distribution(package).version
        versions_info += f"{package} Version: {version}\n"

    return versions_info


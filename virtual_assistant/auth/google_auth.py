"""
Google Auth module for handling Google OAuth authentication
"""

from authlib.integrations.flask_client import OAuth
from flask import redirect, request, url_for
from flask_login import login_user
from requests.exceptions import RequestException

from virtual_assistant.auth.auth_provider import AuthProvider
from virtual_assistant.utils.logger import logger
from virtual_assistant.utils.settings import Settings
from virtual_assistant.utils.user_manager import UserManager


class GoogleAuth(AuthProvider):
    """
    Google Auth class for handling Google OAuth authentication
    """

    def __init__(self, app):
        """
        Initialize the Google Auth instance

        Args:
            app (Flask): The Flask application instance
        """
        oauth = OAuth(app)
        self.google = oauth.register(
            name="google",
            client_id=Settings.GOOGLE_CLIENT_ID,
            client_secret=Settings.GOOGLE_CLIENT_SECRET,
            access_token_url="https://accounts.google.com/o/oauth2/token",
            authorize_url="https://accounts.google.com/o/oauth2/auth",
            api_base_url="https://www.googleapis.com/oauth2/v1/",
            client_kwargs={"scope": "email profile"},
        )
        logger.info("Google Auth initialized")

    def authenticate(self, email=None):
        """
        Redirect the user to the Google authorization page

        Args:
            email (str): The user's email address

        Returns:
            redirect: The redirect response to the Google authorization page
        """
        redirect_uri = url_for("authorize", _external=True)
        return self.google.authorize_redirect(redirect_uri)

    def authorize(self):
        """
        Handle the Google authorization callback

        Returns:
            redirect: The redirect response to the main application page
        """
        try:
            token = self.google.authorize_access_token(redirect_uri=request.url)
            if not token:
                logger.error("Token acquisition failed")
                return redirect(url_for("login"))

            user_info = self.google.get_user_info(token)
            user = UserManager.get_current_user()

            if not user:
                user = UserManager.create_user(user_info)
                logger.info("New user created")
            else:
                logger.info("Existing user logged in")

            login_user(user, remember=True)
            return redirect(url_for("main_app"))
        except RequestException as error:
            logger.error(f"Error during authorization: {str(error)}")
            return redirect(url_for("login"))
        except ValueError as error:
            logger.error(f"Error during authorization: {str(error)}")
            return redirect(url_for("login"))

    def get_credentials(self, email):
        """
        Retrieve the stored credentials for the given email

        Args:
            email (str): The user's email address

        Returns:
            dict: The stored credentials
        """
        return UserManager.get_credentials(email)

    def store_credentials(self, email, credentials):
        """
        Store the credentials for the given email

        Args:
            email (str): The user's email address
            credentials (dict): The credentials to store
        """
        UserManager.save_credentials(email, credentials)

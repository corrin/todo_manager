"""
Google Auth module for handling Google OAuth authentication
"""

from google.oauth2 import id_token
from google.auth.transport import requests

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
        redirect_uri = Settings.LOGIN_REDIRECT_URI
        return self.google.authorize_redirect(redirect_uri)

    def authorize():
        # Get the authorization header from the request
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return "Missing Authorization header", 401

        # Extract the token from the header (assuming "Bearer" scheme)
        try:
            token = auth_header.split(' ')[1]
        except IndexError:
            return "Invalid Authorization header format", 401

        # Verify the token and get the user's email address
        try:
            idinfo = id_token.verify_oauth2_token(token, requests.Request(), CLIENT_ID)
            email = idinfo['email']  # Extract the email address
        except ValueError:
            return "Invalid token", 401

        # Now you have the email address in the 'email' variable
        # You can use this email to identify the user and proceed accordingly
        # For example:
        user_manager = UserManager()  # Assuming you have an instance of UserManager
        user_manager.set_user(email)  # Assuming you have a set_user method in UserManager
        return "User authorized", 200  # Replace with appropriate response


    # def authorize(self):
    #     """
    #     Handle the Google authorization callback

    #     Returns:
    #         redirect: The redirect response to the main application page
    #     """
    #     logger.info("Authorize method called")
    #     # Get the authorization code from the request
    #     code = request.args.get("code")

    #     # Exchange the authorization code for an access token
    #     token_url, headers, body = self.google.authorize_token_url(
    #         code, redirect_uri=request.url
    #     )
    #     token_response = requests.post(
    #         token_url,
    #         headers=headers,
    #         data=body,
    #         auth=(self.client_id, self.client_secret),
    #     )

    #     # Get the user's email address from the People API
    #     people_api_url = "(link unavailable)"
    #     people_response = requests.get(
    #         people_api_url,
    #         headers={
    #             "Authorization": f'Bearer {token_response.json()["access_token"]}'
    #         },
    #     )
    #     email = people_response.json()["emailAddresses"][0]["value"]

    #     # Do something with the email address, such as storing it in a session or database
    #     session["email"] = email

    #     # Redirect to the main application page
    #     return redirect(url_for("main"))

    #     try:
    #         token = self.google.authorize_access_token()
    #         logger.info(f"Authorize token: {token}")
    #         if not token:
    #             logger.error("Token acquisition failed")
    #             return redirect(url_for("login"))

    #         user_info = self.google.get_user_info(token)
    #         user = UserManager.get_current_user()

    #         logger.info(f"User Info: {user_info}")
    #         logger.info(f"User: {user}")

    #         if not user:
    #             user = UserManager.create_user(user_info)
    #             logger.info("New user created")
    #         else:
    #             logger.info("Existing user logged in")

    #         login_user(user, remember=True)
    #         return redirect(url_for("main_app"))
    #     except RequestException as error:
    #         logger.error(f"Error during authorization: {str(error)}")
    #         return redirect(url_for("login"))
    #     except ValueError as error:
    #         logger.error(f"Error during authorization: {str(error)}")
    #         return redirect(url_for("login"))

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

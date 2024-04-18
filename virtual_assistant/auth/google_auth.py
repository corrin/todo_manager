from virtual_assistant.auth.auth_provider import AuthProvider
from virtual_assistant.utils.logger import logger
from flask import url_for, redirect, session
from authlib.integrations.flask_client import OAuth
from virtual_assistant.utils.settings import Settings


class GoogleAuth(AuthProvider):
    def __init__(self, app):
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

    def authenticate(self, email=None):
        redirect_uri = url_for("authorize", _external=True)
        return self.google.authorize_redirect(redirect_uri)

    def authorize():
        token = google_auth.authorize_access_token()
        if not token:
            return redirect(
                url_for("login")
            )  # Redirect to login if token acquisition fails

        user_info = google_auth.get_user_info(token)
        user = UserManager.get_user_by_email(user_info["email"])

        if not user:
            user = UserManager.create_user(user_info)
            login_user(user, remember=True)
            return redirect(url_for("new_user_route"))  # Redirect new users to setup
        else:
            login_user(user, remember=True)
            return redirect(url_for("main_app"))  # Redirect existing users to main app

        def get_credentials(self, email):
            # Implement retrieval of stored credentials
            pass

        def store_credentials(self, email, credentials):
            # Implement storage of credentials
            pass

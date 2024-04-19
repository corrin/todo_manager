from flask import redirect, session, url_for
from flask_login import current_user

from virtual_assistant.meetings.meetings_routes import providers
from virtual_assistant.utils.logger import logger
from virtual_assistant.utils.user_manager import UserManager


def new_user():
    """
    Perform initial setup for the logged-in user's calendar providers.
    This function sets up calendar providers based on predefined settings.

    Returns:
        str: A redirect or a message indicating the completion of the setup.
    """
    # Assume the current_user is set through the login mechanism
    if not current_user.is_authenticated:
        logger.error("No user is logged in.")
        return redirect(url_for("login"))  # Ensure there is a login route

    UserManager.login(current_user.email)

    # Hardcoded list for now
    user_calendar_accounts = {
        "lakeland@gmail.com": "google",  # Assuming `email` attribute is available
        "corrin@morrissheetmetal.co.nz": "google",
        "corrin.lakeland@countdown.co.nz": "google",
        "corrin.lakeland@cmeconnect.com": "o365",
    }

    # Save or update the calendar addresses associated with the user
    UserManager.save_calendar_accounts(user_calendar_accounts)

    for email, provider_key in user_calendar_accounts.items():
        session["current_email"] = email
        provider_class = providers.get(provider_key)

        if not provider_class:
            logger.error(f"Unsupported provider {provider_key} for {email}")
            continue

        logger.info(f"Attempting setup for provider: {provider_key}, email: {email}")

        provider_instance = provider_class()
        credentials = UserManager.get_credentials(email)

        if credentials is None:
            logger.info(f"No credentials found for {email}. Initiating setup.")
            _, redirect_template = provider_instance.authenticate(email)
            if redirect_template is not None:
                logger.info(f"Redirecting to {provider_key} setup URL for {email}")
                session["current_email"] = email
                return redirect(redirect_template)
        else:
            logger.info(f"Credentials already exist for {email}. Skipping setup.")

    return redirect(url_for("new_user_complete_route"))

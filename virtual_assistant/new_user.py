from flask import session, url_for, redirect, current_user
from virtual_assistant.utils.user_manager import UserManager
from virtual_assistant.meetings.meetings_routes import providers
from virtual_assistant.utils.logger import logger


def new_user():
    """
    Perform initial setup for the logged-in user's email providers.
    This function sets up email providers based on predefined settings.

    Returns:
        str: A redirect or a message indicating the completion of the setup.
    """
    # Assume the current_user is set through the login mechanism
    if not current_user.is_authenticated:
        logger.error("No user is logged in.")
        return redirect(url_for("login"))  # Ensure there is a login route

    UserManager.set_current_user(current_user.email)

    # Hardcoded list for now
    user_calendar_accounts = {
        "lakeland@gmail.com": "google",  # Assuming `email` attribute is available
        "corrin@morrissheetmetal.co.nz": "google",
        "corrin.lakeland@countdown.co.nz": "google",
        "corrin.lakeland@cmeconnect.com": "o365",
    }

    # Save or update the email addresses associated with the user
    UserManager.save_email_addresses(email_addresses)

    for email, provider_key in email_addresses.items():
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
                return redirect_template
        else:
            logger.info(f"Credentials already exist for {email}. Skipping setup.")

    return redirect(url_for("new_user_complete_route"))

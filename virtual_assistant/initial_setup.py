"""
Module for performing initial setup and linkage between a new user and their
calendar accounts.  Currently all hardcoded, but could be converted to a form
or other web entry if needed.
"""

from flask import session, redirect, url_for

from virtual_assistant.utils.user_manager import UserManager
from virtual_assistant.meetings.meetings_routes import providers
from virtual_assistant.utils.logger import logger


def initial_setup():
    """
    Perform initial setup and authentication for email providers.
    NOTE: Only does one account at once.   Must be called recursively

    Returns:
        str: A message indicating the completion of the initial setup.
    """
    # Set the current user
    UserManager.set_current_user("lakeland@gmail.com")

    # Define the email addresses and their associated providers
    email_addresses = {
        "lakeland@gmail.com": "google",
        "corrin@morrissheetmetal.co.nz": "google",
        "corrin.lakeland@countdown.co.nz": "google",
        "corrin.lakeland@cmeconnect.com": "o365",
    }

    # Save the email addresses
    UserManager.save_email_addresses(email_addresses)

    for email, provider_key in email_addresses.items():
        session["current_email"] = email
        provider_class = providers.get(provider_key)

        if not provider_class:
            logger.error(f"Unsupported provider {provider_key} for {email}")
            continue

        logger.info(
            f"Attempting authentication for provider: {provider_key}, email: {email}"
        )

        provider_instance = provider_class()
        credentials = UserManager.get_credentials(email)

        if credentials is None:
            logger.info(f"No credentials found for {email}. Initiating authentication.")
            _, redirect_template = provider_instance.authenticate(email)
            if redirect_template is not None:
                logger.info(
                    f"Redirecting to {provider_key} authentication URL for {email}"
                )
                session["current_email"] = email
                return redirect_template
        else:
            logger.info(
                f"Credentials already exist for {email}. Skipping authentication."
            )

    return redirect(url_for("initial_setup_complete_route"))

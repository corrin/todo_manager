from virtual_assistant.utils.user_manager import UserManager
from virtual_assistant.meetings.google_calendar_provider import GoogleCalendarProvider
from virtual_assistant.meetings.o365_calendar_provider import O365CalendarProvider
from virtual_assistant.ai.ai_manager import AIManager
from virtual_assistant.tasks.task_manager import TaskManager
from virtual_assistant.utils.logger import logger


def initial_setup():
    # Set the current user
    UserManager.set_current_user("lakeland@gmail.com")

    # Define the email addresses and their associated providers
    email_addresses = {
        "lakeland@gmail.com": "google",
        "corrin@morrissheetmetal.co.nz": "google",
        "corrin.lakeland@countdown.co.nz": "google",
    }

    # Save the email addresses
    UserManager.save_email_addresses(email_addresses)

    # Check task provider credentials
    task_manager = TaskManager()
    current_user = UserManager.get_current_user()
    task_auth_results = task_manager.authenticate(current_user)
    for provider, result in task_auth_results.items():
        if result:
            logger.warning(f"Task provider {provider} needs authentication")
        else:
            logger.info(f"Task provider {provider} authenticated")
            # Check for AI instructions
            instructions = task_manager.get_ai_instructions(current_user, provider)
            if not instructions:
                logger.warning(f"No AI instructions found for {provider}")
            else:
                logger.info(f"Found AI instructions for {provider}")

    # Check AI provider credentials
    ai_manager = AIManager()
    ai_auth_results = ai_manager.authenticate(current_user)
    for provider, result in ai_auth_results.items():
        if result:
            logger.warning(f"AI provider {provider} needs authentication")
        else:
            logger.info(f"AI provider {provider} authenticated")

    # Set up calendar providers
    providers = {
        "google": GoogleCalendarProvider,
        "o365": O365CalendarProvider,
    }

    for email, provider_key in email_addresses.items():
        provider_class = providers.get(provider_key)

        if not provider_class:
            logger.warning(f"Unsupported provider {provider_key} for {email}")
            continue

        provider_instance = provider_class()
        result = provider_instance.authenticate(email)

        if result:
            logger.info(f"Authentication successful for {email}")
        else:
            logger.warning(f"Authentication failed for {email}")

    return "Initial setup completed."

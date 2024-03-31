from virtual_assistant.utils.user_manager import UserManager
from virtual_assistant.meetings.google_calendar_provider import GoogleCalendarProvider
from virtual_assistant.meetings.o365_calendar_provider import O365CalendarProvider


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

    providers = {
        "google": GoogleCalendarProvider,
        "o365": O365CalendarProvider,
    }

    for email, provider_key in email_addresses.items():
        provider_class = providers.get(provider_key)

        if not provider_class:
            print(f"Unsupported provider {provider_key} for {email}")
            continue

        provider_instance = provider_class()
        result = provider_instance.authenticate(email)

        if result:
            print(f"Authentication successful for {email}")
        else:
            print(f"Authentication failed for {email}")

    return "Initial setup completed."

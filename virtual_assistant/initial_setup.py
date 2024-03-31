import os
import sys
from virtual_assistant.utils.user_manager import UserManager
# from virtual_assistant.utils.settings import Settings
from virtual_assistant.meetings.calendar_manager import CalendarManager

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def main():
    # Set the current user
    UserManager.set_current_user("lakeland@gmail.com")

    # Define the email addresses and their associated providers
    email_addresses = {
        "lakeland@gmail.com": "google",
        "corrin@morrissheetmetal.co.nz": "google",
        "corrin.lakeland@countdown.co.nz": "google"
    }

    # Save the email addresses
    UserManager.save_email_addresses(email_addresses)

    print("Email addresses initialized successfully.")

    # Create a CalendarManager instance
    calendar_manager = CalendarManager()

    # Authenticate each email address
    for email, provider in email_addresses.items():
        print(f"Authenticating {email} with {provider}...")
        result = calendar_manager.authenticate(email)
        if result:
            print(f"Authentication successful for {email}")
        else:
            print(f"Authentication failed for {email}")

if __name__ == "__main__":
    main()
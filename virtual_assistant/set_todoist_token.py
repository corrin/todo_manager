import sys
from utils.user_manager import UserManager
from utils.logger import logger


def set_token():
    """Set the Todoist API token for the current user."""
    if len(sys.argv) != 2:
        print("\nUsage: python set_todoist_token.py YOUR_API_TOKEN")
        print("\nTo get your API token:")
        print("1. Log into Todoist")
        print("2. Go to Settings -> Integrations")
        print("3. Copy your API token")
        return

    # Set the current user
    UserManager.set_current_user("lakeland@gmail.com")
    
    # Get the token from command line
    token = sys.argv[1]
    
    try:
        # Save the token
        UserManager.save_todoist_token(token)
        print("\nTodoist token saved successfully!")
        print("You can now run test_todoist.py to verify the connection")
    except Exception as e:
        logger.error(f"Error saving Todoist token: {e}")
        print("\nError saving token. Please check the logs for details.")


if __name__ == "__main__":
    set_token()
# utils/settings.py
import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Google API credentials
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'https://virtualassistant-lakeland.pythonanywhere.com/meetings/google_authenticate')
GOOGLE_SCOPES = os.environ.get('GOOGLE_SCOPES', 'https://www.googleapis.com/auth/calendar').split(',')

# Office 365 API credentials (if applicable)
OFFICE365_CLIENT_ID = os.environ.get('OFFICE365_CLIENT_ID')
OFFICE365_CLIENT_SECRET = os.environ.get('OFFICE365_CLIENT_SECRET')
OFFICE365_REDIRECT_URI = os.environ.get('OFFICE365_REDIRECT_URI')
OFFICE365_SCOPES = os.environ.get('OFFICE365_SCOPES', '').split(',')

# Other settings
CURRENT_USER = os.environ.get('CURRENT_USER', 'lakeland@gmail.com')
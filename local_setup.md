# Local Development Setup

## Prerequisites
1. Python 3.12+ with Poetry installed
2. ngrok account for OAuth callbacks
3. Google Cloud OAuth credentials
4. Todoist API access
5. OpenAI API key

## Environment Setup

1. Start ngrok:
```bash
ngrok http --subdomain=virtual-assistant 3000
```

2. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Update values in `.env` with your credentials
   - See `.env.example` for all required variables

3. Install dependencies:
```bash
poetry install
```

## Running the Application

1. Start Flask:
```bash
poetry run flask run
```

2. Visit https://virtual-assistant.au.ngrok.io/initial_setup

3. The system will:
   - Check provider authentication
   - Redirect to setup pages as needed

## Database Setup

The application uses SQLAlchemy with MySQL/MariaDB:

1. Ensure your database is running and configured in `.env`
2. Run migrations:
```bash
poetry run flask db upgrade
```

## Provider Setup

### Google Calendar
1. OAuth flow starts automatically
2. Log in with your Google account
3. Grant calendar permissions

### OpenAI
1. Click OpenAI setup link
2. Enter API key from platform.openai.com
3. System creates credentials file

### Todoist
1. Click Todoist setup link
2. Enter API token from todoist.com/app/settings/integrations
3. System creates:
   - Credentials file
   - AI instruction task

## Troubleshooting

If you get "Internal Server Error":
1. Check ngrok is running
2. Verify .env exists with correct values
3. Check Flask logs for details

### Database Issues

If you encounter database-related errors:
1. Check Settings.DATABASE_URI in virtual_assistant/utils/settings.py
2. Ensure database connection details are correct in `.env`
3. Use proper migrations for production environments to preserve user data

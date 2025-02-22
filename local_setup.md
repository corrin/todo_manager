# Local Development Setup

## Prerequisites
1. Python environment (requirements.txt installed)
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

## Running the Application

1. Start Flask:
```bash
python virtual_assistant/flask_app.py
```

2. Visit https://virtual-assistant.ngrok.io/initial_setup

3. The system will:
   - Create user folder for lakeland@gmail.com
   - Check provider authentication
   - Redirect to setup pages as needed

## Provider Setup

### Google Calendar
1. OAuth flow starts automatically
2. Log in with lakeland@gmail.com
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
3. Ensure virtual_assistant/users exists
4. Check Flask logs for details
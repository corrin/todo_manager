# Local Setup Instructions

## 1. Environment Setup
Create `.env` in the project root:
```
GOOGLE_CLIENT_ID=your_client_id_from_google_console
GOOGLE_CLIENT_SECRET=your_client_secret_from_google_console
GOOGLE_REDIRECT_URI=https://virtual-assitant.ngrok.io/meetings/google_authenticate
FLASK_SECRET_KEY=any_random_string_for_development
PORT=3000
```

## 2. Create Users Directory
```bash
mkdir virtual_assistant/users
```

## 3. Start ngrok
In a separate terminal:
```bash
ngrok http --subdomain=virtual-assitant 3000
```
Keep this running throughout development.

## 4. Run the Application
In terminal:
```bash
python virtual_assistant/flask_app.py
```

The server will be available at:
- Local: http://localhost:3000
- Development: https://virtual-assitant.ngrok.io
- Production: https://virtualassistant-lakeland.pythonanywhere.com

## 5. Initial Setup
1. Open https://virtual-assitant.ngrok.io/initial_setup
2. The system will:
   - Set up user folder for lakeland@gmail.com
   - Check provider authentication
   - Redirect to auth setup if needed

## 6. Provider Setup
Follow the prompts to set up each provider:

### Google Calendar
1. Log in with lakeland@gmail.com
2. Grant calendar access

### OpenAI
1. Go to https://platform.openai.com/api-keys
2. Create new API key
3. Copy the key
4. Paste in the setup form

### Todoist
1. Go to https://todoist.com/app/settings/integrations
2. Copy your API token
3. Paste in the setup form

## If Something Goes Wrong
1. Check both terminal windows for errors:
   - Flask server terminal
   - ngrok terminal
2. Common issues:
   - Wrong redirect URI in Google Console
   - Missing environment variables
   - Not using lakeland@gmail.com
3. Solutions:
   - Double-check Google Console settings
   - Verify .env contents
   - Clear browser cookies and try again

## Production Deployment
The same code works on pythonanywhere.com:
1. The redirect URI automatically uses the production URL
2. The app object is imported by the WSGI configuration
3. Environment variables are set in the pythonanywhere dashboard

Need help? Let me know which step you're stuck on.
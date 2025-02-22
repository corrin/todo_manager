import os

import msal
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
client_id = os.getenv("MICROSOFT_CLIENT_ID")
client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
authority = "https://login.microsoftonline.com/common"
redirect_uri = (
    "http://localhost:8000/"  # Make sure this matches the one configured in Azure
)
scopes = ["user.read"]

# Create an instance of MSAL Confidential Client
app = msal.ConfidentialClientApplication(
    client_id,
    authority=authority,
    client_credential=client_secret,
)

# Initiate the auth code flow without PKCE
flow = app.initiate_auth_code_flow(scopes=scopes, redirect_uri=redirect_uri)

print("Visit the following URL to authenticate:", flow["auth_uri"])

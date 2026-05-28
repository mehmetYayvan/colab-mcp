"""run once to complete OAuth flow and save token"""
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/drive"]
TOKEN_PATH = Path("~/.colab_mcp_token.json").expanduser()

creds = None
if TOKEN_PATH.exists():
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
    TOKEN_PATH.write_text(creds.to_json())
    print("token saved to", TOKEN_PATH)
else:
    print("already authenticated")

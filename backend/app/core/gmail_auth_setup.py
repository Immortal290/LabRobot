"""
gmail_auth_setup.py
───────────────────
Run this ONCE on your host machine (not inside Docker) to authorize the Gmail API
and generate a persistent token.json containing the refresh token.

After running, copy the generated token.json into the /secrets/ volume directory
so the backend container can read it automatically on startup.

Usage:
    python gmail_auth_setup.py

Requirements (install on host):
    pip install google-auth-oauthlib google-api-python-client
"""

import os
import json

SCOPES             = ["https://www.googleapis.com/auth/gmail.send"]
CREDENTIALS_FILE   = "gmail_credentials.json"   # downloaded from Google Cloud Console
TOKEN_OUTPUT_FILE  = "gmail_token.json"          # will be created by this script


def main():
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = None

    if os.path.exists(TOKEN_OUTPUT_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_OUTPUT_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"\n❌  '{CREDENTIALS_FILE}' not found in the current directory.")
                print("    Download it from: Google Cloud Console → APIs & Services → Credentials")
                print("    → OAuth 2.0 Client IDs → Download JSON → rename to gmail_credentials.json\n")
                return

            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            # Opens your browser for the one-time authorization screen
            creds = flow.run_local_server(port=0)

        # Save for future use (contains refresh_token — never expires unless revoked)
        with open(TOKEN_OUTPUT_FILE, "w") as token:
            token.write(creds.to_json())

    print(f"\n✅  Authorization successful!")
    print(f"    Token saved to: {TOKEN_OUTPUT_FILE}")
    print(f"\n    Next steps:")
    print(f"    1. Copy {TOKEN_OUTPUT_FILE} into the secrets volume:")
    print(f"       cp {TOKEN_OUTPUT_FILE} /path/to/LabRobot/secrets/")
    print(f"    2. Copy gmail_credentials.json too:")
    print(f"       cp {CREDENTIALS_FILE} /path/to/LabRobot/secrets/")
    print(f"    3. Set in .env:")
    print(f"       GMAIL_SENDER_ADDRESS=your-lab@gmail.com")
    print(f"       GMAIL_SENDER_NAME=Lab Buddy Robot")
    print(f"    4. Restart Docker: docker compose down && docker compose up --build\n")


if __name__ == "__main__":
    main()

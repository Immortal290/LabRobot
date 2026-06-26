#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
get_gmail_token.py
==================
Run this script ONCE to authorize Gmail API and write the refresh token
directly into the project .env file.  No copy-pasting needed.

Usage:
    python3 get_gmail_token.py

What it does:
  1. Asks for your Client Secret (2 seconds)
  2. Opens your browser -> Google sign-in -> you click Allow
  3. Captures the auth code automatically via a local HTTP server
  4. Exchanges it for a permanent refresh_token
  5. Writes GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN,
     GMAIL_SENDER_ADDRESS into LabRobot/.env automatically

Requirements (already installed):
    pip3 install google-auth-oauthlib google-api-python-client
"""

import sys
import json
import webbrowser
import urllib.parse
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────
CLIENT_ID = input(
    "\n[1/3] Paste your OAuth Client ID from Google Cloud Console\n"
    "      (Credentials -> your Web client -> Client ID field):\n"
    ">>> "
).strip()

CLIENT_SECRET = input(
    "\n[2/3] Paste your Client Secret\n"
    "      (same page, Client secret field - starts with GOCSPX-):\n"
    ">>> "
).strip()

SENDER_EMAIL = input(
    "\n[3/3] Paste the Gmail address Lab Buddy will SEND emails FROM:\n"
    "      (e.g. labbuddyaura@gmail.com)\n"
    ">>> "
).strip()

REDIRECT_PORT = 8080
REDIRECT_URI  = "http://localhost:{}/callback".format(REDIRECT_PORT)
SCOPE         = "https://www.googleapis.com/auth/gmail.send"
ENV_FILE      = Path(__file__).parent / ".env"          # LabRobot/.env
# ──────────────────────────────────────────────────────────────────────────────

auth_code_holder = {}

SUCCESS_HTML = (
    "<html><body style='font-family:sans-serif;background:#0f172a;color:#e2e8f0;"
    "display:flex;align-items:center;justify-content:center;height:100vh;margin:0'>"
    "<div style='text-align:center'>"
    "<h2 style='color:#22d3ee'>Authorization Successful!</h2>"
    "<p>You can close this tab and return to the terminal.</p>"
    "</div></body></html>"
)


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        self.send_response(200 if "code" in params else 400)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        if "code" in params:
            auth_code_holder["code"] = params["code"][0]
            self.wfile.write(SUCCESS_HTML.encode("utf-8"))
        else:
            err = params.get("error", ["unknown"])[0]
            self.wfile.write("<h2>Error: {}</h2>".format(err).encode("utf-8"))

        # Shut down after one callback
        self.server._BaseServer__shutdown_request = True

    def log_message(self, format, *args):
        pass   # suppress HTTP access logs


def exchange_code(code):
    body = urllib.parse.urlencode({
        "code":          code,
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri":  REDIRECT_URI,
        "grant_type":    "authorization_code",
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def update_env(refresh_token):
    """Upsert all 4 Gmail vars into the project .env file."""
    env_path = ENV_FILE
    if not env_path.exists():
        print("\nWARN: .env not found at {}, creating it.".format(env_path))
        env_path.write_text("")

    updates = {
        "GMAIL_CLIENT_ID":     CLIENT_ID,
        "GMAIL_CLIENT_SECRET": CLIENT_SECRET,
        "GMAIL_REFRESH_TOKEN": refresh_token,
        "GMAIL_SENDER_ADDRESS": SENDER_EMAIL,
    }

    lines    = env_path.read_text().splitlines()
    new_lines = []
    seen      = set()

    for line in lines:
        key = line.split("=")[0].strip()
        if key in updates:
            new_lines.append("{}={}".format(key, updates[key]))
            seen.add(key)
        else:
            new_lines.append(line)

    for key, val in updates.items():
        if key not in seen:
            new_lines.append("{}={}".format(key, val))

    env_path.write_text("\n".join(new_lines) + "\n")
    print("\n.env updated at: {}".format(env_path))


def main():
    # Build auth URL (access_type=offline + prompt=consent ensures refresh_token)
    query = urllib.parse.urlencode({
        "client_id":     CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         SCOPE,
        "access_type":   "offline",
        "prompt":        "consent",
    })
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?{}".format(query)

    # Start local callback server
    try:
        server = HTTPServer(("localhost", REDIRECT_PORT), CallbackHandler)
    except OSError:
        print("\nERROR: Port {} is already in use.".format(REDIRECT_PORT))
        print("       Run:  fuser -k {}/tcp  then try again.".format(REDIRECT_PORT))
        sys.exit(1)

    print("\nOpening browser for Google authorization...")
    print("If the browser does not open, paste this URL manually:\n")
    print("  " + auth_url + "\n")
    webbrowser.open(auth_url)

    print("Waiting for you to sign in and click Allow...")
    server.handle_request()   # blocks until callback received

    if "code" not in auth_code_holder:
        print("ERROR: No authorization code received. Did you allow the app?")
        sys.exit(1)

    # Exchange code for tokens
    print("\nExchanging authorization code for tokens...")
    try:
        tokens = exchange_code(auth_code_holder["code"])
    except Exception as exc:
        print("ERROR during token exchange: {}".format(exc))
        sys.exit(1)

    if "refresh_token" not in tokens:
        print("\nERROR: No refresh_token in response:")
        print(json.dumps(tokens, indent=2))
        print("\nTip: Revoke old app access at https://myaccount.google.com/permissions")
        print("     then run this script again.")
        sys.exit(1)

    refresh_token = tokens["refresh_token"]
    print("Got refresh_token: {}...".format(refresh_token[:20]))

    # Write to .env
    update_env(refresh_token)

    print("\n" + "=" * 60)
    print("SETUP COMPLETE! .env now has all 4 Gmail values.")
    print("=" * 60)
    print("\nNow restart Docker to apply:")
    print("  docker compose down && docker compose up --build\n")


if __name__ == "__main__":
    main()

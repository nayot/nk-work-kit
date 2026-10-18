#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Post to Nayot's own LinkedIn profile through the official LinkedIn API (Posts + Images).

Part of nk-work-kit. On Nayot's machine `~/.local/bin/linkedin` is a symlink to the clone's copy.
Never post without Nayot's approval of the exact text (same rule as email and WhatsApp).

One-time setup:
  1. developer.linkedin.com -> Create app (must be linked to a Company Page), then on the
     Products tab add "Share on LinkedIn" and "Sign In with LinkedIn using OpenID Connect".
  2. Auth tab -> Authorized redirect URLs: http://localhost:8765/callback
  3. Save ~/.config/linkedin/client.json (chmod 600):
       {"client_id": "...", "client_secret": "..."}
  4. linkedin auth      (opens a sign-in link; the token lasts 60 days, then run it again)

Usage:
  linkedin auth
  linkedin whoami
  linkedin post <text-file> [--image PNG/JPG] [--alt TEXT] [--dry-run]

The text file is plain text. Hashtags (#Word) become LinkedIn hashtags; the characters
LinkedIn reserves ( ) [ ] { } < > @ | * _ ~ \\ are escaped so they show as typed.
"""
import argparse
import http.server
import json
import re
import secrets
import sys
import time
import urllib.parse
from pathlib import Path

import requests

CONF = Path.home() / ".config" / "linkedin"
CLIENT = CONF / "client.json"
TOKEN = CONF / "token.json"
REDIRECT = "http://localhost:8765/callback"
SCOPES = "openid profile w_member_social"
API_VERSION = "202607"  # LinkedIn-Version header (YYYYMM); versions retire after about a year


def load(path):
    if not path.exists():
        sys.exit(f"Missing {path}. See the setup steps: linkedin --help")
    return json.loads(path.read_text())


def save_private(path, data):
    CONF.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    path.chmod(0o600)


def cmd_auth(_):
    client = load(CLIENT)
    state = secrets.token_urlsafe(16)
    url = "https://www.linkedin.com/oauth/v2/authorization?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": client["client_id"],
        "redirect_uri": REDIRECT, "scope": SCOPES, "state": state})
    print(f"Open this link and sign in:\n\n{url}\n\nWaiting on {REDIRECT} ...", flush=True)
    got = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"LinkedIn sign-in received. You can close this tab.")

        def log_message(self, *a):
            pass

    with http.server.HTTPServer(("localhost", 8765), Handler) as srv:
        while "code" not in got and "error" not in got:
            srv.handle_request()
    if "error" in got:
        sys.exit(f"Sign-in failed: {got.get('error')} {got.get('error_description', '')}")
    if got.get("state") != state:
        sys.exit("State mismatch; sign-in aborted.")
    r = requests.post("https://www.linkedin.com/oauth/v2/accessToken", data={
        "grant_type": "authorization_code", "code": got["code"], "redirect_uri": REDIRECT,
        "client_id": client["client_id"], "client_secret": client["client_secret"]}, timeout=30)
    r.raise_for_status()
    tok = r.json()
    me = requests.get("https://api.linkedin.com/v2/userinfo",
                      headers={"Authorization": f"Bearer {tok['access_token']}"}, timeout=30)
    me.raise_for_status()
    info = me.json()
    save_private(TOKEN, {"access_token": tok["access_token"],
                         "expires_at": int(time.time()) + int(tok.get("expires_in", 0)),
                         "person": f"urn:li:person:{info['sub']}", "name": info.get("name")})
    print(f"Signed in as {info.get('name')}. Token saved to {TOKEN}.")


def token():
    t = load(TOKEN)
    if t["expires_at"] < time.time() + 60:
        sys.exit("LinkedIn token expired. Run: linkedin auth")
    return t


def headers(t):
    return {"Authorization": f"Bearer {t['access_token']}", "LinkedIn-Version": API_VERSION,
            "X-Restli-Protocol-Version": "2.0.0", "Content-Type": "application/json"}


def cmd_whoami(_):
    t = token()
    days = (t["expires_at"] - time.time()) / 86400
    print(f"{t['name']} ({t['person']}); token valid {days:.0f} more days")


def little_text(text):
    """Escape LinkedIn's reserved characters and turn #Word into hashtags."""
    out = re.sub(r"([\\|{}@\[\]()<>*_~])", r"\\\1", text)
    return re.sub(r"(?<![\w\\])#(\w+)", r"{hashtag|\\#|\1}", out)


def upload_image(t, path):
    r = requests.post("https://api.linkedin.com/rest/images?action=initializeUpload",
                      headers=headers(t), timeout=30,
                      json={"initializeUploadRequest": {"owner": t["person"]}})
    r.raise_for_status()
    v = r.json()["value"]
    up = requests.put(v["uploadUrl"], data=Path(path).read_bytes(), timeout=120,
                      headers={"Authorization": f"Bearer {t['access_token']}"})
    up.raise_for_status()
    return v["image"]


def cmd_post(a):
    text = little_text(Path(a.text_file).read_text().strip())
    if len(text) > 3000:
        sys.exit(f"Post is {len(text)} characters after escaping; LinkedIn's limit is 3000.")
    if a.dry_run:
        print(text)
        print(f"\n[dry run] {len(text)} characters; image: {a.image or 'none'}")
        return
    t = token()
    body = {"author": t["person"], "commentary": text, "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                             "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False}
    if a.image:
        body["content"] = {"media": {"id": upload_image(t, a.image), "altText": a.alt or ""}}
    r = requests.post("https://api.linkedin.com/rest/posts", headers=headers(t), json=body, timeout=30)
    if r.status_code != 201:
        sys.exit(f"Post failed ({r.status_code}): {r.text}")
    urn = r.headers.get("x-restli-id", "")
    print(f"Posted: https://www.linkedin.com/feed/update/{urn}/")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("auth").set_defaults(fn=cmd_auth)
    sub.add_parser("whoami").set_defaults(fn=cmd_whoami)
    s = sub.add_parser("post")
    s.add_argument("text_file")
    s.add_argument("--image")
    s.add_argument("--alt")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_post)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()

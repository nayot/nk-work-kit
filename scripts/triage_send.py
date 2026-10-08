#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml>=6",
#   "google-auth>=2.30",
#   "requests>=2.31",
#   "google-auth-oauthlib>=1.2",
# ]
# ///
"""
triage_send.py — email a triage brief to the user, and only to the user.

    uv run triage_send.py --subject "..." --html brief.html [--text brief.txt]
                          [--mark-run ISO] [--dry-run]
    uv run triage_send.py --show-config     window + non-secret settings (JSON)

SELF ONLY
---------
There is no recipient option. The address is TRIAGE_TO, else PM_NOTIFY_TO,
from the plugin's .env (one address, no lists). Where the sending account can
be identified, the address must be that account: SMTP_USER for smtp, and the
Gmail profile for gmail-oauth when the token also has gmail.readonly
(`projects.py auth-gmail --scan`). Anything else is refused.

Mail goes out the same way as `projects.py notify` (PM_MAIL_METHOD: gmail-oauth,
the default, smtp or gmail-api), reusing its token and config lookup.

--mark-run ISO   after a successful send, write ISO (the run's start time) to
                 the triage state file, so the next run's window starts there.
                 Nothing is written when the send fails or on --dry-run.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from email.message import EmailMessage
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import projects  # noqa: E402  (same scripts/ dir: config lookup + Gmail sender)

STATE_DIR = Path.home() / ".local" / "state" / "nk-work-kit" / "triage"
LAST_RUN = STATE_DIR / "last_run"
ADDR_RE = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")


def html_to_text(html: str) -> str:
    t = re.sub(r"<li[^>]*>", "\n- ", html, flags=re.I)
    t = re.sub(r"<(br|/?(p|div|ul|ol|h[1-6]|tr|table))\b[^>]*>", "\n", t, flags=re.I)
    t = unescape(re.sub(r"<[^>]+>", "", t))
    return re.sub(r"\n\s*\n+", "\n\n", t).strip()


def recipient() -> str:
    to = (os.environ.get("TRIAGE_TO") or os.environ.get("PM_NOTIFY_TO") or "").strip()
    if not to:
        sys.exit("No recipient: set PM_NOTIFY_TO (your own address) in ~/.config/nk-work-kit/.env.")
    if not ADDR_RE.match(to):
        sys.exit(f"Refusing to send: {to!r} is not a single email address.")
    return to


def mail_method() -> str:
    return (os.environ.get("PM_MAIL_METHOD", "").strip()
            or ("smtp" if os.environ.get("SMTP_PASSWORD") else "gmail-oauth"))


def check_self(to: str, method: str, creds) -> None:
    """Refuse when the sending account is known and is not `to`."""
    own = None
    if method == "smtp":
        own = os.environ.get("SMTP_USER", "").strip()
    elif creds is not None and "https://www.googleapis.com/auth/gmail.readonly" in (creds.scopes or []):
        from google.auth.transport.requests import AuthorizedSession
        r = AuthorizedSession(creds).get(
            "https://gmail.googleapis.com/gmail/v1/users/me/profile", timeout=30)
        if r.ok:
            own = r.json().get("emailAddress", "")
    if own and own.lower() != to.lower():
        sys.exit(f"Refusing to send: the brief goes only to the signed-in account ({own}), "
                 f"but the configured recipient is {to}. Fix TRIAGE_TO / PM_NOTIFY_TO.")


def show_config() -> None:
    """Non-secret settings and the default window, as JSON. The skill uses this
    instead of reading the .env, which also holds passwords."""
    now = datetime.now().astimezone()
    try:
        last = LAST_RUN.read_text(encoding="utf-8").strip()
        start = datetime.fromisoformat(last)
        if start.tzinfo is None:
            start = start.astimezone()
    except (OSError, ValueError):
        last, start = None, now - timedelta(hours=24)
    names = [n.strip() for n in os.environ.get("TRIAGE_NAMES", "").split(",") if n.strip()]
    print(json.dumps({
        "now": now.isoformat(timespec="seconds"),
        "window_start": start.isoformat(timespec="seconds"),
        "window_start_epoch": int(start.timestamp()),
        "last_run": last,
        "names": names,
        "recipient": (os.environ.get("TRIAGE_TO") or os.environ.get("PM_NOTIFY_TO") or "").strip() or None,
        "mail_method": mail_method(),
        "edoc_configured": bool(os.environ.get("EDOC_USERNAME", "").strip()),
        "state_dir": str(STATE_DIR),
    }, ensure_ascii=False, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description="Email a triage brief to yourself.")
    ap.add_argument("--show-config", action="store_true",
                    help="print the non-secret settings and the default window as JSON, then exit")
    ap.add_argument("--subject")
    ap.add_argument("--html", type=Path)
    ap.add_argument("--text", type=Path)
    ap.add_argument("--mark-run", metavar="ISO")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    projects.load_env()
    if a.show_config:
        return show_config()
    if not (a.subject and a.html):
        ap.error("--subject and --html are required")
    if a.mark_run:
        try:
            datetime.fromisoformat(a.mark_run.strip())
        except ValueError:
            sys.exit(f"--mark-run: not an ISO datetime: {a.mark_run!r}")
    html = a.html.read_text(encoding="utf-8")
    text = a.text.read_text(encoding="utf-8") if a.text else html_to_text(html)
    to, method = recipient(), mail_method()

    msg = EmailMessage()
    msg["Subject"] = " ".join(a.subject.split())
    msg["To"] = to
    msg["From"] = os.environ.get("SMTP_USER") if method == "smtp" else to
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    if a.dry_run:
        print(f"[dry-run via {method}] To: {to}\nSubject: {msg['Subject']}\n\n{text}")
        return

    if method == "smtp":
        check_self(to, method, None)
        projects.send_smtp(msg)
    elif method == "gmail-oauth":
        creds = projects.gmail_oauth_creds()
        check_self(to, method, creds)
        projects.send_gmail_api(msg, creds)
    elif method == "gmail-api":
        projects.send_gmail_api(msg)
    else:
        sys.exit(f"Unknown PM_MAIL_METHOD={method}")
    print(f"Sent via {method} to {to}: {msg['Subject']}")

    if a.mark_run:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        LAST_RUN.write_text(a.mark_run.strip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "google-auth>=2.30",
#   "requests>=2.31",
#   "google-auth-oauthlib>=1.2",
# ]
# ///
"""
meet_attendees.py — who is (or was) in a Google Meet call. Read-only.

    uv run meet_attendees.py [--now]               the meeting happening now
    uv run meet_attendees.py abc-mnop-xyz          by meeting code or meet.google.com URL
    uv run meet_attendees.py --record conferenceRecords/ID
    uv run meet_attendees.py recent [--limit 10]   recent meetings you organised
    uv run meet_attendees.py ... --json            for Claude: one JSON object
    uv run meet_attendees.py auth [--no-browser]   one-time browser sign-in
    uv run meet_attendees.py auth --url URL        second step of a headless sign-in

FINDING THE MEETING
-------------------
Meet's `conferenceRecords.list` (and so its `space.meeting_code` and
`end_time IS NULL` filters) returns only meetings the signed-in user
*organised*; `get` works for any participant. So, for a meeting code:
  1. GET spaces/{code}: if the call is live, `activeConference` names its record
     (this should work for a participant too);
  2. else list records with `space.meeting_code = "..."` and take the newest
     (one space can have several records: a call that empties and restarts gets
     a new one; the output says how many, and --record picks another);
  3. else fail: an ended meeting is only visible to its organiser.
Without a code (--now, the default), the code comes from the Calendar event
happening now that has a Meet link; failing that, from the newest record with no
end time (organiser only). Records are kept about 30 days.
Tested (30.10.2026, macOS, gcloud ADC token): steps 2 and --record on an ended
meeting the user organised. Not yet exercised: the live path (step 1, still_here),
a meeting the user only joined, and every Calendar call (the test token lacked
calendar.readonly).

EMAILS
------
Meet gives signed-in users as `users/<id>`; People `people:batchGet` turns that
into an email for BUU-domain users (DOMAIN_PROFILE) and for people in the user's
Contacts (CONTACT). Other external users come back without one. For those, the
display name is matched against the Calendar invite's attendees, and only when
exactly one attendee matches; never a fuzzy guess:
  - an invitee with a name: normalised exact match → email_source "invite";
  - an invitee without one (most external invitees): the email's local part,
    dots/underscores/hyphens/digits dropped, must equal first+last, last+first,
    first initial+last or all name tokens joined (petchtinnabal, kerwin_hing,
    schalam, jkong) → "invite (name≈email)". A one-letter first or last name
    ("Gloria H") is never matched this way. Tests: meet_attendees_test.py.

`minutes` is the span from first join to last leave (or now while still in the
call); someone who left and came back is counted for the gap too.

AUTH
----
`auth` signs in once with the plugin's own Desktop OAuth client (the bundled
gmail_oauth_client.json, or credentials.json in the config dir) and stores
meet-token.json in the config dir, separate from projects.py's Gmail token.
Scopes: meetings.space.readonly, directory.readonly, contacts.readonly,
calendar.readonly. NKW_ACCESS_TOKEN overrides the token (for testing with
`gcloud auth application-default print-access-token`); then requests carry
x-goog-user-project: NKW_QUOTA_PROJECT (default nk-work-kit).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

BKK = timezone(timedelta(hours=7), "ICT")
MEET = "https://meet.googleapis.com/v2"
PEOPLE = "https://people.googleapis.com/v1"
CAL = "https://www.googleapis.com/calendar/v3"
SCOPES = ["https://www.googleapis.com/auth/meetings.space.readonly",
          "https://www.googleapis.com/auth/directory.readonly",
          "https://www.googleapis.com/auth/contacts.readonly",
          "https://www.googleapis.com/auth/calendar.readonly"]
TOKEN_NAME = "meet-token.json"
BUNDLED_CLIENT = Path(__file__).resolve().parent / "gmail_oauth_client.json"
CODE_RE = re.compile(r"\b([a-z]{3}-[a-z]{4}-[a-z]{3})\b")


# ---------------------------------------------------------------- config

def config_files() -> list[Path]:
    """Where plugin config may live, most specific first (kept in step with
    check_pending.py)."""
    bases = []
    if xdg := os.environ.get("XDG_CONFIG_HOME"):
        bases.append(Path(xdg))
    if appdata := os.environ.get("APPDATA"):       # Windows
        bases.append(Path(appdata))
    bases.append(Path.home() / ".config")          # Linux and macOS
    return [b / "nk-work-kit" / ".env" for b in bases] + [
        Path(__file__).resolve().parent / ".env"]


def load_env() -> None:
    """Read KEY=VALUE from the first config file found. Real env vars win."""
    for env_file in config_files():
        if not env_file.is_file():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        return


def config_dir() -> Path:
    """Directory of the config file in use (or the default ~/.config one)."""
    for env_file in config_files():
        if env_file.is_file():
            return env_file.parent
    return Path.home() / ".config" / "nk-work-kit"


# ---------------------------------------------------------------- auth

def oauth_paths() -> tuple[Path, Path]:
    """(client JSON, token). The token always lives in the config dir, never
    beside the bundled client in the version-pinned plugin cache."""
    own = config_dir() / "credentials.json"
    return (own if own.is_file() else BUNDLED_CLIENT), config_dir() / TOKEN_NAME


def save_token(token: Path, creds) -> None:
    fd = os.open(token, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    print(f"Saved {token} (Meet, directory, contacts and calendar, all read-only).")


def cmd_auth(url: str | None = None, no_browser: bool = False) -> None:
    """Same two-step headless flow as projects.py auth-gmail: without a local
    browser, print the sign-in URL; the browser then fails to load
    http://localhost:1/?code=..., and `auth --url '<that address>'` finishes."""
    import webbrowser
    from google_auth_oauthlib.flow import Flow, InstalledAppFlow
    client, token = oauth_paths()
    pending = config_dir() / ".auth-meet-pending.json"
    token.parent.mkdir(parents=True, exist_ok=True)
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"    # the redirect is http://localhost
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"     # Google may add earlier grants
    if url:
        try:
            st = json.loads(pending.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            sys.exit("No sign-in in progress. Run `meet_attendees.py auth` first.")
        flow = Flow.from_client_secrets_file(st["client"], st["scopes"], state=st["state"],
                                             redirect_uri=st["redirect_uri"])
        flow.code_verifier = st["code_verifier"]
        try:
            flow.fetch_token(authorization_response=url.strip())
        except Exception as e:
            sys.exit(f"Could not exchange the code: {e}\nStart again with `meet_attendees.py auth`.")
        pending.unlink(missing_ok=True)
        return save_token(token, flow.credentials)

    if not client.is_file():
        sys.exit(f"OAuth client file not found: {client} (Desktop app JSON from Google Cloud).")
    print(f"OAuth client: {client}")
    if not no_browser:
        try:
            webbrowser.get()
        except webbrowser.Error:
            no_browser = True
    if not no_browser:
        flow = InstalledAppFlow.from_client_secrets_file(str(client), SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True,
                                      authorization_prompt_message="Sign in in your browser: {url}")
        return save_token(token, creds)

    redirect = "http://localhost:1/"
    flow = Flow.from_client_secrets_file(str(client), SCOPES, redirect_uri=redirect,
                                         autogenerate_code_verifier=True)
    auth_url, state = flow.authorization_url(access_type="offline", prompt="consent")
    fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"client": str(client), "scopes": SCOPES, "state": state,
                   "redirect_uri": redirect, "code_verifier": flow.code_verifier}, f)
    print(f"""
No browser here. Sign in on any device:

  1. Open this link and sign in with your BUU Google account:

     {auth_url}

  2. The browser then ends on a page that fails to load, at an address
     starting with http://localhost:1/?state=... Copy that whole address.
  3. Run:  meet_attendees.py auth --url '<the address>'
""")


def session():
    """An HTTP session: NKW_ACCESS_TOKEN if set, else the stored token."""
    import requests
    if tok := os.environ.get("NKW_ACCESS_TOKEN", "").strip():
        s = requests.Session()
        s.headers["Authorization"] = f"Bearer {tok}"
        s.headers["x-goog-user-project"] = os.environ.get("NKW_QUOTA_PROJECT", "nk-work-kit")
        return s
    from google.auth.transport.requests import AuthorizedSession, Request
    from google.oauth2.credentials import Credentials
    _, token = oauth_paths()
    if not token.is_file():
        sys.exit(f"Not signed in (no {token}). Run `meet_attendees.py auth` once.")
    creds = Credentials.from_authorized_user_file(str(token))
    if missing := set(SCOPES) - set(creds.scopes or []):
        sys.exit(f"The Meet token lacks {', '.join(sorted(m.rsplit('/', 1)[-1] for m in missing))}. "
                 "Run `meet_attendees.py auth` again.")
    if not creds.valid:
        creds.refresh(Request())
        fd = os.open(token, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return AuthorizedSession(creds)


class ApiError(Exception):
    def __init__(self, status: int, msg: str):
        super().__init__(f"HTTP {status}: {msg}")
        self.status = status


def get(s, url: str, **params) -> dict:
    r = s.get(url, params=params or None, timeout=30)
    if r.status_code >= 300:
        try:                                      # only the API's own message, never headers
            msg = r.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            msg = r.reason
        raise ApiError(r.status_code, msg)
    return r.json()


def pages(s, url: str, key: str, **params):
    while True:
        d = get(s, url, **params)
        yield from d.get(key, [])
        params["pageToken"] = d.get("nextPageToken")
        if not params["pageToken"]:
            return


# ---------------------------------------------------------------- time

def ts(raw: str | None) -> datetime | None:
    return datetime.fromisoformat(raw.replace("Z", "+00:00")) if raw else None


def hm(t: datetime | None) -> str | None:
    return t.astimezone(BKK).strftime("%H:%M") if t else None


def stamp(t: datetime | None) -> str | None:
    return t.astimezone(BKK).isoformat(timespec="minutes") if t else None


def rfc(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- calendar

def event_code(ev: dict) -> str | None:
    links = [ev.get("hangoutLink", "")] + [
        p.get("uri", "") for p in (ev.get("conferenceData") or {}).get("entryPoints", [])]
    for link in links:
        if "meet.google.com" in link and (m := CODE_RE.search(link)):
            return m.group(1)
    return None


def calendar_events(s, start: datetime, end: datetime) -> list[dict]:
    return list(pages(s, f"{CAL}/calendars/primary/events", "items", singleEvents="true",
                      timeMin=rfc(start), timeMax=rfc(end), maxResults=250, orderBy="startTime"))


def event_now(s) -> dict | None:
    """The Meet event on the primary calendar happening now (or starting within
    15 minutes); the one that started most recently if several."""
    now = datetime.now(timezone.utc)
    hits = [e for e in calendar_events(s, now - timedelta(minutes=1), now + timedelta(minutes=15))
            if event_code(e) and (e.get("start") or {}).get("dateTime")]
    hits = [e for e in hits if ts(e["start"]["dateTime"]) <= now + timedelta(minutes=15)]
    return max(hits, key=lambda e: ts(e["start"]["dateTime"]), default=None)


def event_for(s, code: str, start: datetime, end: datetime) -> dict | None:
    """The calendar event with this meeting code nearest to the call's start."""
    evs = [e for e in calendar_events(s, start - timedelta(hours=12), end + timedelta(hours=12))
           if event_code(e) == code]
    def dist(e):
        st = ts((e.get("start") or {}).get("dateTime")) or start
        return abs((st - start).total_seconds())
    return min(evs, key=dist, default=None)


# ---------------------------------------------------------------- finding the record

def parse_code(arg: str) -> str:
    m = CODE_RE.search(arg.lower())
    if not m:
        sys.exit(f"Not a Meet code or link: {arg!r} (expected abc-mnop-xyz).")
    return m.group(1)


def resolve(s, code: str | None, record: str | None, notes: list[str]) -> tuple[dict, str | None, dict | None]:
    """(conference record, meeting code, calendar event or None)."""
    event = None
    if record:
        rec = get(s, f"{MEET}/{record if record.startswith('conferenceRecords/') else 'conferenceRecords/' + record}")
        return rec, None, None
    if not code:
        try:
            event = event_now(s)
        except ApiError as e:
            notes.append(f"Calendar not readable ({e}); looked for a live meeting you organised.")
        if event:
            code = event_code(event)
        else:
            live = list(get(s, f"{MEET}/conferenceRecords", filter="end_time IS NULL",
                            pageSize=10).get("conferenceRecords", []))
            if not live:
                sys.exit("No meeting found now: no calendar event with a Meet link right now, "
                         "and no live meeting you organised. Give the meeting code or link."
                         + "".join(f"\nNote: {n}" for n in notes))
            if len(live) > 1:
                notes.append(f"{len(live)} live meetings you organised; showing the newest.")
            return live[0], None, None
    try:
        space = get(s, f"{MEET}/spaces/{code}")
    except ApiError as e:
        if e.status == 404:
            sys.exit(f"No Meet space {code}, or it is not visible to you.")
        raise
    if rec_name := (space.get("activeConference") or {}).get("conferenceRecord"):
        return get(s, f"{MEET}/{rec_name}"), code, event
    recs = list(get(s, f"{MEET}/conferenceRecords", filter=f'space.meeting_code = "{code}"',
                    pageSize=25).get("conferenceRecords", []))
    if not recs:
        sys.exit(f"{code} is not live, and no record of it is visible to you: an ended meeting "
                 "is listed only for its organiser (records are kept about 30 days).")
    if len(recs) > 1:
        notes.append(f"{len(recs)} sessions of {code}; showing the newest. Others: "
                     + ", ".join(f"{r['name']} ({stamp(ts(r['startTime']))})" for r in recs[1:]))
    return recs[0], code, event


# ---------------------------------------------------------------- people

def norm(name: str) -> str:
    name = unicodedata.normalize("NFKC", name or "").casefold()
    name = re.sub(r"\(.*?\)", " ", name)
    return re.sub(r"[\W_]+", "", name)


def name_tokens(name: str) -> list[str]:
    """Lowercase letter runs of a display name, digits and (…) dropped."""
    name = re.sub(r"\(.*?\)", " ", unicodedata.normalize("NFKC", name or "").casefold())
    return re.findall(r"[^\W\d_]+", name)


def local_keys(name: str) -> set[str]:
    """Email local parts (dots, underscores, hyphens, digits dropped) this name
    plausibly owns: first+last, last+first, first initial+last, all tokens.
    Empty when the first or last token is a single letter ("Gloria H"): too weak."""
    t = name_tokens(name)
    if len(t) < 2 or len(t[0]) < 2 or len(t[-1]) < 2:
        return set()
    first, last = t[0], t[-1]
    return {first + last, last + first, first[0] + last, "".join(t)}


def local_part(email: str) -> str:
    return re.sub(r"[._\-\d]+", "", email.split("@", 1)[0].lower())


def match_invitee(name: str, attendees: list[dict], taken: set[str]) -> tuple[str | None, str | None, bool]:
    """(email, email_source, ambiguous) for a Meet name against the invite.
    An invitee with a displayName is matched on the normalised name; one without
    on its email's local part. Only a single candidate counts; several →
    ambiguous. Invitees whose email is already taken are skipped."""
    free = [a for a in attendees if a.get("email") and a["email"].lower() not in taken]
    by_name = [a for a in free if a.get("displayName") and norm(a["displayName"]) == norm(name)]
    if by_name:
        return (by_name[0]["email"].lower(), "invite", False) if len(by_name) == 1 else (None, None, True)
    keys = local_keys(name)
    by_local = [a for a in free if not a.get("displayName") and local_part(a["email"]) in keys]
    if len(by_local) == 1:
        return by_local[0]["email"].lower(), "invite (name≈email)", False
    return None, None, len(by_local) > 1


def emails_for(s, user_ids: list[str], notes: list[str]) -> dict[str, tuple[str, str]]:
    """users/<id> → (email, source) via people:batchGet."""
    out: dict[str, tuple[str, str]] = {}
    ids = [u.split("/", 1)[1] for u in user_ids]
    for i in range(0, len(ids), 200):
        try:
            d = get(s, f"{PEOPLE}/people:batchGet", personFields="emailAddresses",
                    resourceNames=[f"people/{x}" for x in ids[i:i + 200]])
        except ApiError as e:
            notes.append(f"People API not readable ({e}); emails only from the invite.")
            return out
        for resp in d.get("responses", []):
            person = resp.get("person") or {}
            addrs = person.get("emailAddresses") or []
            if not addrs:
                continue
            best = next((a for a in addrs if (a.get("metadata") or {}).get("primary")), addrs[0])
            src = ((best.get("metadata") or {}).get("source") or {}).get("type", "")
            uid = "users/" + resp.get("requestedResourceName", "").split("/", 1)[-1]
            out[uid] = (best["value"].lower(),
                        {"DOMAIN_PROFILE": "directory", "CONTACT": "contacts"}.get(src, "profile"))
    return out


def domain(email: str | None) -> str | None:
    return email.rsplit("@", 1)[1] if email else None


def build(s, rec: dict, code: str | None, event: dict | None, notes: list[str]) -> dict:
    now = datetime.now(timezone.utc)
    rec_start, rec_end = ts(rec["startTime"]), ts(rec.get("endTime"))
    if not code:
        try:
            code = get(s, f"{MEET}/{rec['space']}").get("meetingCode")
        except ApiError:
            pass
    if event is None and code:
        try:
            event = event_for(s, code, rec_start, rec_end or now)
        except ApiError as e:
            notes.append(f"Calendar not readable ({e}); invited/absent unknown.")
    attendees = [a for a in (event or {}).get("attendees", []) if not a.get("resource")]

    parts = list(pages(s, f"{MEET}/{rec['name']}/participants", "participants", pageSize=250))
    found = emails_for(s, [p["signedinUser"]["user"] for p in parts if "signedinUser" in p], notes)
    by_email = {a["email"].lower(): a for a in attendees if a.get("email")}
    taken = {e for e, _ in found.values()}
    guesses = {}                                   # participant index → (email, source, ambiguous)
    for i, p in enumerate(parts):
        if "signedinUser" in p and p["signedinUser"].get("user") not in found:
            guesses[i] = match_invitee(p["signedinUser"].get("displayName", ""), attendees, taken)
    claims = [g[0] for g in guesses.values() if g[0]]
    for i, g in guesses.items():                   # one invitee claimed by two names: neither
        if g[0] and claims.count(g[0]) > 1:
            guesses[i] = (None, None, True)

    rows, matched = [], set()
    for i, p in enumerate(parts):
        kind = next(k for k in ("signedinUser", "anonymousUser", "phoneUser") if k in p)
        name = p[kind].get("displayName", "")
        email, source = found.get(p[kind].get("user", ""), (None, None))
        ambiguous = False
        if not email and i in guesses:
            email, source, ambiguous = guesses[i]
        joined, left = ts(p.get("earliestStartTime")), ts(p.get("latestEndTime"))
        here = rec_end is None and left is None
        upto = (now if here else left or rec_end) or now
        # None: no invite to compare with, or no email to compare (a name we could
        # not tie to one invitee may still be on the invite).
        invited = None if not event or ambiguous or not email else email in by_email
        if invited:
            matched.add(email)
        rows.append({"name": name, "email": email, "email_source": source,
                     "kind": {"signedinUser": "signed_in", "anonymousUser": "anonymous",
                              "phoneUser": "phone"}[kind],
                     "domain": domain(email), "joined": stamp(joined), "left": stamp(left),
                     "still_here": here,
                     "minutes": round((upto - joined).total_seconds() / 60) if joined else None,
                     "invited": invited})
    rows.sort(key=lambda r: (not r["still_here"], r["joined"] or ""))
    absent = [{"name": a.get("displayName"), "email": a["email"].lower(),
               "domain": domain(a["email"]), "response": a.get("responseStatus"),
               "organizer": bool(a.get("organizer"))}
              for a in attendees if a.get("email") and a["email"].lower() not in matched]
    return {"meeting": {"code": code, "record": rec["name"],
                        "title": (event or {}).get("summary"),
                        "start": stamp(rec_start), "end": stamp(rec_end), "live": rec_end is None,
                        "calendar_event": bool(event), "timezone": "Asia/Bangkok"},
            "participants": rows,
            "invited_absent": absent if event else None,
            "notes": notes}


def show(d: dict) -> None:
    m = d["meeting"]
    print(f"{m['title'] or m['code'] or m['record']}  {m['start']} → {m['end'] or 'live'}")
    for r in d["participants"]:
        when = f"{(r['joined'] or '')[11:16]}–{'now' if r['still_here'] else (r['left'] or '')[11:16]}"
        inv = {True: "invited", False: "not invited",
               None: "invited?" if m["calendar_event"] else ""}[r["invited"]]
        src = " (from invite)" if (r["email_source"] or "").startswith("invite") else ""
        print(f"  {r['name'][:32]:32} {(r['email'] or '-') + src:54} {when:12} "
              f"{r['minutes'] or 0:>4} min  {inv}")
    present = sum(r["still_here"] for r in d["participants"])
    print(f"{len(d['participants'])} joined" + (f", {present} still here" if m["live"] else ""))
    if d["invited_absent"]:
        print("Invited, did not join:")
        for a in d["invited_absent"]:
            print(f"  {a['name'] or '':32} {a['email']:54} {a['response'] or ''}")
    for n in d["notes"]:
        print(f"Note: {n}")


def cmd_recent(s, limit: int) -> None:
    for r in get(s, f"{MEET}/conferenceRecords", pageSize=limit).get("conferenceRecords", []):
        print(f"{r['name']}  {stamp(ts(r['startTime']))} → {stamp(ts(r.get('endTime'))) or 'live'}")


def main() -> None:
    load_env()
    if len(sys.argv) > 1 and sys.argv[1] == "auth":
        ap = argparse.ArgumentParser(prog="meet_attendees.py auth")
        ap.add_argument("auth")
        ap.add_argument("--url")
        ap.add_argument("--no-browser", action="store_true")
        a = ap.parse_args()
        return cmd_auth(a.url, a.no_browser)
    if len(sys.argv) > 1 and sys.argv[1] == "recent":
        ap = argparse.ArgumentParser(prog="meet_attendees.py recent")
        ap.add_argument("recent")
        ap.add_argument("--limit", type=int, default=10)
        return cmd_recent(session(), ap.parse_args().limit)
    ap = argparse.ArgumentParser(description="Who is (or was) in a Google Meet call.")
    ap.add_argument("meeting", nargs="?", help="meeting code (abc-mnop-xyz) or meet.google.com link")
    ap.add_argument("--now", action="store_true", help="the meeting happening now (default)")
    ap.add_argument("--record", help="a conferenceRecords/ID")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    s, notes = session(), []
    try:
        rec, code, event = resolve(s, parse_code(a.meeting) if a.meeting else None, a.record, notes)
        d = build(s, rec, code, event, notes)
    except ApiError as e:
        sys.exit(f"Google API error: {e}")
    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=1))
    else:
        show(d)


if __name__ == "__main__":
    main()

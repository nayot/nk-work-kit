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
projects.py — project tracking on top of an Obsidian vault.

    uv run projects.py list [--json]            every project + its dated items
    uv run projects.py dashboard                rewrite <vault>/Projects/Dashboard.md
    uv run projects.py digest [--days 14] [--format text|html|json]
    uv run projects.py notify [--dry-run] [--force]
    uv run projects.py auth-gmail               one-time browser sign-in (gmail-oauth)
    uv run projects.py new "Name" [--area A] [--due YYYY-MM-DD] [--priority P]

THE DATA MODEL
--------------
A project is any note (anywhere in the vault) whose YAML frontmatter has
`type: project`. By convention the hub notes live in `Projects/`, but the script
does not care. Fields it reads:

    status          idea | active | waiting | on-hold | done | dropped
    priority        high | normal | low
    area            free text, for grouping
    due             project deadline (optional)
    next_action     one line
    next_action_due YYYY-MM-DD (optional)
    waiting_on      person/office (optional)
    updated         YYYY-MM-DD, last time the hub note was reviewed

Dated items are Tasks-plugin checkboxes — `- [ ] text 📅 YYYY-MM-DD` — found
(a) in the hub note itself, and (b) anywhere else in the vault when the task
line links to the hub note (`[[Hub name]]`). Done (`[x]`) and cancelled (`[-]`)
tasks are ignored.

The vault is never scanned inside `.obsidian/`, `.trash/` or `Confidential/`
(meld-encrypt notes). The only file this script writes is the dashboard, and it
writes it atomically (temp file + rename), because the vault is synced by
rclone/Obsidian Sync while it may be running.

NOTIFY
------
`notify` sends the digest to PM_NOTIFY_TO only when something is overdue or due
within PM_NOTIFY_DAYS. On a quiet day it sends nothing and exits 0 (`--force`
overrides, for testing). Three senders, chosen by PM_MAIL_METHOD (default:
smtp if SMTP_PASSWORD is set, else gmail-oauth):

    gmail-oauth  Gmail REST API. `auth-gmail` signs in once and stores a
                 gmail.send-only token in the config dir (gmail-token.json);
                 it refreshes itself after that. The OAuth client is, in order:
                 PM_GMAIL_CLIENT (token goes beside it), credentials.json in the
                 config dir, or the bundled gmail_oauth_client.json — the
                 plugin's own client, with an Internal consent screen in the
                 BUU Workspace, so only accounts in that organisation can sign
                 in. With your own client, use an Internal consent screen: an
                 External app in Testing mode has refresh tokens that expire
                 after 7 days.
    smtp         SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD (Gmail: app
                 password, smtp.gmail.com:465).
    gmail-api    Gmail REST API with gcloud Application Default Credentials.
                 Google blocks gcloud's own client from the Gmail scopes on
                 many accounts ("This app is blocked"); prefer gmail-oauth.

CONFIG — ~/.config/nk-work-kit/.env (see scripts/.env.example)
--------------------------------------------------------------
Same lookup as check_pending.py: real env vars, then $XDG_CONFIG_HOME,
%APPDATA%, ~/.config (each /nk-work-kit/.env), then a .env beside this script.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import json
import os
import re
import sys
import tempfile
import urllib.parse
from dataclasses import asdict, dataclass, field
from email.message import EmailMessage
from pathlib import Path

import yaml

SKIP_DIRS = {".obsidian", ".trash", "Confidential"}
STATUS_ORDER = ["active", "waiting", "on-hold", "idea", "done", "dropped"]
PRIORITY_ORDER = {"high": 0, "normal": 1, "low": 2}
TASK_RE = re.compile(r"^\s*[-*] \[(?P<mark>.)\] (?P<body>.*)$")
DUE_RE = re.compile(r"📅\s*(\d{4}-\d{2}-\d{2})")
DASHBOARD_NAME = "Dashboard.md"


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


def vault_path() -> Path:
    raw = os.environ.get("OBSIDIAN_VAULT", "").strip()
    if not raw:
        sys.exit("OBSIDIAN_VAULT is not set (add it to ~/.config/nk-work-kit/.env).")
    vault = Path(raw).expanduser()
    if not (vault / ".obsidian").is_dir():
        sys.exit(f"OBSIDIAN_VAULT={vault} is not an Obsidian vault (no .obsidian/).")
    return vault


def projects_dir(vault: Path) -> Path:
    return vault / os.environ.get("PM_FOLDER", "Projects")


# ---------------------------------------------------------------- parsing

@dataclass
class Item:
    project: str
    kind: str            # next_action | task | project_due
    text: str
    due: str | None
    file: str            # vault-relative path
    line: int = 0


@dataclass
class Project:
    name: str
    file: str
    status: str = "active"
    priority: str = "normal"
    area: str = ""
    due: str | None = None
    next_action: str = ""
    next_action_due: str | None = None
    waiting_on: str = ""
    updated: str | None = None
    items: list[Item] = field(default_factory=list)


def as_date_str(v) -> str | None:
    if v in (None, ""):
        return None
    if isinstance(v, (dt.date, dt.datetime)):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    return s if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) else None


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    try:
        meta = yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        return {}, text
    return (meta if isinstance(meta, dict) else {}), text[end + 4:]


def iter_notes(vault: Path):
    for path in vault.rglob("*.md"):
        rel = path.relative_to(vault)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        yield path, rel


def open_tasks(text: str):
    """Yield (line_no, body_without_date, due) for open tasks."""
    for n, line in enumerate(text.splitlines(), 1):
        m = TASK_RE.match(line)
        if not m or m["mark"] not in (" ", "/"):   # open or in-progress
            continue
        body = m["body"]
        due = DUE_RE.search(body)
        clean = DUE_RE.sub("", body).strip()
        yield n, clean, due.group(1) if due else None


def scan(vault: Path) -> list[Project]:
    notes = {}
    projects: dict[str, Project] = {}
    for path, rel in iter_notes(vault):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        notes[rel] = text
        meta, _ = split_frontmatter(text)
        if str(meta.get("type", "")).lower() != "project":
            continue
        name = path.stem
        p = Project(
            name=name, file=rel.as_posix(),
            status=str(meta.get("status") or "active").lower(),
            priority=str(meta.get("priority") or "normal").lower(),
            area=str(meta.get("area") or ""),
            due=as_date_str(meta.get("due")),
            next_action=str(meta.get("next_action") or ""),
            next_action_due=as_date_str(meta.get("next_action_due")),
            waiting_on=str(meta.get("waiting_on") or ""),
            updated=as_date_str(meta.get("updated")),
        )
        if p.next_action:
            p.items.append(Item(name, "next_action", p.next_action, p.next_action_due, p.file))
        if p.due:
            p.items.append(Item(name, "project_due", "Project deadline", p.due, p.file))
        projects[name] = p

    # Tasks: in the hub itself, or elsewhere when the line links to the hub.
    by_file = {p.file: p for p in projects.values()}
    for rel, text in notes.items():
        own = by_file.get(rel.as_posix())
        for n, body, due in open_tasks(text):
            targets = []
            if own:
                targets.append(own)
            else:
                for link in re.findall(r"\[\[([^\]|#]+)", body):
                    if (p := projects.get(Path(link).stem)):
                        targets.append(p)
            for p in targets:
                p.items.append(Item(p.name, "task", body, due, rel.as_posix(), n))
    return sorted(projects.values(), key=lambda p: (
        STATUS_ORDER.index(p.status) if p.status in STATUS_ORDER else 99,
        PRIORITY_ORDER.get(p.priority, 1), p.name))


# ---------------------------------------------------------------- analysis

def today() -> dt.date:
    if (fake := os.environ.get("PM_TODAY")):      # for testing
        return dt.date.fromisoformat(fake)
    return dt.date.today()


def buckets(projects: list[Project], days: int):
    t = today()
    horizon = t + dt.timedelta(days=days)
    overdue, soon = [], []
    for p in projects:
        if p.status in ("done", "dropped"):
            continue
        # The next action and project deadline usually restate a dated task;
        # don't list both.
        task_dues = {it.due for it in p.items if it.kind == "task"}
        for it in p.items:
            if not it.due or (it.kind != "task" and it.due in task_dues):
                continue
            d = dt.date.fromisoformat(it.due)
            if d < t:
                overdue.append(it)
            elif d <= horizon:
                soon.append(it)
    key = lambda it: (it.due, it.project)
    return sorted(overdue, key=key), sorted(soon, key=key)


def is_stale(p: Project, stale_days: int) -> bool:
    if p.status not in ("active", "waiting"):
        return False
    if not p.updated:
        return True
    return (today() - dt.date.fromisoformat(p.updated)).days > stale_days


def rel_days(due: str) -> str:
    n = (dt.date.fromisoformat(due) - today()).days
    if n == 0:
        return "today"
    if n < 0:
        return f"{-n}d late"
    return f"in {n}d"


# ---------------------------------------------------------------- links

def wikilink(rel: str, alias: str | None = None, table: bool = False) -> str:
    target = rel[:-3] if rel.endswith(".md") else rel
    sep = "\\|" if table else "|"
    return f"[[{target}{sep}{alias}]]" if alias else f"[[{target}]]"


def obsidian_uri(vault: Path, rel: str) -> str:
    # The vault's name in the desktop app; override when this machine's copy of
    # the vault sits in a differently named folder (e.g. a server).
    name = os.environ.get("PM_VAULT_NAME") or vault.name
    q = urllib.parse.urlencode({"vault": name, "file": rel[:-3] if rel.endswith(".md") else rel},
                               quote_via=urllib.parse.quote)
    return f"obsidian://open?{q}"


def cell(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


# ---------------------------------------------------------------- dashboard

def render_dashboard(vault: Path, projects: list[Project], days: int, stale_days: int) -> str:
    overdue, soon = buckets(projects, days)
    by_name = {p.name: p for p in projects}
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    folder = os.environ.get("PM_FOLDER", "Projects")
    out = [
        "---", "type: dashboard", f"generated: {now}", "---",
        "# Projects Dashboard", "",
        f"> [!info] Generated by `projects.py dashboard` at {now}. Edits here are overwritten —"
        " change the project notes instead.", "",
    ]

    def item_rows(items):
        rows = ["| Due | Project | Item |", "|---|---|---|"]
        for it in items:
            src = wikilink(it.file, it.project, table=True)
            text = cell(it.text)
            if it.kind == "task" and it.file != by_name[it.project].file:
                text += " (" + wikilink(it.file, Path(it.file).stem, table=True) + ")"
            elif it.kind == "next_action":
                text = "**Next:** " + text
            rows.append(f"| {it.due} · {rel_days(it.due)} | {src} | {text} |")
        return rows

    out += [f"## 🔴 Overdue ({len(overdue)})", ""]
    out += item_rows(overdue) if overdue else ["Nothing overdue."]
    out += ["", f"## 🟡 Due in the next {days} days ({len(soon)})", ""]
    out += item_rows(soon) if soon else ["Nothing due."]

    def project_table(ps, cols_waiting=False):
        head = "| Project | Status | Priority | Next action | Due | Updated |"
        if cols_waiting:
            head = "| Project | Waiting on | Next action | Due | Updated |"
        rows = [head, "|" + "---|" * (head.count("|") - 1)]
        for p in ps:
            upd = (p.updated or "—") + (" ⚠️ stale" if is_stale(p, stale_days) else "")
            due = p.next_action_due or p.due or ""
            if cols_waiting:
                rows.append(f"| {wikilink(p.file, p.name, table=True)} | {cell(p.waiting_on)} | "
                            f"{cell(p.next_action)} | {due} | {upd} |")
            else:
                rows.append(f"| {wikilink(p.file, p.name, table=True)} | {p.status} | {p.priority} | "
                            f"{cell(p.next_action)} | {due} | {upd} |")
        return rows

    active = [p for p in projects if p.status == "active"]
    waiting = [p for p in projects if p.status == "waiting"]
    parked = [p for p in projects if p.status in ("on-hold", "idea")]
    closed = [p for p in projects if p.status in ("done", "dropped")]

    out += ["", f"## Active projects ({len(active)})", ""]
    out += project_table(active) if active else ["None."]
    # Waiting-on also surfaces active projects that name someone to chase.
    chase = waiting + [p for p in active if p.waiting_on]
    out += ["", f"## ⏳ Waiting on others ({len(chase)})", ""]
    out += project_table(chase, cols_waiting=True) if chase else ["None."]
    if parked:
        out += ["", f"> [!note]- On hold / ideas ({len(parked)})"]
        out += ["> " + r for r in project_table(parked)]
    if closed:
        out += ["", f"> [!success]- Done / dropped ({len(closed)})"]
        out += ["> " + f"- {wikilink(p.file, p.name)} — {p.status}" for p in closed]

    # Live views: the Tasks plugin (installed) and Dataview (optional).
    out += [
        "", "## Live views", "",
        "Open dated tasks in project notes (Tasks plugin, always current):", "",
        "```tasks", "not done", "has due date", f"path includes {folder}",
        "sort by due", "group by filename", "```", "",
        "> [!tip]- Dataview table (renders only if the Dataview plugin is installed)",
        "> ```dataview",
        "> TABLE status, priority, next_action AS \"Next action\", next_action_due AS \"Due\", updated",
        "> FROM \"\" WHERE type = \"project\" AND status != \"done\" AND status != \"dropped\"",
        "> SORT priority ASC, next_action_due ASC",
        "> ```", "",
    ]
    return "\n".join(out)


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".md")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------- digest

def digest(vault: Path, projects: list[Project], days: int) -> dict:
    overdue, soon = buckets(projects, days)
    by_name = {p.name: p for p in projects}

    def row(it: Item) -> dict:
        return {**asdict(it), "when": rel_days(it.due),
                "link": obsidian_uri(vault, it.file),
                "project_link": obsidian_uri(vault, by_name[it.project].file)}
    return {
        "today": today().isoformat(), "days": days,
        "overdue": [row(i) for i in overdue], "due_soon": [row(i) for i in soon],
        "dashboard_link": obsidian_uri(vault, f"{os.environ.get('PM_FOLDER', 'Projects')}/{DASHBOARD_NAME}"),
    }


def digest_text(d: dict) -> str:
    lines = [f"Projects digest — {d['today']}", ""]
    for title, key in (("OVERDUE", "overdue"), (f"DUE IN {d['days']} DAYS", "due_soon")):
        lines.append(f"{title} ({len(d[key])})")
        for it in d[key]:
            lines.append(f"  {it['due']} ({it['when']})  [{it['project']}]  {it['text']}")
        lines.append("")
    lines.append(f"Dashboard: {d['dashboard_link']}")
    return "\n".join(lines)


def digest_html(d: dict) -> str:
    def table(items, colour):
        if not items:
            return "<p style='color:#666'>None.</p>"
        rows = "".join(
            f"<tr><td style='white-space:nowrap;padding:4px 8px;color:{colour}'>"
            f"{it['due']}<br><small>{html.escape(it['when'])}</small></td>"
            f"<td style='padding:4px 8px'><a href='{html.escape(it['project_link'])}'>"
            f"{html.escape(it['project'])}</a></td>"
            f"<td style='padding:4px 8px'><a href='{html.escape(it['link'])}'>"
            f"{html.escape(it['text'])}</a></td></tr>" for it in items)
        return f"<table style='border-collapse:collapse;font-size:14px'>{rows}</table>"
    return (
        "<div style='font-family:sans-serif'>"
        f"<h2 style='margin:0 0 8px'>Projects digest — {d['today']}</h2>"
        f"<h3 style='color:#b00020'>🔴 Overdue ({len(d['overdue'])})</h3>{table(d['overdue'], '#b00020')}"
        f"<h3 style='color:#8a6d00'>🟡 Due in {d['days']} days ({len(d['due_soon'])})</h3>"
        f"{table(d['due_soon'], '#8a6d00')}"
        f"<p><a href='{html.escape(d['dashboard_link'])}'>Open the dashboard in Obsidian</a></p>"
        "<p style='color:#888;font-size:12px'>Links open in the Obsidian desktop app. "
        "Sent by nk-work-kit projects.py.</p></div>")


# ---------------------------------------------------------------- sending

def build_message(d: dict, to: str, sender: str) -> EmailMessage:
    n_over, n_soon = len(d["overdue"]), len(d["due_soon"])
    msg = EmailMessage()
    msg["Subject"] = f"[Projects] {n_over} overdue, {n_soon} due soon — {d['today']}"
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(digest_text(d))
    msg.add_alternative(digest_html(d), subtype="html")
    return msg


def send_smtp(msg: EmailMessage) -> None:
    import smtplib
    import ssl
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    user, pw = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASSWORD")
    if not (user and pw):
        sys.exit("SMTP_USER / SMTP_PASSWORD are not set.")
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
            s.login(user, pw)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(user, pw)
            s.send_message(msg)


def send_gmail_api(msg: EmailMessage, creds=None) -> None:
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    if creds is None:
        try:
            creds, _ = google.auth.default(scopes=GMAIL_SEND)
        except google.auth.exceptions.DefaultCredentialsError as e:
            sys.exit(f"No Application Default Credentials: {e}")
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    r = AuthorizedSession(creds).post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send", json={"raw": raw}, timeout=30)
    if r.status_code >= 300:
        hint = ""
        if r.status_code in (401, 403):
            hint = ("\nThe credentials probably lack the gmail.send scope, or the Gmail API "
                    "is not enabled in the OAuth client's Cloud project (see SKILL.md).")
        sys.exit(f"Gmail API send failed: HTTP {r.status_code} {r.text[:300]}{hint}")


GMAIL_SEND = ["https://www.googleapis.com/auth/gmail.send"]


# The plugin's own Desktop OAuth client (BUU Workspace project, Internal consent
# screen, gmail.send only). Google treats an installed app's client secret as
# not confidential; each user's token stays in their own config dir.
BUNDLED_CLIENT = Path(__file__).resolve().parent / "gmail_oauth_client.json"


def gmail_oauth_paths() -> tuple[Path, Path]:
    """(client JSON, token). Client: PM_GMAIL_CLIENT, else credentials.json in the
    config dir, else the bundled one. The token sits beside PM_GMAIL_CLIENT when
    that is set, otherwise in the config dir: never beside the bundled client,
    which lives in the version-pinned plugin cache."""
    if os.environ.get("PM_GMAIL_CLIENT"):
        client = Path(os.environ["PM_GMAIL_CLIENT"]).expanduser()
        return client, client.with_name("gmail-token.json")
    own = config_dir() / "credentials.json"
    return (own if own.is_file() else BUNDLED_CLIENT), config_dir() / "gmail-token.json"


def cmd_auth_gmail() -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow
    client, token = gmail_oauth_paths()
    if not client.is_file():
        sys.exit(f"OAuth client file not found: {client} (Desktop app JSON from Google Cloud).")
    print(f"OAuth client: {client}")
    token.parent.mkdir(parents=True, exist_ok=True)
    flow = InstalledAppFlow.from_client_secrets_file(str(client), GMAIL_SEND)
    creds = flow.run_local_server(port=0, open_browser=True,
                                  authorization_prompt_message="Sign in in your browser: {url}")
    fd = os.open(token, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    print(f"Saved {token} (scope: gmail.send only).")


def gmail_oauth_creds():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    _, token = gmail_oauth_paths()
    if not token.is_file():
        sys.exit(f"No Gmail token at {token}. Run `projects.py auth-gmail` once.")
    creds = Credentials.from_authorized_user_file(str(token), GMAIL_SEND)
    if not creds.valid:
        creds.refresh(Request())
        token.write_text(creds.to_json(), encoding="utf-8")
    return creds


# ---------------------------------------------------------------- new

TEMPLATE = """---
type: project
status: active
priority: {priority}
area: {area}
start: {start}
due: {due}
next_action: ""
next_action_due:
waiting_on: ""
updated: {start}
---
# {name}

## Summary


## Milestones / Tasks
- [ ]

## Related notes


## Log
- {start} — Project note created.
"""


def cmd_new(vault: Path, a) -> None:
    safe = re.sub(r'[\\/:*?"<>|]', "-", a.name).strip()
    path = projects_dir(vault) / f"{safe}.md"
    if path.exists():
        sys.exit(f"Already exists: {path.relative_to(vault)}")
    write_atomic(path, TEMPLATE.format(name=a.name, area=a.area or "", due=a.due or "",
                                       priority=a.priority, start=today().isoformat()))
    print(path.relative_to(vault).as_posix())


# ---------------------------------------------------------------- main

def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    load_env()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list"); s.add_argument("--json", action="store_true")
    sub.add_parser("dashboard")
    sub.add_parser("auth-gmail")
    s = sub.add_parser("digest")
    s.add_argument("--days", type=int); s.add_argument("--format", choices=["text", "html", "json"], default="text")
    s = sub.add_parser("notify")
    s.add_argument("--days", type=int)
    s.add_argument("--dry-run", action="store_true", help="print the message instead of sending")
    s.add_argument("--force", action="store_true", help="send even when nothing is due")
    s = sub.add_parser("new")
    s.add_argument("name"); s.add_argument("--area"); s.add_argument("--due")
    s.add_argument("--priority", default="normal", choices=list(PRIORITY_ORDER))
    a = ap.parse_args()

    if a.cmd == "auth-gmail":
        return cmd_auth_gmail()
    vault = vault_path()
    days = getattr(a, "days", None) or int(os.environ.get("PM_NOTIFY_DAYS", "14"))
    stale_days = int(os.environ.get("PM_STALE_DAYS", "14"))

    if a.cmd == "new":
        return cmd_new(vault, a)
    projects = scan(vault)

    if a.cmd == "list":
        if a.json:
            print(json.dumps([{**asdict(p), "stale": is_stale(p, stale_days),
                               "link": obsidian_uri(vault, p.file)} for p in projects],
                             ensure_ascii=False, indent=2))
        else:
            for p in projects:
                print(f"{p.status:8} {p.priority:6} {p.name}  →  {p.next_action or '—'}"
                      f"{' (' + p.next_action_due + ')' if p.next_action_due else ''}")
    elif a.cmd == "dashboard":
        path = projects_dir(vault) / DASHBOARD_NAME
        write_atomic(path, render_dashboard(vault, projects, days, stale_days))
        o, s_ = buckets(projects, days)
        print(f"{path.relative_to(vault).as_posix()}: {len(projects)} projects, "
              f"{len(o)} overdue, {len(s_)} due in {days}d")
    elif a.cmd == "digest":
        d = digest(vault, projects, days)
        print({"json": lambda: json.dumps(d, ensure_ascii=False, indent=2),
               "html": lambda: digest_html(d), "text": lambda: digest_text(d)}[a.format]())
    elif a.cmd == "notify":
        d = digest(vault, projects, days)
        if not (d["overdue"] or d["due_soon"]) and not a.force:
            print("Nothing overdue or due soon — no email sent.")
            return
        to = os.environ.get("PM_NOTIFY_TO", "").strip()
        if not to:
            sys.exit("PM_NOTIFY_TO is not set.")
        method = (os.environ.get("PM_MAIL_METHOD", "").strip()
                  or ("smtp" if os.environ.get("SMTP_PASSWORD") else "gmail-oauth"))
        msg = build_message(d, to, os.environ.get("SMTP_USER") or to)
        if a.dry_run:
            print(f"[dry-run via {method}] To: {to}\nSubject: {msg['Subject']}\n\n{digest_text(d)}")
            return
        {"smtp": send_smtp, "gmail-api": send_gmail_api,
         "gmail-oauth": lambda m: send_gmail_api(m, gmail_oauth_creds())}.get(
            method, lambda m: sys.exit(f"Unknown PM_MAIL_METHOD={method}"))(msg)
        print(f"Sent via {method} to {to}: {msg['Subject']}")


if __name__ == "__main__":
    main()

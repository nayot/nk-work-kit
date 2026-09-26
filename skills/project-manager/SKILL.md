---
name: project-manager
description: Activate this skill when the user wants to see or update the status of their ongoing projects, tracked as notes in their Obsidian vault — "project status", "สถานะโครงการ", "สถานะโปรเจกต์", "update the X project", "อัปเดตโครงการ", "what's due this week", "มีอะไรใกล้ถึงกำหนด", "มีอะไรเลยกำหนด", "what's overdue", "add a new project", "เพิ่มโครงการ", "update the dashboard", "project digest", "set up project tracking", "ตั้งค่าติดตามโครงการ", "set up the inbox scan", "scan my email for tasks", "ตั้งค่าสแกนอีเมลหางาน". Also activate after a meeting summary, transcript, memo, document number or eDoc item clearly belongs to a tracked project — offer to log it there. Can set up a scheduled email digest of upcoming and overdue items, and a scheduled scan of Gmail and Calendar that adds new tasks to the matching project.
argument-hint: "[setup | status | due | update <project> | new <name> | dashboard | setup-notify | setup-scan]"
allowed-tools: [Bash, Read, Edit, Write]
version: 1.5.1
---

# Project manager — Obsidian as database and dashboard

Projects live in the user's Obsidian vault as **hub notes**. One script reads
them, rebuilds the dashboard note and sends the email digest:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/projects.py" list --json
```

If `CLAUDE_PLUGIN_ROOT` is not set, the script sits at
`<plugin-root>/scripts/projects.py`. The vault path comes from `OBSIDIAN_VAULT`
in `~/.config/nk-work-kit/.env`. If it is missing, ask the user for the vault
folder (the one containing `.obsidian/`) and add it.

## First run: setup and onboarding

Run this when `$ARGUMENTS` is `setup`, when the user asks to set up project
tracking, or when `list --json` returns no projects. Go step by step and ask
before every write. It must never modify the user's existing notes.

1. **Find the vault.** If `OBSIDIAN_VAULT` is unset, read Obsidian's vault
   list: `obsidian.json` in `~/.config/obsidian/` (Linux),
   `~/Library/Application Support/obsidian/` (macOS) or `%APPDATA%\obsidian\`
   (Windows). Offer the vault marked `"open": true`, or the most recent one.
   With the user's OK, append `OBSIDIAN_VAULT=<path>` to
   `~/.config/nk-work-kit/.env`, creating it with `chmod 600` if needed.
2. **Survey, read-only:**
   - plugins in `.obsidian/community-plugins.json` (Tasks? Dataview?
     Templater?);
   - top-level folders, and whether a `Projects/` folder exists;
   - how notes already record dates, tasks and frontmatter;
   - how the vault syncs (Obsidian Sync, Syncthing, rclone, cloud drive).

   The sync method matters later for scheduling and for which machine writes
   the dashboard. If Dataview is missing, recommend installing it: the
   dashboard's live views need it (Settings → Community plugins → Browse →
   Dataview → Install → Enable). The user installs plugins, not you. Also
   suggest two Dataview settings, **Automatic task completion tracking** and
   **Use emoji shorthand for completion**, so that ticking a task in the
   dashboard writes `✅ <date>` as this model expects. Never edit
   `.obsidian/` yourself. Fit the hub notes to what you find: reuse the user's due-date
   format and don't impose a folder layout.
3. **Find candidate projects.** Look for:
   - notes edited in the last 60–90 days;
   - folders or name prefixes that group several notes, and runs of meeting
     notes on one topic;
   - notes with many open checkboxes;
   - existing index or "start here" notes.

   If Gmail or Calendar connectors are available, search recent mail and
   upcoming events for the same topics. Propose **5–8** candidates, one line
   each saying why you think it is a project and how recently it was touched.
   The user picks, adds or drops.
4. **Pre-fill a card per project.** Read each project's notes. With more than
   three projects, use parallel read-only subagents, one or two projects each.
   Each card has:
   - a summary (what, who, the user's role);
   - status and priority (marked as your guess);
   - key dates, each with its source;
   - next action with its due date, and waiting-on;
   - open tasks still worth doing;
   - related notes as `[[links]]`;
   - open questions.

   Present all cards together as a compact table plus a short list of
   inconsistencies found (conflicting dates, duplicate or empty notes, notes
   filed under the wrong topic). Ask about ownership and changes since the
   notes were written.
5. **One correction round.** Accept terse answers ("1: all mine, 3: Stef will
   sign"). If the user points you to email or calendar for dates, search there.
6. **Create the hubs.** Write one hub note per project in `Projects/` (or the
   user's chosen folder) using the data model above:
   - `📅` only on dates that have a source; suggested buffers are noted as such
     in the Log;
   - a first Log line saying where the information came from.

   Then run `dashboard` and show the counts: projects, overdue, due soon.
7. **Offer the email digest (optional).** Walk through **Email digest** below:
   - pick a mail method;
   - `notify --dry-run`, then a single `notify --force` to the user's own
     address, and confirm it arrived;
   - schedule it using the layout table under **Scheduling**. Ask whether the
     desktop stays on and whether an always-on server can see the vault. The
     Dataview dashboard is live, so it needs no timer of its own.

   If the user's instructions require approval before sending email, get an
   explicit standing exception for this digest first, and record it where they
   keep such rules. Otherwise stop at the dry run.

Finish with a short summary: the hub notes created, the dashboard path, the
notification state, and what the user still has to answer.

## The data model

A project is any note with `type: project` in its frontmatter. Hub notes go in
`Projects/` (`PM_FOLDER`), and they **link to** the user's existing notes rather
than replacing them.

```yaml
---
type: project
status: active        # idea | active | waiting | on-hold | done | dropped
priority: high        # high | normal | low
area: GoogleDCI
start: 2026-07-13
due: 2026-12-15       # project deadline, optional
next_action: "One concrete next step"
next_action_due: 2026-10-02
waiting_on: "Person/office — what for"
updated: 2026-09-25   # set to today whenever you touch the note
---
```

Body sections are **Summary**, **Milestones / Tasks**, **Related notes** and
**Log**. Tasks use the Tasks-plugin format:
`- [ ] Send draft MOU 📅 2026-10-02`, done as `- [x] … ✅ 2026-10-01`. A task in
any other note counts for a project when its line links the hub
(`- [ ] Book room [[ABET Accreditation]] 📅 2026-10-05`).

## Commands

| Command | Use |
|---|---|
| `list --json` | Read every project with its dated items. **Start here** for any status question. |
| `dashboard` | Rewrite `Projects/Dashboard.md` (and write the manual if it is missing or outdated). Run after every change. |
| `manual [--force]` | Write `Projects/User Manual.md`, the bilingual (English/Thai) user manual, linked both ways with the dashboard. |
| `digest [--days N] [--format text\|html\|json]` | Overdue and upcoming items. The default window is `PM_NOTIFY_DAYS` (14). |
| `notify [--dry-run] [--force]` | Email the digest to `PM_NOTIFY_TO`. It stays silent when nothing is due. |
| `auth-gmail [--scan]` | One-time browser sign-in for `PM_MAIL_METHOD=gmail-oauth`. `--scan` adds read-only Gmail and Calendar, for `scan-inbox`. On a machine without a browser it prints a link instead; after signing in on any device, pass the `http://localhost:1/?…` address the browser ends on to `auth-gmail --url '<address>'`. |
| `scan-inbox [--dry-run]` | Find new tasks in Gmail and upcoming Calendar events with `claude -p`, and append them to the matching hub's `## Suggested from inbox` section. |
| `new "Name" --area A --due D --priority P` | Create a hub note from the template, then fill it in. |

## Inbox scan (optional)

`scan-inbox` reads Gmail since its last run (archived or not; everything but
Promotions, Social and Updates, or `PM_SCAN_GMAIL_QUERY`) and primary-calendar
events in the next `PM_SCAN_DAYS` (14), and makes one `claude -p` call with no
tools, MCP servers or settings, whose only output is a JSON list of tasks. The
script validates every task (a project that exists and isn't done or dropped,
a source from this run, a date within a year, bounded text, confidence at
least `PM_SCAN_MIN_CONFIDENCE`) and appends the ones that pass to the hub's
`## Suggested from inbox` section:

```
- [ ] Send Audra the final site-visit schedule ([✉ Site visit logistics](https://mail.google.com/…)) ➕ 2026-09-26 📅 2026-09-30
```

It never touches frontmatter, so `updated:` still means "last reviewed". What
it skipped, and why, is printed (`journalctl --user -u nk-projects-scan`).
Processed ids live in `~/.local/share/nk-work-kit/inbox-scan.json`; delete the
file to rescan the last two days. Email content goes to Anthropic through
`claude -p`, so mention that when setting it up.

When reviewing a project with the user, go through its `## Suggested from
inbox` tasks: keep the good ones (move them under Milestones / Tasks if the
user prefers), delete the wrong ones, and bump `updated:` only after the user
has reviewed them.

## Working with the user

**Status questions** ("what's due", "สถานะโครงการ"): run `list --json` or
`digest --format json` and answer from it:

- lead with overdue items, then the next 14 days, then projects that are
  `waiting` or stale (`stale: true`, meaning not updated for more than
  `PM_STALE_DAYS` days);
- link each project as `[[Hub name]]`;
- don't paste the whole dashboard.

**Updates:** when the user reports progress, or a session produces something
that belongs to a project (a meeting note, transcript, memo, document number or
eDoc item), offer to log it. Keep your own words out of the user's notes:
record what happened, don't editorialise. Then:

1. Edit the hub note:
   - tick finished tasks, adding `✅ <today>`;
   - add new tasks, with `📅` only when a real date is known;
   - update the `next_action`, `next_action_due`, `waiting_on`, `status` and
     `updated` fields;
   - link the new note under **Related notes**;
   - append a dated line to **Log**.
2. A **status** change (for example active → done or waiting) is the user's
   call. Propose it and apply it only after they agree. Routine edits (ticking a
   task they said is done, logging a note) need no confirmation.
3. Run `dashboard`.

**Dates:** only put dates in `📅` or the `*_due` fields when they come from
the user, an email, a calendar event or a document. A date you suggest as a
buffer must be marked as a suggestion in the Log line.

**New projects** (one at a time, after setup): look for existing notes about the project first, so the hub
can link them, then create it with `new` and fill in the sections. You can offer
to pre-fill the hub from the vault, email and calendar.

**Never** edit or move the user's other notes to fit this model. The only
exception is adding a hub link to a task line, and only when the user asks.
Skip `Confidential/` (encrypted notes). The dashboard is generated, so never
hand-edit it.

## The dashboard

`Projects/Dashboard.md` is made of **live Dataview views**:

- 🔴 Overdue and 🟡 Due in the next N days (`PM_NOTIFY_DAYS`). Each has a
  `TASK` view of dated tasks, grouped by note, and a table of next actions and
  project deadlines that no open task already restates;
- Active projects, with priority, next action, waiting-on and a stale flag
  (`PM_STALE_DAYS`);
- Waiting on others.

The views follow `projects.py`'s rules: a task counts when it sits in a hub
under `PM_FOLDER` or links to one, has a `📅` date, and isn't done or
cancelled. They re-render as soon as any note changes. Ticking a task in a
`TASK` view edits the source note, and Dataview (not the Tasks plugin) handles
that click, so `✅ <date>` is written only when the two Dataview settings from
setup are on.

Above the views, a callout explains how to install Dataview. It is expanded
when the vault's `.obsidian/community-plugins.json` doesn't enable Dataview,
and collapsed when it does. Without Dataview the dashboard shows only code
blocks, so answer status questions from `list --json` or the digest.

The dashboard links to **`User Manual.md`** in the same folder, a bilingual
(English and Thai) guide for the user. It is written from
`templates/project-manager-manual.md` and carries `plugin_version` in its
frontmatter. The plugin's `SessionStart` hook (`hooks/hooks.json`) runs
`manual --quiet` at startup. That call rewrites the manual only when it is
missing or was written by another plugin version, so it refreshes in the first
session after an install or update. It does nothing when the vault or the
projects folder isn't set up. The manual is generated, so never hand-edit it;
edit the template instead. When the user asks how the system works, point
them to it.

The views need no rebuild when notes change. Run `dashboard` once at setup,
and again after changing `PM_FOLDER`, `PM_NOTIFY_DAYS` or `PM_STALE_DAYS`
(all baked into the queries) or after installing Dataview (to collapse the
install callout). Don't paste the DQL into answers: answer status questions
from `list --json` as described above.

## Email digest (optional)

`notify` sends only when something is overdue or due within the window. Every
item links to its note through an `obsidian://open?vault=…&file=…` URL, which
opens in the Obsidian desktop app. The mail method is `PM_MAIL_METHOD`:

- **`gmail-oauth`** (the default, recommended): no Google Cloud setup needed.
  - Run `projects.py auth-gmail` once. It opens a browser; the user signs in
    with their BUU Google account and allows "send email". It stores a
    send-only token in `~/.config/nk-work-kit/gmail-token.json`.
  - It uses the plugin's bundled OAuth client (`scripts/gmail_oauth_client.json`,
    Internal consent screen in the BUU Workspace). An account outside that
    organisation gets "restricted to users within its organization": that user
    needs their own client (below) or `smtp`.
  - The bundled client file is public on purpose: Google treats an installed
    app's client secret as non-confidential, and the Internal consent screen
    limits it to BUU accounts. The per-user `gmail-token.json` **is** secret:
    never copy it into the repo, a chat or a shared folder.
  - **Own client (optional):** create a Google Cloud project under the
    Workspace organisation, enable the **Gmail API**, set the consent screen to
    **Internal** with the single scope `gmail.send`, create an OAuth client ID
    of type **Desktop app**, and save its JSON as
    `~/.config/nk-work-kit/credentials.json` (or point `PM_GMAIL_CLIENT` at it;
    the token then goes beside that file), `chmod 600`. An **External /
    Testing** app's token expires after 7 days, which breaks a daily timer.
- **`gmail-api`**: gcloud ADC. Google often blocks gcloud's own sign-in from
  requesting Gmail permission ("This app is blocked"), so prefer
  `gmail-oauth`. Where it isn't blocked, the ADC login must include `gmail.send`, and re-running the login replaces the
  old one, so keep any scopes other tools rely on. For example:
  `gcloud auth application-default login --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/contacts,https://www.googleapis.com/auth/gmail.send`
- **`smtp`**: `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD`. For
  Gmail use smtp.gmail.com:465 with an **app password**. Some Workspace admins
  disable app passwords.

**Email approval rules.** If the user's instructions say email needs approval,
an automatic digest is allowed only under a standing exception they have
granted. Until then, suggest `--dry-run` or a Gmail draft instead. Only ever
send to the user's own `PM_NOTIFY_TO`.

### Scheduling, when the user asks to set it up

First, pick the layout from the user's machines. **Exactly one** machine
writes the dashboard, and **exactly one** sends the email:

| User has | Dashboard (on the vault's machine) | Email digest |
|---|---|---|
| A desktop that is always on | email timer's `dashboard` step | desktop email timer |
| A desktop that is often off | none needed (Dataview is live) | desktop email timer (`Persistent=true` catches up after boot) |
| Desktop + always-on server | desktop (Claude's `dashboard` runs) | **server** email timer, running `notify` only when it sees a one-way copy of the vault |
| No machine to schedule on | Claude rebuilds it on each update | none, or a cloud routine that writes a Gmail draft |

Offer the matching timers. Ask whether the machine stays on, and whether an
always-on server with access to the vault exists.

Test first: run `notify --dry-run`, then `notify --force` once, and confirm the
message arrived.

- **Linux (systemd user timer)**, weekdays at 07:00. Replace `<uv>` with the
  output of `command -v uv`, and `<plugin-root>` with the real path. Point it at
  a stable location: a git clone, or the `nk-work-kit` symlink the user keeps.
  The version-pinned cache directory changes on every upgrade.

  `~/.config/systemd/user/nk-projects-notify.service`:
  ```ini
  [Unit]
  Description=nk-work-kit project digest
  [Service]
  Type=oneshot
  ExecStart=<uv> run <plugin-root>/scripts/projects.py dashboard
  ExecStart=<uv> run <plugin-root>/scripts/projects.py notify
  ```

  `~/.config/systemd/user/nk-projects-notify.timer`:
  ```ini
  [Unit]
  Description=Weekday project digest
  [Timer]
  OnCalendar=Mon..Fri 07:00
  Persistent=true
  [Install]
  WantedBy=timers.target
  ```

  Then run `systemctl --user daemon-reload && systemctl --user enable --now nk-projects-notify.timer`.
  `Persistent=true` catches up after the machine was off at 07:00.
- **Dashboard-only timer (optional).** The Dataview views are always
  current, so this timer is rarely needed now. It only picks up config changes
  without a manual `dashboard` run. It rebuilds the dashboard 2 minutes after login and every 3 hours after that, and **never
  sends email**, so it can run as often as needed. Install it on the machine
  that owns the dashboard (usually the desktop where the vault lives),
  alongside or instead of the email timer.

  `~/.config/systemd/user/nk-projects-dashboard.service`:
  ```ini
  [Unit]
  Description=nk-work-kit project dashboard
  [Service]
  Type=oneshot
  ExecStart=<uv> run <plugin-root>/scripts/projects.py dashboard
  ```

  `~/.config/systemd/user/nk-projects-dashboard.timer`:
  ```ini
  [Unit]
  Description=Rebuild project dashboard after login and every 3h
  [Timer]
  OnStartupSec=2min
  OnUnitActiveSec=3h
  [Install]
  WantedBy=timers.target
  ```

  Then run `systemctl --user daemon-reload && systemctl --user enable --now nk-projects-dashboard.timer`.
  On macOS, use a launchd agent with `RunAtLoad` and `StartInterval=10800`.
  On Windows, use a Task Scheduler task "At log on", repeating every 3 hours.
- **macOS:** a launchd agent with `StartCalendarInterval`. **Windows:** Task
  Scheduler running `uv run …\projects.py notify`. **Any Unix with cron:**
  `0 7 * * 1-5 <uv> run <plugin-root>/scripts/projects.py notify`.
- **An always-on server (recommended when the desktop is often off).** The
  server only needs `uv`, a git clone of this repo (update it with
  `git pull`) and the config. It doesn't need Claude Code or the plugin.
  1. Copy `~/.config/nk-work-kit/.env`, `gmail-token.json` (and
     `credentials.json`, if you use your own client) to the same place on the server, with `chmod 600`. The
     token refreshes itself, so no browser is needed there.
  2. In the server's `.env`, set `OBSIDIAN_VAULT` to the server's copy of the
     vault. Set `PM_VAULT_NAME` to the vault's name **on the desktop**, so the
     emailed `obsidian://` links open the right vault.
  3. **Decide who writes the dashboard.** If the server sees the vault through
     a **one-way** copy (for example the desktop's `rclone sync` to Google
     Drive), the server runs **`notify` only**: remove the `dashboard`
     ExecStart from its service. Anything it writes would never reach the
     desktop and would be overwritten. The desktop keeps the dashboard, using
     Claude's `dashboard` runs. Only with two-way
     sync (Syncthing, Obsidian Sync, or the vault living on the server) may
     the server run `dashboard` too, and even then only one machine should
     write it.
  4. Timezone: `OnCalendar` uses the server's local time. Check `timedatectl`,
     or write the zone into the schedule:
     `OnCalendar=Mon..Fri 07:00 Asia/Bangkok`.
  5. Run `loginctl enable-linger $USER` so the user timer runs without anyone
     logged in.
  6. Run `notify --dry-run` on the server, then `notify --force` once. When it
     works, **disable the desktop's email timer**
     (`systemctl --user disable --now nk-projects-notify.timer`) so only one
     machine sends.
- **Inbox scan timer (optional).** Runs `scan-inbox` and then `dashboard` at
  04:40 and 12:40, so the 05:00 digest already includes that morning's new
  tasks. It needs `claude` signed in on the same machine. Set it up only after
  `auth-gmail --scan` and a `scan-inbox --dry-run` the user has looked at.

  `~/.config/systemd/user/nk-projects-scan.service`:

  ```ini
  [Unit]
  Description=nk-work-kit inbox scan
  [Service]
  Type=oneshot
  TimeoutStartSec=15min
  ExecStart=<uv> run <plugin-root>/scripts/projects.py scan-inbox
  ExecStart=<uv> run <plugin-root>/scripts/projects.py dashboard
  ```

  `~/.config/systemd/user/nk-projects-scan.timer`:

  ```ini
  [Unit]
  Description=Scan Gmail + Calendar for project tasks
  [Timer]
  OnCalendar=*-*-* 04,12:40:00 Asia/Bangkok
  Persistent=true
  [Install]
  WantedBy=timers.target
  ```
- **No always-on machine:** a Claude cloud routine (`/schedule`) can read a
  cloud copy of the vault (for example Google Drive) and create a Gmail
  **draft** digest. Or skip scheduling entirely and ask "what's due?" in a
  session. Both are fine.

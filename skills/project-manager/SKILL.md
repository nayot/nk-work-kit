---
name: project-manager
description: Activate this skill when the user wants to see or update the status of their ongoing projects, tracked as notes in their Obsidian vault — "project status", "สถานะโครงการ", "สถานะโปรเจกต์", "update the X project", "อัปเดตโครงการ", "what's due this week", "มีอะไรใกล้ถึงกำหนด", "มีอะไรเลยกำหนด", "what's overdue", "add a new project", "เพิ่มโครงการ", "update the dashboard", "project digest". Also activate after a meeting summary, transcript, memo, document number or eDoc item clearly belongs to a tracked project — offer to log it there. Can set up a scheduled email digest of upcoming and overdue items.
argument-hint: "[status | due | update <project> | new <name> | dashboard | setup-notify]"
allowed-tools: [Bash, Read, Edit, Write]
version: 1.0.0
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
| `dashboard` | Rewrite `Projects/Dashboard.md`. Run after every change. |
| `digest [--days N] [--format text\|html\|json]` | Overdue and upcoming items. The default window is `PM_NOTIFY_DAYS` (14). |
| `notify [--dry-run] [--force]` | Email the digest to `PM_NOTIFY_TO`. It stays silent when nothing is due. |
| `auth-gmail` | One-time browser sign-in for `PM_MAIL_METHOD=gmail-oauth`. |
| `new "Name" --area A --due D --priority P` | Create a hub note from the template, then fill it in. |

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

**New projects:** look for existing notes about the project first, so the hub
can link them, then create it with `new` and fill in the sections. You can offer
to pre-fill the hub from the vault, email and calendar.

**Never** edit or move the user's other notes to fit this model. The only
exception is adding a hub link to a task line, and only when the user asks.
Skip `Confidential/` (encrypted notes). The dashboard is generated, so never
hand-edit it.

## The dashboard

`Projects/Dashboard.md` contains:

- 🔴 Overdue and 🟡 Due in the next N days, one row per item, linked to its
  hub and source note;
- a table of active projects with a stale flag;
- Waiting on others;
- collapsed On hold / Ideas and Done sections;
- live views: a Tasks-plugin query (always current) and a Dataview table, which
  renders only if Dataview is installed.

The dashboard is regenerated whenever `dashboard` runs, not live, so run it
after every update. A scheduled `notify` run does not rebuild it. Add a
`dashboard` step to the timer if the user wants it refreshed daily.

## Email digest (optional)

`notify` sends only when something is overdue or due within the window. Every
item links to its note through an `obsidian://open?vault=…&file=…` URL, which
opens in the Obsidian desktop app. The mail method is `PM_MAIL_METHOD`:

- **`gmail-oauth`** (recommended for Google Workspace): the user's own Desktop
  OAuth client.
  - **Setup in Google Cloud:**
    - create a project **under the Workspace organisation**;
    - enable the **Gmail API** only (the Gmail MCP API isn't needed);
    - set the consent screen to **Internal**, with the single scope `gmail.send`;
    - create an OAuth client ID of type **Desktop app**.
  - Save the client JSON as `~/.config/nk-work-kit/credentials.json`
    (`PM_GMAIL_CLIENT`) with `chmod 600`.
  - Run `projects.py auth-gmail` once. It opens a browser and stores a
    send-only token in `gmail-token.json` beside the client file.
  - An **External / Testing** app's token expires after 7 days, which breaks a
    daily timer.
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
- **Dashboard-only timer, for a machine that isn't always on.** It rebuilds the
  dashboard after login and every 3 hours, and never sends email. Use it on
  the desktop when a server does the email. It needs a
  `nk-projects-dashboard.service` with only the `dashboard` ExecStart, and a
  `nk-projects-dashboard.timer`:
  ```ini
  [Timer]
  OnStartupSec=2min
  OnUnitActiveSec=3h
  [Install]
  WantedBy=timers.target
  ```
- **macOS:** a launchd agent with `StartCalendarInterval`. **Windows:** Task
  Scheduler running `uv run …\projects.py notify`. **Any Unix with cron:**
  `0 7 * * 1-5 <uv> run <plugin-root>/scripts/projects.py notify`.
- **An always-on server (recommended when the desktop is often off).** The
  server only needs `uv`, a git clone of this repo (update it with
  `git pull`) and the config. It doesn't need Claude Code or the plugin.
  1. Copy `~/.config/nk-work-kit/.env`, `credentials.json` and
     `gmail-token.json` to the same place on the server, with `chmod 600`. The
     token refreshes itself, so no browser is needed there.
  2. In the server's `.env`, set `OBSIDIAN_VAULT` to the server's copy of the
     vault. Set `PM_VAULT_NAME` to the vault's name **on the desktop**, so the
     emailed `obsidian://` links open the right vault.
  3. **Decide who writes the dashboard.** If the server sees the vault through
     a **one-way** copy (for example the desktop's `rclone sync` to Google
     Drive), the server runs **`notify` only**: remove the `dashboard`
     ExecStart from its service. Anything it writes would never reach the
     desktop and would be overwritten. The desktop keeps the dashboard, using
     the dashboard-only timer above plus Claude's updates. Only with two-way
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
- **No always-on machine:** a Claude cloud routine (`/schedule`) can read a
  cloud copy of the vault (for example Google Drive) and create a Gmail
  **draft** digest. Or skip scheduling entirely and ask "what's due?" in a
  session. Both are fine.

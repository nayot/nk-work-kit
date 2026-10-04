# nk-work-kit

A [Claude Code](https://claude.ai/code) plugin for everyday work in the Faculty of
Engineering, Burapha University.

| Skill | What it does |
|---|---|
| `draft-memo` / `thai-memo` | Draft **บันทึกข้อความภายใน** (`nai`, internal memo) and **หนังสือภายนอก** (`nok`, external letter) from LibreOffice OTT templates, exported to ODT/PDF |
| `doc-number` | Request, list or cancel document numbers in the faculty's **ระบบขอเลขเอกสารอัตโนมัติ** |
| `thai-memo` (e-Signature) | Upload a finished PDF to **BUU e-Signature** and assign a signer |
| `pending-docs` | Report what is still waiting in **eDoc** (หนังสือค้างรับ) and **e-Signature** (รอลงนาม) — read-only |
| `edoc-digest` | Fetch unread **eDoc** documents and their PDFs, **ลงรับ** them, and write a summary report with important ones flagged and linked to their PDFs — never signs |
| `e-leave` | Check leave balance and status in **BUU e-Leave**, and submit (ยื่นใบลา) or cancel leave requests with evidence attached — shows the rendered ใบลา and submits only after you approve it |
| `transcribe` | Turn a meeting recording into a Markdown transcript — Thai, English or mixed |
| `project-manager` | Track ongoing projects as notes in an **Obsidian** vault: a generated dashboard with links to the notes, updates while you work, and an optional email digest of upcoming and overdue items |
| `business-card` | Turn a photo of a business card (นามบัตร) into a **Google Contact** (updating an existing one) and a Gmail **draft** greeting that shares your vCard link, and files the photo in your Drive **Business Cards** folder |
| `personal-finance` | **BUU Personnel Finance**: keep income, spending, advances, budget, mortgage, tax and a retirement projection in your own private **Google Sheet**, imported from Krung Thai and UOB statements, with an Obsidian or HTML dashboard |

Ask Claude in your own words, or use the slash commands below.

## Requirements

- [Claude Code](https://claude.ai/code) CLI
- Python 3 with `lxml` (`pip install lxml`)
- LibreOffice (for PDF export)
- For the `transcribe` skill only: [`uv`](https://docs.astral.sh/uv/), `ffmpeg`,
  an [OpenRouter](https://openrouter.ai/keys) API key, and optionally
  [`rclone`](https://rclone.org/) with a Google Drive remote (to file the
  recordings and transcripts) — see
  [Audio transcription](#audio-transcription).
- For the `pending-docs` skill only: [`uv`](https://docs.astral.sh/uv/) and
  Chromium for Playwright — see [Pending documents](#pending-documents).
- For the `e-leave` skill only: [`uv`](https://docs.astral.sh/uv/) and Chromium
  for Playwright, as for `pending-docs` — see [e-Leave](#e-leave).
- For the `project-manager` skill only: [`uv`](https://docs.astral.sh/uv/) and an
  Obsidian vault — see [Project manager](#project-manager).
- For the `business-card` skill only: [`uv`](https://docs.astral.sh/uv/), the
  Gmail connector, the Google Cloud CLI (`gcloud`) signed in with the
  contacts scope, and [`rclone`](https://rclone.org/) with a Google Drive
  remote (to file the card photos) — see
  [Business cards](#business-cards).
- For the `personal-finance` skill only: [`uv`](https://docs.astral.sh/uv/),
  `pdftotext` (poppler) and a BUU Google account; optionally Obsidian and
  [`rclone`](https://rclone.org/) — see [Personal finance](#personal-finance).

## Install

The plugin is published through the `nayot-buu` marketplace, which lives in this
same repository. Add the marketplace once, then install from it:

```bash
claude plugin marketplace add nayot/nk-work-kit
claude plugin install nk-work-kit@nayot-buu
```

No authentication needed — the repository is public.

Inside a running Claude Code session the same two steps are available from the
`/plugin` menu.

Or clone first and add the marketplace from the local path:

```bash
git clone https://github.com/nayot/nk-work-kit
claude plugin marketplace add ./nk-work-kit
claude plugin install nk-work-kit@nayot-buu
```

Check what got installed with `claude plugin list` and
`claude plugin marketplace list`.

## Configuration

Everything the plugin needs from you lives in **one file**:

```bash
mkdir -p ~/.config/nk-work-kit
cp scripts/.env.example ~/.config/nk-work-kit/.env
chmod 600 ~/.config/nk-work-kit/.env      # Linux/macOS; skip on Windows
```

On Windows the file goes to `%APPDATA%\nk-work-kit\.env` instead (`~/.config`
still works if you prefer it).

| Variable | Used by | Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | `transcribe` | From <https://openrouter.ai/keys> |
| `TRANSCRIBE_RCLONE_DEST` | `transcribe` | rclone `remote:path` (e.g. `GDrive:Recordings`) that the audio and its `.md` transcript are **moved** to after transcription. Empty: ask on first run. `none`: keep both local |
| `EDOC_USERNAME` / `EDOC_PASSWORD` | `pending-docs` | BUU login |
| `EDOC_INBOX` | `pending-docs` | Optional. Comma-separated inbox names; **leave empty to check them all** |
| `EDOC_DIGEST_INBOX` | `edoc-digest` | Required. Comma-separated inbox names to fetch and ลงรับ — no "all" default |
| `ESIGN_USERNAME` / `ESIGN_PASSWORD` | `pending-docs` | Optional — defaults to the `EDOC_` pair |
| `ELEAVE_USERNAME` / `ELEAVE_PASSWORD` | `e-leave` | Optional — defaults to the `EDOC_` pair |

Lookup order is: real environment variables, then
`$XDG_CONFIG_HOME/nk-work-kit/.env`, then `%APPDATA%\nk-work-kit\.env` on
Windows, then `~/.config/nk-work-kit/.env`, then a `.env` beside the scripts. **Keep it in `~/.config`.** A plugin installs into a
version-pinned directory —
`~/.claude/plugins/cache/nayot-buu/nk-work-kit/<version>/` — so a `.env` left
beside the scripts is orphaned the moment you upgrade. The script-local path
remains as a fallback for running from a clone.

The `doc-number` skill stores no credentials; it keeps a signed-in Chromium
profile at `~/.local/share/buu-docnum/profile`, already outside the plugin.

## Platform support

| Skill | Linux | macOS | Windows |
|---|---|---|---|
| `pending-docs` | tested | should work | should work |
| `edoc-digest` | should work | tested | should work |
| `e-leave` | tested (cancel not yet) | should work | should work |
| `transcribe` | tested | should work | should work |
| `business-card` | script tested (full flow not yet) | should work | should work |
| `personal-finance` | tested (Google sign-in step not yet) | should work | should work (`aisync` needs bash) |
| `doc-number` | tested | should work | needs a graphical session |
| `draft-memo` / `thai-memo` | tested | check the LibreOffice path | check the LibreOffice path |

Only Linux is actually tested. Nothing in the Python is platform-specific —
paths go through `pathlib`, config resolution understands `%APPDATA%`, and
stdout is forced to UTF-8 so Thai text survives a Windows console code page —
but macOS and Windows have not been exercised end to end. Two things to know:

- **LibreOffice** is invoked as `libreoffice` in these docs, which is the Linux
  name. On macOS it is
  `/Applications/LibreOffice.app/Contents/MacOS/soffice`, on Windows
  `soffice.exe`. Substitute accordingly when converting to PDF.
- The scripts carry a `#!/usr/bin/env -S uv run --script` shebang, which
  Windows ignores. That is fine — every documented invocation is
  `uv run <script>`, which works the same on all three platforms.

## Usage

### Slash command

```
/draft-memo nai    # บันทึกข้อความภายใน
/draft-memo nok    # หนังสือภายนอก
```

Claude will guide you through collecting all required fields, then generate the document.

### Model-invoked

The skill also activates automatically when you describe a Thai memo task:

> "ร่างบันทึกข้อความถึงหัวหน้าภาควิชาเพื่อขอแก้ไขเกรด"

Same for transcription — no slash command needed, just describe the task:

> "Transcribe this meeting recording for me" (with an audio file path or attachment)
> "ช่วยถอดเสียงไฟล์นี้หน่อย"

### Direct script

```bash
python3 scripts/build_memo.py examples/grade_correction_nai.json
# → /tmp/memo_grade_correction.odt

libreoffice --headless --convert-to pdf /tmp/memo_grade_correction.odt
```

## JSON schema

See [`examples/grade_correction_nai.json`](examples/grade_correction_nai.json) for a full example.

| Field | Type | `nai` | `nok` | Description |
|---|---|---|---|---|
| `type` | string | ✓ | ✓ | `"nai"` or `"nok"` |
| `department` | string | ✓ | — | ส่วนงาน |
| `phone` | string | optional | — | โทร. |
| `from_org` | string | — | ✓ | ชื่อหน่วยงานผู้ส่ง |
| `from_address` | string[] | — | optional | ที่อยู่ (list of lines) |
| `doc_number` | string | optional | ✓ | เลขที่หนังสือ |
| `date` | string | ✓ | ✓ | วันที่ (Thai Buddhist Era string) |
| `subject` | string | ✓ | ✓ | เรื่อง |
| `to` | string | ✓ | ✓ | เรียน |
| `enclosures` | string[] | — | optional | สิ่งที่ส่งมาด้วย |
| `body` | string[] | ✓ | ✓ | เนื้อความ (one string per paragraph) |
| `table` | object | optional | optional | `{ headers, rows }` |
| `attachments` | string[] | optional | optional | สิ่งที่แนบ (numbered list) |
| `signer_name` | string | ✓ | ✓ | ชื่อผู้ลงนาม |
| `signer_roles` | string[] | ✓ | ✓ | ตำแหน่ง (one string per line) |
| `contact_box` | string[] | — | ✓ | ส่วนราชการเจ้าของเรื่อง / โทร / อีเมล — one string per line, printed in a borderless text box at the bottom left of page 1. Always emitted; without it the box shows `from_org` only, with a warning |
| `output` | string | optional | optional | Output `.odt` path |

## Templates

The `templates/` directory contains OTT files for Burapha University (BUU). To use with another institution's templates, replace the `.ott` files — the script will pick them up automatically as long as filenames match.

The bundled templates carry the BUU letterhead, page styles and paragraph
styles only — the body is intentionally empty, since `build_memo.py` replaces
it with the document's own content.

## Pending documents

The `pending-docs` skill wraps `scripts/check_pending.py`, which signs in to
**eDoc** and **BUU e-Signature** and counts what is waiting. It is strictly
read-only — it never opens, receives or signs a document, because opening a
document in eDoc marks it read.

Setup: fill in `EDOC_USERNAME` / `EDOC_PASSWORD` in
[`~/.config/nk-work-kit/.env`](#configuration) (e-Signature reuses them by
default), then install the browser once:

```bash
uv run --with playwright==1.60.0 playwright install chromium
```

Direct use:

```bash
uv run scripts/check_pending.py            # report
uv run scripts/check_pending.py --json     # machine-readable
uv run scripts/check_pending.py --only esign
```

An eDoc account usually has several inboxes — personal, faculty, department,
and any role the user holds. The script discovers them at run time and reports
each one separately, so leave `EDOC_INBOX` empty unless you want to narrow the
check. An `EDOC_INBOX` name that is not on eDoc's ทางลัด tab is reported as
"not listed (likely no new documents)" rather than an error — an inbox with
nothing new can drop off the tab — together with the names that are listed,
so a typo still shows. The same applies to `EDOC_DIGEST_INBOX` in
`edoc-digest`.

Two eDoc numbers are reported per inbox and they are not the same: documents
marked **ใหม่/ยังไม่ได้อ่าน** (the actionable count) and the full
**รายการหนังสือค้างรับ** list, which on a shared inbox is a years-deep backlog
and is capped by the server at 500 rows.

The Playwright logic began as a port of the eDoc and e-Sign checkers in
[eDashboard](https://github.com/nayot/NKAutomationAI); the eDoc half has since
been rewritten around multi-inbox discovery.

## eDoc digest

The `edoc-digest` skill wraps `scripts/edoc_digest.py`. For each unread
document in the inboxes named by `EDOC_DIGEST_INBOX` it saves the detail page,
downloads every attachment, extracts the PDF text layer, and — with
`--receive` — ลงรับ the document once all of that is on disk. Claude then
reads the result and writes a report: important documents (urgent, deadlines,
action needed from you, money/people/legal) flagged at the top with links to
their PDFs, the rest in an FYI table.

It never signs. ลงรับ uses "ไม่ออกเลข" or "ใช้หมายเลขเดิม" only; if the dialog
would issue a new เลขรับ from a number book, the document is left unreceived.
A document whose attachments failed to download is also left unreceived.

Output goes to `~/.local/share/nk-work-kit/edoc/<YYYY-MM-DD>/`
(`%LOCALAPPDATA%\nk-work-kit\edoc\` on Windows): `manifest.json`, one
folder per document with its PDFs and extracted text, and Claude's
`report-<HHMM>.md`.

Direct use:

```bash
uv run scripts/edoc_digest.py --json                 # fetch only, no ลงรับ
uv run scripts/edoc_digest.py --receive --json       # fetch + ลงรับ
uv run scripts/edoc_digest.py --all --receive        # also rows already read but not received
```

Opening a document marks it read in eDoc, so a second run finds nothing
unread; `--all` picks up anything still in ค้างรับ.

## e-Leave

The `e-leave` skill wraps `scripts/eleave.py`, which signs in to
**https://e-leave.buu.ac.th** through BUU SSO with the eDoc account.

```bash
uv run scripts/eleave.py balance                   # วันลาคงเหลือ, leave taken
uv run scripts/eleave.py status [--year 2569]      # สถานะการลา + approvers
uv run scripts/eleave.py types                     # leave types, which are automated
uv run scripts/eleave.py fields ไปราชการ            # form fields of one type
uv run scripts/eleave.py request spec.json         # fill + review page only
uv run scripts/eleave.py request spec.json --confirm <preview_id>   # submit
uv run scripts/eleave.py cancel --start 2026-11-18 [--confirm]
```

`request` takes a JSON spec (type, dates, half days, reason, evidence files;
see the script's docstring or `skills/e-leave/SKILL.md`). Without `--confirm`
it fills the form, stops at e-Leave's own review page and prints the rendered
ใบลา with a `preview_id`; `--confirm <preview_id>` submits, and refuses if the
ใบลา differs from the previewed one. Submitting and cancelling e-mail the
approvers, so Claude always shows the preview and waits for your yes.
Evidence must be .pdf/.jpg/.jpeg/.png under 5 MB. ลากิจ, ลาป่วย, ลาพักผ่อน,
ไปราชการ and the two ไปต่างประเทศ types are automated; the rare long forms
(อุปสมบท, ช่วยเหลือภริยาคลอดบุตร, ติดตามคู่สมรส, ฟื้นฟูสมรรถภาพ) are left to
the website. Review-page screenshots go to `~/.local/share/nk-work-kit/eleave/`.

Submitting has been verified with a real request; the cancel step follows the
official manual and has not yet been exercised.

## Project manager

The `project-manager` skill wraps `scripts/projects.py` and uses an Obsidian
vault as both database and dashboard. Each project is a **hub note** (by
convention in `Projects/`) with `type: project` frontmatter — `status`,
`priority`, `next_action`, `next_action_due`, `waiting_on`, `updated` — plus
Tasks-plugin checkboxes (`- [ ] … 📅 YYYY-MM-DD`). Hub notes link to your
existing meeting notes instead of replacing them; a task in any other note
counts for a project when its line links the hub.

While you work, Claude updates the hub notes (ticks tasks, logs meetings,
moves the next action) and regenerates `Projects/Dashboard.md`. The dashboard
leads with **Dataview** views: loose tasks (from `Projects/To-do.md`, ranked
by ⏫/🔽 priority, then due date), a focus list of overdue and due-in-14-days
items, one row per project with open/late task counts and a stale flag, and
waiting-on-others. A loose task can later be turned into a project. They are live: they update
the moment a note changes, and ticking a task in the dashboard ticks it in its
note. The views need the Dataview plugin, and the dashboard explains how to
install it.

The dashboard links to a bilingual (English/Thai) **user manual**,
`Projects/User Manual.md`. A `SessionStart` hook writes it in the first Claude
Code session after the plugin is installed or updated. The hook does nothing
until project tracking is set up, and `projects.py manual --force` rewrites the
manual by hand.

Setup: run `/project-manager setup`, or ask "set up project tracking". Claude
finds your vault, surveys it without changing anything, suggests 5–8 active
projects from recent notes (and from email and calendar if those connectors
are on), pre-fills a status card for each one for you to correct, then creates
the hub notes and the first dashboard. You can also set it up by hand in
[`~/.config/nk-work-kit/.env`](#configuration):

```
OBSIDIAN_VAULT=/path/to/your/vault
```

Direct use:

```bash
uv run scripts/projects.py list [--json]
uv run scripts/projects.py dashboard
uv run scripts/projects.py manual [--force]      # bilingual user manual note
uv run scripts/projects.py digest --days 14
uv run scripts/projects.py new "Project name" --area X --due 2026-12-15
uv run scripts/projects.py notify --dry-run
uv run scripts/projects.py scan-inbox --dry-run  # needs auth-gmail --scan
```

**Inbox scan (optional).** `scan-inbox` reads new Gmail (not Promotions, Social or Updates) and
upcoming Calendar events, asks `claude -p` (no tools, JSON output only) which
of them are tasks for a tracked project, validates the answer, and appends each
task, linked to its email or event, to the hub's `## Suggested from inbox`
section. Run `projects.py auth-gmail --scan` once to grant read-only Gmail and
Calendar access. Email content is sent to Anthropic through Claude Code.

**Email digest (optional).** `notify` emails `PM_NOTIFY_TO` only when something
is overdue or due within `PM_NOTIFY_DAYS`; each item links to its note with an
`obsidian://` URL. Send via the Gmail API (`PM_MAIL_METHOD=gmail-oauth`, the
default): run `projects.py auth-gmail` once and sign in with your BUU Google
account. No Google Cloud setup is needed: the plugin ships its own OAuth client
(Internal to the BUU Workspace); to use your own Desktop-app client instead,
save it as `~/.config/nk-work-kit/credentials.json`. The bundled client file is public
on purpose: Google treats a desktop app's client secret as non-confidential, and
only BUU accounts can use it. What *is* secret is your own
`~/.config/nk-work-kit/gmail-token.json`: never share or commit it. Or send via SMTP (`PM_MAIL_METHOD=smtp`, e.g. a
Gmail app password), or via gcloud ADC (`PM_MAIL_METHOD=gmail-api`, often
blocked by Google for Gmail scopes). Schedule it with a systemd user timer,
cron, launchd or Task Scheduler — see
[`skills/project-manager/SKILL.md`](skills/project-manager/SKILL.md). An always-on
server can send it instead: a git clone plus the config files is enough, no
plugin or Claude Code needed, and it runs `notify` only when it sees a one-way
copy of the vault. The skill page walks through it. Without
an always-on machine, skip the schedule and ask Claude "what's due?", or use a
Claude cloud routine that writes a Gmail draft.

## Audio transcription

The `transcribe` skill wraps `scripts/transcribe.py` — a single-file CLI
(vendored from [autoTranscribe](https://github.com/nayot/autoTranscribe),
which remains the source of truth) that sends audio to an audio-capable LLM
via OpenRouter and writes a Markdown transcript: summary, then
`[MM:SS]`-timestamped, speaker-labeled, verbatim text in the original
language — Thai, English, or mixed, never translated.

Setup: paste your OpenRouter key into
[`~/.config/nk-work-kit/.env`](#configuration) as `OPENROUTER_API_KEY=`.

When the transcript looks right, Claude **moves the recording and its `.md`
transcript** to a Google Drive folder with [`rclone`](https://rclone.org/), so
the pair stays together. The folder is `TRANSCRIBE_RCLONE_DEST` (an rclone `remote:path`).
Claude asks for it on the first run and saves it to the `.env`. Set it to
`none` to keep both local. The script itself never uploads anything, so
running it directly leaves both files in place.

For a meeting, Claude then **fills in the meeting note** in your Obsidian vault
(`OBSIDIAN_VAULT`). If you prepared a note beforehand (agenda, invited
attendees), it fills that note in place and keeps what you wrote. Otherwise it
creates one from your vault's meeting template, dated for the meeting, with a
link back to the recording and transcript.

Direct use:

```bash
uv run scripts/transcribe.py path/to/recording.m4a --model google/gemini-2.5-flash --yes
# → path/to/recording.md
```

Ask Claude instead and it will pick a model, run it, and summarize the result
in chat — see [`skills/transcribe/SKILL.md`](skills/transcribe/SKILL.md) for
the model catalog and the long-file chunking behavior.

## Business cards

Send Claude a photo of a business card (or say "here's a card" with the image)
and the `business-card` skill reads it — Thai and English sides kept as they
are, phones normalised to `+66`, unsure characters flagged with "(?)" — and
shows the fields as a table. It then:

1. **Saves the contact.** It searches your Google Contacts first. An existing
   contact is updated and a new one is created with `scripts/gcontacts.py`
   (People API), since the Contacts connector is search-only. If that can't
   sign in, a new contact becomes a `.vcf` file, built by `scripts/make_vcf.py`, in `~/Downloads/`,
   for you to import at contacts.google.com or open on your phone.
2. **Files the photo** in your Google Drive "Business Cards" folder with
   `rclone`, named `<First> <Last> - <Org> <date>`. It copies the photo, so the
   local file stays, and never overwrites a file of the same name. It needs an
   rclone Google Drive remote, and is skipped if there isn't one.
3. **Drafts a greeting email** in Gmail — English, or Thai for Thai
   counterparts — thanking them and linking your vCard. It is a draft; nothing
   is sent.

Setup, once: sign gcloud's Application Default Credentials in with the
contacts scope. `gcontacts.py` stores nothing itself.

```bash
gcloud auth application-default login \
  --scopes=https://www.googleapis.com/auth/contacts,https://www.googleapis.com/auth/cloud-platform
```

Direct use:

```bash
uv run scripts/gcontacts.py search "Somchai"
uv run scripts/gcontacts.py create contact.json        # refuses an email already on a contact; --force overrides
uv run scripts/gcontacts.py update people/c123 --add-phone "+66 81 234 5678"
python3 scripts/make_vcf.py contact.json Somchai_Jaidee.vcf
```

The JSON fields are listed in
[`skills/business-card/SKILL.md`](skills/business-card/SKILL.md).

## Personal finance

The `personal-finance` skill (**BUU Personnel Finance**) keeps your money in a
private Google Sheet that it builds for you: transactions, budget, card
statements, advances owed back by the university (เงินทดรองจ่าย, ค่าเล่าเรียนบุตร),
mortgage, tax, investments and a retirement projection to your plan age.
`scripts/pf.py` imports **Krung Thai** account and home-loan statements and
**UOB** credit-card e-statements (PDF). Each statement is checked against the
totals the bank printed on it before anything is written, re-importing never
duplicates rows, and locked PDFs are opened with a password you type at import
time — it is never stored. The dashboard (Obsidian Markdown, or `--html` for a
browser) shows totals only.

User manual: [Thai](templates/personal-finance-manual.th.md) ·
[English](templates/personal-finance-manual.en.md).

Setup, once — or just tell Claude "set up personal finance tracking":

```bash
uv run scripts/pf.py auth                                  # BUU Google sign-in, Sheets access only
uv run scripts/pf.py setup --dob 1980-01-15 --save         # creates the sheet, saves PF_SHEET_ID
uv run scripts/pf.py init-folder ~/Finance --save          # Statements/, Tax/, Insurance/, saves PF_DIR
```

Then each month:

```bash
uv run scripts/pf.py import --dry-run && uv run scripts/pf.py import
uv run scripts/pf.py dashboard [--html]
```

`auth` uses the plugin's bundled OAuth client (Internal to the BUU Workspace) or
your own `credentials.json` in `~/.config/nk-work-kit/`; the token is saved as
`pf-token.json` there. If gcloud Application Default Credentials already carry
the spreadsheets scope, they are used instead.

Optional sync across machines: `scripts/aisync` runs `rclone bisync` between a
folder under `AISYNC_ROOT` (default `~/aiSpace`) and the same path on Google
Drive; `pf.py init-folder <dir> --sync` adds Claude Code hooks that run it at
the start and end of each session in that folder.

## License

MIT

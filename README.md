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
| `transcribe` | Turn a meeting recording into a Markdown transcript — Thai, English or mixed |
| `project-manager` | Track ongoing projects as notes in an **Obsidian** vault: a generated dashboard with links to the notes, updates while you work, and an optional email digest of upcoming and overdue items |

Ask Claude in your own words, or use the slash commands below.

## Requirements

- [Claude Code](https://claude.ai/code) CLI
- Python 3 with `lxml` (`pip install lxml`)
- LibreOffice (for PDF export)
- For the `transcribe` skill only: [`uv`](https://docs.astral.sh/uv/), `ffmpeg`,
  an [OpenRouter](https://openrouter.ai/keys) API key, and optionally
  [`rclone`](https://rclone.org/) with a Google Drive remote (to file the
  recordings) — see
  [Audio transcription](#audio-transcription).
- For the `pending-docs` skill only: [`uv`](https://docs.astral.sh/uv/) and
  Chromium for Playwright — see [Pending documents](#pending-documents).
- For the `project-manager` skill only: [`uv`](https://docs.astral.sh/uv/) and an
  Obsidian vault — see [Project manager](#project-manager).

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
| `TRANSCRIBE_RCLONE_DEST` | `transcribe` | rclone `remote:path` (e.g. `GDrive:Recordings`) that the audio is **moved** to after transcription. Empty: ask on first run. `none`: keep audio local |
| `EDOC_USERNAME` / `EDOC_PASSWORD` | `pending-docs` | BUU login |
| `EDOC_INBOX` | `pending-docs` | Optional. Comma-separated inbox names; **leave empty to check them all** |
| `EDOC_DIGEST_INBOX` | `edoc-digest` | Required. Comma-separated inbox names to fetch and ลงรับ — no "all" default |
| `ESIGN_USERNAME` / `ESIGN_PASSWORD` | `pending-docs` | Optional — defaults to the `EDOC_` pair |

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
| `transcribe` | tested | should work | should work |
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
check; an `EDOC_INBOX` name that matches no inbox is a hard error rather than a
silent zero.

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

## Project manager

The `project-manager` skill wraps `scripts/projects.py` and uses an Obsidian
vault as both database and dashboard. Each project is a **hub note** (by
convention in `Projects/`) with `type: project` frontmatter — `status`,
`priority`, `next_action`, `next_action_due`, `waiting_on`, `updated` — plus
Tasks-plugin checkboxes (`- [ ] … 📅 YYYY-MM-DD`). Hub notes link to your
existing meeting notes instead of replacing them; a task in any other note
counts for a project when its line links the hub.

While you work, Claude updates the hub notes (ticks tasks, logs meetings,
moves the next action) and regenerates `Projects/Dashboard.md`: overdue and
upcoming items, active projects with a stale flag, waiting-on-others, and live
Tasks/Dataview views. No Obsidian plugin is required; Tasks and Dataview
blocks light up if you have them.

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
uv run scripts/projects.py digest --days 14
uv run scripts/projects.py new "Project name" --area X --due 2026-12-15
uv run scripts/projects.py notify --dry-run
```

**Email digest (optional).** `notify` emails `PM_NOTIFY_TO` only when something
is overdue or due within `PM_NOTIFY_DAYS`; each item links to its note with an
`obsidian://` URL. Send via your own Google Cloud OAuth client
(`PM_MAIL_METHOD=gmail-oauth`: a Desktop-app client with an Internal consent
screen, the Gmail API enabled, saved as `~/.config/nk-work-kit/credentials.json`;
run `projects.py auth-gmail` once), via SMTP (`PM_MAIL_METHOD=smtp`, e.g. a
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

When the transcript looks right, Claude **moves the recording** to a Google
Drive folder with [`rclone`](https://rclone.org/) and leaves the `.md` where it
was written. The folder is `TRANSCRIBE_RCLONE_DEST` (an rclone `remote:path`).
Claude asks for it on the first run and saves it to the `.env`. Set it to
`none` to keep recordings local. The script itself never uploads anything, so
running it directly leaves the audio in place.

Direct use:

```bash
uv run scripts/transcribe.py path/to/recording.m4a --model google/gemini-2.5-flash --yes
# → path/to/recording.md
```

Ask Claude instead and it will pick a model, run it, and summarize the result
in chat — see [`skills/transcribe/SKILL.md`](skills/transcribe/SKILL.md) for
the model catalog and the long-file chunking behavior.

## License

MIT

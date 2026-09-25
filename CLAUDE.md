# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Claude Code **plugin** (`nk-work-kit`) and its own **marketplace** (`nayot-buu`), both in this repo, for day-to-day work in the Faculty of Engineering, Burapha University (BUU). There is no build, lint or test suite. Each skill is a `skills/<name>/SKILL.md` prompt that drives one standalone script in `scripts/`.

| Skill | Script | Runner |
|---|---|---|
| `draft-memo`, `thai-memo` | `build_memo.py` (JSON → ODT from `templates/*.ott`; then LibreOffice → PDF) | `python3` (needs `lxml`) |
| `doc-number` | `docnum.py` (faculty's Apps Script numbering system) | `python3` (needs `playwright` installed via pip) |
| `pending-docs` | `check_pending.py` (eDoc + e-Signature, read-only) | `uv run` (PEP 723 inline deps) |
| `edoc-digest` | `edoc_digest.py` (fetch unread eDoc docs + PDFs, ลงรับ; Claude writes the flagged report) | `uv run` (PEP 723 inline deps) |
| `transcribe` | `transcribe.py` (audio → Markdown via OpenRouter) | `uv run` (PEP 723 inline deps) |
| `project-manager` | `projects.py` (Obsidian hub notes → `Projects/Dashboard.md`; email digest) | `uv run` (PEP 723 inline deps) |

## Running scripts directly

```bash
python3 scripts/build_memo.py examples/grade_correction_nai.json   # → /tmp/memo_grade_correction.odt
libreoffice --headless --convert-to pdf /tmp/memo_grade_correction.odt
# macOS: /Applications/LibreOffice.app/Contents/MacOS/soffice

python3 scripts/docnum.py login | whoami | list [--json] [--all] | request ... | cancel <docNumber>
uv run scripts/check_pending.py [--json] [--only edoc|esign]
uv run scripts/edoc_digest.py [--receive] [--all] [--limit N] [--inbox NAME] [--json]
uv run scripts/transcribe.py rec.m4a --model google/gemini-2.5-flash --yes
uv run scripts/projects.py list [--json] | dashboard | digest [--days N] | notify [--dry-run] [--force] | new "Name"

uv run --with playwright==1.60.0 playwright install chromium        # one-time, for check_pending
```

Local plugin install for testing: `claude plugin marketplace add ./` then `claude plugin install nk-work-kit@nayot-buu`.

## Architecture and conventions

- **Skills reference scripts via `${CLAUDE_PLUGIN_ROOT}/scripts/...`**, with a fallback note for when it is unset. Never hardcode the plugin name or install path: the plugin installs into a version-pinned cache dir (`~/.claude/plugins/cache/nayot-buu/nk-work-kit/<version>/`), and the v2.0.0 rename broke a hardcoded path.
- **One config file for all skills:** `~/.config/nk-work-kit/.env` (template: `scripts/.env.example`). Lookup order: real env vars → `$XDG_CONFIG_HOME/nk-work-kit/.env` → `%APPDATA%\nk-work-kit\.env` → `~/.config/nk-work-kit/.env` → `.env` beside the script (fallback when running from a clone; gitignored). `check_pending.py` has its own parser (`config_files()`/`load_env()`); `transcribe.py` uses `python-dotenv` in the same order, plus a CWD-upward search. Keep the two aligned when changing lookup. `doc-number` stores no credentials, only a Chromium profile at `~/.local/share/buu-docnum/profile`.
- **Versioning:** a release bumps `version` in `.claude-plugin/plugin.json` (commits are titled `nk-work-kit vX.Y.Z` with a detailed body). Skills carry their own `version` in frontmatter. `marketplace.json` repeats the plugin description, so keep it in sync with `plugin.json`. A breaking change to the install command is a major version.
- **Side effects are deliberate and constrained:**
  - `check_pending.py` is **read-only by construction**. Never open, receive, sign or forward a document: opening one in eDoc marks it read. เอกสารลับ are counted, never opened.
  - eDoc inboxes are discovered at run time. An `EDOC_INBOX` name that matches nothing is a hard error, never a silent zero. Name matching ignores whitespace, because Thai titles appear both as "ผศ. ดร. X" and "ผศ.ดร.X". Two counts are reported per inbox: unread/ใหม่ (the actionable one) and the full ค้างรับ list, which the server caps at 500.
  - `edoc_digest.py` writes to eDoc only with `--receive`, and only after a doc's attachments are on disk. It refuses to ลงรับ unless the dialog preselects ไม่ออกเลข/ใช้หมายเลขเดิม (a number book would issue a new เลขรับ), and never signs. It must stay separate from `check_pending.py`, whose read-only promise the `pending-docs` skill relies on. Its docstring has a HARD-WON DETAILS block: ลงรับ only works from `home.aspx` (the dialog lives on the parent page), and attachment links carry per-render tokens. Downloads go to `~/.local/share/nk-work-kit/edoc/<date>/`.
  - `projects.py` writes only `<vault>/<PM_FOLDER>/Dashboard.md` (atomically: the vault is synced while it runs) and new hub notes via `new`; it never edits other notes, and skips `.obsidian/`, `.trash/`, `Confidential/`. `notify` sends only to `PM_NOTIFY_TO` and only when something is due — the user's "no email without approval" rule has a standing exception for exactly this digest. Its config lookup is a copy of `check_pending.py`'s; keep them aligned.
  - `docnum.py request` is irreversible and asks for confirmation first. `cancel` works only within 24 hours.
- **`docnum.py` has a "HARD-WON DETAILS" block in its docstring. Do not simplify those behaviours away.** It calls the app's `google.script.run` server functions inside the `script.googleusercontent.com` `/blank` iframe, bypassing the wizard. Chromium must run **headed**, placed offscreen: headless stalls at Google's confirmidentifier. The GPU is disabled. `requester` is an email address, not a name.
- **`transcribe.py` is vendored** from github.com/nayot/autoTranscribe, which remains the source of truth. Upstream is where fixes belong. Local divergences are marked `# LOCAL CHANGE` (shared config lookup, UTF-8 stdout/stderr, ffmpeg/ffprobe resolution + UTF-8 decoding of their output) and must be re-applied after each re-sync.
- **`build_memo.py`** unzips an `.ott` template, rebuilds the ODF `content.xml` body with lxml, and re-zips it (`mimetype` goes first, stored uncompressed). The templates hold only the letterhead, page styles and paragraph styles; the body is intentionally empty. Templates are selected by filename (`แบบหนังสือภายใน.ott` / `แบบหนังสือภายนอก.ott`). The JSON schema is documented in `README.md` and `skills/draft-memo/SKILL.md`. Dates are Thai Buddhist Era strings with Thai numerals.
- `check_pending.py` and `transcribe.py` force UTF-8 on stdout/stderr so Thai text survives Windows code pages (callers pipe the output). Paths go through `pathlib`/`os.path`. Only Linux is tested end to end.

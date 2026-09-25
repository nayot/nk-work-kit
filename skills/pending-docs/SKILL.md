---
name: pending-docs
description: Activate this skill when the user asks whether anything is waiting for them in BUU's document systems — "มีเอกสารค้างไหม", "เอกสารค้างรับ", "มีอะไรรอเซ็น", "มีหนังสือเข้าใหม่ไหม", "เช็ค eDoc", "เช็ค e-sign", "check pending documents", "anything waiting for me to sign", "what's in my inbox". Also activate when the user asks for a morning/daily summary of their BUU workload. This skill only checks and reports — it never opens, receives or signs anything.
allowed-tools: [Bash]
version: 1.0.1
---

# เอกสารค้าง — eDoc & e-Signature

Reports what is waiting in **eDoc** (`doc.buu.ac.th`) and **BUU e-Signature**
(`e-sign.buu.ac.th`). One script does all the work:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/check_pending.py" --json
```

If `CLAUDE_PLUGIN_ROOT` is not set, the script sits at
`<plugin-root>/scripts/check_pending.py`. It runs headless — nothing appears on
the user's screen. A run takes roughly 30–60 seconds; both systems are checked
in parallel, and a system that fails is retried once, so an unlucky run can take
about twice that.

## This skill reports. It does not act.

Opening a document in eDoc marks it read, and signing in e-Signature is
irreversible. Neither belongs in a status check.

- **Never** open, receive (รับ), forward or sign anything from here.
- If the user wants to act on what you found, point them at the site, or hand
  off to the `thai-memo` skill for the e-Signature upload flow.
- The script is read-only by construction. Do not write your own browser
  automation against these sites to "check more thoroughly".

## Options

| Flag | Use |
|---|---|
| `--json` | Machine-readable. **Use this** — parse it, then write the summary yourself. |
| `--only edoc` / `--only esign` | One system, when the user asked about only that one. |
| `--timeout N` | Seconds per system, default 180. Raise it if a run times out. |

## Reading the result

```json
{"ok": true, "total_pending": 140, "checked_at": "...", "systems": [
  {"name": "eDoc", "pending": 140, "error": null, "items": [...],
   "inboxes": [{"name": "ผศ. ดร. ณยศ ...", "entity_id": "1140",
                "pending": 114, "in_list": 114, "items": [...]},
               {"name": "คณะวิศวกรรมศาสตร์", "pending": 3,
                "in_list": 500, "list_capped": true, "items": [...]}]},
  {"name": "eSign", "pending": 0, "error": null, "items": [],
   "breakdown": {"รอลงนาม": 0, "เอกสารลับ": 0}}]}
```

**eDoc — two numbers, and they mean different things.**

- `pending` — documents marked **ใหม่/ยังไม่ได้อ่าน**. This is the number the
  user cares about. Lead with it.
- `in_list` — every row in that inbox's **รายการหนังสือค้างรับ**. On a shared
  inbox this is a years-deep backlog, so it is context, not a to-do count.
  Mention it only in passing, if at all.
- `list_capped: true` — the server returned its 500-row maximum, so `in_list`
  is a floor, not the true size. Say "500+" and never present it as exact.
- The account has **several inboxes** — personal, faculty, department and any
  role the user holds. They are discovered at run time. Report them separately;
  a document in the faculty inbox is not necessarily the user's to handle.
- `absent: true` — an `EDOC_INBOX` name that is not on eDoc's ทางลัด tab right
  now. That usually just means the inbox has **no new documents** (an inbox
  with nothing new can drop off the tab), so **don't be alarmed and don't call
  it an error**: report it as "no new documents" (ไม่มีหนังสือใหม่). The
  system's `note` lists the inboxes that *are* on the tab; mention it only if
  the user asks, or if the configured name looks like a typo of a listed one.
- eDoc filters the list to the current Buddhist-era year. Anything older is not
  shown by eDoc itself and is therefore not counted.

**eSign** — `pending` is รอลงนาม plus เอกสารลับ, split in `breakdown`. Report
the split when เอกสารลับ is non-zero; secret documents are a different queue.
Only รอลงนาม documents come with titles: เอกสารลับ are counted but never
opened, because a status check should not pull secret document titles into a
chat log. When that happens the entry carries a `note` — pass it on rather than
implying the count is unexplained, and point the user at e-Signature itself.

Each item carries `number` (เลขที่หนังสือ), `subject`, `date`, `sender`, and
for eDoc `inbox`. At most 10 items per inbox are returned even when `pending`
is larger — say "และอีก N ฉบับ" rather than implying the list is complete.

## Writing the summary

Answer in the language the user asked in; for Thai, keep the eDoc vocabulary
(ค้างรับ, ยังไม่ได้อ่าน, รอลงนาม). Lead with the totals per system, then the
per-inbox breakdown, then the newest few items with their เลขที่หนังสือ — that
is what the user will quote when following up. Do not paste all 10 items for
every inbox unless asked; two or three of the newest per inbox is usually
enough, with the rest summarised as a count.

If everything is zero, say so in one line. Do not pad it.

## When it fails

| Exit | Meaning | What to do |
|---|---|---|
| 0 | success (possibly partial — check each system's `error`) | report it |
| 1 | every system checked failed | report the errors verbatim; do not say "nothing pending" |
| 3 | configuration problem | see below |

**A failed check is never "nothing pending".** If a system carries an `error`,
say that system could not be checked and quote the message. Reporting zero for
a system that failed to log in is the one genuinely harmful outcome here.

Exit **3** means credentials are missing, or an `EDOC_INBOX` name matches more
than one inbox. (A name that matches *no* inbox is not an error — see
`absent` above.) Fix is in
**`~/.config/nk-work-kit/.env`** — the one config file for the whole plugin
(copy `scripts/.env.example` into it). A `.env` beside the script still works
as a fallback, but it is lost on the next plugin upgrade, so prefer
`~/.config`:

```
EDOC_USERNAME=...        BUU login
EDOC_PASSWORD=...
EDOC_INBOX=              optional: comma-separated inbox names; empty = all
ESIGN_USERNAME=          optional: defaults to the EDOC_ pair
ESIGN_PASSWORD=
```

Tell the user what to fill in — never type credentials into the browser or the
file on their behalf, and never echo the contents of `.env` back to them.
Leaving `EDOC_INBOX` empty is the recommended setting: every inbox on the
ทางลัด tab gets checked.

## Requirements

- [`uv`](https://docs.astral.sh/uv/) — the script's shebang installs its own
  dependencies (Playwright 1.60.0).
- Chromium for Playwright, once:
  `uv run --with playwright==1.60.0 playwright install chromium`

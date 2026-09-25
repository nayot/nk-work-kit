---
name: edoc-digest
description: Activate this skill when the user wants the documents in their BUU eDoc inbox fetched, read and summarised, or ลงรับ'd — "สรุปเอกสาร eDoc", "สรุปหนังสือเข้า", "วิเคราะห์เอกสารใน eDoc", "อ่านหนังสือเข้าให้หน่อย", "ลงรับเอกสาร", "ลงรับหนังสือ", "digest my eDoc inbox", "summarise my new eDoc documents", "what's important in eDoc", "flag the urgent documents". Downloads each unread document and its PDFs, ลงรับ each one, and writes a summary report with important documents flagged and linked to their PDFs. Never signs (ลงนาม). For a quick count of what is waiting, without opening or receiving anything, use pending-docs instead.
argument-hint: "[--all] [--limit N] [--inbox NAME]"
allowed-tools: [Bash, Read, Write]
version: 1.0.1
---

# สรุปเอกสาร eDoc — fetch, ลงรับ, analyse, flag

One script fetches documents; you do the analysis. The script opens each unread
document in the configured eDoc inbox, saves the detail page, downloads every
attachment, pulls the PDF text layer, and — with `--receive` — ลงรับ the
document once all of that is on disk. You then read what it saved and write the
report.

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/edoc_digest.py" --receive --json
```

If `CLAUDE_PLUGIN_ROOT` is not set, the script sits at
`<plugin-root>/scripts/edoc_digest.py`. It runs headless. Allow about 10–20 s
per document (a Bash timeout of 600000 ms covers ~30 documents; for more, run it
in the background). Progress lines go to stderr; the JSON goes to stdout.

## Arguments

`$ARGUMENTS` are passed straight through to the script:

| Flag | Meaning |
|---|---|
| `--all` | Every row still in ค้างรับ, not only unread ones. Use it to pick up a document that was opened (so no longer unread) but never received — e.g. after a crashed run, or one opened by hand in the browser. With `--receive` and more than 30 rows it exits 3 unless `--limit N` is given; ask the user for N rather than choosing one. |
| `--limit N` | At most N documents per inbox |
| `--inbox NAME` | Override `EDOC_DIGEST_INBOX` (repeatable) |

Always pass `--receive` and `--json` yourself: ลงรับ during the fetch is what the
user asked this skill to do. Leave `--receive` off only when the user explicitly
says not to receive ("อย่าเพิ่งลงรับ", "just summarise, don't receive").

## What the script does and does not do

- **ลงรับ with "ไม่ออกเลข" / "ใช้หมายเลขเดิม" only.** If the dialog ever preselects a
  receive-number book (which would issue a new เลขรับ), it refuses and leaves
  that document unreceived with a note. Pass that note on; do not work around it.
- **A document is received only after its attachments downloaded.** A failed
  download leaves it unreceived (`received: false`, note says why) so it stays
  visible in eDoc.
- **Never ลงนาม, ส่งต่อ, ตอบกลับ, ยกเลิกรายการ.** Nothing in this skill signs, and
  you must not attempt it by other means.
- **Opening a document marks it read.** That is inherent. Do not re-run the
  script just to "check again": a second run finds nothing unread. Use `--all`
  only for the recovery case above.

## Output

Everything lands in `~/.local/share/nk-work-kit/edoc/<YYYY-MM-DD>/`
(`%LOCALAPPDATA%\nk-work-kit\edoc\<YYYY-MM-DD>\` on Windows) — `out_dir` in the
JSON. It is outside the plugin directory, so upgrades never delete it.

The JSON printed on stdout covers **this run's** documents:

```jsonc
{
  "ok": true, "out_dir": "...", "manifest": ".../manifest.json", "receive_requested": true,
  "inboxes": [{"name": "...", "entity_id": "16609", "selected": 2}],
  "documents": [{
    "data_id": "30654636", "inbox": "...", "subject": "...", "urgency": "ด่วนที่สุด",
    "number": "อว 8119/ ว.668", "date_in": "10/8/2569 15:14:36", "sender": "...",
    "fields": {"from", "sent_at", "action", "doc_number", "secrecy", "speed",
               "doc_type", "doc_date", "to", "subject", "due"},   // whichever are present
    "notes": ["ข้อความแนบท้าย/สั่งการ ..."],
    "detail_text_path": ".../30654636/detail.txt",
    "edoc_url": "https://doc.buu.ac.th/docweb/v2/inboxdetail.aspx?id=30654636",
    "attachments": [{"name": "...pdf", "path": "...", "file_uri": "file:///...",
                     "bytes": 463733, "is_pdf": true, "pages": 6,
                     "text_path": "...pdf.txt", "text_chars": 9554,
                     "text_quality": "ok"}],   // ok | garbled | empty
    "received": true, "receive_note": "received (ไม่ออกเลข)", "error": null
  }]
}
```

An inbox entry with `"absent": true` (and `entity_id: null`, `selected: 0`)
is a configured inbox that is not on eDoc's ทางลัด tab right now. That usually
just means it has **no new documents** — an inbox with nothing new can drop
off the tab — so **don't be alarmed and don't treat it as a failure**. Say
"ไม่มีเอกสารใหม่ใน <inbox>" in one line. Its `note` lists the inboxes that are
on the tab; mention it only if the user asks or the configured name looks like
a typo of a listed one.

`received` is `true`, `false` (tried and failed/refused — see `receive_note`),
or `null` (not requested). `error` is set when the document could not be read at
all; its attachments may be missing.

`manifest.json` in the same folder accumulates every document fetched that day.

### Exit codes

| Code | Meaning | What to do |
|---|---|---|
| 0 | every document processed | analyse |
| 1 | login/navigation failed, or at least one document has `error` | report what did work; name the failures |
| 3 | configuration: no credentials, no inbox chosen, or an ambiguous inbox name | relay the message — it lists the matching inbox names. The user fixes `~/.config/nk-work-kit/.env` |

## Analysing

Work document by document from the JSON. For each one:

1. Start from `subject`, `fields`, `notes` and `urgency` — they are cheap and
   often enough to classify an FYI circular.
2. Read the attachment text: the `.txt` at each `text_path`, first attachment
   first (it is normally the covering memo; later ones are annexes or the same
   memo re-addressed to other people — skip near-duplicates, same
   `text_chars`).
3. **Read the PDF itself** (Read tool, `pages: "1-3"`) when `text_quality` is
   `garbled` or `empty` — don't open that `.txt` at all — or when the document
   is a flag candidate and you need an exact date, amount or requested action.
   Even `ok` text of Thai PDFs routinely drops tone marks (บันทึกขอความ for
   บันทึกข้อความ): fine for skimming, not for quoting. Page 1 usually has
   everything; read further only if the memo continues.
4. Open `detail.txt` only if the fields above are missing or you need the
   route / other recipients.

### What to flag

Flag a document when **any** of these holds, and say which:

- **ชั้นความเร็ว** ด่วน / ด่วนมาก / ด่วนที่สุด (`urgency` or `fields.speed`)
- **A deadline or date** the user must meet: ภายในวันที่…, ก่อนวันที่…, a reply-by
  date, a nomination or submission cut-off, or `fields.due` set to a real date.
  Also any meeting/event the user is invited to attend, chair, or speak at.
- **The user must act personally**: sign or approve (โปรดพิจารณาลงนาม, ขออนุมัติ,
  ขอความเห็นชอบ), nominate, reply, attend, or appoint — as opposed to เพื่อทราบ.
  `fields.action` = เพื่อทราบ with nothing else in the text is **not** a flag.
- **Money, people or legal exposure**: budget, procurement, personnel
  appointments/discipline, complaints, audit, litigation, anything marked ลับ.

**Compare every date with today.** A deadline or event that has already passed
is not a flag: list the document under เพื่อทราบ with "(ผ่านไปแล้ว)" after the
date. A deadline within 7 days goes to the top of the flagged list.

Do not flag on topic importance alone. When unsure, flag and say why in one
line — a false flag costs a glance, a missed one costs a deadline.

Never invent a deadline. Quote dates exactly as the document states them (Thai
Buddhist-era), and add the DD.MM.YYYY Gregorian form in parentheses.

## The report

Write it to `<out_dir>/report-<HHMM>.md` in Thai (the documents are Thai), and
reply in chat in the user's language.

```markdown
# สรุปเอกสาร eDoc — <DD.MM.YYYY HH:MM>

**Inbox:** <names> · <n> เอกสาร · ลงรับแล้ว <x> · ยังไม่ลงรับ <y> · ⚑ <f> เรื่องที่ต้องดำเนินการ

## ⚑ ต้องดำเนินการ

### 1. <subject>
- **ที่:** <doc_number> · **จาก:** <from> · **ความเร็ว:** <urgency> · **วันที่เข้า:** <date_in>
- **สาระสำคัญ:** <1–2 sentences>
- **สิ่งที่ต้องทำ / กำหนดเวลา:** <action, exact date>
- **เหตุที่ flag:** <which rule>
- **PDF:** [<attachment name>](<file_uri>) · [<next>](<file_uri>)
- **เปิดใน eDoc:** <edoc_url>
- **ลงรับ:** ✓ | ✗ <receive_note>

## เพื่อทราบ

| # | เรื่อง | จาก | สรุป | PDF |
|---|---|---|---|---|
| 1 | <subject> | <from> | <one line> | [PDF](<file_uri of main attachment>) |

## ปัญหา
<documents with error, received=false, or failed downloads — with the note>
```

Order flagged items by urgency, then nearest deadline.

**PDF links are the point of the report — get them exactly right:**

- Copy every link **verbatim** from `file_uri` in the JSON. Never build a path
  or URI yourself; the script already percent-encodes Thai, spaces and
  parentheses. In the link *text* (the attachment name), escape `[`, `]` as
  `\[`, `\]`, and in table cells escape `|` as `\|`.
- Every flagged document lists **all** its PDF attachments (skip only exact
  duplicates). An unflagged row links at least its first attachment.
- `edoc_url` needs a signed-in browser — label it "เปิดใน eDoc", it is not a
  PDF link.
- If a flagged document has no downloaded attachment, say so in its entry.

In chat, give: the counts line, then each flagged item as subject — action/date —
PDF link(s), then the report path. Don't paste the เพื่อทราบ table into chat
unless asked.

## After the report

If flagged items include meetings or deadlines, offer (don't do unprompted) to
add them to Google Calendar. Don't offer to sign anything.

## Configuration

`~/.config/nk-work-kit/.env` (copy `scripts/.env.example`):

```
EDOC_USERNAME=...           # shared with pending-docs
EDOC_PASSWORD=...
EDOC_DIGEST_INBOX=รองอธิการบดีฝ่ายกิจการเขตพัฒนาพิเศษ(EEC)
```

`EDOC_DIGEST_INBOX` is comma-separated and has no "all inboxes" default,
because this skill writes (ลงรับ). Names match ignoring whitespace. Shared
inboxes (faculty, department) are often received by สารบรรณ staff — add them
only if the user wants to ลงรับ there personally.

One-time browser install (shared with pending-docs):

```bash
uv run --with playwright==1.60.0 playwright install chromium
```

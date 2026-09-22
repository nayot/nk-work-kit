---
name: thai-memo
description: Activate this skill when the user asks to write, draft, or create a Thai official document — บันทึกข้อความ, บันทึกข้อความภายใน, หนังสือภายนอก, หนังสือราชการ, Thai government memo, Thai official letter, or any Thai administrative document. Also activate when the user says "ร่างบันทึกข้อความ", "เขียนหนังสือ", "ขอแก้ไขเกรด" (grade correction memo), or similar Thai bureaucratic writing tasks. Also covers sending a finished PDF to BUU e-Signature (e-sign.buu.ac.th) for signing.
version: 1.2.0
---

# Thai Official Document Skill

This skill guides you through drafting Thai official documents using BUU OTT
templates and a Python build pipeline, and — for documents that need signing —
getting them into BUU e-Signature.

## Document Types

| Type | Thai name | Command |
|---|---|---|
| `nai` | บันทึกข้อความภายใน | `/draft-memo nai` |
| `nok` | หนังสือภายนอก | `/draft-memo nok` |

## When to invoke

Invoke `/draft-memo` (or follow the steps below directly) when the user asks to produce one of these document types.

## End-to-end workflow

The full path for a document that will be signed:

**draft → approve → number → build → PDF → e-sign upload → assign signer**

1. **Identify type** from the user's request.
2. **Collect fields** — see the table in `/draft-memo` skill. Ask only for missing required fields; infer defaults where obvious (e.g. today's date in Thai Buddhist Era).
3. **Show the draft in chat and get approval** before building anything. Ask for the เลขที่หนังสือ at the same time: the user may already have one, or may want you to request one (step 4).
4. **Request the document number** with the `doc-number` skill, using the approved เรื่อง and เรียน. Requesting consumes a real sequence number — never do it without the user's agreement in that turn.
5. **Write JSON data file** to `/tmp/memo_data_<timestamp>.json`.
6. **Find build script**: locate `build_memo.py` in the `scripts/` directory alongside this plugin.
7. **Run**: `python3 <plugin>/scripts/build_memo.py /tmp/memo_data_<timestamp>.json`
8. **Convert to PDF**: `libreoffice --headless --convert-to pdf <output.odt> --outdir <dir>` — on macOS the binary is `/Applications/LibreOffice.app/Contents/MacOS/soffice`; plain `soffice` is not on PATH.
9. **Look at the rendered PDF** before reporting it as finished (render a page to PNG and inspect it). Check the ที่ line, the sender block, คำลงท้าย and the signature block.
10. **Upload to e-Signature** if the user asks — see below.

## Template locations

Templates are bundled at `<plugin-root>/templates/`:
- `แบบหนังสือภายใน.ott` — for `nai`
- `แบบหนังสือภายนอก.ott` — for `nok`

The build script resolves templates relative to its own location automatically.

## Thai date conversion

Gregorian → Buddhist Era: add 543 to the year.  
Use Thai digits (๐–๙) and Thai month names.

## Layout rules the build script already handles

Do not re-implement these by hand or post-process the ODT — `build_memo.py` emits them, matching the signed หนังสือภายนอก precedent:

- **`doc_number` renders inline** on the ที่ line: `ที่ อว ๘๑๑๖ / XXXX`, with the tab jumping to the sender block on the right. Pass only the part after `อว` — the script writes the `ที่ อว` prefix itself.
- **คำลงท้าย** (`ขอแสดงความนับถือ`) is emitted automatically for `nok`, indented by tabs. Do **not** put it in `body[]` — it would appear twice. Pass `"closing": ""` to suppress it, or a different string to replace it.
- **Signature and role lines** get a leading tab so they land on the centre tab stop of the `ลงชื่อ` style.
- **`content.xml` is written with `pretty_print` off.** lxml's indentation between sibling spans is rendered by ODF as a visible space — that is what once produced `( ผู้ช่วยศาสตราจารย์ ... )` instead of `(ผู้ช่วยศาสตราจารย์ ...)`. Keep it off.

## Signer's name in brackets

The name sits tight inside the brackets — `(ผู้ช่วยศาสตราจารย์ ดร. ชื่อ  นามสกุล)` — with no space after `(` or before `)`. Check this on the rendered PDF, not only in the JSON.

## Tips

- For grade correction memos, `type = nai`, `to = หัวหน้าภาควิชา...`, body explains the error and includes a comparison table.
- For formal external letters, `type = nok`; include `from_org`, `from_address`, and optionally `enclosures`.
- Tables are optional; include only when the user provides structured data to compare.
- `attachments` become a numbered list (๑. ๒. ๓.) at the end of the body, before คำลงท้าย.

---

# BUU e-Signature (e-sign.buu.ac.th)

Use this when the user asks to upload a finished PDF for signing ("อัปโหลดขึ้น e-sign", "ส่งลงนาม", "upload to e-sign").

Drive it with the **Chrome extension tools** (`mcp__claude-in-chrome__*`), not Playwright — the user's Chrome already holds the SSO session. Invoke the `claude-in-chrome` skill first.

## Sign-in

`https://e-sign.buu.ac.th` redirects to `sso.buu.ac.th`. **Never type the user's username or password.** Open the tab, ask the user to sign in themselves, and wait for them to say they are done.

## Upload

Path: **จัดการเอกสาร → อัปโหลดเอกสาร → เพิ่มเอกสาร** (`/addDocument`).

| Field | What to do |
|---|---|
| ชื่อเอกสาร | document number + เรื่อง |
| อัปโหลดเอกสาร | the PDF |
| สถานะเอกสาร (ด่วน) | **ask the user** — it changes the signing queue |
| ข้อความท้ายเอกสาร | leave the default tick on (adds the e-sign verification footer) |

Two gotchas, both of which otherwise cost a round trip:

- **`ชื่อเอกสาร` rejects special characters**: `, " ' ; = ? & # \ / % : +`
  Write the document number with a hyphen — `ที่ อว 8116-XXXX ...` — even though the PDF itself carries `ที่ อว ๘๑๑๖ / XXXX`. The validation message appears inline and shifts the form down, so re-read the page before clicking anything after a failed submit.
- **`file_upload` only accepts paths the session may read.** A PDF sitting outside the session's shared paths is rejected — copy it into the session scratchpad first and upload from there.

Use `file_upload` with the file input's `ref`; never click a file input, which opens a native picker you cannot see.

## Assign the signer

From the document list, click the person-plus icon in the **ผู้ลงนาม** column (`/manageAssign/<id>`) → **เพิ่มผู้ลงนาม** → search with **ชื่อ and นามสกุล in separate fields** → green `+` on the matching row.

The assignment saves immediately — there is no submit button. The document then shows as **รอลงนาม** with the signer's name.

## What not to do

- **Never click ลงนาม or ปฏิเสธการลงนาม.** Signing is the user's own act; stop once the document is queued and tell them it is waiting.
- Do not use **อัปโหลดเอกสาร (ลับ)** unless the user says the document is confidential.
- Do not delete or cancel documents in the list without being asked.

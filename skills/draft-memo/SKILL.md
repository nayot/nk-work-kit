---
name: draft-memo
description: Draft a Thai official document. Use `/draft-memo nai` for บันทึกข้อความภายใน (internal memo) or `/draft-memo nok` for หนังสือภายนอก (external letter). Omit the type to be prompted.
argument-hint: <nai|nok> [output-path]
allowed-tools: [Read, Write, Bash]
---

# draft-memo — Thai Official Document Drafter

You are helping the user draft a Thai government document using the OTT templates bundled with this plugin.

## Arguments

`$ARGUMENTS`

Parse as: `<type> [output-path]`
- `type`: `nai` = บันทึกข้อความภายใน, `nok` = หนังสือภายนอก. If omitted, ask.
- `output-path`: optional target path for the PDF (default: current directory).

---

## Step 1 — Identify document type

If type is not in arguments, ask:
> "ต้องการร่าง **บันทึกข้อความภายใน** (nai) หรือ **หนังสือภายนอก** (nok)?"

---

## Step 2 — Collect fields

Ask the user for missing fields. Use the language they're writing in (Thai/English).

### For `nai` — บันทึกข้อความภายใน

| Field | Thai label | Required |
|---|---|---|
| `department` | ส่วนงาน | Yes |
| `phone` | โทร. | No |
| `doc_number` | ที่ | No (leave blank if unknown) |
| `date` | วันที่ | Yes (default: today in Thai Buddhist Era) |
| `subject` | เรื่อง | Yes |
| `to` | เรียน | Yes |
| `body` | เนื้อความ | Yes (list of paragraphs) |
| `attachments` | สิ่งที่แนบ | No (list of strings) |
| `table` | ตาราง | No (headers + rows) |
| `signer_name` | ชื่อผู้ลงนาม | Yes |
| `signer_roles` | ตำแหน่ง | Yes (list, one per line) |

### For `nok` — หนังสือภายนอก

| Field | Thai label | Required |
|---|---|---|
| `doc_number` | ที่ | Yes — the part after `อว` only, e.g. `๘๑๑๖ / XXXX` |
| `from_org` | จาก (ชื่อหน่วยงาน) | Yes |
| `from_address` | ที่อยู่หน่วยงาน | No |
| `date` | วันที่ | Yes |
| `subject` | เรื่อง | Yes |
| `to` | เรียน | Yes |
| `enclosures` | สิ่งที่ส่งมาด้วย | No (list) |
| `body` | เนื้อความ | Yes (list of paragraphs) |
| `attachments` | สิ่งที่แนบ | No |
| `table` | ตาราง | No |
| `closing` | คำลงท้าย | No — defaults to `ขอแสดงความนับถือ`; `""` omits it |
| `signer_name` | ชื่อผู้ลงนาม | Yes |
| `signer_roles` | ตำแหน่ง | Yes |

The script writes the `ที่ อว` prefix and puts `doc_number` on the same line as
the sender block, so do not repeat either in `from_org`.

**Do not put `ขอแสดงความนับถือ` in `body[]`** — the script emits it from
`closing`, and it would otherwise appear twice.

**Date default:** Convert today's Gregorian date to Thai Buddhist Era (add 543).  
Thai month names: มกราคม กุมภาพันธ์ มีนาคม เมษายน พฤษภาคม มิถุนายน กรกฎาคม สิงหาคม กันยายน ตุลาคม พฤศจิกายน ธันวาคม  
Use Thai digits: ๐๑๒๓๔๕๖๗๘๙

---

## Step 3 — Confirm and build

Once all required fields are collected, show the user a summary and ask for confirmation before building.

Then write a JSON data file to a temp path and call the build script:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_memo.py" /tmp/memo_data.json
```

If `CLAUDE_PLUGIN_ROOT` is not set, the script sits at `<plugin-root>/scripts/build_memo.py` — i.e. `../../scripts/build_memo.py` relative to this SKILL.md.

---

## Step 4 — Convert to PDF

After generating the ODT, convert to PDF:

```bash
libreoffice --headless --convert-to pdf <output.odt> --outdir <outdir>
```

On macOS use `/Applications/LibreOffice.app/Contents/MacOS/soffice` — neither
`libreoffice` nor `soffice` is on PATH.

Render a page of the PDF to PNG and look at it before reporting it as finished.
Then report the final PDF path to the user.

---

## Data JSON format

Write `/tmp/memo_data_<timestamp>.json`:

```json
{
  "type": "nai",
  "department": "ภาควิชาวิศวกรรมไฟฟ้า   คณะวิศวกรรมศาสตร์",
  "phone": "๓๓๓๖",
  "doc_number": "อฟ. ๐๐๑/๒๕๖๙",
  "date": "๒๔ มิถุนายน พ.ศ. ๒๕๖๙",
  "subject": "ขออนุมัติ...",
  "to": "หัวหน้าภาควิชาวิศวกรรมไฟฟ้า",
  "body": [
    "ด้วย...(paragraph 1)",
    "จึงเรียนมาเพื่อโปรดพิจารณา..."
  ],
  "table": {
    "headers": ["", "ก่อนแก้ไข", "หลังแก้ไข"],
    "rows": [
      ["คะแนนรวม", "65.08", "85.46"],
      ["เกรด", "C+", "A"]
    ]
  },
  "attachments": [
    "ตารางคะแนนเดิมในระบบทะเบียน",
    "ตารางคะแนนดิบ (Google Sheet Roster)"
  ],
  "signer_name": "ผู้ช่วยศาสตราจารย์ ดร. ชื่อ  นามสกุล",
  "signer_roles": [
    "ผู้สอนรายวิชา ๕๑๔๓๓๖๖๔ Engineering Electromagnetics",
    "ภาควิชาวิศวกรรมไฟฟ้า คณะวิศวกรรมศาสตร์"
  ],
  "output": "/home/user/documents/memo.odt"
}
```

For `nok`, add `"from_org"`, `"from_address"` and `"enclosures"`; omit
`"department"` and `"phone"`. `"closing"` defaults to `ขอแสดงความนับถือ`:

```json
{
  "type": "nok",
  "doc_number": "๘๑๑๖ / XXXX",
  "from_org": "คณะวิศวกรรมศาสตร์ มหาวิทยาลัยบูรพา",
  "from_address": [
    "๑๖๙ ถนนลงหาดบางแสน ตำบลแสนสุข",
    "อำเภอเมือง ชลบุรี ๒๐๑๓๑"
  ],
  "date": "๒๒ กันยายน พ.ศ. ๒๕๖๙",
  "subject": "ขอเชิญเข้าร่วม...",
  "to": "คุณ... ตำแหน่ง หน่วยงาน",
  "body": [
    "ด้วยคณะวิศวกรรมศาสตร์ ...",
    "จึงเรียนมาเพื่อโปรดพิจารณา ..."
  ],
  "signer_name": "ผู้ช่วยศาสตราจารย์ ดร. ชื่อ  นามสกุล",
  "signer_roles": ["คณบดีคณะวิศวกรรมศาสตร์"],
  "output": "/home/user/documents/letter.odt"
}
```

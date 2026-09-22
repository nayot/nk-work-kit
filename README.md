# thai-memo-plugin

A [Claude Code](https://claude.ai/code) plugin for drafting Thai official documents:

- **บันทึกข้อความภายใน** (`nai`) — internal memo
- **หนังสือภายนอก** (`nok`) — external letter

Documents are generated from LibreOffice OTT templates and exported to ODT/PDF.

## Requirements

- [Claude Code](https://claude.ai/code) CLI
- Python 3 with `lxml` (`pip install lxml`)
- LibreOffice (for PDF export)

## Install

The plugin is published through the `nayot-buu` marketplace, which lives in this
same repository. Add the marketplace once, then install from it:

```bash
claude plugin marketplace add nayot/thai-memo-plugin
claude plugin install thai-memo-plugin@nayot-buu
```

No authentication needed — the repository is public.

Inside a running Claude Code session the same two steps are available from the
`/plugin` menu.

Or clone first and add the marketplace from the local path:

```bash
git clone https://github.com/nayot/thai-memo-plugin
claude plugin marketplace add ./thai-memo-plugin
claude plugin install thai-memo-plugin@nayot-buu
```

Check what got installed with `claude plugin list` and
`claude plugin marketplace list`.

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

## License

MIT

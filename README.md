# nk-work-kit

A [Claude Code](https://claude.ai/code) plugin for everyday work in the Faculty of
Engineering, Burapha University.

| Skill | What it does |
|---|---|
| `draft-memo` / `thai-memo` | Draft **บันทึกข้อความภายใน** (`nai`, internal memo) and **หนังสือภายนอก** (`nok`, external letter) from LibreOffice OTT templates, exported to ODT/PDF |
| `doc-number` | Request, list or cancel document numbers in the faculty's **ระบบขอเลขเอกสารอัตโนมัติ** |
| `thai-memo` (e-Signature) | Upload a finished PDF to **BUU e-Signature** and assign a signer |
| `transcribe` | Turn a meeting recording into a Markdown transcript — Thai, English or mixed |

Ask Claude in your own words, or use the slash commands below.

## Requirements

- [Claude Code](https://claude.ai/code) CLI
- Python 3 with `lxml` (`pip install lxml`)
- LibreOffice (for PDF export)
- For the `transcribe` skill only: [`uv`](https://docs.astral.sh/uv/), `ffmpeg`,
  and an [OpenRouter](https://openrouter.ai/keys) API key — see
  [Audio transcription](#audio-transcription).

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

## Audio transcription

The `transcribe` skill wraps `scripts/transcribe.py` — a single-file CLI
(vendored from [autoTranscribe](https://github.com/nayot/autoTranscribe),
which remains the source of truth) that sends audio to an audio-capable LLM
via OpenRouter and writes a Markdown transcript: summary, then
`[MM:SS]`-timestamped, speaker-labeled, verbatim text in the original
language — Thai, English, or mixed, never translated.

Setup:

```bash
cp scripts/.env.example scripts/.env
# edit scripts/.env and paste your OPENROUTER_API_KEY (from https://openrouter.ai/keys)
```

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

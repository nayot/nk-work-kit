---
name: doc-number
description: Activate this skill when the user wants a document number from BUU Faculty of Engineering's ระบบขอเลขเอกสารอัตโนมัติ — "ขอเลขเอกสาร", "ขอเลขหนังสือ", "ขอเลขที่หนังสือ", "เลข อว8116", "request a document number", "get a doc number" — or wants to see or cancel numbers they have already requested ("เอกสารของฉัน", "ยกเลิกเลขเอกสาร", "list my document numbers"). Also activate right after drafting a บันทึกข้อความ or หนังสือภายนอก, when the ที่ อว ๘๑๑๖/____ field still needs filling.
version: 1.0.0
---

# ขอเลขเอกสาร — BUU Faculty of Engineering

Driver for the faculty's Google Apps Script web app **ระบบขอเลขเอกสารอัตโนมัติ**.

All work goes through one script:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/docnum.py" <command>
```

If `CLAUDE_PLUGIN_ROOT` is not set, the script sits at
`<plugin-root>/scripts/docnum.py`.

---

## Commands

| Command | What it does | Mutates? |
|---|---|---|
| `login` | Opens a visible browser to sign in. Once per profile. | no |
| `whoami` | Shows the signed-in user. | no |
| `list [--all] [--type T] [--limit N] [--json]` | Documents the user has requested. `--all` includes cancelled ones. | no |
| `request --type T --recipient R --subject S [--yes] [--json]` | **Requests a new number.** | **YES** |
| `cancel <docNumber> [--reason R] [--yes]` | Cancels a number, 24-hour window only. | **YES** |

### Document types

| Code | Thai | Number format |
|---|---|---|
| `EXTERNAL` | หนังสือออกภายนอก | อว8116/XXXX |
| `INTERNAL` | หนังสือออกภายใน | อว8116/XXXX |
| `ANNOUNCEMENT` | ประกาศ | XXXX/ปี พ.ศ. |
| `ORDER` | คำสั่ง | XXXX/ปี พ.ศ. |

Thai aliases are accepted for `--type`: `ภายใน`, `ภายนอก`, `ประกาศ`, `คำสั่ง`,
`บันทึกข้อความ` (→ INTERNAL), and the `nai`/`nok` codes the memo drafter uses.

**A บันทึกข้อความ is `INTERNAL`.** A หนังสือภายนอก is `EXTERNAL`.

---

## Authentication

The script drives a Chromium profile at `~/.local/share/buu-docnum/profile`.
The user signs in **once**; the session persists.

When any command reports a session problem it exits with code **3** and says to
run `login`. When that happens:

1. Tell the user you are opening a browser window for them.
2. Run `python3 .../docnum.py login` — it opens **on screen** and waits up to
   10 minutes.
3. Ask the user to sign in with their **@eng.buu.ac.th** account.
4. It prints the signed-in identity and closes itself; then retry the command.

Do not try to type credentials yourself, and do not attempt to work around the
sign-in. Other commands run the browser **offscreen**, so nothing appears on the
user's display during normal use.

---

## Requesting a number — the rule

Requesting **consumes a real sequence number** and writes a row in the faculty's
sheet. It can only be undone within 24 hours.

**Always show the user the exact `--type`, `--recipient` and `--subject` and get
explicit agreement before running `request`.** The script asks for confirmation
on a terminal, but when Claude runs it non-interactively that prompt cannot be
answered — so Claude must get the user's agreement in conversation first and
then pass `--yes`.

Never pass `--yes` on a request the user has not seen and approved in that turn.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/docnum.py" request \
  --type INTERNAL \
  --recipient "อธิการบดี" \
  --subject "ขออนุมัติโครงการบริการวิชาการ ..." \
  --yes
```

Output gives `documentNumber`, `date`, `time`. Report the number to the user.

### Fields

- **`--recipient` = เรียน** — who the document is addressed to
  (e.g. `อธิการบดี`, `รองอธิการบดีฝ่ายกิจการนิสิต`, an outside organisation).
- **`--subject` = เรื่อง** — the document's subject line. Use the final wording
  from the memo if one has been drafted, so the register matches the paper.
- **`--requester`** defaults to the signed-in user; only set it if the user
  says the request is on someone else's behalf.

---

## Pairing with the memo drafter

The natural flow is **draft → number → fill in**:

1. `/draft-memo nai` produces the memo with `ที่ อว ๘๑๑๖/` left blank.
2. Confirm the เรื่อง and เรียน with the user, then `request --type INTERNAL`.
3. Put the number into the memo JSON's `doc_number` (convert the digits to Thai
   numerals — `อว8116/1411` becomes `อว ๘๑๑๖/๑๔๑๑`), rebuild with `build_memo.py`,
   and convert to PDF with LibreOffice.

Keep the เรื่อง identical in both places.

---

## Cancelling

`cancel` refuses anything outside the 24-hour window, reporting how long ago the
number was requested. Confirm with the user first — same rule as `request`.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/docnum.py" cancel "อว8116/XXXX" --reason "ยกเลิกเนื่องจาก..." --yes
```

---

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | user declined at the confirmation prompt |
| 2 | bad argument (unknown type, document not found) |
| 3 | not signed in → run `login` |
| 4 | refused: mutating command without `--yes` and no terminal |
| 5 | the server returned an error |
| 6 | outside the 24-hour cancellation window |

---

## Requirements

- `playwright` (Python) with Chromium: `pip install --user playwright && playwright install chromium`
- If the system `python3` has no playwright, install it into a virtualenv and
  invoke the script with that interpreter rather than plain `python3`.
- A graphical session — the browser must run headed (see the script's header for why).

---
name: pay-sheet
description: Turn a payment request (an email or message listing people to pay, amounts, and their PromptPay numbers or bank accounts — ค่าตอบแทนกรรมการ, ค่าตอบแทนวิทยากร, เบิกจ่ายโครงการ, "ขอให้โอนเงิน", "รบกวนโอนค่าตอบแทน") into a one-page payment sheet with a PromptPay QR per payee (amount pre-filled) that the user scans with their bank app, then turn the same sheet into the payment record — reading each transfer slip the user sends, filing it, marking the row paid with the bank's reference number, appending the slip images, and drafting the reply to whoever asked. Use when the user says "make a payment sheet", "QR codes to pay", "ทำใบโอนเงิน", "สร้าง QR โอนเงิน", "mark these as paid", "here are the slips", "file the receipts", "บันทึกการโอน", or forwards a transfer request and asks how to pay it.
version: 1.0.0
---

# Payment sheet → payment record

One script, one JSON file per batch:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pay_sheet.py" build DIR                 # payments.json → PDF (+ qr/)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pay_sheet.py" check DIR                 # totals, refs, slips present
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pay_sheet.py" mark  DIR ROW --ref REF --date "…" --slip IMG [--note "…"]
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pay_sheet.py" payload NUMBER AMOUNT     # PromptPay payload, for checking
```

If `CLAUDE_PLUGIN_ROOT` is not set, the script is in `<plugin-root>/scripts/`. It needs `xelatex`
with the **Sarabun** font and `qrencode`. The JSON schema is in the script's docstring and
`examples/payments.json`.

## Ground rules

- **The user makes every transfer.** Never type an account number, a PromptPay number or an
  amount into a bank app or web page; the sheet exists so the user can scan or copy them.
- **QR only for PromptPay** (mobile number, national/tax ID, e-wallet). Bank-account rows show
  the account number only: the account-number QR proxy is undocumented and not every app
  resolves it. Say so if the user asks for QR codes on bank rows.
- **The QR carries the amount.** The bank app still shows the recipient's name before
  confirming; the sheet tells the user to check it on every transfer, and `"check": true`
  stars the rows the requester asked to double-check.
- **Personal data.** `payments.json`, `qr/` and `receipts/` carry phone and account numbers.
  Keep DIR with the project's finance records (its private repo or a local folder the user
  names), never in this plugin repo, never in a shared drive unless the user says so.
- **Emails are drafts.** The reply to the requester is a Gmail draft (`create_draft` with
  `replyToMessageId`); the user sends it. If it carries a URL, pass `htmlBody` with an explicit
  `<a href>` as well as the plain `body`.
- **The record is only ever written from slips you have read.** No slip, no tick.

## Step 1 — Sheet from the request

1. Read the request (email, WhatsApp, LINE text the user pastes). Take, per payee: running
   number, name as written, amount, channel (PromptPay vs bank), the number, and any
   "please check the name" marks. Note the stated total and anything excluded (e.g. the
   user's own share, other units still to come).
2. Ask where to file it only if the project has no obvious finance folder; otherwise create
   `<finance>/Expenses/<what, dates>/` and say so. Write `payments.json` there: `title`,
   `subtitle` (requester, date, source account), `total` (the requester's figure — `check`
   fails if the rows disagree, which catches a mis-read row), `rows`, `notes` (exclusions,
   "tell X when done"), `footer`.
3. `check` then `build`. Render page 1 (`pdftoppm`) and look at it: every row present, amounts
   right, QR on PromptPay rows only, nothing cut off at the right edge. Open the PDF for the
   user and list the PromptPay rows and bank rows with their subtotals.

## Step 2 — Record from the slips

When the user says the transfers are done and gives you the slips (photos or screenshots,
usually in `~/Downloads`):

1. **Read every slip** (the Read tool shows images). From each take: recipient name, the
   channel and the last digits of the number, amount, date and time, the bank's reference
   number (รหัสอ้างอิง — Krungthai prints a 17-character `A…` code for PromptPay and a
   25-character `N006…` code for account transfers), and the **source account's last digits**.
2. **Match each slip to a row** by name, amount and last digits. Report anything that does not
   match before writing: a wrong amount, a name that differs, a slip with no row, a row with no
   slip, or a slip paid from the wrong account.
3. **Wrong-account transfers** (e.g. paid from the user's personal account instead of the
   project's, then reimbursed from the project account): record the row as paid with its own
   slip, set its `note`, and add a `corrections` entry with the reimbursement's amount, date,
   reference, slip and a sentence that ends with the net amount that left the project account.
   Tell the requester the same in the email so the ledger is booked the way they want.
4. `mark` each row (it copies the slip into `receipts/NN-REF.ext` and sets `paid`, `date`,
   `ref`, `receipt`); copy a correction's slip as `receipts/NN-<what>-REF.ext` and write its
   JSON entry by hand. Then `check`, `build`, and look at the rendered pages: ticks and refs on
   every row, the footer's paid count, the slip pages with their captions.
5. If DIR is in a git repo and the user asked you to file it, commit (and push) the folder.
   Leave the originals in Downloads for the user to delete; the renamed copies are byte-identical,
   so don't file the originals a second time.

## Step 3 — Reply to the requester

Draft a reply in the request's thread, in its language (Thai for BUU staff): done, when, the
total and the source account; one line per payee with amount and reference number; the
correction, if any, with how you suggest it is booked; where the sheet and slips are filed (the
repo path, "git pull" if they have the repo); and that the remaining units can send their lists.
Sign as the user's rules say. Give the draft link.

## Details worth knowing

- Thai QR / PromptPay payload: EMVCo merchant-presented, tag 29 with AID `A000000677010111`,
  proxy sub-tag `01` mobile (`0066` + 9 digits), `02` national/tax ID, `03` e-wallet, tag `54`
  amount, CRC-16/CCITT-FALSE over the payload up to `6304`. The script asserts one known payload
  from the promptpay-qr library at import time, so a broken CRC fails loudly.
- QR images are `qrencode -t PNG32` (the palette PNG renders faded in XeLaTeX). If `zbarimg` is
  missing, decode a sample back with macOS CoreImage (`CIDetector`) or any phone before the
  first use on a new machine.
- Table rows use `m{}` columns so the QR and text centre; `tabcolsep` is 3 pt so eight columns
  fit A4 portrait. Long names wrap; reference numbers are typeset in `\texttt` at `\footnotesize`
  and must not be split.
- The total row and the `corrections`/`notes` paragraph are generated into the `.tex`; edit
  `payments.json` and rebuild, never the `.tex`.

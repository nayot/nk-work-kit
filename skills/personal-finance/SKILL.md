---
name: personal-finance
description: BUU Personnel Finance — personal money tracking and retirement planning for Burapha University staff, kept in the user's own private Google Sheet with an optional Obsidian/HTML dashboard. Use this skill whenever the user wants to track income and spending, import bank or credit-card statements (Krung Thai รายการเดินบัญชี, UOB e-statement), check their budget, net worth, credit-card due date or mortgage, follow up money the university owes them (เงินทดรองจ่าย, เบิกคืน, ค่าเล่าเรียนบุตร), look at income tax and deductions (ภ.ง.ด.90/91, RMF, ThaiESG, ประกันบำนาญ), or plan for retirement (เกษียณ, บำนาญ, กบข., กองทุนสำรองเลี้ยงชีพ). Triggers include "การเงินส่วนตัว", "รายรับรายจ่าย", "นำเข้าสเตทเมนต์", "บัตรเครดิตครบกำหนด", "เงินทดรองจ่ายค้าง", "วางแผนเกษียณ", "ภาษีปีนี้", "personal finance", "import my statement", "update the finance dashboard", "how much did I spend", "am I on track for retirement", "set up finance tracking", even when the user only drops a bank statement PDF into the chat.
version: 1.0.0
---

# BUU Personnel Finance

Personal finance for Burapha University staff. The user's **own private Google Sheet** holds the
data; `pf.py` builds the sheet, imports statements, and renders a dashboard. Claude does the
talking: setup interview, reviewing what was imported, categorising, following up advances, and
explaining the retirement and tax picture.

```
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/pf.py" <command> ...
```

Below, `pf.py` means that line. If `CLAUDE_PLUGIN_ROOT` is not set, the script is in
`<plugin-root>/scripts/`. Config lives in `~/.config/nk-work-kit/.env`:
`PF_SHEET_ID`, `PF_DIR` (the folder holding `Statements/`), optional `OBSIDIAN_VAULT`,
`PF_DASHBOARD`. The user manual (Thai and English) is in
`${CLAUDE_PLUGIN_ROOT}/templates/personal-finance-manual.th.md` and `.en.md`; point the user to
it, or offer to copy it into their finance folder.

## Ground rules

These protect the user's money data; follow them even when it slows things down.

- **Never store a statement password** — not in a file, note, the sheet, memory or a command you
  save. Bank PDFs stay locked on disk. `pf.py import` asks for the password itself (it also accepts
  `PF_PDF_PASSWORD` for that one run). If the user types it in chat, use it only for that run.
- **Never save unlocked copies** of statements, especially in a folder that syncs to Google Drive.
- **The dashboard shows totals only**: no account numbers, no transaction descriptions, no payee
  names. Keep that true if you add anything to it.
- **Ask before writing** anything other than the import itself: new rules, recategorising rows,
  budgets, advances, settings. Show what will change, then write.
- **Never share the sheet** or send its contents anywhere (email, chat, artifact) without an
  explicit request for that specific action.
- Retirement and tax figures are **planning estimates**. Say which assumptions drive them, and
  tell the user to confirm rules and limits with HR, the fund manager or the Revenue Department.

## First run: setup

Run when the user asks to set up, or when `PF_SHEET_ID` is missing. Go one step at a time.

1. **Tools.** Needs `uv` and `pdftotext` (poppler). If missing, give the install command for their
   OS and stop until done.
2. **Sign in.** `pf.py auth` opens a browser to sign in with the BUU Google account (Sheets access
   only; token saved to `~/.config/nk-work-kit/pf-token.json`). Use `--no-browser` on a server.
3. **Interview** (short, one message): date of birth; employment status (ข้าราชการ with
   กบข. / พนักงานมหาวิทยาลัย with provident fund and social security / transferred from ข้าราชการ
   with a lifetime pension); banks and credit cards used; mortgage; funds and insurance; retirement
   spending goal. The answers fill the Settings and Accounts tabs.
4. **Create the sheet:** `pf.py setup --dob YYYY-MM-DD --save` (title defaults to "Personal
   Finance"). Give the user the link.
5. **Folder:** ask where statements will live, then `pf.py init-folder <dir> --save`. Offer
   `--sync` if they use rclone with Google Drive: it adds Claude Code hooks that run `aisync` at the
   start and end of each session in that folder (install it once:
   `install -m 755 "${CLAUDE_PLUGIN_ROOT}/scripts/aisync" ~/.local/bin/aisync`, and set
   `AISYNC_ROOT` to the folder's parent root if it is not under `~/aiSpace`).
6. **Settings:** write what the interview gave you to the Settings tab (pension, provident fund
   rates, spending target, annuity) after showing the values.
7. **First import:** ask them to put statements in `Statements/`, then run the import below.
   Unknown accounts stop the import with a list; add each with
   `pf.py add-account --id KTB-CUR --name "Current account" --type Bank --institution "Krung Thai" --number <account no.>`
   (cards: `--type "Credit card" --number <last 4>`; home loan: `--type Loan`).

## Monthly routine

1. `pf.py import --dry-run`, report what it found, then `pf.py import`. Every statement is checked
   against the bank's own totals; on a mismatch nothing is written, so report it rather than work
   around it. Running it twice never duplicates rows.
2. **Review `Uncategorised` and `Unspecified QR/PromptPay`** (read Transactions where Category is
   one of those). Group by counterparty, ask the user what the big or recurring ones are, then
   propose rules for the Rules tab: priority, pattern, sign, category. Typical personal rules: the
   mortgage transfer, family transfers, a regular payee, a recurring merchant. Write them after the
   user agrees, then re-categorise matching rows.
3. **Advances:** for anything the user paid on behalf of the university, add a row on the Advances
   tab (ID, description, project, date, amount, evidence) and put the same Advance ID on the
   transaction. When reimbursed, set Status, date and amount. `thai-memo` / `doc-number` in this
   plugin help with the reimbursement memo.
4. Investments: once a month or quarter, add a dated row per fund (RMF, SSF, ThaiESG, provident
   fund) on the Investments tab.
5. `pf.py dashboard` (add `--html` for a browser version). `pf.py status` gives a short text summary.

After the first two or three months of data, offer `pf.py suggest-budget` to fill budgets from the
averages, then let the user adjust them.

## Statements supported

| Bank | Statement | How the user gets it |
|---|---|---|
| Krung Thai | Deposit account รายการเดินบัญชี (ออมทรัพย์ / กระแสรายวัน), PDF | Krungthai NEXT, or request at a branch |
| Krung Thai | Home loan (สินเชื่อเพื่อที่อยู่อาศัย), PDF | Same; updates the Mortgage tab |
| UOB | Credit-card e-statement, PDF, all cards in it | Monthly email |

Other banks: rows can be typed or pasted into Transactions (Txn ID can be any unique text), or the
parser in `scripts/pf_parsers.py` can be extended; any new parser must check the statement's own
totals before returning rows.

## Retirement and tax notes for BUU staff

Read `references/retirement-tax-th.md` before giving retirement or tax advice. In short:

- Retirement is **30 September of the fiscal year in which the person reaches 60** (the Settings
  tab computes it from the date of birth).
- ข้าราชการ: pension (บำนาญ) or lump sum (บำเหน็จ) plus กบข. Transferred staff may receive a fixed
  lifetime pension. พนักงานมหาวิทยาลัย: provident fund plus social security.
- The Retirement tab projects assets to the plan age and compares them with what is needed; the
  main levers are provident fund contributions, RMF/ThaiESG, redirecting a paid-off mortgage, and
  income after retirement. Missing provident-fund figures make the projection pessimistic; say so.
- RMF, ThaiESG and insurance premiums count for a tax year only if paid by 31 December.

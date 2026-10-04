# BUU Personnel Finance — User manual

Personal finance tracking and retirement planning for Burapha University staff
(the `personal-finance` skill in nk-work-kit for Claude Code).

> ฉบับภาษาไทย: `personal-finance-manual.th.md`

---

## 1. What it does

- **Brings income and spending together** from bank statements and credit-card statements, checking
  every statement against the totals the bank printed on it before anything is saved.
- **Categorises automatically** (salary, pension, food, fuel, …) and learns the rules you add.
- **Tracks money the university owes you** (advances, child education allowance) until it is repaid.
- **Shows the big picture**: net worth, monthly budget, credit-card due dates, mortgage.
- **Plans retirement**: works out your retirement date from your birth date, estimates what you will
  need, compares it with what you are on track to have, and tells you how much more to save.
- **Dashboard** with charts and tables (totals only, never account numbers).

All data lives in **your own private Google Sheet**. Claude is the assistant you talk to: it imports
statements and explains the numbers.

## 2. What you need

| Requirement | Notes |
|---|---|
| Your BUU Google account (@buu.ac.th) | Used to sign in to Google Sheets |
| [Claude Code](https://claude.ai/code) with the nk-work-kit plugin | See installation below |
| `uv` and `pdftotext` (poppler) | Claude gives the install command for your system |
| Statements as PDF files | See section 5 |
| Optional: Obsidian | Without it, the dashboard is written as an HTML page for your browser |
| Optional: rclone with Google Drive | Keeps your documents in Google Drive and lets you work from several machines |

### Install the plugin

```bash
claude plugin marketplace add nayot/nk-work-kit
claude plugin install nk-work-kit@nayot-buu
```

## 3. First-time setup (about 15 minutes)

Open Claude Code and say **"set up personal finance tracking"**. Claude walks you through it:

1. **Sign in to Google**: a browser opens; choose your @buu.ac.th account and allow access
   (Google Sheets only).
2. **A few questions**: date of birth; employment status (civil servant / university employee /
   transferred); banks and cards; mortgage; funds and insurance; how much you want to spend each
   month after retiring.
3. **Create the Google Sheet** "Personal Finance"; Claude gives you the link.
4. **Choose a folder** for documents, e.g. `~/Finance`. It gets `Statements/`, `Tax/` and
   `Insurance/` subfolders.
5. **First import**: put PDF statements anywhere in `Statements/` (any file name) and say
   **"import my statements"**. For an account it doesn't know yet, Claude asks what it is and adds it.

## 4. Monthly routine (about 10 minutes)

| When | What | Say to Claude |
|---|---|---|
| Card statement arrives by email | Save the PDF to `Statements/` | "import my statements" |
| Every 1–3 months | Download bank statements from Krungthai NEXT | "import my statements" |
| After an import | Review uncategorised items | "what is still uncategorised?" |
| You pay something for the university | Record the advance | "record an advance for project …, ฿…" |
| You are reimbursed | Close it | "ADV-003 has been reimbursed" |
| Monthly or quarterly | Update fund values | "my RMF is now worth ฿…" |
| Any time | Refresh the dashboard | "update my finance dashboard" |

**Why some items say "Unspecified QR/PromptPay"**: bank statements only say a PromptPay transfer or
QR payment happened, not who was paid. Tell Claude who a number or account belongs to and it adds a
rule so future ones are categorised automatically.

## 5. Supported statements

| Bank | Statement | Where to get it |
|---|---|---|
| Krung Thai | Savings / current account statement (รายการเดินบัญชี), PDF | Krungthai NEXT app, or a branch |
| Krung Thai | Home-loan statement, PDF | Same; updates the mortgage balance and interest |
| UOB | Credit-card e-statement, PDF, all cards in it | Monthly email |

Other banks: type or paste rows into the Transactions tab, or ask the maintainer to add a reader.

**Password-protected PDFs**: no need to unlock them. The importer asks for the password and
**never stores it**. Don't keep unlocked copies in a folder that syncs to the cloud.

## 6. What is in the Google Sheet

| Tab | Contents |
|---|---|
| Net Worth | Bank + investments + money owed to you − cards − loans |
| Budget | Monthly budget per category against actual spending |
| Retirement | Projection to your plan age, with a "projected vs needed" chart |
| Transactions | Every transaction (added by the importer; you can change categories) |
| Card | Each card statement, its due date and whether it was paid in full |
| Advances | Advances and other money waiting to be reimbursed |
| Tax | Your filed ภ.ง.ด.90/91 in summary |
| Mortgage | Loan balance, interest paid this year, projected payoff |
| Investments | RMF / ThaiESG / provident fund values |
| Rules | Categorisation rules (edit or add) |
| Accounts | Your accounts and cards with their latest balances |
| Categories | Category list |
| Settings | Birth date, retirement date, pension, contribution rates, inflation, return, spending goal |

Colours: **blue text** = values you set; **green** = linked from another tab; **yellow fill** = still to
fill in. Everything else is a formula; don't type over it.

## 7. Retirement planning

- **Retirement date** = 30 September of the fiscal year in which you reach 60 (calculated for you).
- On Settings: monthly pension (if any), provident-fund rates, the monthly spending you want after
  retiring (in today's money), annuity insurance (if any).
- On Retirement: provident-fund contributions per month, RMF/ThaiESG per year, children's education
  costs, and income after retirement (e.g. consulting).
- The summary shows projected vs needed assets at retirement, the gap or surplus, the extra saving
  per month to close it, and the age the money lasts to.
- Ask Claude things like **"what if I buy ฿100,000 of RMF a year?"** or **"would my provident fund
  be taxed if I change jobs before 55?"**

> Figures are planning estimates. Confirm entitlements and rules with BUU HR, your fund manager or
> the Revenue Department before acting.

## 8. Tax

- Copy the figures from your filed ภ.ง.ด.90/91 into the Tax tab to see your effective rate and which
  allowances you used.
- Worth checking: whether provident-fund contributions above ฿10,000 were claimed in full, the child
  allowance, mortgage interest and insurance premiums.
- RMF, ThaiESG and insurance premiums count for a tax year only if paid **by 31 December**.

## 9. Several machines with Google Drive (optional)

If you already use rclone with Google Drive:

1. Install the sync command: `install -m 755 <plugin>/scripts/aisync ~/.local/bin/aisync`
2. If your finance folder is not under `~/aiSpace`, add to `~/.config/nk-work-kit/.env`:
   `AISYNC_ROOT=~/Finance` (and `AISYNC_REMOTE=<remote>:` if your remote is not called `GDrive`).
3. Tell Claude **"sync my finance folder with Google Drive"**: it syncs at the start and end of every
   Claude session in that folder.
4. On a new machine: install rclone and the plugin, run `aisync` once in the same folder, and sign in
   again with `pf.py auth` (sign-in files are never synced).

## 10. Privacy and security

- The Google Sheet is yours and not shared. Claude does not send your data anywhere unless you ask.
- PDF passwords are never stored. The sign-in file (`pf-token.json`) stays on your machine; never
  share it.
- The dashboard shows totals only, without account numbers or payee names.
- To stop using it: delete the Google Sheet and `~/.config/nk-work-kit/pf-token.json`.

## 11. Troubleshooting

| Message or symptom | What to do |
|---|---|
| "Not signed in" | Run `pf.py auth` again (or tell Claude "sign in to Google again") |
| "totals do not match the bank" | The file may be incomplete or damaged; download it again. Nothing is saved from a mismatched statement |
| "accounts are not on the Accounts tab" | Tell Claude what the account is, then import again |
| The latest month looks too low | The next card statement hasn't arrived yet; the dashboard says so |
| Mortgage looks paid twice in one month | The bank debited at the start and the end of a month |
| Afraid of duplicates when importing again | Can't happen: only new transactions are added |

## 12. Commands for advanced users

```bash
pf.py auth                      # sign in to Google
pf.py setup --dob 1980-01-15 --save
pf.py init-folder ~/Finance --save [--sync]
pf.py add-account --id KTB-CUR --name "Current account" --type Bank --institution "Krung Thai" --number 1234567890
pf.py import [--dry-run]
pf.py suggest-budget [--overwrite]
pf.py dashboard [--html]
pf.py status
```

`pf.py` means `uv run <plugin>/scripts/pf.py` · settings file `~/.config/nk-work-kit/.env`
(`PF_SHEET_ID`, `PF_DIR`, `OBSIDIAN_VAULT`, `PF_DASHBOARD`, `AISYNC_*`)

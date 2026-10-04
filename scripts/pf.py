#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["google-auth", "google-auth-oauthlib", "requests", "markdown"]
# ///
"""Personal finance for BUU personnel (nk-work-kit, personal-finance skill).

A private Google Sheet holds the data; this script builds it, imports bank and credit-card
statements into it, and renders a dashboard.

  pf.py auth                         sign in with your BUU Google account (Sheets access, once)
  pf.py setup --dob YYYY-MM-DD [--title T] [--save]
                                     create the Personal Finance sheet (--save writes PF_SHEET_ID to .env)
  pf.py init-folder DIR [--sync]     make the statements folder (Statements/, Tax/, Insurance/, CLAUDE.md);
                                     --sync adds Claude Code hooks that run aisync (Google Drive) per session
  pf.py add-account --id ID --name N --type Bank|"Credit card"|Loan|Fund|"Provident fund"|Insurance|Other
                    [--institution I] [--number NUMBER] [--use U]
  pf.py import [--dir DIR] [--dry-run] [--skip-unknown]
                                     parse every statement under DIR/Statements, check it against the bank's own
                                     totals, categorise with the Rules tab, add only new transactions
  pf.py suggest-budget [--overwrite] set each budget to the average of complete months
  pf.py dashboard [--out PATH] [--html]
                                     render the dashboard (default: <OBSIDIAN_VAULT>/Finance/Dashboard.md,
                                     else <PF_DIR>/Dashboard.md); --html also writes Dashboard.html
  pf.py status                       short text summary for Claude to report

Config (~/.config/nk-work-kit/.env): PF_SHEET_ID, PF_DIR, optional OBSIDIAN_VAULT, PF_DASHBOARD.
Locked statement PDFs: the password is asked for when needed (or read from PF_PDF_PASSWORD in the
environment) and never stored.
"""
import argparse
import collections
import datetime as dt
import getpass
import hashlib
import json
import os
import pathlib
import re
import sys

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pf_parsers as P  # noqa: E402

SCRIPTS = pathlib.Path(__file__).resolve().parent
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
API = 'https://sheets.googleapis.com/v4/spreadsheets'


# ---------------------------------------------------------------- config

def config_files():
    bases = []
    if xdg := os.environ.get('XDG_CONFIG_HOME'):
        bases.append(pathlib.Path(xdg))
    if appdata := os.environ.get('APPDATA'):
        bases.append(pathlib.Path(appdata))
    bases.append(pathlib.Path.home() / '.config')
    return [b / 'nk-work-kit' / '.env' for b in bases] + [SCRIPTS / '.env']


def config_dir():
    for f in config_files():
        if f.is_file():
            return f.parent
    return pathlib.Path.home() / '.config' / 'nk-work-kit'


def load_env():
    for f in config_files():
        if f.is_file():
            for line in f.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, _, v = line.partition('=')
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            return


def save_env(key, value):
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    f = d / '.env'
    lines = f.read_text(encoding='utf-8').splitlines() if f.exists() else []
    lines = [l for l in lines if not l.startswith(f'{key}=')] + [f'{key}={value}']
    f.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    f.chmod(0o600)
    os.environ[key] = value


def sheet_id():
    sid = os.environ.get('PF_SHEET_ID', '').strip()
    if not sid:
        sys.exit('PF_SHEET_ID is not set. Run `pf.py setup --dob YYYY-MM-DD --save` first, '
                 'or add PF_SHEET_ID=<id> to ~/.config/nk-work-kit/.env.')
    return sid


def pf_dir(arg=None):
    raw = arg or os.environ.get('PF_DIR', '').strip()
    if not raw:
        sys.exit('PF_DIR is not set: the folder that holds Statements/. Pass --dir or add PF_DIR to the .env.')
    return pathlib.Path(raw).expanduser()


# ---------------------------------------------------------------- auth / API

def token_path():
    return config_dir() / 'pf-token.json'


def client_file():
    own = config_dir() / 'credentials.json'
    return own if own.is_file() else SCRIPTS / 'gmail_oauth_client.json'


def credentials():
    import google.auth.transport.requests
    tp = token_path()
    if tp.is_file():
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(str(tp), SCOPES)
        if not creds.valid:
            creds.refresh(google.auth.transport.requests.Request())
            tp.write_text(creds.to_json())
        return creds, None
    try:
        import google.auth
        creds, project = google.auth.default(scopes=SCOPES)
        creds.refresh(google.auth.transport.requests.Request())
        return creds, project
    except Exception:
        sys.exit('Not signed in. Run `pf.py auth` once (signs in with your BUU Google account).')


class Sheet:
    def __init__(self, sid=None):
        creds, project = credentials()
        self.s = requests.Session()
        self.s.headers['Authorization'] = f'Bearer {creds.token}'
        if project:
            self.s.headers['x-goog-user-project'] = project
        self.id = sid

    def _ok(self, r):
        if r.status_code >= 400:
            sys.exit(f'Google Sheets error {r.status_code}: {r.text[:500]}')
        return r.json()

    def get(self, rng, raw=False):
        params = {'valueRenderOption': 'UNFORMATTED_VALUE', 'dateTimeRenderOption': 'FORMATTED_STRING'} if raw else {}
        r = self.s.get(f'{API}/{self.id}/values/{requests.utils.quote(rng)}', params=params)
        return self._ok(r).get('values', [])

    def put(self, rng, rows):
        return self._ok(self.s.put(f'{API}/{self.id}/values/{requests.utils.quote(rng)}',
                                   params={'valueInputOption': 'USER_ENTERED'}, json={'values': rows}))

    def put_many(self, data):
        body = {'valueInputOption': 'USER_ENTERED', 'data': [{'range': k, 'values': v} for k, v in data.items()]}
        return self._ok(self.s.post(f'{API}/{self.id}/values:batchUpdate', json=body))

    def ensure_rows(self, title, need):
        """Grow a tab so row `need` exists: a values write that starts below the grid is rejected."""
        meta = self._ok(self.s.get(f'{API}/{self.id}', params={'fields': 'sheets.properties(sheetId,title,gridProperties)'}))
        p = next(x['properties'] for x in meta['sheets'] if x['properties']['title'] == title)
        have = p['gridProperties']['rowCount']
        if need > have:
            self.batch([{'appendDimension': {'sheetId': p['sheetId'], 'dimension': 'ROWS', 'length': need - have + 500}}])

    def batch(self, requests_):
        return self._ok(self.s.post(f'{API}/{self.id}:batchUpdate', json={'requests': requests_}))


def cmd_auth(args):
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(str(client_file()), SCOPES)
    creds = flow.run_local_server(port=0, open_browser=not args.no_browser,
                                  authorization_prompt_message='Open this URL to sign in with your BUU Google account:\n{url}\n')
    tp = token_path()
    tp.parent.mkdir(parents=True, exist_ok=True)
    tp.write_text(creds.to_json())
    tp.chmod(0o600)
    print(f'Signed in. Token saved to {tp} (keep it private).')


# ---------------------------------------------------------------- setup

def cmd_setup(args):
    import pf_sheet
    dob = dt.date.fromisoformat(args.dob)
    sh = Sheet()
    body = {'properties': {'title': args.title, 'locale': 'en_GB', 'timeZone': 'Asia/Bangkok'},
            'sheets': [{'properties': {'sheetId': i, 'title': t, 'index': i}} for i, t in enumerate(pf_sheet.TABS)]}
    created = sh._ok(sh.s.post(API, json=body))
    sh.id = created['spreadsheetId']
    values, reqs = pf_sheet.build(dob)
    sh.put_many(values)
    sh.batch(reqs)
    url = f'https://docs.google.com/spreadsheets/d/{sh.id}'
    print(f'Created "{args.title}": {url}')
    if args.save:
        save_env('PF_SHEET_ID', sh.id)
        print(f'Saved PF_SHEET_ID to {config_dir() / ".env"}')
    else:
        print(f'Add this line to ~/.config/nk-work-kit/.env:  PF_SHEET_ID={sh.id}')


CLAUDE_MD = """# Personal finance

This folder holds my statements for the nk-work-kit **personal-finance** skill. The data lives in my
Google Sheet ({url}); the skill's `pf.py` imports statements from `Statements/` into it.

- Save bank and credit-card statements anywhere under `Statements/` (any file name).
- Keep bank PDFs password-locked. Never write the password into a file, note, sheet or memory.
- The dashboard shows totals only: no account numbers or transaction descriptions.
"""

HOOKS = {"hooks": {
    "SessionStart": [{"hooks": [{"type": "command", "timeout": 180, "statusMessage": "Syncing finance files with Google Drive...",
                                 "command": "cd \"$CLAUDE_PROJECT_DIR\" && \"$HOME/.local/bin/aisync\" >/dev/null 2>&1 || true"}]}],
    "SessionEnd": [{"hooks": [{"type": "command", "timeout": 180,
                               "command": "cd \"$CLAUDE_PROJECT_DIR\" && \"$HOME/.local/bin/aisync\" >/dev/null 2>&1 || true"}]}]}}


def cmd_init_folder(args):
    d = pathlib.Path(args.dir).expanduser()
    for sub in ('Statements', 'Tax', 'Insurance'):
        (d / sub).mkdir(parents=True, exist_ok=True)
    cm = d / 'CLAUDE.md'
    if not cm.exists():
        sid = os.environ.get('PF_SHEET_ID', '')
        cm.write_text(CLAUDE_MD.format(url=f'https://docs.google.com/spreadsheets/d/{sid}' if sid else 'see PF_SHEET_ID'), encoding='utf-8')
    if args.sync:
        st = d / '.claude' / 'settings.json'
        st.parent.mkdir(exist_ok=True)
        cur = json.loads(st.read_text()) if st.exists() else {}
        cur.setdefault('hooks', {}).update(HOOKS['hooks'])
        st.write_text(json.dumps(cur, indent=2) + '\n')
    if args.save:
        save_env('PF_DIR', str(d))
    print(f'Folder ready: {d}' + (' (with Google Drive sync hooks)' if args.sync else ''))


def cmd_add_account(args):
    sh = Sheet(sheet_id())
    have = sh.get('Accounts!A2:A')
    if any(r and r[0] == args.id for r in have):
        sys.exit(f'Account {args.id} already exists.')
    row = len(have) + 2
    sh.put(f'Accounts!A{row}:G{row}', [[args.id, args.name, args.institution or '', args.type,
                                        f"'{args.number}" if args.number else '', args.use or '', 'Active']])
    print(f'Added {args.id} on row {row}.')


# ---------------------------------------------------------------- import

def load_rules(sh):
    rules = []
    for v in sh.get('Rules!A2:H'):
        v = v + [''] * (8 - len(v))
        if not v[2]:
            continue
        try:
            pat = re.compile(v[2], re.I)
        except re.error as e:
            print(f'  ! skipped rule with bad pattern {v[2]!r}: {e}')
            continue
        rules.append(dict(pri=float(v[0] or 999), acct=v[1], pat=pat, sign=v[4], cat=v[5], cp=v[6], adv=v[7],
                          amt=float(str(v[3]).replace(',', '')) if str(v[3]).strip() else None))
    return sorted(rules, key=lambda r: r['pri'])


def categorise(r, rules, own_numbers):
    if r['kind'] == 'ktb-deposit':
        for n in own_numbers:
            if n in re.sub(r'\D', '', r['desc'].split('|', 1)[-1]):
                return 'Transfer between own accounts', '', ''
    for ru in rules:
        if ru['acct'] and ru['acct'] != r['acct']:
            continue
        if (ru['sign'] == '-' and r['amount'] >= 0) or (ru['sign'] == '+' and r['amount'] <= 0):
            continue
        if ru['amt'] is not None and abs(abs(r['amount']) - abs(ru['amt'])) > 0.005:
            continue
        if ru['pat'].search(r['desc']):
            return ru['cat'], ru['cp'], ru['adv']
    return 'Uncategorised', '', ''


class Passwords:
    def __init__(self):
        self.known = [p for p in [os.environ.get('PF_PDF_PASSWORD')] if p]

    def text(self, path):
        try:
            return P.pdf_text(path)
        except P.PasswordNeeded:
            pass
        for pw in self.known:
            try:
                return P.pdf_text(path, pw)
            except P.PasswordNeeded:
                continue
        for _ in range(3):
            try:
                pw = getpass.getpass(f'Password for {path.name}: ')
            except EOFError:
                sys.exit(f'{path.name} is password-protected. Run the import in a terminal, '
                         'or set PF_PDF_PASSWORD for this one run.')
            try:
                t = P.pdf_text(path, pw)
                self.known.append(pw)
                return t
            except P.PasswordNeeded:
                print('  wrong password')
        sys.exit(f'Could not open {path}')


def read_accounts(sh):
    rows = sh.get('Accounts!A2:I', raw=True)
    accts = []
    for i, r in enumerate(rows):
        r = r + [''] * (9 - len(r))
        if not r[0]:
            continue
        number = re.sub(r'\D', '', str(r[4]))
        accts.append(dict(row=i + 2, id=r[0], type=r[3], number=number, last4=number[-4:] if number else '',
                          balance_date=str(r[8])))
    return accts


def cmd_import(args):
    sh = Sheet(sheet_id())
    base = pf_dir(args.dir)
    files = sorted(p for p in (base / 'Statements').rglob('*') if p.suffix.lower() == '.pdf')
    if not files:
        sys.exit(f'No PDF statements under {base / "Statements"}')
    accts = read_accounts(sh)
    by_last4 = collections.defaultdict(list)
    for a in accts:
        if a['last4']:
            by_last4[a['last4']].append(a)
    own_numbers = [a['number'] for a in accts if len(a['number']) >= 8]

    def account(last4, want):
        cands = [a for a in by_last4.get(last4, []) if a['type'] in want] or by_last4.get(last4, [])
        return cands[0] if cands else None

    pw = Passwords()
    out, unknown, cards, loans, balances = [], {}, [], [], {}
    for f in files:
        text = pw.text(f)
        kind = P.detect(text)
        rel = f.relative_to(base).as_posix()
        if kind == 'ktb-deposit':
            rows, chk = P.parse_ktb_deposit(text)
            if not chk['ok']:
                sys.exit(f'{rel}: totals do not match the bank ({chk["ours"]} vs {chk["bank"]}). Nothing imported.')
            a = account(chk['account'][-4:], {'Bank'})
            if not a:
                unknown[chk['account']] = ('Krung Thai deposit account', len(rows), rel)
                continue
            out += [dict(kind=kind, acct=a['id'], date=r['date'], key=r['time'], desc=f"{r['type']} | {r['detail']}",
                         amount=r['amount'], src=f.name) for r in rows]
            balances[a['id']] = (chk['balance_date'], chk['balance'])
            print(f'  {rel}: {len(rows)} rows, totals match the bank')
        elif kind == 'ktb-loan':
            rows, chk = P.parse_ktb_loan(text)
            if not chk['ok']:
                sys.exit(f'{rel}: loan balance does not reconcile. Nothing imported.')
            a = account(chk['account'][-4:], {'Loan'})
            if not a:
                unknown[chk['account']] = ('Krung Thai loan', len(rows), rel)
                continue
            loans.append((a, rows, chk))
            balances[a['id']] = (chk['balance_date'], chk['balance'])
            print(f'  {rel}: loan, {len(rows)} payments, balance {chk["balance"]:,.2f}')
        elif kind == 'uob-card':
            rows, chk = P.parse_uob(text)
            if not chk['ok']:
                sys.exit(f'{rel}: card balances do not reconcile ({chk["cards"]}). Nothing imported.')
            for c in chk['cards']:
                if c['n'] == 0 and not c['total'] and not c['previous']:
                    continue                              # dormant card, nothing to record
                a = account(c['last4'], {'Credit card'})
                if not a:
                    unknown[c['last4']] = (f'credit card {c["name"] or "UOB"}', c['n'], rel)
                    continue
                cards.append([a['id'], chk['statement'], chk['due'], chk['limit'], c['total'], c['minimum'], f.name])
                if (balances.get(a['id']) or ('',))[0] < chk['statement']:
                    balances[a['id']] = (chk['statement'], c['total'])
                out += [dict(kind=kind, acct=a['id'], date=r['date'], key=r['post'],
                             desc=r['desc'] + (f" [{r['fx']}]" if r['fx'] else ''), amount=r['amount'], src=f.name)
                        for r in rows if r['last4'] == c['last4']]
            print(f'  {rel}: card statement {chk["statement"]}, balances reconcile')
        else:
            print(f'  {rel}: not a supported statement, skipped')

    if unknown and not args.skip_unknown:
        print('\nThese accounts are not on the Accounts tab yet, so nothing was imported:')
        for num, (what, n, rel) in unknown.items():
            print(f'  ...{num[-4:]}  {what}  ({n} rows, {rel})')
        print('Add each with `pf.py add-account` (or run with --skip-unknown).')
        sys.exit(3)

    seen = collections.Counter()
    for r in out:  # stable ID: the same transaction always gets the same ID; identical twins get #2, #3
        b = f"{r['acct']}|{r['date']}|{r['key']}|{r['amount']:.2f}|{r['desc']}"
        seen[b] += 1
        r['id'] = f"{r['acct']}-{r['date'].replace('-', '')}-" + hashlib.sha1(f'{b}|{seen[b]}'.encode()).hexdigest()[:6]
    have = {v[0] for v in sh.get('Transactions!A2:A') if v}
    rules = load_rules(sh)
    new = []
    for r in sorted((r for r in out if r['id'] not in have), key=lambda r: (r['date'], r['acct'])):
        cat, cp, adv = categorise(r, rules, own_numbers)
        new.append([r['id'], r['date'], r['acct'], r['desc'], r['amount'], cat, cp, adv, r['src'], '', False])
    counts = collections.Counter(n[5] for n in new)
    print(f'\n{len(out)} transactions in statements, {len(out) - len(new)} already in the sheet, {len(new)} new')
    if counts:
        print('  ' + ', '.join(f'{k}: {v}' for k, v in counts.most_common()))
    if args.dry_run:
        print('Dry run: nothing written.')
        return
    data = {}
    if new:
        start = len(sh.get('Transactions!A:A')) + 1
        sh.ensure_rows('Transactions', start + len(new))
        data[f'Transactions!A{start}'] = new
    # card statements: upsert by (card, statement date)
    card_rows = sh.get('Card!A2:B')
    idx = {(r[0], r[1]): i + 2 for i, r in enumerate(card_rows) if len(r) > 1}
    nxt = len(card_rows) + 2
    for c in sorted(cards, key=lambda c: (c[1], c[0])):
        row = idx.get((c[0], c[1]))
        if row is None:
            row, nxt = nxt, nxt + 1
        g = (f'=SUMIFS(Transactions!$E:$E,Transactions!$C:$C,$A{row},Transactions!$F:$F,"Card payment",'
             f'Transactions!$B:$B,">"&$B{row},Transactions!$B:$B,"<="&($C{row}+3))')
        data[f'Card!A{row}:J{row}'] = [c[:6] + [g, f'=IF(E{row}<=0,"-",IF(G{row}>=E{row}-0.005,"Yes",IF(G{row}=0,"Not yet","No")))',
                                                f'=IF(N(D{row})=0,0,E{row}/D{row})', c[6]]]
    # loans: statement entries + balance and rate on the Mortgage tab
    if loans:
        existing = {r[0] for r in sh.get('Mortgage!H3:H', raw=True) if r}
        lrows = [[r['date'], r['principal'], r['interest'], r['total'], r['balance']]
                 for a, rows, chk in loans for r in rows if r['date'] not in existing]
        if lrows:
            start = len(sh.get('Mortgage!H1:H')) + 1
            data[f'Mortgage!H{max(start, 3)}'] = lrows
        a, rows, chk = max(loans, key=lambda x: x[2]['balance_date'] or '')
        data['Mortgage!B2'] = [[chk['balance']]]
        if chk['rate']:
            data['Mortgage!B3'] = [[chk['rate']]]
    for a in accts:
        if a['id'] in balances:
            d, bal = balances[a['id']]
            if d and d >= (a['balance_date'] or ''):
                data[f'Accounts!H{a["row"]}:I{a["row"]}'] = [[bal, d]]
    if data:
        sh.put_many(data)
    print(f'Written: {len(new)} transactions, {len(cards)} card statements, {len(loans)} loan statements.')


# ---------------------------------------------------------------- budget

def cmd_suggest_budget(args):
    sh = Sheet(sheet_id())
    v = sh.get('Budget!A4:P80', raw=True)
    flags = v[0]
    done = [j for j in range(4, len(flags)) if flags[j] is True]
    if not done:
        sys.exit('No complete months with data yet.')
    writes = {}
    for i, r in enumerate(v[3:], start=7):
        if not r or not r[0] or r[0] in ('Total spending', 'Income', 'Net (income less spending)'):
            continue
        vals = [float(r[j] or 0) for j in done if j < len(r)]
        avg = sum(vals) / len(done)
        cur = r[1] if len(r) > 1 else 0
        if args.overwrite or not cur:
            writes[f'Budget!B{i}'] = [[int(round(avg / 500.0) * 500)]]
    if writes:
        sh.put_many(writes)
    print(f'Set {len(writes)} budgets from {len(done)} complete months.')


# ---------------------------------------------------------------- dashboard + status

def gather(sh):
    """Read everything the dashboard and status need."""
    def pdate(v):
        if v in (None, ''):
            return None
        for f in ('%Y-%m-%d', '%b %Y', '%d/%m/%Y'):
            try:
                return dt.datetime.strptime(str(v)[:10], f).date()
            except ValueError:
                pass
        return None
    tx = [dict(date=str(r[1]), account=r[2], amount=float(r[4]), category=r[5], type=r[11] if len(r) > 11 else '')
          for r in sh.get('Transactions!A2:L', raw=True) if len(r) > 5 and r[0]]
    nw = {r[0]: (r[1] if len(r) > 1 else 0) for r in sh.get("'Net Worth'!A5:B11", raw=True) if r and r[0]}
    accts = [r + [''] * (9 - len(r)) for r in sh.get('Accounts!A2:I', raw=True) if r and r[0]]
    bank = [dict(id=a[0], name=a[1], balance=a[7], date=str(a[8])) for a in accts if a[3] == 'Bank']
    cards = []
    for r in sh.get('Card!A2:H', raw=True):
        if len(r) > 4 and r[0]:
            cards.append(dict(card=r[0], statement=pdate(r[1]), due=pdate(r[2]), total=float(r[4] or 0),
                              paid=r[7] if len(r) > 7 else ''))
    latest_card = {}
    for c in sorted(cards, key=lambda c: c['statement'] or dt.date.min):
        latest_card[c['card']] = c
    adv = []
    for r in sh.get('Advances!A2:M', raw=True):
        if r and r[0]:
            r = r + [''] * (13 - len(r))
            adv.append(dict(id=r[0], what=r[1], project=r[2], date=str(r[3]), status=r[8],
                            outstanding=float(r[11]) if r[11] not in ('', '-') else 0, days=r[12]))
    m = sh.get('Mortgage!A2:F7', raw=True)
    mi = {r[0]: r[1] for r in m if len(r) > 1}
    mp = {r[4]: r[5] for r in m if len(r) > 5}
    st = {r[0]: r[1] for r in sh.get('Settings!A5:B19', raw=True) if len(r) > 1}
    rv = sh.get('Retirement!A5:F28', raw=True)
    rs = {r[4]: r[5] for r in rv if len(r) > 5 and r[4]}
    ri = {r[0]: r[1] for r in rv if len(r) > 1 and r[0]}
    proj = [(int(r[0]), int(r[1]), float(r[12]), float(r[13])) for r in sh.get('Retirement!A31:N120', raw=True)
            if len(r) > 13 and str(r[0]).isdigit()]
    bv = sh.get('Budget!A4:P80', raw=True)
    budget = None
    if bv:
        flags, hdr = bv[0], bv[2]
        card_to = max((t['date'] for t in tx if any(t['account'] == c for c in latest_card)), default='9999')
        import calendar
        def covered(j):
            d = pdate(hdr[j]) if j < len(hdr) else None
            if not d or flags[j] is not True:
                return False
            end = d.replace(day=calendar.monthrange(d.year, d.month)[1])
            return not latest_card or end.isoformat() <= card_to
        col = max((j for j in range(4, len(flags)) if covered(j)), default=None)
        if col is not None:
            rows = [(r[0], float(r[1] or 0), float(r[col] or 0)) for r in bv[3:]
                    if r and r[0] and r[0] not in ('Total spending', 'Income', 'Net (income less spending)')]
            tot = next(r for r in bv if r and r[0] == 'Total spending')
            budget = dict(month=pdate(hdr[col]).strftime('%B %Y'), budget=float(tot[1] or 0), actual=float(tot[col] or 0),
                          rows=sorted(rows, key=lambda r: -max(r[1], r[2])))
    payoff = pdate(mp.get('Projected payoff month'))
    return dict(
        url=f'https://docs.google.com/spreadsheets/d/{sh.id}', tx=tx, nw=nw, bank=bank, cards=latest_card, advances=adv,
        mortgage=dict(balance=float(mi.get('Balance (฿)') or 0), rate=float(mi.get('Interest rate (annual)') or 0),
                      payment=float(mi.get('Monthly payment (฿)') or 0), payoff=payoff,
                      left=mp.get('Payments to payoff'), interest_ytd=float(mp.get('Interest paid this calendar year (฿)') or 0)),
        settings=dict(dob=pdate(st.get('Date of birth')), retire=pdate(st.get('Retirement date')),
                      months_left=st.get('Months to retirement'), target=float(st.get("Retirement spending target (today's money, per month)") or 0),
                      inflation=float(st.get('Inflation (planning)') or 0), ret=float(st.get('Investment return (planning)') or 0),
                      pension=float(st.get('Lifetime pension (บำนาญ, per month)') or 0),
                      annuity=float(st.get('Annuity insurance payout (per year)') or 0), annuity_first=pdate(st.get('Annuity first payout date')),
                      annuity_end=st.get('Annuity payouts end at age')),
        retirement=dict(projected=float(rs.get('Projected assets at retirement') or 0), needed=float(rs.get('Needed at retirement') or 0),
                        extra=float(rs.get('Extra saving per month to close the gap') or 0), last_age=rs.get('Assets last until age'),
                        retire_fy=int(ri.get('First retired fiscal year') or 0) - 1, rows=proj,
                        missing=[k for k in ('Provident fund contributions, you + employer (per month)',) if not ri.get(k)]),
        budget=budget)


def cmd_dashboard(args):
    import pf_dashboard
    sh = Sheet(sheet_id())
    md = pf_dashboard.render(gather(sh))
    if args.out:
        path = pathlib.Path(args.out).expanduser()
    elif os.environ.get('PF_DASHBOARD'):
        path = pathlib.Path(os.environ['PF_DASHBOARD']).expanduser()
    elif os.environ.get('OBSIDIAN_VAULT') and (pathlib.Path(os.environ['OBSIDIAN_VAULT']).expanduser() / '.obsidian').is_dir():
        path = pathlib.Path(os.environ['OBSIDIAN_VAULT']).expanduser() / 'Finance' / 'Dashboard.md'
    else:
        path = pf_dir() / 'Dashboard.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md, encoding='utf-8')
    print('wrote', path)
    if args.html:
        hp = path.with_suffix('.html')
        hp.write_text(pf_dashboard.to_html(md), encoding='utf-8')
        print('wrote', hp)


def cmd_status(args):
    sh = Sheet(sheet_id())
    d = gather(sh)
    today = dt.date.today()
    print(f"Net worth: {float(d['nw'].get('Net worth') or 0):,.0f}")
    for c in d['cards'].values():
        print(f"Card {c['card']}: statement {c['statement']} balance {c['total']:,.2f}, due {c['due']}, paid in full: {c['paid']}")
    owed = [a for a in d['advances'] if a['status'] != 'Reimbursed']
    print(f"Owed to you: {sum(a['outstanding'] for a in owed):,.0f} in {len(owed)} items"
          + (f"; oldest {max((a['days'] for a in owed if a['days'] != ''), default='-')} days" if owed else ''))
    unc = [t for t in d['tx'] if t['category'] == 'Uncategorised']
    print(f"Uncategorised transactions: {len(unc)}")
    last = {}
    for t in d['tx']:
        last[t['account']] = max(last.get(t['account'], ''), t['date'])
    print('Latest transaction per account: ' + ', '.join(f'{k} {v}' for k, v in sorted(last.items())))
    r = d['retirement']
    if d['settings']['retire']:
        print(f"Retirement {d['settings']['retire']} ({d['settings']['months_left']} months): projected {r['projected']:,.0f} "
              f"vs needed {r['needed']:,.0f}; lasts to age {r['last_age']}")
    if today.month >= 10:
        print(f'Reminder: RMF/ThaiESG purchases for tax year {today.year} must be made by 31 Dec.')


def main():
    for stream in (sys.stdout, sys.stderr):      # Thai text on a Windows console code page
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    load_env()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('auth'); a.add_argument('--no-browser', action='store_true'); a.set_defaults(f=cmd_auth)
    a = sub.add_parser('setup'); a.add_argument('--dob', required=True); a.add_argument('--title', default='Personal Finance')
    a.add_argument('--save', action='store_true'); a.set_defaults(f=cmd_setup)
    a = sub.add_parser('init-folder'); a.add_argument('dir'); a.add_argument('--sync', action='store_true')
    a.add_argument('--save', action='store_true'); a.set_defaults(f=cmd_init_folder)
    a = sub.add_parser('add-account')
    for k in ('--id', '--name', '--type'):
        a.add_argument(k, required=True)
    for k in ('--institution', '--number', '--use'):
        a.add_argument(k)
    a.set_defaults(f=cmd_add_account)
    a = sub.add_parser('import'); a.add_argument('--dir'); a.add_argument('--dry-run', action='store_true')
    a.add_argument('--skip-unknown', action='store_true'); a.set_defaults(f=cmd_import)
    a = sub.add_parser('suggest-budget'); a.add_argument('--overwrite', action='store_true'); a.set_defaults(f=cmd_suggest_budget)
    a = sub.add_parser('dashboard'); a.add_argument('--out'); a.add_argument('--html', action='store_true'); a.set_defaults(f=cmd_dashboard)
    a = sub.add_parser('status'); a.set_defaults(f=cmd_status)
    args = ap.parse_args()
    args.f(args)


if __name__ == '__main__':
    main()

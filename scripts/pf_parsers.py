"""Statement parsers for the personal-finance skill (nk-work-kit).

Supported:
  * Krung Thai (KTB) deposit-account statements (รายการเดินบัญชี, ออมทรัพย์ / กระแสรายวัน) — PDF
  * Krung Thai home-loan statements (สินเชื่อเพื่อที่อยู่อาศัย) — PDF
  * UOB credit-card e-statements — PDF, one or more cards per statement

Every parser returns its rows plus a control check against the statement's own totals, so an
import never proceeds on a statement that does not add up. The statement type and the account
or card number are read from the document itself, never from the file name.
"""
import datetime as dt
import re
import subprocess

AMT = r'[\d,]+\.\d\d'
MON = {m: i for i, m in enumerate('JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC'.split(), 1)}


def num(s):
    return float(s.replace(',', ''))


class PasswordNeeded(Exception):
    pass


def pdf_text(path, password=None):
    """Text of a PDF in layout mode. Raises PasswordNeeded for a locked file without the right password."""
    cmd = ['pdftotext', '-layout'] + (['-upw', password] if password else []) + [str(path), '-']
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        if 'password' in r.stderr.lower():
            raise PasswordNeeded(str(path))
        raise RuntimeError(f'pdftotext failed on {path}: {r.stderr.strip()}')
    return r.stdout


def detect(text):
    """'ktb-deposit' | 'ktb-loan' | 'uob-card' | None"""
    if 'รายการเดินบัญชี' in text and 'ประเภทบัญชี' in text:
        return 'ktb-loan' if 'สินเชื่อ' in text.split('ประเภทบัญชี', 1)[1][:80] else 'ktb-deposit'
    if 'UOB' in text and 'STATEMENT DATE' in text:
        return 'uob-card'
    return None


def _be_date(d, mo, y):
    """dd/mm/yy in the Buddhist era (69 = 2569 = 2026) -> ISO date."""
    return f'{int(y) + 2500 - 543:04d}-{mo}-{d}'


def _ktb_account(text):
    m = re.search(r'เลขที่บัญชี\s+([\d-]{6,})', text)
    return re.sub(r'\D', '', m[1]) if m else ''


# ---------- Krung Thai deposit accounts ----------
_ktb_row = re.compile(r'^(\d\d)/(\d\d)/(\d\d)\s+(.*?)\s+(' + AMT + r')\s+(' + AMT + r')\s+(\S+)\s*$')
_DEPOSIT_WORDS = ('ดอกเบี้ย', 'iPay', 'เข้า', 'ฝาก', 'เงินเดือน', 'บำนาญ')


def parse_ktb_deposit(text):
    lines = text.splitlines()
    rows, i = [], 0
    while i < len(lines):
        m = _ktb_row.match(lines[i])
        if m:
            d, mo, y, mid, amt, bal, _br = m.groups()
            parts = re.split(r'\s{2,}', mid.strip(), maxsplit=1)
            t, extra = '', ''
            if i + 1 < len(lines):
                n = re.match(r'^(\d\d:\d\d)\s*(.*)$', lines[i + 1])
                if n:
                    t, extra = n.group(1), n.group(2).strip()
                    i += 1
            rows.append(dict(date=_be_date(d, mo, y), time=t, type=parts[0],
                             detail=((parts[1] if len(parts) > 1 else '') + ' ' + extra).strip(),
                             amt=num(amt), bal=num(bal)))
        i += 1
    for k, r in enumerate(rows):
        diff = round(r['bal'] - rows[k - 1]['bal'], 2) if k else None
        if diff is not None and abs(abs(diff) - r['amt']) < 0.005:
            r['amount'] = diff
        else:  # first row, or a row pdftotext printed out of order: sign from the transaction type
            dep = any(w in r['type'] for w in _DEPOSIT_WORDS) or re.search(r'\(BSD|\(IORSD|\(NBSDT|\(MORISD|\(IORISD', r['type'])
            r['amount'] = r['amt'] if dep else -r['amt']
            r['out_of_order'] = k > 0
    out_n = re.search(r'รายการถอนทั้งหมด\s+(\d+)\s+(' + AMT + ')', text)
    in_n = re.search(r'รายการฝากทั้งหมด\s+(\d+)\s+(' + AMT + ')', text)
    w = [r['amount'] for r in rows if r['amount'] < 0]
    dp = [r['amount'] for r in rows if r['amount'] > 0]
    ours = (len(w), round(-sum(w), 2), len(dp), round(sum(dp), 2))
    bank = (int(out_n[1]), num(out_n[2]), int(in_n[1]), num(in_n[2])) if out_n and in_n else None
    # closing balance: last row whose balance reconciles (out-of-order rows carry a shifted balance)
    closing = next((r for r in reversed(rows) if not r.get('out_of_order')), None)
    return rows, dict(ok=bank is not None and ours == bank, ours=ours, bank=bank,
                      account=_ktb_account(text),
                      balance=closing['bal'] if closing else None, balance_date=closing['date'] if closing else None)


# ---------- Krung Thai home loan ----------
_loan_row = re.compile(r'^(\d\d)/(\d\d)/(\d\d)\s+(.*?)\s+' + r'\s+'.join(['(' + AMT + ')'] * 6))


def parse_ktb_loan(text):
    rows = []
    for line in text.splitlines():
        m = _loan_row.match(line)
        if m:
            d, mo, y = m.group(1, 2, 3)
            principal, interest, penalty, fee, total, balance = (num(m.group(i)) for i in range(5, 11))
            rows.append(dict(date=_be_date(d, mo, y), principal=principal, interest=interest,
                             penalty=penalty, fee=fee, total=total, balance=balance))
    rows.sort(key=lambda r: r['date'])
    m = re.search(r'เงินต้นคงเหลือ\s+(' + AMT + ')', text)
    rate = re.search(r'อัตราดอกเบี้ย\s+([\d.]+)', text)
    principal_left = num(m[1]) if m else None
    ok = bool(rows) and principal_left is not None and abs(rows[-1]['balance'] - principal_left) < 0.005
    return rows, dict(ok=ok, account=_ktb_account(text), balance=principal_left,
                      balance_date=rows[-1]['date'] if rows else None,
                      rate=float(rate[1]) / 100 if rate else None)


# ---------- UOB credit card ----------
_uob_row = re.compile(r'^\s*(\d\d) ([A-Z]{3})\s+(\d\d) ([A-Z]{3})\s+(.+?)\s{2,}(?:([A-Z]{3}) (' + AMT + r')\s+)?(' + AMT + r')( CR)?\s*$')
_card_no = re.compile(r"^\s*(\d{4} \d{2}XX XXXX (\d{4}))\s+[A-Z][A-Z .'-]+\s*$")  # card no. + holder name


def parse_uob(text):
    """Returns (rows, check) where check['cards'] lists one summary per card section."""
    sd = re.search(r'STATEMENT DATE\s+(\d\d) ([A-Z]{3}) (\d{4})', text)
    st = dt.date(int(sd[3]), MON[sd[2]], int(sd[1]))
    due = re.search(r'PAYMENT DUE DATE\s+(\d\d) ([A-Z]{3}) (\d{4})', text)
    limit = re.search(r'TOTAL CREDIT LINE\s+([\d,]+)', text)

    def date(dd, mon):
        y = st.year - (1 if MON[mon] > st.month else 0)
        return dt.date(y, MON[mon], int(dd)).isoformat()

    # per-card minimum payment from the summary block: "<card no>   <total>   <minimum>"
    minimum = {}
    for m in re.finditer(r'^\s*\d{4} \d{2}XX XXXX (\d{4})\s+(' + AMT + r')\s+(' + AMT + r')\s*$', text, re.M):
        minimum[m[1]] = num(m[3])

    rows, cards, cur, prev_line = [], [], None, ''
    for line in text.splitlines():
        cm = _card_no.match(line)
        if cm and cur is None and prev_line.strip():
            name = prev_line.strip() if re.fullmatch(r"[A-Z][A-Z0-9 &'-]{2,40}", prev_line.strip()) else ''
            cur = dict(name=name, last4=cm[2], previous=None, total=None, rows=[])
        elif cur is not None:
            if cur['previous'] is None and (m := re.search(r'PREVIOUS BALANCE\s+(' + AMT + ')', line)):
                cur['previous'] = num(m[1])
            elif (m := re.search(r'TOTAL BALANCE - .*?\s+(' + AMT + r')\s*$', line)):
                cur['total'] = num(m[1])
                cards.append(cur)
                cur = None
            elif (m := _uob_row.match(line)):
                pd_, pm, td, tm, desc, ccy, famt, amt, cr = m.groups()
                a = num(amt)
                r = dict(post=date(pd_, pm), date=date(td, tm), desc=re.sub(r'\s{2,}' + AMT + r'$', '', desc.strip()),
                         fx=f'{ccy} {famt}' if ccy else '', amount=a if cr else -a, last4=cur['last4'])
                cur['rows'].append(r)
                rows.append(r)
        if line.strip():
            prev_line = line
    summaries = []
    for c in cards:
        calc = round((c['previous'] or 0) - sum(r['amount'] for r in c['rows']), 2)
        summaries.append(dict(name=c['name'], last4=c['last4'], previous=c['previous'], total=c['total'],
                              calc=calc, n=len(c['rows']), ok=c['total'] is not None and abs(calc - c['total']) < 0.005,
                              minimum=minimum.get(c['last4'])))
    return rows, dict(ok=bool(summaries) and all(s['ok'] for s in summaries), statement=st.isoformat(),
                      due=dt.date(int(due[3]), MON[due[2]], int(due[1])).isoformat() if due else None,
                      limit=num(limit[1]) if limit else None, cards=summaries)

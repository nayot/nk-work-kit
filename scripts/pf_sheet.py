"""Build the blank Personal Finance Google Sheet (personal-finance skill, nk-work-kit).

Every derived number is a formula. Inputs are blue, links to other tabs green, cells the user still
has to fill in have a yellow fill. Nothing personal is written here except the date of birth the
user gives to `pf.py setup`.
"""
import datetime as dt

TABS = ['Net Worth', 'Budget', 'Retirement', 'Transactions', 'Card', 'Advances', 'Tax', 'Mortgage',
        'Investments', 'Rules', 'Accounts', 'Categories', 'Settings']
SID = {t: i for i, t in enumerate(TABS)}

CATEGORIES = [  # name, type, counts in budget
    ('Salary', 'Income', 'Yes'), ('Academic position allowance', 'Income', 'Yes'), ('Pension', 'Income', 'Yes'),
    ('Fees and allowances', 'Income', 'Yes'), ('Rental income', 'Income', 'Yes'),
    ('Investment income', 'Income', 'Yes'), ('Other income', 'Income', 'Yes'),
    ('Mortgage payment', 'Expense', 'Yes'), ('Utilities', 'Expense', 'Yes'), ('Phone and internet', 'Expense', 'Yes'),
    ('Groceries', 'Expense', 'Yes'), ('Food and dining', 'Expense', 'Yes'), ('Transport and fuel', 'Expense', 'Yes'),
    ('Family', 'Expense', 'Yes'), ('Education', 'Expense', 'Yes'), ('Health', 'Expense', 'Yes'),
    ('Insurance', 'Expense', 'Yes'), ('Travel', 'Expense', 'Yes'), ('Shopping', 'Expense', 'Yes'),
    ('Subscriptions', 'Expense', 'Yes'), ('Sport and hobbies', 'Expense', 'Yes'),
    ('Gifts and donations', 'Expense', 'Yes'), ('Bank and card fees', 'Expense', 'Yes'), ('Tax', 'Expense', 'Yes'),
    ('Personal', 'Expense', 'Yes'), ('Unspecified QR/PromptPay', 'Expense', 'Yes'), ('Uncategorised', 'Expense', 'Yes'),
    ('Transfer between own accounts', 'Transfer', 'No'), ('Card payment', 'Transfer', 'No'),
    ('Investment contribution', 'Savings', 'No'), ('Advance paid', 'Advance', 'No'), ('Advance reimbursed', 'Advance', 'No'),
]

# Starter rules: generic BUU / Krung Thai / UOB patterns. Personal ones (mortgage transfer, family,
# regular payees) are added by the user, or by Claude after asking.
RULES = [
    [10, '', '024-BILLERID', '', '-', 'Card payment', 'UOB credit card', ''],
    [11, '', 'PAYMENT THANK YOU', '', '+', 'Card payment', '', ''],
    [21, '', '0994000158441', '', '-', 'Tax', 'Revenue Department', ''],
    [30, '', 'BSD02', '', '+', 'Salary', 'BUU', ''],
    [31, '', 'BSD46', '', '+', 'Pension', "Comptroller General's Department", ''],
    [32, '', 'BUU', '', '+', 'Fees and allowances', 'BUU', ''],
    [36, '', 'ดอกเบี้ย', '', '+', 'Investment income', 'Bank interest', ''],
    [62, '', 'CTRIP|Trip\\.com|AGODA|BOOKING\\.COM|AIRASIA|THAI AIRWAYS|HOTEL|HYATT|XNBSWT|DR TRAVEL|\\[(EUR|USD|JPY|TWD|GBP|SGD) ', '', '-', 'Travel', '', ''],
    [70, '', 'AIA|MUANG THAI LIFE|FWD|ALLIANZ|VIRIYAH|MSIG|DHIPAYA|INSURANCE', '', '-', 'Insurance', '', ''],
    [72, '', 'MEMBERSHIP FEE|ANNUAL FEE|LATE CHARGE|INTEREST CHARGE', '', '-', 'Bank and card fees', '', ''],
    [73, '', 'SHELL|PTT|BANGCHAK|ESSO|CALTEX|K\\.C\\.ENERGY|LAND TRANSP|UBER|BOLT|EXPRESSWAY|EASY PASS', '', '-', 'Transport and fuel', '', ''],
    [74, '', 'AIS|TRUE|DTAC|3BB|NT ', '', '-', 'Phone and internet', '', ''],
    [75, '', 'HOSPIT|CLINIC|PHARMA|BOOTS|WATSONS', '', '-', 'Health', '', ''],
    [76, '', 'APPLE\\.COM|Google|YouTube|Disney|NETFLIX|SPOTIFY|OPENAI|ANTHROPIC|MICROSOFT|ADOBE', '', '-', 'Subscriptions', '', ''],
    [77, '', 'GRAB|LINE MAN|FOODPANDA|AMZ_DD|CAFE|COFFEE|STARBUCKS|RESTAURANT|KFC|MCDONALD|MK |SUKI', '', '-', 'Food and dining', '', ''],
    [78, '', 'TMN|7-11|7-ELEVEN|LOTUS|BIGC|MAKRO|TOPS|FAMILYMART|LAWSON|VILLA', '', '-', 'Groceries', '', ''],
    [79, '', 'SHOPEE|LAZADA|aliexpress|HOMEPRO|IKEA|CENTRAL|ROBINSON|POWER BUY', '', '-', 'Shopping', '', ''],
    [80, '', 'FOUNDATION|มูลนิธิ|TEMPLE|วัด', '', '-', 'Gifts and donations', '', ''],
    [90, '', 'BILLERID|MSISDN|NATID|EWALLETID|PromptPay|พร้อมเพย์|NMPSWP|NBSWP|IORSWT|CGSWP', '', '-', 'Unspecified QR/PromptPay', '', ''],
    [91, '', '\\(BSD|\\(IORSD|\\(NBSDT|\\(MORISD|\\(IORISD|เข้า', '', '+', 'Other income', '', ''],
]

BLUE, GREEN, BLACK = '#0000FF', '#008000', '#000000'
YELLOW, WHITE, HDR_BG = '#FFFF00', '#FFFFFF', '#1F3864'
NUM = {'type': 'NUMBER', 'pattern': '#,##0;(#,##0);"-"'}
NUM2 = {'type': 'NUMBER', 'pattern': '#,##0.00;(#,##0.00);"-"'}
PCT = {'type': 'PERCENT', 'pattern': '0.0%'}
INT = {'type': 'NUMBER', 'pattern': '0'}
DATE = {'type': 'DATE', 'pattern': 'yyyy-mm-dd'}
MONTH = {'type': 'DATE', 'pattern': 'mmm yyyy'}


def rgb(h):
    return {'red': int(h[1:3], 16) / 255, 'green': int(h[3:5], 16) / 255, 'blue': int(h[5:7], 16) / 255}


def col_index(c):
    n = 0
    for ch in c:
        n = n * 26 + ord(ch) - 64
    return n - 1


def grid(tab, a1):
    """A1 range on a tab -> GridRange. 'B2:B' leaves the end row open."""
    import re
    m = re.fullmatch(r'([A-Z]+)(\d+)?(?::([A-Z]+)(\d+)?)?', a1)
    c0, r0, c1, r1 = m[1], m[2], m[3] or m[1], m[4]
    g = {'sheetId': SID[tab], 'startColumnIndex': col_index(c0), 'endColumnIndex': col_index(c1) + 1}
    if r0:
        g['startRowIndex'] = int(r0) - 1
        if r1 or not m[3]:
            g['endRowIndex'] = int(r1 or r0)
    return g


def fmt(tab, a1, **f):
    cell, fields, tf = {}, [], {}
    if 'num' in f:
        cell['numberFormat'] = f['num']; fields.append('userEnteredFormat.numberFormat')
    if 'fg' in f:
        tf['foregroundColor'] = rgb(f['fg'])
    for k, key in (('bold', 'bold'), ('italic', 'italic')):
        if f.get(k):
            tf[key] = True
    if 'size' in f:
        tf['fontSize'] = f['size']
    if 'font' in f:
        tf['fontFamily'] = f['font']
    if tf:
        cell['textFormat'] = tf; fields += [f'userEnteredFormat.textFormat.{k}' for k in tf]
    if 'bg' in f:
        cell['backgroundColor'] = rgb(f['bg']); fields.append('userEnteredFormat.backgroundColor')
    if f.get('wrap'):
        cell['wrapStrategy'] = 'WRAP'; fields.append('userEnteredFormat.wrapStrategy')
    return {'repeatCell': {'range': grid(tab, a1), 'cell': {'userEnteredFormat': cell}, 'fields': ','.join(fields)}}


def header(tab, a1):
    return fmt(tab, a1, bg=HDR_BG, fg=WHITE, bold=True, wrap=True)


def widths(tab, spec):
    out = []
    for cols, px in spec.items():
        a, _, b = cols.partition(':')
        out.append({'updateDimensionProperties': {'range': {'sheetId': SID[tab], 'dimension': 'COLUMNS',
                    'startIndex': col_index(a), 'endIndex': col_index(b or a) + 1},
                    'properties': {'pixelSize': px}, 'fields': 'pixelSize'}})
    return out


def freeze(tab, rows, cols=0):
    return {'updateSheetProperties': {'properties': {'sheetId': SID[tab], 'gridProperties': {'frozenRowCount': rows, 'frozenColumnCount': cols}},
            'fields': 'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}}


def note(tab, a1, text):
    g = grid(tab, a1)
    return {'updateCells': {'rows': [{'values': [{'note': text}]}], 'fields': 'note',
            'start': {'sheetId': g['sheetId'], 'rowIndex': g['startRowIndex'], 'columnIndex': g['startColumnIndex']}}}


def red_if(tab, a1, formula):
    return {'addConditionalFormatRule': {'rule': {'ranges': [grid(tab, a1)], 'booleanRule': {
        'condition': {'type': 'CUSTOM_FORMULA', 'values': [{'userEnteredValue': formula}]},
        'format': {'textFormat': {'foregroundColor': rgb('#C00000')}}}}, 'index': 0}}


def dropdown(tab, a1, values=None, src=None, strict=False):
    cond = {'type': 'ONE_OF_LIST', 'values': [{'userEnteredValue': v} for v in values]} if values else \
           {'type': 'ONE_OF_RANGE', 'values': [{'userEnteredValue': src}]}
    return {'setDataValidation': {'range': grid(tab, a1), 'rule': {'condition': cond, 'showCustomUi': True, 'strict': strict}}}


def build(dob, today=None):
    """Return (values, requests): values = {range: rows} for USER_ENTERED write; requests = batchUpdate."""
    today = today or dt.date.today()
    start_fy = today.year + (1 if today.month >= 10 else 0)
    plan_age = 90
    end_fy = dob.year + plan_age + (1 if (dob.month, dob.day) >= (10, 2) else 0)
    n_years = max(10, end_fy - start_fy + 1)
    t0, t1 = 31, 31 + n_years - 1          # retirement table rows
    V, R = {}, []

    # ---------- Settings ----------
    V['Settings!A1'] = [
        ['Settings and assumptions', None, None],
        ['Blue = input you can change. Yellow fill = still to fill in.', None, None],
        [None, None, None],
        ['Item', 'Value', 'Source / note'],
        ['Date of birth', dob.isoformat(), 'Entered at setup'],
        ['Retirement date', '=IF(B5="","",LET(d,EDATE(B5,720)-1,DATE(YEAR(d)+IF(MONTH(d)>=10,1,0),9,30)))',
         'End of the fiscal year in which you reach 60'],
        ['Months to retirement', '=IF(B6="","",DATEDIF(TODAY(),B6,"M"))', None],
        ['Lifetime pension (บำนาญ, per month)', 0, '0 if you will not receive a government pension'],
        ['Provident fund contribution, you', 0, '% of base salary, e.g. 0.07'],
        ['Provident fund contribution, employer', 0, '% of base salary'],
        ['Inflation (planning)', 0.025, 'Planning assumption'],
        ['Investment return (planning)', 0.04, 'Planning assumption'],
        ['Retirement spending target (today\'s money, per month)', None, 'How much you want to spend each month after retiring'],
        ['Plan to age', plan_age, 'Planning assumption'],
        ['Annuity insurance payout (per year)', 0, 'From your annuity policy (ประกันบำนาญ), 0 if none'],
        ['Annuity first payout date', None, 'From your annuity policy'],
        ['Annuity payouts end at age', 85, 'From your annuity policy'],
        ['Annuity premium (per year)', 0, 'From your annuity policy'],
        ['Price year for today\'s money', today.year, 'Year the spending target is expressed in'],
    ]
    R += [fmt('Settings', 'A1:C25', font='Arial'), fmt('Settings', 'A1', bold=True, size=14), fmt('Settings', 'A2', italic=True),
          header('Settings', 'A4:C4'), fmt('Settings', 'B5:B19', fg=BLUE, num=NUM),
          fmt('Settings', 'B5:B6', num=DATE), fmt('Settings', 'B16', num=DATE), fmt('Settings', 'B6:B7', fg=BLACK),
          fmt('Settings', 'B7', num=INT), fmt('Settings', 'B9:B12', num=PCT), fmt('Settings', 'B14', num=INT),
          fmt('Settings', 'B17', num=INT), fmt('Settings', 'B19', num=INT),
          fmt('Settings', 'B13', bg=YELLOW), fmt('Settings', 'B8:B10', bg=YELLOW),
          freeze('Settings', 4)] + widths('Settings', {'A': 340, 'B': 120, 'C': 380})

    # ---------- Accounts ----------
    V['Accounts!A1'] = [['Account ID', 'Name', 'Institution', 'Type', 'Account number', 'Use', 'Status', 'Latest balance (฿)', 'Balance date']]
    R += [fmt('Accounts', 'A1:I200', font='Arial'), header('Accounts', 'A1:I1'), fmt('Accounts', 'E2:E', num={'type': 'TEXT'}),
          fmt('Accounts', 'H2:H', num=NUM2), fmt('Accounts', 'I2:I', num=DATE), freeze('Accounts', 1),
          dropdown('Accounts', 'D2:D200', ['Bank', 'Credit card', 'Loan', 'Fund', 'Provident fund', 'Insurance', 'Other']),
          note('Accounts', 'E1', 'Account number as printed on the statement (for a credit card, the last 4 digits). The importer matches statements to accounts by the last 4 digits. Latest balance and date are filled in by the importer.')
          ] + widths('Accounts', {'A': 110, 'B': 200, 'C': 120, 'D': 110, 'E': 130, 'F': 220, 'G': 90, 'H': 130, 'I': 100})

    # ---------- Categories ----------
    V['Categories!A1'] = [['Category', 'Type', 'Counts in budget']] + [list(c) for c in CATEGORIES]
    R += [fmt('Categories', 'A1:C100', font='Arial'), header('Categories', 'A1:C1'), freeze('Categories', 1),
          dropdown('Categories', 'B2:B100', ['Income', 'Expense', 'Transfer', 'Savings', 'Advance'])
          ] + widths('Categories', {'A': 240, 'B': 100, 'C': 130})

    # ---------- Rules ----------
    # leading apostrophe keeps "+", "-" and digit-only patterns as text (otherwise Sheets parses them)
    V['Rules!A1'] = [['Priority', 'Account', 'Pattern (regex)', 'Amount', 'Sign', 'Category', 'Counterparty', 'Advance ID']] + \
        [[r[0], r[1], "'" + r[2], r[3], ("'" + r[4]) if r[4] else '', r[5], r[6], r[7]] for r in RULES]
    R += [fmt('Rules', 'A1:H300', font='Arial'), header('Rules', 'A1:H1'), freeze('Rules', 1),
          dropdown('Rules', 'F2:F300', src='=Categories!$A$2:$A$100'),
          note('Rules', 'A1', 'Rules run in Priority order and the first match wins. Account blank = any account. Sign "-" = money out, "+" = money in, blank = either. Amount blank = any amount. Pattern is a regular expression matched against the transaction description. Transfers between your own accounts (numbers on the Accounts tab) are detected automatically before these rules.')
          ] + widths('Rules', {'C': 460, 'F:G': 210})

    # ---------- Transactions ----------
    V['Transactions!A1'] = [['Txn ID', 'Date', 'Account', 'Description', 'Amount (฿)', 'Category', 'Counterparty', 'Advance ID',
                             'Source document', 'Slip', 'Reconciled', 'Type', 'Month'],
                            [None] * 11 + ['=ARRAYFORMULA(IF(LEN(F2:F),IFERROR(VLOOKUP(F2:F,Categories!A:B,2,FALSE),"Unknown"),))',
                                           '=ARRAYFORMULA(IF(LEN(B2:B),EOMONTH(B2:B,-1)+1,))']]
    R += [fmt('Transactions', 'A1:M1000', font='Arial'), header('Transactions', 'A1:M1'), fmt('Transactions', 'B2:B', num=DATE),
          fmt('Transactions', 'E2:E', num=NUM2), fmt('Transactions', 'M2:M', num={'type': 'DATE', 'pattern': 'yyyy-mm'}),
          freeze('Transactions', 1), dropdown('Transactions', 'F2:F', src='=Categories!$A$2:$A$100'),
          dropdown('Transactions', 'C2:C', src='=Accounts!$A$2:$A$200')
          ] + widths('Transactions', {'A': 150, 'B': 95, 'C': 100, 'D': 360, 'E': 110, 'F:G': 200, 'H': 90, 'I': 240, 'J': 120, 'K': 90, 'L': 90, 'M': 80})

    # ---------- Card ----------
    V['Card!A1'] = [['Card', 'Statement date', 'Due date', 'Credit limit (฿)', 'Total balance (฿)', 'Minimum payment (฿)',
                     'Paid by due date (฿)', 'Paid in full', 'Utilisation', 'Statement file']]
    R += [fmt('Card', 'A1:J500', font='Arial'), header('Card', 'A1:J1'), fmt('Card', 'B2:C', num=DATE), fmt('Card', 'D2:G', num=NUM2),
          fmt('Card', 'I2:I', num=PCT), freeze('Card', 1),
          note('Card', 'A1', 'Filled in by the importer from each credit-card statement. "Paid by due date" adds up the card-payment credits on the card between the statement date and the due date (plus 3 days for posting).')
          ] + widths('Card', {'A': 100, 'B:I': 115, 'J': 240})

    # ---------- Advances ----------
    V['Advances!A1'] = [['Advance ID', 'Description', 'Project or trip', 'Date paid', 'Amount (฿)', 'Evidence', 'Memo / doc no.',
                         'Claim submitted', 'Status', 'Reimbursed date', 'Reimbursed (฿)', 'Outstanding (฿)', 'Days outstanding'],
                        [None] * 11 + ['=ARRAYFORMULA(IF(LEN(A2:A),IF(E2:E="","",E2:E-IF(K2:K="",0,K2:K)),))',
                                       '=ARRAYFORMULA(IF(LEN(A2:A),IF((D2:D="")+(I2:I="Reimbursed"),"",TODAY()-D2:D),))']]
    R += [fmt('Advances', 'A1:M500', font='Arial'), header('Advances', 'A1:M1'), fmt('Advances', 'D2:D', num=DATE),
          fmt('Advances', 'H2:H', num=DATE), fmt('Advances', 'J2:J', num=DATE), fmt('Advances', 'E2:E', num=NUM2),
          fmt('Advances', 'K2:L', num=NUM2), fmt('Advances', 'M2:M', num=INT), freeze('Advances', 1),
          dropdown('Advances', 'I2:I500', ['Estimate', 'Paid', 'Claimed', 'Approved', 'Reimbursed'], strict=True),
          note('Advances', 'A1', 'Money you paid on behalf of the university (เงินทดรองจ่าย) or that is otherwise owed back to you, e.g. the child education allowance (ค่าเล่าเรียนบุตร). Link the transaction with the same Advance ID in Transactions.')
          ] + widths('Advances', {'A': 90, 'B': 280, 'C': 160, 'D:E': 105, 'F': 200, 'G': 130, 'H:M': 110})

    # ---------- Investments ----------
    V['Investments!A1'] = [['Date', 'Account ID', 'Value (฿)', 'Source']]
    R += [fmt('Investments', 'A1:D500', font='Arial'), header('Investments', 'A1:D1'), fmt('Investments', 'A2:A', num=DATE),
          fmt('Investments', 'C2:C', num=NUM2), freeze('Investments', 1),
          dropdown('Investments', 'B2:B', src='=Accounts!$A$2:$A$200'),
          note('Investments', 'A1', 'A snapshot of each fund, provident fund or investment, all with the same date. Add a new set of rows each month or quarter; the latest date is used.')
          ] + widths('Investments', {'A': 100, 'B': 120, 'C': 130, 'D': 260})

    # ---------- Mortgage ----------
    mort = [
        ['Mortgage inputs', None, None, None, 'Projection', None, None, 'Loan statement entries', None, None, None, None],
        ['Balance (฿)', 0, 'Updated by the importer from the loan statement', None, 'Projected payoff month',
         '=IF($B$2<=0,"",IFERROR(INDEX(A10:A129,MATCH(TRUE,INDEX(F10:F129<0.01,0),0)),"After "&TEXT(A129,"mmm yyyy")))',
         None, 'Date', 'Principal (฿)', 'Interest (฿)', 'Total (฿)', 'Balance after (฿)'],
        ['Interest rate (annual)', 0, 'Updated by the importer', None, 'Payments to payoff',
         '=IF($B$2<=0,"",IFERROR(MATCH(TRUE,INDEX(F10:F129<0.01,0),0),">120"))'],
        ['Monthly payment (฿)', 0, 'Your regular payment', None, 'Total interest to payoff (฿)', '=SUM(C10:C129)'],
        ['Extra principal per month (฿)', 0, 'Scenario input', None, 'Interest paid this calendar year (฿)',
         '=SUMIFS(J:J,H:H,">="&DATE(YEAR(TODAY()),1,1),H:H,"<"&DATE(YEAR(TODAY())+1,1,1))'],
        ['First payment month', (today.replace(day=1) + dt.timedelta(days=32)).replace(day=1).isoformat(), 'Next payment', None, None, None],
        [None] * 6,
        ['Projection only. Banks charge interest daily, so actual figures differ slightly.', None, None, None, None, None],
        ['Month', 'Opening balance (฿)', 'Interest (฿)', 'Payment (฿)', 'Principal (฿)', 'Closing balance (฿)'],
    ]
    mort = [r + [None] * (12 - len(r)) for r in mort]
    for i in range(120):
        r = 10 + i
        mort.append(['=$B$6' if i == 0 else f'=EDATE(A{r - 1},1)', '=$B$2' if i == 0 else f'=F{r - 1}',
                     f'=ROUND(B{r}*$B$3/12,2)', f'=MIN($B$4+$B$5,B{r}+C{r})', f'=D{r}-C{r}', f'=B{r}-E{r}'] + [None] * 6)
    V['Mortgage!A1'] = mort
    R += [fmt('Mortgage', 'A1:L130', font='Arial'), fmt('Mortgage', 'A1', bold=True), fmt('Mortgage', 'E1', bold=True),
          fmt('Mortgage', 'H1', bold=True), header('Mortgage', 'H2:L2'),
          fmt('Mortgage', 'B2:B5', fg=BLUE, num=NUM), fmt('Mortgage', 'B3', num={'type': 'PERCENT', 'pattern': '0.00%'}),
          fmt('Mortgage', 'B6', fg=BLUE, num=DATE), fmt('Mortgage', 'B4', bg=YELLOW),
          fmt('Mortgage', 'F2', num=MONTH, bold=True), fmt('Mortgage', 'F4:F5', num=NUM), fmt('Mortgage', 'A8', italic=True),
          header('Mortgage', 'A9:F9'), fmt('Mortgage', 'A10:A129', num=MONTH), fmt('Mortgage', 'B10:F129', num=NUM2),
          fmt('Mortgage', 'H3:H', num=DATE), fmt('Mortgage', 'I3:L', num=NUM2), freeze('Mortgage', 9),
          ] + widths('Mortgage', {'A': 220, 'B': 130, 'C': 280, 'D': 110, 'E': 230, 'F': 130, 'G': 20, 'H': 100, 'I:L': 120})

    # ---------- Tax ----------
    y = today.year - 1
    V['Tax!A1'] = [
        ['Personal income tax (ภ.ง.ด.90/91)', None, None],
        ['Copy the figures from your filed return. Blue = figures from the return.', None, None],
        ['Item (฿)', f"'{y}", 'Note'],
        ['Income after expense deductions', None, 'Return, page with the tax calculation, line 1'],
        ['Personal allowance', None, None], ['Spouse and children', None, None], ['Life and health insurance premiums', None, None],
        ['Annuity insurance premium', None, None], ['Provident fund contributions', None, None], ['RMF / SSF / ThaiESG', None, None],
        ['Mortgage interest', None, None], ['Social security', None, None], ['Other allowances', None, None],
        ['Total allowances', '=SUM(B5:B13)', None], ['Donations', None, None],
        ['Net taxable income', '=B4-B14-B15', None], ['Tax due', None, 'From the return'],
        ['Tax withheld by payers', None, 'From the return'], ['Additional tax (refund if negative)', '=B17-B18', None],
        ['Effective tax rate on income', '=IF(N(B4)=0,0,B17/B4)', None],
    ]
    R += [fmt('Tax', 'A1:D40', font='Arial'), fmt('Tax', 'A1', bold=True, size=14), fmt('Tax', 'A2', italic=True),
          header('Tax', 'A3:C3'), fmt('Tax', 'B4:B19', num=NUM2, fg=BLUE), fmt('Tax', 'B14', fg=BLACK, bold=True),
          fmt('Tax', 'B16', fg=BLACK, bold=True), fmt('Tax', 'B19', fg=BLACK, bold=True), fmt('Tax', 'B20', num=PCT),
          freeze('Tax', 3)] + widths('Tax', {'A': 300, 'B': 130, 'C': 320})

    # ---------- Net Worth ----------
    V["'Net Worth'!A1"] = [
        ['Net worth', None, None], ['Updated automatically from statements and the Investments and Advances tabs.', None, None], [None] * 3,
        ['Item', 'Amount (฿)', 'Source'],
        ['Bank accounts (latest statements)', '=SUMIFS(Accounts!H:H,Accounts!D:D,"Bank")', 'Accounts tab'],
        ['Investments (latest values)', '=IFERROR(SUMIFS(Investments!C:C,Investments!A:A,MAX(Investments!A:A)),0)', 'Investments tab'],
        ['Advances owed to you', '=SUM(Advances!L2:L)', 'Advances tab'],
        ['Credit cards (latest statements)', '=-SUMIFS(Accounts!H:H,Accounts!D:D,"Credit card")', 'Accounts tab'],
        ['Loans', '=-SUMIFS(Accounts!H:H,Accounts!D:D,"Loan")', 'Accounts tab'],
        [None] * 3, ['Net worth', '=SUM(B5:B9)', None],
        ['Pensions and annuities pay income rather than hold a balance, so they are not counted here.', None, None],
    ]
    R += [fmt('Net Worth', 'A1:C20', font='Arial'), fmt('Net Worth', 'A1', bold=True, size=14), fmt('Net Worth', 'A2', italic=True),
          header('Net Worth', 'A4:C4'), fmt('Net Worth', 'B5:B11', num=NUM2, fg=GREEN), fmt('Net Worth', 'A11:B11', bold=True),
          fmt('Net Worth', 'B11', fg=BLACK), fmt('Net Worth', 'A12', italic=True)] + widths('Net Worth', {'A': 300, 'B': 140, 'C': 200})

    # ---------- Budget ----------
    cats = [c for c, t, b in CATEGORIES if t == 'Expense' and b == 'Yes']
    first, last = 7, 7 + len(cats) - 1
    t = last + 1
    months = 'EFGHIJKLMNOP'
    bud = [['Monthly budget'] + [None] * 15,
           ['Blue = budget you set (run "suggest budget" to fill it from your averages). Actuals come from Transactions.'] + [None] * 15,
           ['First month shown', f'{today.year}-01-01'] + [None] * 14,
           ['Complete month', None, None, None] + [f'={c}6<DATE(YEAR(TODAY()),MONTH(TODAY()),1)' for c in months],
           [None] * 16,
           ['Category', 'Budget (฿/month)', 'Average actual', 'Under (over) budget'] + ['=$B$3' if c == 'E' else f'=EDATE({chr(ord(c) - 1)}6,1)' for c in months]]
    for i, c in enumerate(cats):
        r = first + i
        bud.append([c, 0, f'=IFERROR(AVERAGEIFS(E{r}:P{r},$E$4:$P$4,TRUE),0)', f'=B{r}-C{r}'] +
                   [f'=-SUMIFS(Transactions!$E:$E,Transactions!$F:$F,$A{r},Transactions!$M:$M,{m}$6)' for m in months])
    bud.append(['Total spending', f'=SUM(B{first}:B{last})', f'=SUM(C{first}:C{last})', f'=B{t}-C{t}'] + [f'=SUM({m}{first}:{m}{last})' for m in months])
    bud.append(['Income', None, f'=IFERROR(AVERAGEIFS(E{t + 1}:P{t + 1},$E$4:$P$4,TRUE),0)', None] +
               [f'=SUMIFS(Transactions!$E:$E,Transactions!$L:$L,"Income",Transactions!$M:$M,{m}$6)' for m in months])
    bud.append(['Net (income less spending)', None, f'=C{t + 1}-C{t}', None] + [f'={m}{t + 1}-{m}{t}' for m in months])
    V['Budget!A1'] = bud
    R += [fmt('Budget', 'A1:P60', font='Arial'), fmt('Budget', 'A1', bold=True, size=14), fmt('Budget', 'A2', italic=True),
          fmt('Budget', 'A3', bold=True), fmt('Budget', 'B3', fg=BLUE, num=MONTH), fmt('Budget', 'A4:P4', italic=True, fg='#808080'),
          header('Budget', 'A6:P6'), fmt('Budget', 'E6:P6', num=MONTH), fmt('Budget', f'B{first}:P{t + 2}', num=NUM),
          fmt('Budget', f'B{first}:B{last}', fg=BLUE), fmt('Budget', f'A{t}:P{t}', bold=True), fmt('Budget', f'A{t + 2}:P{t + 2}', bold=True),
          red_if('Budget', f'D{first}:D{t}', f'=D{first}<0'), red_if('Budget', f'E{t + 2}:P{t + 2}', f'=E{t + 2}<0'),
          freeze('Budget', 6, 1)] + widths('Budget', {'A': 230, 'B:D': 120, 'E:P': 95})

    # ---------- Retirement ----------
    ret = [
        ['Retirement projection', None, None, None, 'Summary', None],
        ['Blue = input you can change. Green = linked from another tab. Yellow = still to fill in. Baht, fiscal years (Oct to Sep).', None, None, None, None, None],
        [None] * 6,
        ['Assumption', 'Value', 'Source', None, 'Item', 'Value'],
        ['Spending target (today\'s money, per month)', '=N(Settings!B13)', 'Settings', None, 'Projected assets at retirement',
         f'=IFERROR(INDEX($M${t0}:$M${t1},MATCH($B$25-1,$A${t0}:$A${t1},0)),0)'],
        ['Inflation', '=Settings!B11', 'Settings', None, 'Needed at retirement', f'=IFERROR(INDEX($N${t0}:$N${t1},MATCH($B$25-1,$A${t0}:$A${t1},0)),0)'],
        ['Investment return', '=Settings!B12', 'Settings', None, 'Surplus (gap) at retirement', '=F5-F6'],
        ['Lifetime pension (per month)', '=N(Settings!B8)', 'Settings', None, 'Extra saving per month to close the gap',
         '=IF(F7>=0,0,PMT($B$7/12,MAX(1,N(Settings!B7)),0,F7))'],
        ['Pension raise per year', 0, 'Planning assumption', None, 'Assets last until age',
         f'=IFERROR(INDEX($B${t0}:$B${t1},MATCH(TRUE,INDEX($M${t0}:$M${t1}<0,0),0)),"Beyond "&MAX($B${t0}:$B${t1}))'],
        ['Annuity payout (per year)', '=N(Settings!B15)', 'Settings', None, None, None],
        ['Annuity payouts end at age', '=Settings!B17', 'Settings', None, None, None],
        ['Annuity first payout (fiscal year)', '=IF(Settings!B16="",0,YEAR(Settings!B16)+IF(MONTH(Settings!B16)>=10,1,0))', 'Settings', None, None, None],
        ['Investments now (funds, provident fund)', "='Net Worth'!B6", 'Net Worth tab', None, None, None],
        ['Bank savings counted toward retirement', "=MAX(0,'Net Worth'!B5-B15)", 'Bank balances less the emergency reserve', None, None, None],
        ['Emergency reserve kept aside', 0, 'About 6 months of spending', None, None, None],
        ['Provident fund contributions, you + employer (per month)', 0, 'From your payslip', None, None, None],
        ['RMF / ThaiESG purchases (per year)', 0, 'Scenario input', None, None, None],
        ['Other savings while working (per month)', 0, 'Scenario input', None, None, None],
        ['Redirect mortgage payment after payoff', 'Yes', 'Scenario input (Yes or No)', None, None, None],
        ['Other income after retirement, e.g. consulting (per month)', 0, 'Scenario input', None, None, None],
        ['Years of that income after retirement', 0, 'Scenario input', None, None, None],
        ['Child education cost, your share (per year, today\'s money)', 0, 'Planning input', None, None, None],
        ['Education first fiscal year', 0, 'Planning input', None, None, None],
        ['Education years', 0, 'Planning input', None, None, None],
        ['First retired fiscal year', '=IF(Settings!B6="",0,YEAR(Settings!B6)+1)', 'Retire on 30 Sep', None, None, None],
        ['Price year for today\'s money', '=Settings!B19', 'Settings', None, None, None],
        ['Mortgage paid off in fiscal year', '=IFERROR(YEAR(Mortgage!F2)+IF(MONTH(Mortgage!F2)>=10,1,0),0)', 'Mortgage tab', None, None, None],
        ['Projection starts (fiscal year)', start_fy, None, None, None, None],
        [None] * 6,
        ['Fiscal year', 'Age (Sep)', 'Phase', 'Opening assets', 'Contributions', 'Spending need', 'Pension', 'Annuity',
         'Other income', 'Education', 'Net withdrawal', 'Investment return', 'Closing assets', 'Needed at year end'],
    ]
    ret = [r + [None] * (14 - len(r)) for r in ret]
    for i in range(n_years):
        r = t0 + i
        ret.append([
            '=$B$28' if i == 0 else f'=A{r - 1}+1',
            f'=A{r}-YEAR(Settings!$B$5)',
            f'=IF(A{r}<$B$25,"Working","Retired")',
            '=$B$13+$B$14' if i == 0 else f'=M{r - 1}',
            f'=IF(C{r}="Working",12*$B$16+$B$17+12*$B$18+IF(AND($B$19="Yes",$B$27>0,A{r}>$B$27),12*Mortgage!$B$4,0),0)',
            f'=IF(C{r}="Retired",12*$B$5*(1+$B$6)^(A{r}-$B$26),0)',
            f'=IF(C{r}="Retired",12*$B$8*(1+$B$9)^(A{r}-$B$26),0)',
            f'=IF(AND($B$12>0,A{r}>=$B$12,B{r}<=$B$11),$B$10,0)',
            f'=IF(AND(C{r}="Retired",A{r}<$B$25+$B$21),12*$B$20,0)',
            f'=IF(AND($B$23>0,A{r}>=$B$23,A{r}<$B$23+$B$24),$B$22*(1+$B$6)^(A{r}-$B$26),0)',
            f'=F{r}+J{r}-G{r}-H{r}-I{r}',
            f'=D{r}*$B$7',
            f'=D{r}+L{r}+E{r}-K{r}',
            '=0' if i == n_years - 1 else f'=MAX(0,(K{r + 1}+N{r + 1})/(1+$B$7))',
        ])
    V['Retirement!A1'] = ret
    src = lambda c: {'sourceRange': {'sources': [{'sheetId': SID['Retirement'], 'startRowIndex': t0 - 2, 'endRowIndex': t1,
                                                  'startColumnIndex': c, 'endColumnIndex': c + 1}]}}
    R += [fmt('Retirement', f'A1:N{t1}', font='Arial'), fmt('Retirement', 'A1', bold=True, size=14), fmt('Retirement', 'A2', italic=True),
          header('Retirement', 'A4:C4'), header('Retirement', 'E4:F4'), header('Retirement', f'A{t0 - 1}:N{t0 - 1}'),
          fmt('Retirement', 'B5:B28', num=NUM, fg=BLUE), fmt('Retirement', 'B5:B8', fg=GREEN), fmt('Retirement', 'B10:B13', fg=GREEN),
          fmt('Retirement', 'B14', fg=BLACK), fmt('Retirement', 'B25:B27', fg=GREEN), fmt('Retirement', 'B25', fg=BLACK),
          fmt('Retirement', 'B6:B7', num=PCT), fmt('Retirement', 'B9', num=PCT),
          fmt('Retirement', 'B11:B12', num=INT), fmt('Retirement', 'B21', num=INT), fmt('Retirement', 'B23:B28', num=INT),
          fmt('Retirement', 'B15:B16', bg=YELLOW), fmt('Retirement', 'B22', bg=YELLOW),
          fmt('Retirement', 'F5:F8', num=NUM, bold=True), fmt('Retirement', 'F9', bold=True),
          fmt('Retirement', f'A{t0}:B{t1}', num=INT), fmt('Retirement', f'D{t0}:N{t1}', num=NUM),
          red_if('Retirement', f'M{t0}:M{t1}', f'=M{t0}<0'), red_if('Retirement', 'F7', '=F7<0'),
          dropdown('Retirement', 'B19', ['Yes', 'No'], strict=True),
          note('Retirement', f'N{t0 - 1}', 'Needed at year end: the assets required at that point to pay every later net withdrawal up to the plan age, at the investment return. On track when Closing assets is at or above this line at retirement.'),
          {'addChart': {'chart': {'spec': {'title': 'Projected assets vs assets needed',
              'basicChart': {'chartType': 'LINE', 'legendPosition': 'TOP_LEGEND', 'headerCount': 1,
                  'axis': [{'position': 'BOTTOM_AXIS', 'title': 'Fiscal year'}, {'position': 'LEFT_AXIS', 'title': 'Baht'}],
                  'domains': [{'domain': src(0)}],
                  'series': [{'series': src(12), 'targetAxis': 'LEFT_AXIS', 'color': rgb('#2a78d6'), 'lineStyle': {'width': 2}},
                             {'series': src(13), 'targetAxis': 'LEFT_AXIS', 'color': rgb('#52514e'), 'lineStyle': {'width': 2, 'type': 'MEDIUM_DASHED'}}]}},
              'position': {'overlayPosition': {'anchorCell': {'sheetId': SID['Retirement'], 'rowIndex': 10, 'columnIndex': 4},
                                               'widthPixels': 720, 'heightPixels': 360}}}}},
          ] + widths('Retirement', {'A': 360, 'B': 110, 'C': 280, 'D': 105, 'E': 260, 'F': 120, 'G:N': 105})
    return V, R

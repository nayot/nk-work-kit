"""Render the personal-finance dashboard (Markdown with inline SVG charts; optional HTML).

Totals only: no account numbers, no transaction descriptions. Called by `pf.py dashboard`.
Chart colours are validated categorical steps for light and dark themes (dataviz palette).
"""
import datetime as dt, pathlib, re, collections, os

MONTHS = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()
INC, SPD = ('#2a78d6', '#3987e5'), ('#eb6834', '#d95926')   # validated light/dark steps
# pie: categorical slots 1-7 + neutral gray "Other" between slot 7 and slot 1 (keeps violet off blue);
# validated as a ring in both modes (gray fails only the chroma floor, by design)
PIE = [('#2a78d6', '#3987e5'), ('#eb6834', '#d95926'), ('#1baf7a', '#199e70'), ('#eda100', '#c98500'),
       ('#e87ba4', '#d55181'), ('#008300', '#008300'), ('#4a3aa7', '#9085e9'), ('#8f8e89', '#6e6d68')]
NEED = ('#52514e', '#c3c2b7')                                  # goal line: secondary text ink, dashed

def baht(x, dec=0):
    s = f'{abs(x):,.{dec}f}'
    return f'฿{s}' if x >= 0 else f'−฿{s}'

def fill(light_dark):
    l, d = light_dark
    return f'fill:{l};fill:light-dark({l},{d})'

def col(x0, y0, w, h, r=4):
    """Column anchored on the baseline with rounded data-end (top)."""
    r = min(r, h, w / 2)
    if h <= 0: return ''
    return (f'M{x0:.1f},{y0:.1f}V{y0 - h + r:.1f}Q{x0:.1f},{y0 - h:.1f} {x0 + r:.1f},{y0 - h:.1f}'
            f'H{x0 + w - r:.1f}Q{x0 + w:.1f},{y0 - h:.1f} {x0 + w:.1f},{y0 - h + r:.1f}V{y0:.1f}Z')

def cashflow_svg(months):
    """months: list of (label, income, spending). Grouped columns, one axis, hover titles."""
    W, H, L, R, T, B = 640, 250, 52, 8, 34, 26
    top = max(max(i, s) for _, i, s in months)
    step = 50000 if top <= 300000 else 100000
    ymax = step * (int(top // step) + 1)
    pw, ph = W - L - R, H - T - B
    y = lambda v: T + ph - v / ymax * ph
    txt = 'fill:var(--text-muted,#6b6b6b);font-size:11px;font-family:var(--font-interface,sans-serif)'
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Monthly income and spending" xmlns="http://www.w3.org/2000/svg">']
    for v in range(0, ymax + 1, step):
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" style="stroke:var(--background-modifier-border,#ddd);stroke-width:1"/>')
        out.append(f'<text x="{L - 6}" y="{y(v) + 4:.1f}" text-anchor="end" style="{txt}">{f"{v // 1000:,}k" if v else "0"}</text>')
    slot = pw / len(months); bw = min(22, (slot - 10) / 2)
    for k, (lab, inc, spd) in enumerate(months):
        cx = L + slot * k + slot / 2
        for j, (v, c, name) in enumerate(((inc, INC, 'Income'), (spd, SPD, 'Spending'))):
            x0 = cx - bw - 1 + j * (bw + 2)          # 2px gap between the pair
            out.append(f'<path d="{col(x0, y(0), bw, y(0) - y(v))}" style="{fill(c)}"><title>{lab}: {name} {baht(v)}</title></path>')
            out.append(f'<rect x="{x0 - 1:.1f}" y="{T}" width="{bw + 2:.1f}" height="{ph}" style="fill:transparent"><title>{lab}: {name} {baht(v)}</title></rect>')
        out.append(f'<text x="{cx:.1f}" y="{H - 8}" text-anchor="middle" style="{txt}">{lab.split()[0]}</text>')
    lx = L
    for c, name in ((INC, 'Income'), (SPD, 'Spending')):
        out.append(f'<rect x="{lx}" y="8" width="10" height="10" rx="2" style="{fill(c)}"/>'
                   f'<text x="{lx + 15}" y="17" style="{txt};fill:var(--text-normal,#222)">{name}</text>')
        lx += 90
    out.append('</svg>')
    return ''.join(out)

import math

def pie_svg(items):
    """items: [(label, value)], already folded to <= 8 with 'Other' last (gray)."""
    W, H, cx, cy, r = 640, 270, 130, 135, 115
    total = sum(v for _, v in items) or 1
    txt = 'font-family:var(--font-interface,sans-serif);font-size:12px'
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Spending by category" xmlns="http://www.w3.org/2000/svg">']
    a0 = -math.pi / 2
    for k, (lab, v) in enumerate(items):
        a1 = a0 + 2 * math.pi * v / total
        large = 1 if a1 - a0 > math.pi else 0
        x0, y0, x1, y1 = cx + r * math.cos(a0), cy + r * math.sin(a0), cx + r * math.cos(a1), cy + r * math.sin(a1)
        d = f'M{cx},{cy}L{x0:.2f},{y0:.2f}A{r},{r} 0 {large} 1 {x1:.2f},{y1:.2f}Z'
        c = PIE[-1] if lab == 'Other' else PIE[k]
        out.append(f'<path d="{d}" style="{fill(c)};stroke:var(--background-primary,#fff);stroke-width:2;stroke-linejoin:round">'
                   f'<title>{lab}: {baht(v)} ({v / total:.0%})</title></path>')
        a0 = a1
    for k, (lab, v) in enumerate(items):           # legend doubles as the direct label
        y = 30 + k * 30
        c = PIE[-1] if lab == 'Other' else PIE[k]
        out.append(f'<rect x="290" y="{y - 10}" width="12" height="12" rx="2" style="{fill(c)}"/>'
                   f'<text x="310" y="{y}" style="{txt};fill:var(--text-normal,#222)">{lab}</text>'
                   f'<text x="{W - 10}" y="{y}" text-anchor="end" style="{txt};fill:var(--text-muted,#6b6b6b)">{baht(v)} · {v / total:.0%}</text>')
    out.append('</svg>')
    return ''.join(out)

def projection_svg(rows, retire_fy):
    """rows: [(fy, age, projected, needed)]. One axis, two lines; dashed = goal.
    The projected line stops where the money runs out (a negative balance would read as debt)."""
    W, H, L, R_, T, B = 640, 290, 52, 70, 30, 40
    hi = max(max(p, n) for _, _, p, n in rows); step = 2_000_000
    hi = step * math.ceil(hi / step); lo = 0
    x = lambda fy: L + (fy - rows[0][0]) / (rows[-1][0] - rows[0][0]) * (W - L - R_)
    y = lambda v: T + (hi - v) / (hi - lo) * (H - T - B)
    txt = 'fill:var(--text-muted,#6b6b6b);font-size:11px;font-family:var(--font-interface,sans-serif)'
    ink = 'fill:var(--text-normal,#222)'
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Projected assets against assets needed" xmlns="http://www.w3.org/2000/svg">']
    for v in range(lo, int(hi) + 1, step):
        sw = 'stroke:var(--text-faint,#999)' if v == 0 else 'stroke:var(--background-modifier-border,#ddd)'
        out.append(f'<line x1="{L}" x2="{W - R_}" y1="{y(v):.1f}" y2="{y(v):.1f}" style="{sw};stroke-width:1"/>'
                   f'<text x="{L - 6}" y="{y(v) + 4:.1f}" text-anchor="end" style="{txt}">{f"{v / 1e6:,.0f}M" if v else "0"}</text>')
    for fy, age, _, _ in rows:
        if age % 5 == 0:
            out.append(f'<text x="{x(fy):.1f}" y="{H - 22}" text-anchor="middle" style="{txt}">{fy}</text>'
                       f'<text x="{x(fy):.1f}" y="{H - 8}" text-anchor="middle" style="{txt}">age {age}</text>')
    xr = x(retire_fy)
    out.append(f'<line x1="{xr:.1f}" x2="{xr:.1f}" y1="{T}" y2="{H - B}" style="stroke:var(--text-faint,#999);stroke-width:1;stroke-dasharray:3 3"/>'
               f'<text x="{xr - 4:.1f}" y="{H - B - 6}" text-anchor="end" style="{txt}">Retire</text>')
    need = ' '.join(f'{x(r[0]):.1f},{y(r[3]):.1f}' for r in rows)
    out.append(f'<polyline points="{need}" style="fill:none;stroke:{NEED[0]};stroke:light-dark({NEED[0]},{NEED[1]});stroke-width:2;stroke-dasharray:6 4;stroke-linejoin:round"/>')
    pts, out_at = [], None
    for k, (fy, age, p, _) in enumerate(rows):
        if p >= 0: pts.append((x(fy), y(p))); continue
        fy0, p0 = rows[k - 1][0], rows[k - 1][2]          # interpolate the zero crossing
        out_at = (fy0 + p0 / (p0 - p), rows[k - 1][1] + p0 / (p0 - p)); pts.append((x(out_at[0]), y(0))); break
    out.append(f'<polyline points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}" style="fill:none;stroke:{INC[0]};stroke:light-dark({INC[0]},{INC[1]});stroke-width:2;stroke-linejoin:round"/>')
    if out_at:
        cx_, cy_ = pts[-1]
        out.append(f'<circle cx="{cx_:.1f}" cy="{cy_:.1f}" r="4" style="{fill(INC)};stroke:var(--background-primary,#fff);stroke-width:2"/>'
                   f'<text x="{cx_ + 8:.1f}" y="{cy_ - 8:.1f}" text-anchor="start" style="{txt};{ink}">Runs out, age {out_at[1]:.0f}</text>')
    else:
        out.append(f'<text x="{x(rows[-1][0]) + 4:.1f}" y="{y(rows[-1][2]) + 4:.1f}" style="{txt};{ink}">Projected</text>')
    out.append(f'<text x="{x(rows[-1][0]) + 4:.1f}" y="{y(rows[-1][3]) + 4:.1f}" style="{txt};{ink}">Needed</text>')
    for fy, age, p, n in rows:                      # hover columns, wider than the marks
        out.append(f'<rect x="{x(fy) - 6:.1f}" y="{T}" width="12" height="{H - T - B}" style="fill:transparent">'
                   f'<title>FY{fy} (age {age}): projected {baht(p)}, needed {baht(n)}</title></rect>')
    out.append(f'<rect x="{L}" y="8" width="14" height="3" style="{fill(INC)}"/><text x="{L + 20}" y="13" style="{txt};{ink}">Projected assets</text>'
               f'<line x1="{L + 140}" x2="{L + 154}" y1="9.5" y2="9.5" style="stroke:{NEED[0]};stroke:light-dark({NEED[0]},{NEED[1]});stroke-width:2;stroke-dasharray:4 3"/>'
               f'<text x="{L + 160}" y="13" style="{txt};{ink}">Needed to last to age 90</text>')
    out.append('</svg>')
    return ''.join(out)

import re

def render(d, today=None):
    today = today or dt.date.today()
    tx = d['tx']
    by_m = collections.defaultdict(lambda: [0.0, 0.0])
    cat_ytd, cat_last = collections.Counter(), collections.Counter()
    last_full = (today.replace(day=1) - dt.timedelta(days=1)).strftime('%Y-%m')
    for t in tx:
        m = t['date'][:7]
        if t['type'] == 'Income':
            by_m[m][0] += t['amount']
        if t['type'] == 'Expense':
            by_m[m][1] -= t['amount']
            if t['date'][:4] == str(today.year) and m <= last_full:
                cat_ytd[t['category']] -= t['amount']
            if m == last_full:
                cat_last[t['category']] -= t['amount']
    months = [m for m in sorted(by_m) if f'{today.year}-01' <= m <= last_full][-12:]
    if not months:  # early in the year: show the last 12 complete months instead
        months = [m for m in sorted(by_m) if m <= last_full][-12:]
    series = [(f"{MONTHS[int(m[5:]) - 1]} {m[:4]}", *by_m[m]) for m in months]
    n = len(series) or 1
    avg_in = sum(s[1] for s in series) / n
    avg_sp = sum(s[2] for s in series) / n
    lf = MONTHS[int(last_full[5:]) - 1]
    st, mtg, ret = d['settings'], d['mortgage'], d['retirement']
    owed_items = [a for a in d['advances'] if a['status'] != 'Reimbursed']
    owed = sum(a['outstanding'] for a in owed_items)
    cash = sum(float(b['balance'] or 0) for b in d['bank'])
    nw = float(d['nw'].get('Net worth') or 0)
    fresh = {}
    for t in tx:
        fresh[t['account']] = max(fresh.get(t['account'], ''), t['date'])
    card_to = max((fresh.get(c, '') for c in d['cards']), default='')

    L = ['---', 'tags: [finance, dashboard]', f'updated: {today.isoformat()}', '---', '', '# Finance dashboard', '',
         f"> Generated from your [Personal Finance sheet]({d['url']}) on {today:%d %b %Y}. "
         'Do not edit by hand: ask Claude to refresh it, or run `pf.py dashboard`.', '', '## Headline', '']
    head = ['Net worth', 'Cash in bank', 'Owed to you']
    vals = [f'**{baht(nw)}**', baht(cash), baht(owed)]
    for c in d['cards'].values():
        if c['total'] <= 0:          # dormant card: nothing due
            continue
        head.append(f"{c['card']} due")
        vals.append(f"{baht(c['total'])} on {c['due']:%d %b}" + (' ✅ paid' if c['paid'] == 'Yes' else '') if c['due'] else baht(c['total']))
    if st['retire']:
        head.append('Retirement')
        vals.append(f"{st['retire']:%d %b %Y} · {st['months_left']} months")
    L += ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head), '| ' + ' | '.join(vals) + ' |', '']

    if series:
        L += [f'## Cash flow, {series[0][0]} to {series[-1][0]}', '',
              f'Average per month: income **{baht(avg_in)}**, spending **{baht(avg_sp)}**, net **{baht(avg_in - avg_sp)}**. '
              'Card payments, transfers between your own accounts and work advances are excluded; '
              'loan payments and income tax count as spending.', '']
        if card_to and card_to < f'{last_full}-31':
            L += [f"> [!warning] Card spending after {dt.date.fromisoformat(card_to):%d %b} arrives with the next card statement, "
                  f"so {lf} is understated.", '']
        L += [cashflow_svg(series), '', '| Month | Income | Spending | Net |', '|---|--:|--:|--:|']
        L += [f'| {lab} | {baht(i)} | {baht(s)} | {baht(i - s)} |' for lab, i, s in series]
        L.append('')
    if cat_ytd:
        tot = sum(cat_ytd.values()) or 1
        ranked = [(c, v) for c, v in cat_ytd.most_common() if v > 0]
        items = ranked[:7] + ([('Other', sum(v for _, v in ranked[7:]))] if len(ranked) > 7 else [])
        L += [f'## Spending by category, Jan to {lf} {today.year}', '', pie_svg(items), '',
              f'| Category | Jan to {lf} | Share | {lf} |', '|---|--:|--:|--:|']
        L += [f'| {c} | {baht(v)} | {v / tot:.0%} | {baht(cat_last.get(c, 0))} |' for c, v in cat_ytd.most_common()]
        L.append('')
    bud = d.get('budget')
    if bud and bud['budget']:
        L += [f"## Budget, {bud['month']}", '',
              f"Spent **{baht(bud['actual'])}** against a budget of **{baht(bud['budget'])}** "
              f"({'under' if bud['budget'] >= bud['actual'] else 'over'} by {baht(abs(bud['budget'] - bud['actual']))}).", '',
              '| Category | Budget | Actual | Under (over) |', '|---|--:|--:|--:|']
        L += [f"| {c} | {baht(b)} | {baht(a)} | {baht(b - a) if b >= a else '(' + baht(a - b) + ')'} |"
              for c, b, a in bud['rows'] if b or a]
        L.append('')
    if owed_items:
        L += ['## Owed to you', '', '| ID | Project | Paid | Amount | Status | Days |', '|---|---|---|--:|---|--:|']
        L += [f"| {a['id']} | {a['project']} | {a['date'] or '–'} | {baht(a['outstanding']) if a['outstanding'] else 'to confirm'} "
              f"| {a['status']} | {a['days'] if a['days'] != '' else '–'} |" for a in owed_items]
        L += [f'| **Total** | | | **{baht(owed)}** | | |', '']
    if mtg['balance'] > 0:
        L += ['## Mortgage', '',
              f"- Balance **{baht(mtg['balance'])}** at {mtg['rate']:.2%}"
              + (f"; projected payoff **{mtg['payoff']:%b %Y}** ({mtg['left']} payments of {baht(mtg['payment'])})." if mtg['payoff'] and mtg['payment'] else '.'),
              f"- Interest paid {today.year} to date: {baht(mtg['interest_ytd'])} (tax-deductible, up to ฿100,000 a year).", '']
    if ret['rows'] and st['target']:
        gap = ret['projected'] - ret['needed']
        L += ['## Retirement projection', '',
              f"At retirement (Sep {ret['retire_fy']}): projected **{baht(ret['projected'])}**, needed **{baht(ret['needed'])}**, "
              + (f'surplus **{baht(gap)}**.' if gap >= 0 else
                 f"gap **{baht(-gap)}**. Closing it means saving about **{baht(ret['extra'])} more a month** until retirement. "
                 f"On the current plan the money lasts to about **age {ret['last_age']}**."), '',
              projection_svg(ret['rows'], ret['retire_fy']), '',
              f"> [!note] Assumptions: {baht(st['target'])} a month in today's money, {st['inflation']:.1%} inflation, "
              f"{st['ret']:.1%} return" + (f", {baht(st['pension'])} a month pension" if st['pension'] else '')
              + (f", annuity {baht(st['annuity'])} a year" if st['annuity'] else '') + '. Change them on the Settings and Retirement tabs.', '']
    elif not st['target']:
        L += ['## Retirement projection', '', '> [!note] Set your retirement spending target on the Settings tab to see the projection.', '']
    if st['dob'] and st['retire']:
        ms = [(st['dob'].replace(year=st['dob'].year + 55), 'Age 55: RMF units held 5+ years can be redeemed tax-free; provident fund can be paid out tax-free'),
              (st['retire'], 'Retirement (end of the fiscal year you reach 60)')]
        if mtg['payoff']:
            ms.append((mtg['payoff'], 'Mortgage paid off; redirect the payment to savings'))
        if st['annuity_first']:
            ms.append((st['annuity_first'], f"First annuity payout ({baht(st['annuity'])} a year)"))
        L += ['## Milestones', '', '| Date | Milestone |', '|---|---|']
        L += [f"| {m:%b %Y} | {t}{' ✅' if m < today else ''} |" if m.day == 1 else
              f"| {m:%d %b %Y} | {t}{' ✅' if m < today else ''} |" for m, t in sorted(ms)]
        L.append('')
    if today.month >= 9:
        L += [f'> [!tip] Tax year {today.year}: RMF, ThaiESG and insurance premiums count only if paid by 31 Dec {today.year}.', '']
    if fresh:
        L += ['## Data freshness', '', '| Account | Latest transaction |', '|---|---|']
        L += [f'| {a} | {v} |' for a, v in sorted(fresh.items())]
    return '\n'.join(L) + '\n'


def to_html(md_text):
    import markdown
    body = re.sub(r'^---\n.*?\n---\n', '', md_text, flags=re.S)
    body = re.sub(r'^> \[!(\w+)\] ', lambda m: '> **' + m[1].capitalize() + ':** ', body, flags=re.M)
    html = markdown.markdown(body, extensions=['tables'])
    return ('''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Finance dashboard</title><style>
:root{color-scheme:light dark;--background-primary:#fcfcfb;--text-normal:#0b0b0b;--text-muted:#52514e;--text-faint:#999;--background-modifier-border:#e2e1dc}
@media (prefers-color-scheme:dark){:root{--background-primary:#1a1a19;--text-normal:#fff;--text-muted:#c3c2b7;--text-faint:#777;--background-modifier-border:#383835}}
body{font-family:system-ui,"Noto Sans Thai",sans-serif;background:var(--background-primary);color:var(--text-normal);max-width:860px;margin:0 auto;padding:16px;line-height:1.5}
table{border-collapse:collapse;width:100%;margin:8px 0}td,th{border-bottom:1px solid var(--background-modifier-border);padding:4px 8px;text-align:left}
blockquote{margin:8px 0;padding:6px 12px;border-left:3px solid var(--text-faint);color:var(--text-muted)}a{color:#2a78d6}
</style></head><body>''' + html + '</body></html>')

#!/usr/bin/env python3
"""Payment sheet and record for a batch of transfers (ใบโอนเงิน / บันทึกการโอน).

One JSON file per batch (`payments.json`, schema below) drives everything:

    python3 pay_sheet.py build DIR                 # payments.json in DIR → <file>.tex + <file>.pdf (+ qr/)
    python3 pay_sheet.py check DIR                 # totals, numbering, duplicate refs, missing slips; exit 1 on a problem
    python3 pay_sheet.py mark  DIR ROW --ref REF --date "28 ต.ค. 2569 14:40" --slip IMG [--note TEXT]
                                                   # copy the slip into DIR/receipts/NN-REF.ext and set the row paid
    python3 pay_sheet.py payload NUMBER AMOUNT     # print the PromptPay QR payload (debugging)

The PDF has the table on page 1 — one row per payee with number, name, amount, channel and
account / PromptPay number, a **PromptPay QR with the amount pre-filled** on PromptPay rows
only (scan it with any Thai bank app; the app shows the recipient's name before confirming),
status / date, the bank's reference number and a tick when a slip is filed — followed by every
filed slip image, captioned, 12 per page. The footer carries paid-count / amount / outstanding.

Bank-account rows get no QR on purpose: the account-number proxy of the Thai QR standard
is not documented by the Bank of Thailand and not every app resolves it. The user types
those by hand from the number on the sheet.

payments.json
-------------
{
  "file": "payment-sheet",                 # output basename (default "payment-sheet")
  "title": "ค่าตอบแทนกรรมการสอบคัดเลือก 23–25 ต.ค. 2569 — คณะวิศวกรรมศาสตร์ 14 คน รวม 43,600 บาท",
  "subtitle": "ตามอีเมลของ … 28 ต.ค. 2569 11:07 — โอนจากบัญชีโครงการ ธ.กรุงไทย xxx-x-xxxxx-x",
  "total": 43600,                          # optional: build/check fail if the rows don't add up to it
  "rows": [
    {"no": 1, "name": "…", "amount": 14400, "channel": "bank", "bank": "ธ.กรุงไทย", "number": "000-0-00000-0",
     "check": false, "paid": false, "date": "", "ref": "", "receipt": "", "note": ""},
    {"no": 2, "name": "…", "amount": 3600,  "channel": "pp",   "number": "081-234-5678", "check": true, …}
  ],
  "corrections": [                          # anything that is not a plain row payment (wrong account, refund …)
    {"for_row": 4, "amount": 3600, "date": "28 ต.ค. 2569 14:43", "ref": "N0067…", "receipt": "04-reimburse-N0067….jpg",
     "text": "รายการที่ 4 โอนออกจากบัญชีส่วนตัวโดยผิดพลาด จึงโอนชดเชยจากบัญชีโครงการคืน … ยอดสุทธิจากบัญชีโครงการยังคง 43,600 บาท"}
  ],
  "notes": ["ส่วนของ … ไม่อยู่ในชุดนี้", "โอนครบแล้วแจ้ง … เพื่อบันทึกในทะเบียน"],
  "footer": "Google STAR APAC DCI — บันทึกการโอน …"   # left footer; the right one is the running total
}

channel: "pp" (PromptPay: a mobile number 0XX-XXX-XXXX, a 13-digit national/tax ID, or a 15-digit
e-wallet ID) or "bank" (account transfer; "bank" names the bank for the sheet). "check": true marks
rows the requester asked to double-check the recipient name on screen (shown as *). Dates are
free text as the slip prints them. "receipt" is a file name inside DIR/receipts/.

Needs: xelatex (TeX Live) with the Sarabun font, qrencode. Stdlib only. The QR payload follows
EMVCo merchant-presented QR as used by PromptPay (tag 29, AID A000000677010111, proxy sub-tag
01/02/03, tag 54 amount, CRC-16/CCITT-FALSE), checked against the promptpay-qr library.

Personal data: the JSON, the QR images and the slips carry account and phone numbers. Keep DIR
with the project's finance records (a private repo or local folder), never in this plugin repo.
"""
import argparse, json, pathlib, re, shutil, subprocess, sys

sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------- PromptPay payload
def _tlv(tag, value): return f"{tag}{len(value):02d}{value}"

def crc16(s):
    c = 0xFFFF
    for b in s.encode():
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) if c & 0x8000 else c << 1
            c &= 0xFFFF
    return f"{c:04X}"

def promptpay_payload(number, amount):
    d = re.sub(r"\D", "", number)
    if len(d) == 10 and d[0] == "0": proxy = _tlv("01", "0066" + d[1:])      # mobile
    elif len(d) == 13: proxy = _tlv("02", d)                                  # national ID / tax ID
    elif len(d) == 15: proxy = _tlv("03", d)                                  # e-wallet
    else: raise ValueError(f"not a PromptPay number: {number}")
    p = (_tlv("00", "01") + _tlv("01", "12") + _tlv("29", _tlv("00", "A000000677010111") + proxy)
         + _tlv("58", "TH") + _tlv("53", "764") + _tlv("54", f"{amount:.2f}") + "6304")
    return p + crc16(p)

assert promptpay_payload("081-234-5678", 1200) == "00020101021229370016A000000677010111011300668123456785802TH530376454071200.006304759A"

# ---------------------------------------------------------------- data
def load(d):
    f = pathlib.Path(d) / "payments.json"
    if not f.exists(): sys.exit(f"no payments.json in {d}")
    return json.loads(f.read_text(encoding="utf-8"))

def save(d, data):
    (pathlib.Path(d) / "payments.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

def problems(d, data):
    rows, out = data["rows"], []
    nos = [r["no"] for r in rows]
    if nos != list(range(1, len(rows) + 1)): out.append(f"rows are not numbered 1..{len(rows)}: {nos}")
    total = sum(r["amount"] for r in rows)
    if "total" in data and data["total"] != total: out.append(f"rows add up to {total:,}, 'total' says {data['total']:,}")
    for r in rows:
        if r.get("channel") not in ("pp", "bank"): out.append(f"row {r['no']}: channel must be pp or bank")
        if r.get("channel") == "pp":
            try: promptpay_payload(r["number"], r["amount"])
            except ValueError as e: out.append(f"row {r['no']}: {e}")
        if r.get("paid"):
            for k in ("date", "ref", "receipt"):
                if not r.get(k): out.append(f"row {r['no']}: paid but no {k}")
            if r.get("receipt") and not (pathlib.Path(d) / "receipts" / r["receipt"]).exists(): out.append(f"row {r['no']}: slip receipts/{r['receipt']} not found")
    for c in data.get("corrections", []):
        if c.get("receipt") and not (pathlib.Path(d) / "receipts" / c["receipt"]).exists(): out.append(f"correction for row {c.get('for_row')}: slip receipts/{c['receipt']} not found")
    refs = [x["ref"] for x in rows + data.get("corrections", []) if x.get("ref")]
    dup = sorted({x for x in refs if refs.count(x) > 1})
    if dup: out.append(f"duplicate reference numbers: {dup}")
    return out

# ---------------------------------------------------------------- LaTeX
def esc(s): return re.sub(r"([&%$#_{}~^\\])", r"\\\1", str(s))

PREAMBLE = r"""\documentclass[a4paper,10pt]{article}
\usepackage[margin=10mm,top=10mm,bottom=11mm]{geometry}
\usepackage{fontspec}
\setmainfont{Sarabun}[Script=Thai]
\XeTeXlinebreaklocale "th"
\XeTeXlinebreakskip = 0pt plus 1pt
\usepackage{graphicx,array,amssymb,fancyhdr}
\usepackage[hidelinks]{hyperref}
\hypersetup{pdftitle={%(pdftitle)s}}
\pagestyle{fancy}\fancyhf{}\renewcommand{\headrulewidth}{0pt}
\fancyfoot[L]{\footnotesize %(footer)s}
\fancyfoot[R]{\footnotesize โอนแล้ว %(paid_n)d/%(n)d — %(paid_sum)s บาท — คงเหลือ %(left)s บาท}
\setlength{\parindent}{0pt}
\renewcommand{\arraystretch}{1.0}\setlength{\tabcolsep}{3pt}
\begin{document}
{\large\textbf{%(title)s}}\\[2pt]
{\small %(subtitle)s}

\vspace{2mm}
\small
\begin{tabular}{|>{\centering\arraybackslash}m{5mm}|>{\raggedright\arraybackslash}m{36mm}|>{\raggedleft\arraybackslash}m{13mm}|m{26mm}|>{\centering\arraybackslash}m{16mm}|>{\raggedright\arraybackslash}m{24mm}|m{42mm}|>{\centering\arraybackslash}m{7mm}|}
\hline
\textbf{ที่} & \textbf{ชื่อ} & \textbf{บาท} & \textbf{ช่องทาง / เลขที่} & \textbf{QR พร้อมเพย์} & \textbf{สถานะ / วันที่โอน} & \textbf{เลขที่อ้างอิง} & \textbf{สลิป} \\\hline
"""

def build(d, slips=True):
    d = pathlib.Path(d); data = load(d)
    bad = problems(d, data)
    if bad: sys.exit("payments.json: " + "; ".join(bad))
    rows = data["rows"]; (d / "qr").mkdir(exist_ok=True)
    base = data.get("file", "payment-sheet")
    paid = [r for r in rows if r.get("paid")]
    total = sum(r["amount"] for r in rows); paid_sum = sum(r["amount"] for r in paid)
    pp = [r for r in rows if r["channel"] == "pp"]; bank = [r for r in rows if r["channel"] == "bank"]
    sub = data.get("subtitle", "")
    if pp: sub += " — พร้อมเพย์: สแกน QR ยอดเงินกรอกให้แล้ว"
    if bank: sub += " — บัญชีธนาคาร: โอนเข้าบัญชีตามเลขที่"
    sub += " — \\textbf{ตรวจชื่อผู้รับบนหน้าจอก่อนยืนยันทุกรายการ}" + (" (* ขอให้ตรวจเป็นพิเศษ)" if any(r.get("check") for r in rows) else "")
    tex = [PREAMBLE % dict(pdftitle=esc(data.get("title", base)), footer=esc(data.get("footer", "")), paid_n=len(paid), n=len(rows),
                           paid_sum=f"{paid_sum:,}", left=f"{total - paid_sum:,}", title=esc(data.get("title", "")), subtitle=sub)]
    for r in rows:
        if r["channel"] == "pp":
            png = d / "qr" / f"{r['no']:02d}.png"
            subprocess.run(["qrencode", "-o", str(png), "-s", "8", "-m", "1", "-l", "M", "-t", "PNG32", promptpay_payload(r["number"], r["amount"])], check=True)
            qr = f"\\includegraphics[width=15mm]{{qr/{r['no']:02d}.png}}"
            chan = "พร้อมเพย์" + (" \\textbf{*}" if r.get("check") else "")
        else:
            qr, chan = "", esc(r.get("bank", "ธนาคาร")) + (" \\textbf{*}" if r.get("check") else "")
        if r.get("paid"):
            status = f"\\checkmark~โอนแล้ว\\newline {esc(r['date'])}" + ("\\newline \\footnotesize\\textbf{ดูหมายเหตุ}" if r.get("note") else "")
            ref, slip = "\\footnotesize\\texttt{" + esc(r["ref"]) + "}", "\\checkmark" if r.get("receipt") else ""
        else:
            status, ref, slip = "$\\square$", "", ""
        tex.append(f"{r['no']} & {esc(r['name'])} & {r['amount']:,} & {chan}\\newline\\texttt{{{esc(r['number'])}}} & {qr} & {status} & {ref} & {slip} \\\\\\hline\n")
    summary = " — ".join(x for x in [f"พร้อมเพย์ {len(pp)} รายการ {sum(r['amount'] for r in pp):,} บาท" if pp else "",
                                     f"บัญชีธนาคาร {len(bank)} รายการ {sum(r['amount'] for r in bank):,} บาท" if bank else "",
                                     f"โอนแล้ว {len(paid)} รายการ {paid_sum:,} บาท"] if x)
    tex.append(f"\\multicolumn{{2}}{{|l|}}{{\\textbf{{รวม {len(rows)} รายการ}}}} & \\textbf{{{total:,}}} & \\multicolumn{{5}}{{l|}}{{{summary}}} \\\\\\hline\n\\end{{tabular}}\n\n\\vspace{{2mm}}\n{{\\footnotesize\n")
    for c in data.get("corrections", []):
        tex.append(f"\\textbf{{หมายเหตุ:}} {esc(c['text'])}" + (f" (อ้างอิง \\texttt{{{esc(c['ref'])}}}, {esc(c['date'])}" + (f", สลิป \\texttt{{{esc(c['receipt'])}}}" if c.get("receipt") else "") + ")" if c.get("ref") else "") + "\\par\n")
    for r in rows:
        if r.get("note") and not any(c.get("for_row") == r["no"] for c in data.get("corrections", [])): tex.append(f"\\textbf{{หมายเหตุ รายการที่ {r['no']}:}} {esc(r['note'])}\\par\n")
    notes = list(data.get("notes", [])) + ["สลิปเก็บใน receipts/ ชื่อไฟล์ ที่-เลขอ้างอิง"]
    tex.append(esc(" — ".join(notes)) + "}\n")
    if slips:
        items = [(f"{r['no']}. {r['name']} — {r['amount']:,} บาท", r["ref"], r["receipt"]) for r in rows if r.get("receipt")]
        items += [(f"หมายเหตุ รายการที่ {c['for_row']} — {c['amount']:,} บาท", c.get("ref", ""), c["receipt"]) for c in data.get("corrections", []) if c.get("receipt")]
        cells = [f"\\begin{{minipage}}[t]{{46mm}}\\centering\\includegraphics[width=44mm]{{receipts/{f}}}\\\\[1pt]{{\\scriptsize {esc(cap)}\\\\\\texttt{{{esc(ref)}}}}}\\end{{minipage}}" for cap, ref, f in items]
        pages = [cells[i:i + 12] for i in range(0, len(cells), 12)]
        for i, chunk in enumerate(pages):
            grid = "\\\\[3mm]\n".join("\\hfill".join(chunk[j:j + 4]) for j in range(0, len(chunk), 4))
            tex.append(f"\\clearpage\n{{\\normalsize\\textbf{{สลิปการโอน ({i + 1}/{len(pages)})}}}}\\\\[2mm]\n{grid}\n")
    tex.append("\\end{document}\n")
    (d / f"{base}.tex").write_text("".join(tex), encoding="utf-8")
    r = subprocess.run(["xelatex", "-interaction=nonstopmode", f"{base}.tex"], cwd=d, capture_output=True, text=True)
    if r.returncode or not (d / f"{base}.pdf").exists():
        err = [l for l in (d / f"{base}.log").read_text(encoding="utf-8", errors="replace").splitlines() if l.startswith("!")]
        sys.exit("xelatex failed: " + " | ".join(err[:5]))
    for e in ("aux", "log", "out"): (d / f"{base}.{e}").unlink(missing_ok=True)
    print(f"built {d / (base + '.pdf')}: {len(rows)} rows, paid {len(paid)}/{len(rows)}, {paid_sum:,} of {total:,}")

def mark(d, row, ref, date, slip, note):
    d = pathlib.Path(d); data = load(d)
    r = next((x for x in data["rows"] if x["no"] == row), None)
    if not r: sys.exit(f"no row {row}")
    src = pathlib.Path(slip).expanduser()
    if not src.exists(): sys.exit(f"slip not found: {src}")
    (d / "receipts").mkdir(exist_ok=True)
    dest = d / "receipts" / f"{row:02d}-{ref}{src.suffix.lower().replace('.jpeg', '.jpg')}"
    shutil.copy2(src, dest)
    r.update(paid=True, date=date, ref=ref, receipt=dest.name)
    if note: r["note"] = note
    save(d, data)
    print(f"row {row} ({r['name']}, {r['amount']:,}) marked paid — {dest.name}")

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); sp = ap.add_subparsers(dest="cmd", required=True)
    b = sp.add_parser("build"); b.add_argument("dir"); b.add_argument("--no-slips", action="store_true")
    c = sp.add_parser("check"); c.add_argument("dir")
    m = sp.add_parser("mark"); m.add_argument("dir"); m.add_argument("row", type=int); m.add_argument("--ref", required=True); m.add_argument("--date", required=True); m.add_argument("--slip", required=True); m.add_argument("--note", default="")
    p = sp.add_parser("payload"); p.add_argument("number"); p.add_argument("amount", type=float)
    a = ap.parse_args()
    if a.cmd == "build": build(a.dir, slips=not a.no_slips)
    elif a.cmd == "check":
        bad = problems(a.dir, load(a.dir))
        print("\n".join(bad) if bad else "ok"); sys.exit(1 if bad else 0)
    elif a.cmd == "mark": mark(a.dir, a.row, a.ref, a.date, a.slip, a.note)
    elif a.cmd == "payload": print(promptpay_payload(a.number, a.amount))

if __name__ == "__main__": main()

#!/usr/bin/env python3
"""Child-education claims (ค่าการศึกษาบุตร): fill the two claim forms and assemble the submission packs.

    python3 edu_claim.py blank OUT.pdf [--form gov]      # empty form (default: welfare-fund form)
    python3 edu_claim.py fill SPEC.json OUT.pdf          # filled form
    python3 edu_claim.py check SPEC.json                 # amounts add up, words match figures
    python3 edu_claim.py pack PACK.json                  # form + certified copies → one PDF
    python3 edu_claim.py words 20500                     # 20,500 → สองหมื่นห้าร้อยบาทถ้วน
    python3 edu_claim.py fields [--form gov]             # list fillable field names
    python3 edu_claim.py where                           # the claims folder (EDU_CLAIM_DIR)

Forms:
  welfare  ใบเบิกเงินสวัสดิการเกี่ยวกับการศึกษาของบุตร กองทุนสวัสดิการมหาวิทยาลัยบูรพา (พนักงานมหาวิทยาลัย)
  gov      แบบ 7223 ใบเบิกเงินสวัสดิการเกี่ยวกับการศึกษาของบุตร (ข้าราชการ / สิทธิข้าราชการบำนาญ)
Geometry lives in edu_claim_layout.py / edu_claim_gov_layout.py, measured from scans of the printed forms.

SPEC.json: {"form": "welfare"|"gov", "fields": {field: text}, "ticks": [field, ...]}. Field names are the
``field`` of the leaders and boxes in the layout module (``fields`` lists them); an unknown name is an
error, so a typo can't silently drop a value. A ``*_words`` field left out is written from its figure.
``fill`` runs ``check`` first and refuses a spec whose amounts don't add up.

PACK.json (paths are relative to the JSON file; ~ is expanded):
  {"output": "pack.pdf", "form": "filled-form.pdf",
   "certifier": {"name": "(name as signed)", "role": "(position line)"},
   "only_for": "ใช้เพื่อ… เท่านั้น",
   "pages": [{"src": "doc.pdf", "pages": [1, 2], "layout": "fit"|"full",
              "certify": "สำเนาถูกต้อง"|"รับรองสำเนาถูกต้อง"|null, "diagonal": true|false,
              "name": "…", "role": "…"}]}
Every attachment page gets a certification block (title, blank space for the signature, name, role) at the
foot of the page; ``diagonal`` adds the ``only_for`` line across the document. "fit" shrinks the source page to
leave room for the block; "full" keeps a full-page A4 scan as is (for a card scanned on an A4 sheet).
Signatures are never drawn: the claimant signs the printout.
"""
import importlib, os, shutil, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
FORMS = {"welfare": "edu_claim_layout", "gov": "edu_claim_gov_layout"}

FONT_PT = 14

PREAMBLE = r"""\documentclass{article}
\usepackage[a4paper,margin=0mm]{geometry}
\usepackage{fontspec,tikz}
\usetikzlibrary{calc}
\setmainfont{TH SarabunPSK}[Script=Thai]
\XeTeXlinebreaklocale "th"
\pagestyle{empty}
\setlength{\parindent}{0pt}
\newcommand{\cbox}[1][2.4mm]{\tikz[baseline=0pt]\draw[line width=0.5pt](0,0.15mm) rectangle (#1,#1+0.15mm);}
\newcommand{\ckmark}{\tikz[baseline=0pt]\draw[line width=0.7pt,line cap=round,line join=round](0,1.3mm)--(0.9mm,0.2mm)--(2.6mm,3.0mm);}
\begin{document}
\fontsize{%(pt)s}{%(pt)s}\selectfont
"""


def tex_escape(s):
    return s.replace("%", r"\%").replace("&", r"\&").replace("#", r"\#")


FILL_PT = 15


def page_tex(items, mm, rule_pt=1.0, box_pt=0.5, fields=None, ticks=(), fill_pt=FILL_PT):
    fields = fields or {}
    out = [r"\begin{tikzpicture}[remember picture,overlay,shift={(current page.north west)},y=-1mm,x=1mm]"]
    prev = None
    for n, it in enumerate(items):
        k = it[0]
        if k in ("t", "c"):
            _, x, y, s, bold = it[:5]
            pt = it[5] if len(it) > 5 else FONT_PT
            X, Y = mm(x, y)
            s = s if "\\" in s else tex_escape(s)
            txt = r"\fontsize{%s}{%s}\selectfont " % (pt, pt) + (r"\textbf{%s}" % s if bold else s)
            anchor = "base west" if k == "t" else "base"
            out.append(r"\node[anchor=%s,inner sep=0pt] (n%d) at (%.2f,%.2f) {%s};" % (anchor, n, X, Y, txt))
        elif k == "d":
            _, x0, x1, y, _f = it
            X0, Y = mm(x0, y); X1, _ = mm(x1, y)
            # a leader right after a label on the same line starts where the label ends
            start = "(%.2f,%.2f)" % (X0 + 0.3, Y - 0.15)
            if prev and prev[1][0] == "t" and abs(prev[1][2] - y) < 1:
                start = "([xshift=0.4mm]n%d.base east |- 0,%.2f)" % (prev[0], Y - 0.15)
            out.append(r"\draw[line width=0.55pt,line cap=round,dash pattern=on 0pt off 1.7pt] %s--(%.2f,%.2f);"
                       % (start, X1, Y - 0.15))
            if _f in fields and str(fields[_f]).strip():
                out.append(r"\path %s coordinate (s%d) (%.2f,%.2f) coordinate (e%d);" % (start, n, X1, Y - 0.15, n))
                out.append(r"\node[anchor=base,inner sep=0pt] at ($(s%d)!0.5!(e%d)+(0,-0.45)$) {\fontsize{%s}{%s}\selectfont %s};"
                           % (n, n, fill_pt, fill_pt, tex_escape(str(fields[_f]))))
        elif k == "b":
            _, x, y, _f = it[:4]
            side = it[4] if len(it) > 4 else 2.4  # mm
            X, Y = mm(x, y)
            out.append(r"\draw[line width=%spt] (%.2f,%.2f) rectangle (%.2f,%.2f);"
                       % (box_pt, X, Y - 0.15, X + side, Y - 0.15 - side))
            if _f in ticks:
                out.append(r"\draw[line width=0.9pt,line cap=round,line join=round] (%.2f,%.2f)--(%.2f,%.2f)--(%.2f,%.2f);"
                           % (X + 0.15 * side, Y - 0.55 * side, X + 0.4 * side, Y - 0.2 * side, X + 1.05 * side, Y - 1.2 * side))
        elif k == "B":
            _, x0, y0, x1, y1, s = it[:6]
            lw, pt, bold = (it[6:9] if len(it) > 6 else (0.9, None, True))
            X0, Y0 = mm(x0, y0); X1, Y1 = mm(x1, y1)
            out.append(r"\draw[line width=%spt] (%.2f,%.2f) rectangle (%.2f,%.2f);" % (lw, X0, Y0, X1, Y1))
            txt = (r"\textbf{%s}" % s) if bold else s
            if pt:
                txt = r"\fontsize{%s}{%s}\selectfont " % (pt, pt) + txt
            out.append(r"\node[inner sep=0pt] at (%.2f,%.2f) {%s};" % ((X0 + X1) / 2, (Y0 + Y1) / 2 + 0.3, txt))
        elif k == "h":
            _, x0, x1, y = it
            X0, Y = mm(x0, y); X1, _ = mm(x1, y)
            out.append(r"\draw[line width=%spt] (%.2f,%.2f)--(%.2f,%.2f);" % (rule_pt, X0, Y, X1, Y))
        elif k == "v":
            _, x, y0, y1 = it
            X, Y0 = mm(x, y0); _, Y1 = mm(x, y1)
            out.append(r"\draw[line width=%spt] (%.2f,%.2f)--(%.2f,%.2f);" % (rule_pt, X, Y0, X, Y1))
        prev = (n, it)
    out.append(r"\end{tikzpicture}\null")
    return "\n".join(out)


def field_names(L):
    names = set()
    for p in L.PAGES:
        for it in p():
            if it[0] == "d" and it[4]:
                names.add(it[4])
            elif it[0] == "b" and it[3]:
                names.add(it[3])
    return names


THAI_DIGIT = ["", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
THAI_PLACE = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน"]


def _thai_int(n):
    if n == 0:
        return "ศูนย์"
    if n >= 1_000_000:
        hi, lo = divmod(n, 1_000_000)
        return _thai_int(hi) + "ล้าน" + (_thai_int(lo) if lo else "")
    out, digits = "", str(n)
    for i, ch in enumerate(digits):
        d, place = int(ch), len(digits) - i - 1
        if d == 0:
            continue
        if place == 1 and d == 1:
            out += "สิบ"
        elif place == 1 and d == 2:
            out += "ยี่สิบ"
        elif place == 0 and d == 1 and len(digits) > 1:
            out += "เอ็ด"
        else:
            out += THAI_DIGIT[d] + THAI_PLACE[place]
    return out


def baht_words(amount):
    """20500 → 'สองหมื่นห้าร้อยบาทถ้วน'; 1850.50 → '…บาทห้าสิบสตางค์'."""
    satang = round(float(amount) * 100)
    b, s = divmod(satang, 100)
    return _thai_int(b) + "บาท" + (_thai_int(s) + "สตางค์" if s else "ถ้วน")


def num(v):
    if v in (None, "", "-"):
        return 0.0
    return float(str(v).replace(",", "").strip())


def check(spec):
    """Return a list of problems with a fill spec's amounts (empty list = fine)."""
    f, probs = spec.get("fields", {}), []
    form = spec.get("form", "welfare")
    if form == "welfare":
        totals = 0.0
        for n in (1, 2, 3):
            p = f"child{n}_"
            parts = [num(f.get(p + k)) for k in ("claim_5_8", "claim_5_9_10")]
            if any(parts) or f.get(p + "total"):
                if abs(sum(parts) - num(f.get(p + "total"))) > 0.005:
                    probs.append(f"{p}total {f.get(p + 'total')} ≠ claim_5_8 + claim_5_9_10 = {sum(parts):,.2f}")
                if num(f.get(p + "total")) + num(f.get(p + "other_source")) > num(f.get(p + "paid")) + 0.005:
                    probs.append(f"{p}: claimed + other_source exceeds paid")
                totals += num(f.get(p + "total"))
        claim_keys = ("receive_amount", "received_amount")
    else:
        totals = None
        claim_keys = ("receive_amount", "received_amount")
        paid = sum(num(f.get(f"child{n}_amount")) for n in (1, 2, 3))
        if num(f.get("receive_amount")) > paid + 0.005:
            probs.append("receive_amount exceeds the amounts paid in section 4")
    vals = [num(f.get(k)) for k in claim_keys if f.get(k)]
    if len(set(vals)) > 1:
        probs.append("receive_amount and received_amount differ")
    if totals is not None and vals and abs(vals[0] - totals) > 0.005:
        probs.append(f"receive_amount {vals[0]:,.2f} ≠ sum of child totals {totals:,.2f}")
    for k in claim_keys:
        w = f.get(k + "_words")
        if f.get(k) and w and w != baht_words(num(f[k])):
            probs.append(f"{k}_words '{w}' ≠ '{baht_words(num(f[k]))}'")
    return probs


def with_words(spec):
    f = dict(spec.get("fields", {}))
    for k in ("receive_amount", "received_amount"):
        if f.get(k) and not f.get(k + "_words"):
            f[k + "_words"] = baht_words(num(f[k]))
    return dict(spec, fields=f)


def xelatex(tex, out_pdf, keep_tex=False, name="form"):
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, name + ".tex")
        open(src, "w", encoding="utf-8").write(tex)
        for _ in range(2):  # remember picture needs two runs
            r = subprocess.run(["xelatex", "-interaction=nonstopmode", "-halt-on-error", name + ".tex"],
                               cwd=d, capture_output=True, text=True)
            if r.returncode:
                sys.exit(r.stdout[-3000:])
        shutil.copy(os.path.join(d, name + ".pdf"), out_pdf)
        if keep_tex:
            shutil.copy(src, os.path.splitext(out_pdf)[0] + ".tex")


def build(out_pdf, keep_tex=False, form="welfare", fields=None, ticks=()):
    L = importlib.import_module(FORMS[form])
    known = field_names(L)
    bad = [f for f in list(fields or {}) + list(ticks) if f not in known]
    if bad:
        sys.exit("unknown field(s) for form %s: %s" % (form, ", ".join(bad)))
    kw = dict(rule_pt=getattr(L, "RULE_PT", 1.0), box_pt=getattr(L, "BOX_PT", 0.5), fields=fields, ticks=set(ticks),
              fill_pt=getattr(L, "FILL_PT", FILL_PT))
    body = (r"\newpage" + "\n").join(page_tex(p(), L.mm, **kw) for p in L.PAGES)
    xelatex(PREAMBLE % {"pt": FONT_PT} + body + "\n\\end{document}\n", out_pdf, keep_tex)


# ---- packs ---------------------------------------------------------------------------------------

PACK_PRE = r"""\documentclass{article}
\usepackage[a4paper,margin=0mm]{geometry}
\usepackage{fontspec,tikz,graphicx,xcolor}
\setmainfont{TH SarabunPSK}[Script=Thai]
\XeTeXlinebreaklocale "th"
\definecolor{ink}{RGB}{20,40,150}
\pagestyle{empty}\setlength{\parindent}{0pt}
\begin{document}
"""


def _certify(x, y, title, name, role):
    out = [r"\node[ink,anchor=base] at (%.1f,%.1f) {\fontsize{18}{18}\selectfont\textbf{%s}};" % (x, y, title)]
    if name:
        out.append(r"\node[ink,anchor=base] at (%.1f,%.1f) {\fontsize{14}{14}\selectfont (%s)};" % (x, y + 17, tex_escape(name)))
    if role:
        out.append(r"\node[ink,anchor=base] at (%.1f,%.1f) {\fontsize{14}{14}\selectfont %s};" % (x, y + 23, tex_escape(role)))
    return "\n".join(out)


def _pdf_pages(path):
    r = subprocess.run(["pdfinfo", path], capture_output=True, text=True, check=True)
    return int(next(l.split()[-1] for l in r.stdout.splitlines() if l.startswith("Pages:")))


def pack(spec_path):
    import json
    base = os.path.dirname(os.path.abspath(spec_path))
    P = lambda p: os.path.join(base, os.path.expanduser(p))
    spec = json.load(open(spec_path, encoding="utf-8"))
    cert = spec.get("certifier", {})
    only = spec.get("only_for", "")
    body = []
    for a in spec["pages"]:
        src = P(a["src"])
        if not os.path.exists(src):
            sys.exit(f"missing attachment: {src}")
        pages = a.get("pages") or list(range(1, _pdf_pages(src) + 1))
        full = a.get("layout", "fit") == "full"
        title = a.get("certify", "สำเนาถูกต้อง")
        name, role = a.get("name", cert.get("name")), a.get("role", cert.get("role"))
        for n in pages:
            if full:
                img = r"\node[anchor=north west,inner sep=0] at (0,0) {\includegraphics[width=210mm,height=297mm,page=%d]{%s}};" % (n, src)
                dx, dy, bx, by = a.get("diagonal_at", [108, 98]) + a.get("certify_at", [108, 150])
            else:
                img = r"\node[anchor=center,inner sep=0] at (105,129) {\includegraphics[width=200mm,height=246mm,keepaspectratio,page=%d]{%s}};" % (n, src)
                dx, dy, bx, by = a.get("diagonal_at", [105, 129]) + a.get("certify_at", [150, 261])
            parts = [img]
            if a.get("diagonal") and only:
                parts.append(r"\node[ink,rotate=%d,anchor=center] at (%.1f,%.1f) {\fontsize{17}{17}\selectfont %s};"
                             % (a.get("angle", 40), dx, dy, tex_escape(only)))
            if title:
                parts.append(_certify(bx, by, title, name, role))
            body.append(r"\begin{tikzpicture}[remember picture,overlay,shift={(current page.north west)},x=1mm,y=-1mm]"
                        + "\n" + "\n".join(parts) + "\n" + r"\end{tikzpicture}\null\newpage" + "\n")
    out = P(spec["output"])
    with tempfile.TemporaryDirectory() as d:
        att = os.path.join(d, "att.pdf")
        xelatex(PACK_PRE + "".join(body) + r"\end{document}" + "\n", att, name="att")
        parts = ([P(spec["form"])] if spec.get("form") else []) + [att]
        subprocess.run(["qpdf", "--empty", "--pages", *parts, "--", out], check=True)
    print(out)


def claims_dir():
    """EDU_CLAIM_DIR from the environment or the shared nk-work-kit .env (only this key is read)."""
    if os.environ.get("EDU_CLAIM_DIR"):
        return os.path.expanduser(os.environ["EDU_CLAIM_DIR"])
    xdg = os.environ.get("XDG_CONFIG_HOME")
    cands = ([os.path.join(xdg, "nk-work-kit", ".env")] if xdg else [])
    if os.environ.get("APPDATA"):
        cands.append(os.path.join(os.environ["APPDATA"], "nk-work-kit", ".env"))
    cands += [os.path.expanduser("~/.config/nk-work-kit/.env"),
              os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")]
    for c in cands:
        if os.path.exists(c):
            for line in open(c, encoding="utf-8"):
                k, _, v = line.strip().partition("=")
                if k.strip() == "EDU_CLAIM_DIR" and v.strip():
                    return os.path.expanduser(v.strip().strip('"').strip("'"))
    return ""


def main(argv):
    import json
    cmd = argv[1] if len(argv) > 1 else ""
    form = argv[argv.index("--form") + 1] if "--form" in argv else "welfare"
    if form not in FORMS:
        sys.exit(f"unknown --form {form}; choose from {', '.join(FORMS)}")
    if cmd == "blank" and len(argv) >= 3:
        build(argv[2], keep_tex="--tex" in argv, form=form)
        print(argv[2])
    elif cmd in ("fill", "check") and len(argv) >= 3:
        spec = json.load(open(argv[2], encoding="utf-8"))
        if spec.get("form", "welfare") not in FORMS:
            sys.exit(f"unknown form {spec.get('form')}")
        probs = check(with_words(spec))
        if cmd == "check" or probs:
            print("\n".join(probs) or "OK")
            sys.exit(1 if probs else 0)
        if len(argv) < 4:
            sys.exit(__doc__)
        spec = with_words(spec)
        build(argv[3], keep_tex="--tex" in argv, form=spec.get("form", "welfare"),
              fields=spec.get("fields", {}), ticks=spec.get("ticks", []))
        print(argv[3])
    elif cmd == "pack" and len(argv) >= 3:
        pack(argv[2])
    elif cmd == "words" and len(argv) >= 3:
        print(baht_words(num(argv[2])))
    elif cmd == "where":
        d = claims_dir()
        print(d or "EDU_CLAIM_DIR is not set")
        sys.exit(0 if d else 1)
    elif cmd == "fields":
        print("\n".join(sorted(field_names(importlib.import_module(FORMS[form])))))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)

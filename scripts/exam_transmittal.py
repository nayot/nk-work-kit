"""Fill the faculty's ใบนำส่งรายละเอียดข้อสอบ (scanned form) by typing over it.

    python3 exam_transmittal.py SPEC.json --out DIR [--roster ROSTER.csv] [--template FORM.pdf]
        -> DIR/ใบนำส่งรายละเอียดข้อสอบ_<course>.tex/.pdf

Rows of section 2 = the spec's rooms (max 3 on the form): groups, count, room. Counts come from
the roster (minus reg_status W) when given, else from each room's "count" in the spec.
Section 3.1: set 1 = the question paper (paper_pages + 1 with the cover sheet), set 2 = the
bubble answer sheet, `copies` of each. The lecturer still signs the box by hand.
Contact phone and LINE ID come from the spec (contact_phone, contact_line); never hardcode them.

HARD-WON DETAILS
- The form is a 200-dpi scan (page 832 x 589 bp, marked "NEW66", printed year 2566), so it has no
  text layer. Positions are pixels of the page rendered at 110 dpi (1272 x 900), converted with
  0.654545 bp/px; the printed "2566" is covered with white and the year written over it.
- Ticks are drawn next to (not on) the printed circles; each position was checked by rendering.
  A new scan of the form needs every coordinate re-measured: render it at 110 dpi and compare.
"""
import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path


def esc(s):
    return str(s).replace("&", r"\&").replace("%", r"\%").replace("_", r"\_").replace("#", r"\#")


def gkey(g):
    return f"{int(g):02d}" if str(g).strip().isdigit() else str(g).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("spec")
    ap.add_argument("--out", required=True)
    ap.add_argument("--roster")
    ap.add_argument("--template", default=str(Path(__file__).resolve().parent.parent / "templates" / "exam" / "ใบนำส่งสำเนาข้อสอบ.pdf"))
    a = ap.parse_args()
    s = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    counts = {}
    if a.roster:
        for r in csv.DictReader(open(a.roster, encoding="utf-8-sig")):
            if (r.get("reg_status") or "").strip().upper() != "W":
                counts[gkey(r["group"])] = counts.get(gkey(r["group"]), 0) + 1
    rooms = []
    for rm in s.get("rooms", []):
        gs = [gkey(g) for g in rm["groups"]]
        n = sum(counts.get(g, 0) for g in gs) if counts else rm.get("count", "")
        rooms.append((", ".join(gs), n, rm["room"]))
    if len(rooms) > 3:
        sys.exit("the form has 3 room rows; split the extra rooms onto a second form by hand")
    pages = int(s.get("paper_pages", 0)) + 1
    T = []
    t = T.append
    t(rf"\T{{617}}{{84}}{{{s.get('semester', '')}}}")
    t(r"\fill[white] \Q{726}{70} rectangle \Q{772}{90};")
    t(rf"\T{{732}}{{86}}{{{s.get('year', '')}}}")
    t(rf"\T{{155}}{{131}}{{{esc(s.get('submitter', ''))}}}")
    t(rf"\T{{525}}{{131}}{{{esc(s.get('department', ''))}}}")
    if s.get("contact_phone"):
        t(rf"\T{{445}}{{159}}{{{esc(s['contact_phone'])}}}")
    if s.get("contact_line"):
        t(rf"\T{{722}}{{159}}{{{esc(s['contact_line'])}}}")
    t(rf"\T{{158}}{{214}}{{{esc(s['course_code'])}}}")
    t(rf"\T{{335}}{{215}}{{{esc(s['course_th'])} ({esc(s.get('course_en', ''))})}}")
    t(rf"\T{{163}}{{243}}{{{esc(s.get('date_th', '').replace('วัน', '', 1).split('ที่ ', 1)[-1])}}}")
    t(rf"\T{{295}}{{244}}{{{esc(s.get('time_th', ''))} ({esc(s.get('duration_th', ''))})}}")
    for i, (g, n, room) in enumerate(rooms):
        y = 268 + 28 * i
        t(rf"\C{{114}}{{{y}}} \T{{160}}{{{y + 3}}}{{{esc(g)}}} \T{{345}}{{{y + 3}}}{{{n}}} \T{{478}}{{{y + 3}}}{{{esc(room)}}}")
    t(rf"\C{{282}}{{382}} \T{{455}}{{385}}{{{s.get('copies', '')}}} \T{{698}}{{385}}{{= ข้อสอบ {pages} หน้า (รวมใบปะหน้า)}}")
    t(rf"\C{{282}}{{410}} \T{{455}}{{413}}{{{s.get('copies', '')}}} \T{{698}}{{413}}{{= กระดาษคำตอบแบบระบาย 1 แผ่น}}")
    t(rf"\T{{258}}{{497}}{{{pages}}} \C{{340}}{{494}} \T{{528}}{{497}}{{{s['n_questions']}}}")
    t(r"\C{485}{578} \T{556}{581}{กระดาษคำตอบแบบระบาย 1 แผ่น/คน}")
    t(r"\C{404}{606}")
    if s.get("calculator"):
        t(r"\C{85}{662} \T{218}{665}{" + esc(s["calculator"].replace("เครื่องคิดเลข", "").strip() or s["calculator"]) + "}")
    rules = ("ปิดตำรา " if s.get("closed_book", True) else "") + (s.get("extra_rule") or "")
    if rules.strip():
        t(rf"\T{{218}}{{723}}{{{esc(rules)}}}")
    t(r"\T{108}{752}{กระดาษคำตอบแบบระบาย: พิมพ์ขนาดจริง 100\% ห้ามย่อหรือขยาย หน้าเดียว (ตรวจด้วยเครื่องอ่าน)}")
    t(rf"\T{{790}}{{734}}{{{esc(s.get('submitter_short', s.get('submitter', '')))}}}")
    tex = r"""\documentclass{article}
\usepackage[paperwidth=832bp,paperheight=589bp,margin=0pt]{geometry}
\usepackage{fontspec}
\setmainfont{Sarabun}[Script=Thai]
\XeTeXlinebreaklocale "th"
\usepackage{pdfpages}
\usepackage{tikz}
\pagestyle{empty}
\newcommand{\Q}[2]{({(#1)*0.654545*1bp},{-(#2)*0.654545*1bp})}
\newcommand{\T}[3]{\node[anchor=base west,inner sep=0pt,font=\fontsize{10}{12}\selectfont\color{blue!60!black}] at \Q{#1}{#2} {#3};}
\newcommand{\C}[2]{\draw[line width=1.3pt,blue!60!black] \Q{#1-6}{#2-1} -- \Q{#1-1}{#2+5} -- \Q{#1+9}{#2-9};}
\begin{document}
\includepdf[pagecommand={%
\begin{tikzpicture}[remember picture,overlay,shift={(current page.north west)}]
""" + "\n".join(T) + "\n" + r"""\end{tikzpicture}}]{""" + str(Path(a.template).resolve()) + "}\n\\end{document}\n"
    d = Path(a.out)
    d.mkdir(parents=True, exist_ok=True)
    name = f"ใบนำส่งรายละเอียดข้อสอบ_{s['course_code']}"
    (d / f"{name}.tex").write_text(tex, encoding="utf-8")
    for _ in range(2):   # the overlay uses remember picture: needs two passes
        r = subprocess.run(["xelatex", "-interaction=nonstopmode", f"{name}.tex"], cwd=d,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for ext in ("aux", "log"):
        (d / f"{name}.{ext}").unlink(missing_ok=True)
    if not (d / f"{name}.pdf").exists():
        sys.exit("xelatex failed:\n" + r.stdout[-2000:])
    for g, n, room in rooms:
        print(f"groups {g}: {n} students, room {room}")
    print(d / f"{name}.pdf", "(sign the lecturer box by hand)")


if __name__ == "__main__":
    main()

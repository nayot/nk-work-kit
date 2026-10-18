"""Exam sign-in sheets (ใบเซ็นชื่อเข้าสอบ): one section per exam room, from the reg roster.

    python3 exam_signin.py SPEC.json ROSTER.csv --out DIR      -> DIR/signin_sheets.tex/.pdf

ROSTER.csv columns: group,student_id,title,name,reg_status (reg_status W = withdrawn).
Take it from reg.buu.ac.th: teacher menu -> รายชื่อนิสิต -> each group of the course (see the skill).
The spec's `rooms` maps groups to rooms; counts come from the roster, minus withdrawn students,
who are left off and reported. Each room starts a new page with its own page numbers; rows are
by group, then student ID. The row number is what students copy into "ลำดับที่ในใบเซ็นชื่อ".
The department usually wants 2 sets: print twice. The output holds student names: keep it with
the course's student data, never in a public repo.
"""
import argparse
import csv
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
    ap.add_argument("roster")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    import json
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    rows = list(csv.DictReader(open(a.roster, encoding="utf-8-sig")))
    withdrawn = [r for r in rows if (r.get("reg_status") or "").strip().upper() == "W"]
    rows = [r for r in rows if r not in withdrawn]
    rooms = [(rm["room"], [gkey(g) for g in rm["groups"]]) for rm in spec["rooms"]]
    covered = {g for _, gs in rooms for g in gs}
    missing = sorted({gkey(r["group"]) for r in rows} - covered)
    if missing:
        sys.exit(f"groups {missing} are in the roster but in no room of the spec")
    logo = spec.get("logo") or ""
    out = [r"""\documentclass[11pt,a4paper]{article}
\usepackage[a4paper,margin=1.5cm,top=1.3cm,bottom=1.6cm]{geometry}
\usepackage{fontspec}
\setmainfont{Sarabun}[Script=Thai]
\XeTeXlinebreaklocale "th"
\XeTeXlinebreakskip = 0pt plus 1pt
\usepackage{longtable,array,graphicx,fancyhdr}
\newcommand{\roomname}{}
\pagestyle{fancy}\fancyhf{}\renewcommand{\headrulewidth}{0pt}
""" + f"\\fancyfoot[L]{{\\small {esc(spec['course_code'])} {esc(spec['course_th'])} \\textbullet\\ ใบเซ็นชื่อเข้า{esc(spec.get('exam_th', 'สอบ'))} {spec.get('semester', '')}/{spec.get('year', '')}}}\n" + r"""\fancyfoot[R]{\small ห้องสอบ \roomname\ \textbullet\ หน้า \thepage}
\setlength{\parindent}{0pt}
\begin{document}
"""]
    report = []
    for i, (room, groups) in enumerate(rooms):
        rs = sorted((r for r in rows if gkey(r["group"]) in groups), key=lambda r: (gkey(r["group"]), r["student_id"]))
        report.append(f"{room}: groups {', '.join(groups)} -> {len(rs)}")
        if i:
            out.append("\\newpage")
        out.append(f"\\setcounter{{page}}{{1}}\\renewcommand{{\\roomname}}{{{esc(room)}}}\n\\begin{{center}}\n")
        if logo:
            out.append(f"\\includegraphics[height=1.4cm]{{{Path(logo).resolve()}}}\\\\[2pt]\n")
        out.append(f"""{{\\large\\bfseries ใบเซ็นชื่อเข้า{esc(spec.get('exam_th', 'สอบ'))} ภาคการศึกษาที่ {spec.get('semester', '')} ปีการศึกษา {spec.get('year', '')}}}\\\\[2pt]
รายวิชา {esc(spec['course_code'])} {esc(spec['course_th'])} ({esc(spec.get('course_en', ''))})\\\\
{esc(spec.get('date_th', ''))} เวลา {esc(spec.get('time_th', ''))} \\quad \\textbf{{ห้องสอบ {esc(room)}}} \\quad กลุ่ม {', '.join(groups)} \\quad จำนวน {len(rs)} คน
\\end{{center}}
\\begin{{longtable}}{{|>{{\\centering\\arraybackslash}}p{{0.8cm}}|>{{\\centering\\arraybackslash}}p{{1.9cm}}|p{{6.3cm}}|>{{\\centering\\arraybackslash}}p{{1.0cm}}|p{{3.6cm}}|p{{2.0cm}}|}}
\\hline
\\textbf{{ที่}} & \\textbf{{รหัสนิสิต}} & \\textbf{{ชื่อ-สกุล}} & \\textbf{{กลุ่ม}} & \\textbf{{ลายมือชื่อ}} & \\textbf{{หมายเหตุ}} \\\\ \\hline
\\endhead
""")
        for n, r in enumerate(rs, 1):
            out.append(f"\\rule[-2.5mm]{{0pt}}{{8mm}}{n} & {esc(r['student_id'])} & {esc(r.get('title', ''))} {esc(r['name'])} & {gkey(r['group'])} & & \\\\ \\hline\n")
        out.append(r"""\end{longtable}
\vspace{4mm}
จำนวนผู้เข้าสอบ \makebox[1.6cm]{\dotfill} คน \quad ขาดสอบ \makebox[1.6cm]{\dotfill} คน

\vspace{8mm}
\begin{tabular}{@{}p{8cm}p{8cm}@{}}
ลงชื่อ \makebox[4.2cm]{\dotfill} กรรมการคุมสอบ & ลงชื่อ \makebox[4.2cm]{\dotfill} กรรมการคุมสอบ \\[2mm]
\hspace{8mm}(\makebox[4.2cm]{\dotfill}) & \hspace{8mm}(\makebox[4.2cm]{\dotfill})
\end{tabular}
""")
    out.append("\\end{document}\n")
    d = Path(a.out)
    d.mkdir(parents=True, exist_ok=True)
    (d / "signin_sheets.tex").write_text("".join(out), encoding="utf-8")
    for _ in range(2):
        r = subprocess.run(["xelatex", "-interaction=nonstopmode", "signin_sheets.tex"], cwd=d,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for ext in ("aux", "log"):
        (d / f"signin_sheets.{ext}").unlink(missing_ok=True)
    if not (d / "signin_sheets.pdf").exists():
        sys.exit("xelatex failed:\n" + r.stdout[-2000:])
    print("\n".join(report))
    print("left off (withdrawn):", ", ".join(f"{r['student_id']} (group {gkey(r['group'])})" for r in withdrawn) or "none")
    print(f"{d / 'signin_sheets.pdf'}  (print 2 sets)")


if __name__ == "__main__":
    main()

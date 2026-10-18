r"""Build a multiple-choice exam paper from a spec + questions file, and check it before printing.

    python3 exam_paper.py build SPEC.json QUESTIONS.tex --out DIR    -> DIR/exam_paper.tex/.pdf
    python3 exam_paper.py check SPEC.json QUESTIONS.tex KEY.txt       -> report; exit 1 on a problem

QUESTIONS.tex holds only the questions, one environment per question:

    \partheading{ส่วนที่ 1 ... (ข้อ 1--20, 10 คะแนน)}      % optional
    \subsection*{ตอนที่ 1 ...}                              % optional
    \begin{question}{1}
    Stem text, inline maths in $...$
    \opfour{A text}{B text}{C text}{D text}                % short options, one row
    \end{question}

\opfour / \optwo / \opone lay four options in one row, 2 x 2, or one per line; with five
choices use \opfive (one per line). The cover (seal/logo, course, date, time, lecturers,
instructions pointing to the bubble answer sheet) comes from the spec. The paper itself has no
answer grid: students answer only on the bubble sheet (exam_omr_sheet.py).

`check` reports, per the rules learnt writing the Oct 2026 Funda EE final:
- the key length and that every letter is a valid choice;
- how often each letter is correct (should be near-even);
- questions whose correct option is clearly the longest (a test-wise student gets them free);
- numeric options that are not in ascending order (sort them; it reads tidier and hides nothing);
- duplicate options within a question.
Numbers in worked answers must still be computed in Python, not typed: `check` can't see them.
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


def esc(s):
    return str(s).replace("&", r"\&").replace("%", r"\%").replace("_", r"\_").replace("#", r"\#")


PREAMBLE = r"""\documentclass[12pt,a4paper]{article}
\usepackage[a4paper,margin=1.8cm,top=1.6cm,bottom=2.0cm]{geometry}
\usepackage{amsmath}
\usepackage{fontspec}
\usepackage{unicode-math}
\setmainfont{Sarabun}[Script=Thai]
\setsansfont{Sarabun}[Script=Thai]
\setmathfont{latinmodern-math.otf}
\XeTeXlinebreaklocale "th"
\XeTeXlinebreakskip = 0pt plus 1pt
\linespread{1.12}
\usepackage{array,tabularx,enumitem,lastpage,fancyhdr,graphicx,xcolor,titlesec}
\setlength{\parindent}{0pt}
\setlength{\parskip}{2pt}
\pagestyle{fancy}\fancyhf{}\renewcommand{\headrulewidth}{0pt}
\fancyfoot[R]{\small หน้า \thepage/\pageref{LastPage}}
\newenvironment{question}[1]{%
  \par\addvspace{7pt}\noindent\begin{minipage}{\linewidth}%
  \begin{list}{\textbf{#1.}}{\leftmargin=2.3em\labelwidth=2em\labelsep=0.3em\itemsep=0pt\topsep=0pt\parsep=2pt}\item\raggedright}
  {\end{list}\end{minipage}\par}
\newcolumntype{O}{>{\raggedright\arraybackslash\hangindent=1.7em\hangafter=1}X}
\newcommand{\op}[2]{\makebox[1.7em][l]{#1)}#2}
\newcommand{\opfour}[4]{\par\noindent\begin{tabularx}{\linewidth}{@{}OOOO@{}}\op{A}{#1} & \op{B}{#2} & \op{C}{#3} & \op{D}{#4}\end{tabularx}}
\newcommand{\optwo}[4]{\par\noindent\begin{tabularx}{\linewidth}{@{}OO@{}}\op{A}{#1} & \op{B}{#2}\\[1pt] \op{C}{#3} & \op{D}{#4}\end{tabularx}}
\newcommand{\opone}[4]{\par\begin{list}{}{\leftmargin=1.7em\labelwidth=1.5em\labelsep=0.2em\itemsep=1pt\topsep=1pt\parsep=0pt}
  \item[A)] #1 \item[B)] #2 \item[C)] #3 \item[D)] #4\end{list}}
\newcommand{\opfive}[5]{\par\begin{list}{}{\leftmargin=1.7em\labelwidth=1.5em\labelsep=0.2em\itemsep=1pt\topsep=1pt\parsep=0pt}
  \item[A)] #1 \item[B)] #2 \item[C)] #3 \item[D)] #4 \item[E)] #5\end{list}}
\newcommand{\partheading}[1]{\par\addvspace{10pt}\noindent\colorbox{black!10}{\parbox{\dimexpr\linewidth-2\fboxsep}{\large\bfseries #1}}\par}
\titleformat*{\subsection}{\bfseries}
\titlespacing*{\subsection}{0pt}{8pt}{2pt}
"""


def cover(s):
    who = s.get("candidate_word", "นิสิต")
    total = s["n_questions"] * s.get("points_per_question", 1)
    parts = s.get("parts") or []
    lect = " \\quad ".join(f"{esc(p['name'])} {esc(p.get('author', ''))}" for p in parts if p.get("author")) \
        or " และ ".join(esc(i) for i in s.get("instructors", []))
    logo = s.get("logo") or ""
    rules = []
    if s.get("closed_book", True):
        rules.append("ห้ามนำตำราและเอกสารใด ๆ เข้าห้องสอบ (ปิดตำรา)")
    if s.get("extra_rule"):
        rules.append(esc(s["extra_rule"]))
    items = [
        f"ข้อสอบมี {len(parts) or 1} ส่วน รวม \\textbf{{{s['n_questions']} ข้อ}} เป็นข้อสอบปรนัย {len(s.get('choices', 'ABCD'))} ตัวเลือก ข้อละ {s.get('points_per_question', 1):g} คะแนน รวม \\textbf{{{total:g} คะแนน}} เลือกคำตอบที่ถูกที่สุดเพียงข้อเดียว ไม่หักคะแนนข้อที่ตอบผิด",
        "ข้อสอบมีทั้งหมด \\pageref{LastPage} หน้า รวมหน้านี้ ตรวจดูให้ครบก่อนเริ่มทำ",
        f"\\textbf{{ตอบใน\\underline{{กระดาษคำตอบ}}ที่แจกแยกต่างหาก โดยระบายวงกลมด้วยดินสอ 2B ให้เต็มวง}} ข้อละ 1 คำตอบ และระบาย{esc(s.get('id_label', 'รหัส')).split(' (')[0]}ให้ครบ {s.get('id_digits', 8)} หลัก จะเปลี่ยนคำตอบให้ลบให้สะอาด คำตอบที่เขียนในชุดข้อสอบนี้จะไม่ถูกนำมาตรวจ",
    ]
    if rules:
        items.append("\\textbf{" + " ".join(rules) + "}")
    if s.get("calculator"):
        items.append(f"อนุญาตให้ใช้{esc(s['calculator'])}")
    items += [esc(x) for x in s.get("notes", [])]
    out = ["\\begin{center}\n"]
    if logo:
        out.append(f"  \\includegraphics[height=1.9cm]{{{Path(logo).resolve()}}}\\\\[1pt]\n")
    out.append(f"""  {{\\large\\bfseries ข้อ{esc(s.get('exam_th', 'สอบ'))} ภาคการศึกษาที่ {s.get('semester', '')}/{s.get('year', '')}}}\\\\[1pt]
  {{\\large\\bfseries {esc(s['course_code'])} {esc(s['course_th'])} ({esc(s.get('course_en', ''))})}}
\\end{{center}}
\\vspace{{-4pt}}
สอบ{esc(s.get('date_th', ''))} \\quad เวลา {esc(s.get('time_th', ''))} ({esc(s.get('duration_th', ''))})\\\\
อาจารย์ผู้สอน: {lect}

\\smallskip
ชื่อ-สกุล \\makebox[5.6cm]{{\\dotfill}} \\ {esc(s.get('id_label', 'รหัสนิสิต')).split(' (')[0]} \\makebox[2.8cm]{{\\dotfill}} \\ กลุ่ม \\makebox[1.1cm]{{\\dotfill}} \\ ที่นั่งสอบ \\makebox[1.1cm]{{\\dotfill}}

\\smallskip
{{\\small\\textbf{{คำชี้แจง}}
\\begin{{enumerate}}[leftmargin=1.6em,itemsep=0pt,topsep=2pt,parsep=0pt]
""")
    out += [f"  \\item {i}\n" for i in items]
    out.append(f"  \\item ให้{who}ปฏิบัติตามข้อบังคับมหาวิทยาลัยบูรพา ว่าด้วยการศึกษา\n\\end{{enumerate}}}}\n\\medskip\n")
    return "".join(out)


def build(a):
    s = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    d = Path(a.out)
    d.mkdir(parents=True, exist_ok=True)
    foot = f"\\fancyfoot[L]{{\\small {esc(s['course_code'])} {esc(s['course_th'])} \\textbullet\\ {esc(s.get('exam_th', 'สอบ'))} {s.get('semester', '')}/{s.get('year', '')}}}\n"
    tex = PREAMBLE + foot + "\\begin{document}\n" + cover(s) + f"\\input{{{Path(a.questions).resolve()}}}\n" + \
        "\\vspace{1.5em}\n\\begin{center}\\textbf{--- จบข้อสอบ ---}\\\\ {\\small ตรวจว่าระบายคำตอบครบทุกข้อและรหัสในกระดาษคำตอบ แล้วส่งกระดาษคำตอบแยกจากชุดข้อสอบ}\\end{center}\n\\end{document}\n"
    (d / "exam_paper.tex").write_text(tex, encoding="utf-8")
    for _ in range(2):
        r = subprocess.run(["xelatex", "-interaction=nonstopmode", "exam_paper.tex"], cwd=d,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log = (d / "exam_paper.log").read_text(errors="replace") if (d / "exam_paper.log").exists() else ""
    for ext in ("aux", "log"):
        (d / f"exam_paper.{ext}").unlink(missing_ok=True)
    if not (d / "exam_paper.pdf").exists():
        sys.exit("xelatex failed:\n" + r.stdout[-2000:])
    if "Overfull \\vbox" in log:
        print("warning: a question runs past the page bottom (Overfull \\vbox); look at the pages")
    print(d / "exam_paper.pdf", "(print single-sided; look at every page before sending)")


def args_of(line):
    out, depth, cur = [], 0, ""
    for ch in line[line.index("{"):]:
        if ch == "{":
            depth += 1
            if depth == 1:
                cur = ""
                continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                out.append(cur)
                continue
        if depth >= 1:
            cur += ch
    return out


def width(s):
    s = re.sub(r"\\[a-zA-Z]+|[{}$\\^_]", "", s)
    return len(re.sub(r"[\u0E31\u0E34-\u0E3A\u0E47-\u0E4E]", "", s))


def number(s):
    """The option's value when it is a single number (with unit/words), else None."""
    nums = re.findall(r"-?\d[\d,]*\.?\d*", s.replace("\\,", "").replace("\\angle", " "))
    if len(nums) != 1:
        return None
    try:
        return float(nums[0].replace(",", ""))
    except ValueError:
        return None


def check(a):
    s = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    choices = s.get("choices", "ABCD")
    text = Path(a.questions).read_text(encoding="utf-8")
    key = "".join(ch for line in Path(a.key).read_text(encoding="utf-8").splitlines() if not line.startswith("#")
                  for ch in line if ch in choices)
    qs = {}
    for m in re.finditer(r"\\begin\{question\}\{(\d+)\}\n(.*?)\\end\{question\}", text, re.S):
        lines = m.group(2).rstrip("\n").split("\n")
        opt = next((ln for ln in reversed(lines) if re.match(r"\s*\\op(four|two|one|five)\{", ln)), None)
        qs[int(m.group(1))] = args_of(opt) if opt else []
    problems = []
    n = s["n_questions"]
    if sorted(qs) != list(range(1, n + 1)):
        problems.append(f"questions found: {len(qs)}; expected 1..{n}")
    if len(key) != n:
        problems.append(f"key has {len(key)} answers; expected {n}")
    cnt = Counter(key)
    print("correct-letter counts:", ", ".join(f"{c}={cnt.get(c, 0)}" for c in choices))
    if cnt and max(cnt.values()) - min(cnt.get(c, 0) for c in choices) > max(3, n // 10):
        problems.append("the key is unbalanced across letters")
    for q, opts in sorted(qs.items()):
        if len(opts) != len(choices):
            problems.append(f"Q{q}: {len(opts)} options, expected {len(choices)}")
            continue
        if len(set(o.strip() for o in opts)) != len(opts):
            problems.append(f"Q{q}: duplicate options")
        if q <= len(key):
            w = [width(o) for o in opts]
            c = choices.index(key[q - 1])
            if w[c] == max(w) and sorted(w)[-1] - sorted(w)[-2] > 8:
                problems.append(f"Q{q}: the correct option is clearly the longest ({w})")
        nums = [number(o) for o in opts]
        if all(v is not None for v in nums) and nums != sorted(nums):
            print(f"note Q{q}: numeric options not in ascending order {nums}")
    for p in problems:
        print("PROBLEM", p)
    print("OK" if not problems else f"{len(problems)} problem(s)")
    sys.exit(1 if problems else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("spec")
    b.add_argument("questions")
    b.add_argument("--out", required=True)
    c = sub.add_parser("check")
    c.add_argument("spec")
    c.add_argument("questions")
    c.add_argument("key")
    a = ap.parse_args()
    build(a) if a.cmd == "build" else check(a)


if __name__ == "__main__":
    main()

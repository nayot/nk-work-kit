"""Draw the bubble answer sheet for an exam spec and build it to PDF with XeLaTeX.

    python3 exam_omr_sheet.py SPEC.json --out DIR      -> DIR/answer_sheet.tex, DIR/answer_sheet.pdf

Needs xelatex (TeX Live) and the Sarabun font. Positions come from exam_omr_layout.py.

HARD-WON DETAILS
- The reader finds the page by the four 8 mm black squares and then expects every bubble exactly
  where the layout puts it. Print and photocopy the sheet at 100 % ("Actual size"): "Fit to page"
  or a copier's reduce setting moves the bubbles. Tell the copy room.
- No letters are printed inside the bubbles (they would read as a faint mark); the A-E headings
  sit above each block instead.
- Keep the sheet single-sided and away from the question paper so it can be scanned as one stack.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exam_omr_layout as G  # noqa: E402


def X(v):
    return f"{v:.2f}mm"


def Y(v):
    return f"{-v:.2f}mm"


def tex_escape(s):
    return str(s).replace("&", r"\&").replace("%", r"\%").replace("_", r"\_").replace("#", r"\#")


def body(L):
    o = ["\\begin{tikzpicture}[remember picture,overlay,shift={(current page.north west)}]\n"]
    a = o.append
    for x, y in G.FIDUCIALS.values():
        a(f"\\fill[black] ({X(x)},{Y(y)}) rectangle ++({X(G.FID_SIZE)},{Y(G.FID_SIZE)});\n")
    x0 = L.id_x0 - L.id_col_pitch / 2
    for c in range(L.id_digits):
        cx = L.id_x0 + c * L.id_col_pitch
        a(f"\\draw[thick] ({X(cx - 3.2)},{Y(L.id_box_y)}) rectangle ({X(cx + 3.2)},{Y(L.id_box_y + 7)});\n")
        for d in range(10):
            bx, by = L.id_bubble(c, d)
            a(f"\\draw[line width=0.35pt] ({X(bx)},{Y(by)}) circle ({X(L.bubble_r)});\n")
    for d in range(10):
        _, by = L.id_bubble(0, d)
        a(f"\\node[font=\\scriptsize,gray] at ({X(L.id_x0 - 6.5)},{Y(by)}) {{{d}}};\n")
        a(f"\\node[font=\\scriptsize,gray] at ({X(L.id_right + 6.5)},{Y(by)}) {{{d}}};\n")
    a(f"\\draw[gray] ({X(x0 - 4)},{Y(L.id_box_y - 6.5)}) rectangle ({X(L.id_right + L.id_col_pitch / 2 + 4)},{Y(L.id_bubble(0, 9)[1] + 4.5)});\n")
    for q in range(1, L.n_q + 1):
        lx, ly = L.answer_label(q)
        a(f"\\node[anchor=east,font=\\small\\bfseries] at ({X(lx + 4.5)},{Y(ly)}) {{{q}}};\n")
        for i in range(len(L.choices)):
            bx, by = L.answer_bubble(q, i)
            a(f"\\draw[line width=0.35pt] ({X(bx)},{Y(by)}) circle ({X(L.bubble_r)});\n")
        row = (q - 1) % L.rows
        if row % 5 == 4 and row != L.rows - 1 and q != L.n_q:
            a(f"\\draw[gray!60,line width=0.3pt] ({X(lx - 2)},{Y(ly + L.row_pitch / 2)}) -- ++({X(L.block_w)},0);\n")
    for b, bx0 in enumerate(L.block_x):
        for i, ch in enumerate(L.choices):
            bx, by = L.answer_bubble(b * L.rows + 1, i)
            a(f"\\node[font=\\small\\bfseries] at ({X(bx)},{Y(by - 6)}) {{{ch}}};\n")
        a(f"\\draw[gray] ({X(bx0 - 3)},{Y(L.ans_y0 - 10)}) rectangle ({X(bx0 - 3 + L.block_w + 3)},{Y(L.ans_y0 + (L.rows - 1) * L.row_pitch + 4)});\n")
    for i, bit in enumerate(L.fingerprint()):
        fx, fy = L.fp_square(i)
        if bit:
            a(f"\\fill[black] ({X(fx)},{Y(fy)}) rectangle ++({X(L.FP_SIZE)},{Y(L.FP_SIZE)});\n")
    a(f"\\node[font=\\tiny,gray,anchor=south] at ({X(G.PAGE_W / 2)},{Y(G.PAGE_H - 7.5)}) {{layout {L.code()}}};\n")
    a("\\end{tikzpicture}\n")
    return "".join(o)


def header(spec, L):
    who = spec.get("candidate_word", "นิสิต")
    ix = max(94.0, L.id_right + 14)
    iw = 190.0 - ix
    logo = spec.get("logo") or ""
    title_x = 40 if logo else 24
    parts = spec.get("parts") or []
    ppq = spec.get('points_per_question', 1)
    boxes = [f"{p['name']} ({(p['last'] - p['first'] + 1) * ppq:g})" for p in parts] + [f"รวม ({spec['n_questions'] * ppq:g})"]
    fs = "\\small" if iw >= 80 else "\\footnotesize"
    bw = min(30.0, iw / len(boxes))
    s = [r"""\documentclass[11pt,a4paper]{article}
\usepackage[a4paper,margin=0mm]{geometry}
\usepackage{fontspec}
\setmainfont{Sarabun}[Script=Thai]
\XeTeXlinebreaklocale "th"
\XeTeXlinebreakskip = 0pt plus 1pt
\usepackage{tikz}
\usepackage{graphicx}
\pagestyle{empty}
\setlength{\parindent}{0pt}
\begin{document}
\null
\begin{tikzpicture}[remember picture,overlay,shift={(current page.north west)}]
"""]
    if logo:
        s.append(f"  \\node[anchor=north west] at (24mm,-11mm) {{\\includegraphics[height=13mm]{{{Path(logo).resolve()}}}}};\n")
    s.append(f"""  \\node[anchor=north west,align=left] at ({title_x}mm,-12mm) {{%
    {{\\large\\bfseries กระดาษคำตอบ {tex_escape(spec.get('exam_th', 'สอบ'))} ภาคการศึกษาที่ {spec.get('semester', '')}/{spec.get('year', '')}}}\\\\[1pt]
    {tex_escape(spec['course_code'])} {tex_escape(spec['course_th'])} \\textbullet\\ {tex_escape(spec.get('date_th', ''))} เวลา {tex_escape(spec.get('time_th', ''))}}};
  \\node[anchor=north west,align=left] at (16mm,-30mm) {{%
    ชื่อ-สกุล \\makebox[78mm]{{\\dotfill}}\\quad กลุ่ม \\makebox[14mm]{{\\dotfill}}\\quad ที่นั่งสอบ \\makebox[16mm]{{\\dotfill}}\\\\[5mm]
    ลายมือชื่อ{who} \\makebox[60mm]{{\\dotfill}}}};
  \\node[anchor=south west,font=\\small\\bfseries] at ({X(L.id_x0 - L.id_col_pitch / 2)},{Y(L.id_box_y - 1)}) {{{tex_escape(spec.get('id_label', 'รหัสนิสิต'))}}};
  \\node[anchor=north west,text width={iw:.1f}mm,align=left,font={fs}] (ins) at ({ix:.1f}mm,-57mm) {{%
    \\textbf{{วิธีตอบ (กระดาษนี้ตรวจด้วยเครื่องอ่านอัตโนมัติ)}}
    \\begin{{enumerate}}\\setlength{{\\itemsep}}{{0pt}}\\setlength{{\\parsep}}{{0pt}}\\setlength{{\\leftmargin}}{{4mm}}
      \\item ใช้\\textbf{{ดินสอ 2B}} ระบายให้\\textbf{{เต็มวงกลม}}และเข้ม ข้อละ 1 คำตอบ
      \\item เขียน{tex_escape(spec.get('id_label', 'รหัส')).split(' (')[0]} {L.id_digits} หลักในช่อง แล้วระบายตัวเลขใต้แต่ละช่อง
      \\item จะเปลี่ยนคำตอบ ให้\\textbf{{ลบให้สะอาด}}ก่อน ห้ามขีดฆ่า
      \\item ห้ามพับ ห้ามเขียนหรือทำเครื่องหมายใกล้สี่เหลี่ยมดำที่มุมกระดาษ
      \\item ส่งกระดาษคำตอบนี้แยกจากชุดข้อสอบ
    \\end{{enumerate}}}};
  \\begin{{scope}}[shift={{([yshift=-2mm]ins.south west)}}]
  \\node[anchor=north west,font=\\small] at (0,0) {{ตัวอย่าง\\quad ถูก}};
  \\fill[black] (24mm,-3mm) circle (2.3mm);
  \\node[anchor=north west,font=\\small] at (30mm,0) {{ผิด}};
  \\draw (40mm,-3mm) circle (2.3mm); \\draw[thick] (38.4mm,-1.4mm) -- (41.6mm,-4.6mm) (38.4mm,-4.6mm) -- (41.6mm,-1.4mm);
  \\draw (47mm,-3mm) circle (2.3mm); \\draw[thick] (45.6mm,-3mm) -- (46.6mm,-4.2mm) -- (48.6mm,-1.6mm);
  \\draw (54mm,-3mm) circle (2.3mm); \\fill[black] (54mm,-3mm) circle (0.8mm);
  \\node[anchor=north west,font=\\small] at (0,-8mm) {{สำหรับผู้ตรวจ}};
""")
    for i, t in enumerate(boxes):
        s.append(f"  \\draw ({i * bw:.1f}mm,-14mm) rectangle ++({bw:.1f}mm,-12mm);\n"
                 f"  \\node[font=\\scriptsize,anchor=north,text width={bw - 1:.1f}mm,align=center] at ({i * bw + bw / 2:.1f}mm,-14.5mm) {{{tex_escape(t)}}};\n")
    s.append("  \\end{scope}\n\\end{tikzpicture}\n\\input{answer_sheet_body.tex}\n\\end{document}\n")
    return "".join(s)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("spec")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    spec = G.load_spec(a.spec)
    L = G.Layout(spec)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "answer_sheet_body.tex").write_text("% Generated by exam_omr_sheet.py. Do not edit.\n" + body(L), encoding="utf-8")
    (out / "answer_sheet.tex").write_text(header(spec, L), encoding="utf-8")
    (out / "layout.json").write_text(json.dumps(L.as_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    for _ in range(2):
        r = subprocess.run(["xelatex", "-interaction=nonstopmode", "answer_sheet.tex"], cwd=out,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for ext in ("aux", "log"):
        (out / f"answer_sheet.{ext}").unlink(missing_ok=True)
    pdf = out / "answer_sheet.pdf"
    if r.returncode or not pdf.exists():
        sys.exit("xelatex failed:\n" + r.stdout[-2000:])
    print(f"{pdf}  ({L.n_q} questions x {len(L.choices)} choices, {L.id_digits}-digit ID). Print at 100 %.")


if __name__ == "__main__":
    main()

"""Fill the faculty's ใบปะหน้าข้อสอบ (exam cover sheet, .docx) from an exam spec.

    python3 exam_cover_form.py SPEC.json --out DIR [--template templates/exam/ใบปะหน้าข้อสอบ.docx]
        -> DIR/ใบปะหน้าข้อสอบ_<course>.docx and .pdf (PDF via LibreOffice when soffice is on PATH)

The student fills in name, ID, group and ลำดับที่ในใบเซ็นชื่อ themselves; those stay blank.
Pages written = spec paper_pages + 1 (this cover sheet goes on top of the paper).

HARD-WON DETAILS
- Word splits a visible line into many <w:t> runs, and the dotted leaders are runs of their own.
  Each line is found by its printed label; within it, every run made only of dots/ellipses is a
  blank, and consecutive dotted runs form one field (the first gets the value, the rest go empty).
- Every label is asserted before anything is written, so a revised faculty template fails loudly
  instead of filling the wrong line. The form exists twice for some lines (a text-box fallback),
  so the same edit is applied to every paragraph that matches.
- The ไม่อนุญาต/อนุญาต choice is made by deleting the word that doesn't apply (and its slash).
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

DOTS = re.compile(r"^[\s.…·]+$")
T_RE = re.compile(r"(<w:t(?: [^>]*)?>)([^<]*)(</w:t>)")


def x(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fill_fields(para, values):
    """Replace successive dotted fields in the paragraph with values (None = leave)."""
    vals = list(values)
    prev_dots = False
    out, pos = [], 0
    for m in T_RE.finditer(para):
        text = m.group(2)
        new = None
        if text and DOTS.match(text) and any(ch in text for ch in ".…"):
            if not prev_dots and vals:
                v = vals.pop(0)
                new = None if v is None else f" {v} "
            elif prev_dots and new is None:
                new = ""
            prev_dots = True
        else:
            prev_dots = False if text.strip() else prev_dots
        out.append(para[pos:m.start()])
        if new is None:
            out.append(m.group(0))
        else:
            out.append('<w:t xml:space="preserve">' + x(new) + "</w:t>")
        pos = m.end()
    out.append(para[pos:])
    return "".join(out)


def blank_words(para, words):
    """Empty the runs whose text is exactly one of `words` (first occurrence of each, in order)."""
    todo = list(words)
    def sub(m):
        if todo and m.group(2).strip() == todo[0]:
            todo.pop(0)
            return '<w:t xml:space="preserve"></w:t>'
        return m.group(0)
    return T_RE.sub(sub, para)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("spec")
    ap.add_argument("--out", required=True)
    ap.add_argument("--template", default=str(Path(__file__).resolve().parent.parent / "templates" / "exam" / "ใบปะหน้าข้อสอบ.docx"))
    a = ap.parse_args()
    s = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    who = s.get("candidate_word", "นิสิต")
    sheet = f"กระดาษคำตอบแบบระบายวงกลม 1 แผ่น (แจกแยกจากชุดข้อสอบ)"
    calc = s.get("calculator") or ""
    rules = [
        ("รหัสวิชา", lambda p: fill_fields(p, [s["course_code"], f"{s['course_th']} ({s.get('course_en', '')})".replace(" ()", "")])),
        ("สอบวันที่", lambda p: fill_fields(p, [s.get("date_th", ""), s.get("time_th", "")])),
        ("อาจารย์ผู้สอน", lambda p: fill_fields(p, [" และ ".join(s.get("instructors", [])), "", ""])),
        ("ข้อสอบมีทั้งหมด", lambda p: fill_fields(p, [s["n_questions"], int(s.get("paper_pages", 0)) + 1])),
        ("สมุดคำตอบจำนวน", lambda p: fill_fields(p, ["–"])),
        ("แผ่น", lambda p: fill_fields(p, ["–"]) if "A4" in p else p),
        ("อื่นๆ", lambda p: fill_fields(p, [sheet]) if "ตำรา" not in p else p),
        ("ตำราและเอกสารใดๆ", lambda p: fill_fields(blank_words(p, ["/", "อนุญาต"] if s.get("closed_book", True) else ["ไม่อนุญาต", "/"]), ["", ""])),
        ("ให้ใช้เครื่องคำนวณ", lambda p: fill_fields(blank_words(p, ["ไม่อนุญาต", "/"] if calc else ["/", "อนุญาต"]),
                                                     [f"{calc} ({s['extra_rule']})" if calc and s.get("extra_rule") else (calc or "")])),
        ("ให้ทำใน", lambda p: T_RE.sub(lambda m: ('<w:t xml:space="preserve">กระดาษคำตอบแบบระบายวงกลม (ใช้ดินสอ 2B)</w:t>' if m.group(2) == "ข้อสอบ"
                                                  else '<w:t xml:space="preserve"></w:t>' if m.group(2).strip() in ("/", "สมุดคำตอบ", "กระดาษ", "A", "…", ".....") else m.group(0)), p)),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(a.template) as z:
            z.extractall(tmp)
            names = z.namelist()
        doc = Path(tmp) / "word" / "document.xml"
        xml = doc.read_text(encoding="utf-8")
        paras = list(re.finditer(r"<w:p[ >].*?</w:p>", xml, re.S))
        texts = ["".join(m.group(2) for m in T_RE.finditer(p.group(0))) for p in paras]
        for label, _ in rules:
            if not any(label in t for t in texts):
                sys.exit(f"template changed: no line with '{label}'. Update exam_cover_form.py before using it.")
        out, pos = [], 0
        for p, t in zip(paras, texts):
            para = p.group(0)
            for label, fn in rules:
                if label in t:
                    para = fn(para)
                    break
            out.append(xml[pos:p.start()])
            out.append(para)
            pos = p.end()
        out.append(xml[pos:])
        doc.write_text("".join(out), encoding="utf-8")
        d = Path(a.out)
        d.mkdir(parents=True, exist_ok=True)
        dst = d / f"ใบปะหน้าข้อสอบ_{s['course_code']}.docx"
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
            for n in names:
                z.write(Path(tmp) / n, n)
    print(dst)
    if shutil.which("soffice") or shutil.which("libreoffice"):
        subprocess.run([shutil.which("soffice") or shutil.which("libreoffice"), "--headless", "--convert-to", "pdf",
                        "--outdir", str(d), str(dst)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(dst.with_suffix(".pdf"))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Prepare a มคอ.3 (TQF 3 course specification) for entry in tqf.buu.ac.th, stdlib only.

The tqf3 skill drives the TQF BUU pages in the user's own browser (Claude in
Chrome); this script only checks a spec JSON and prints the texts and page
scripts those pages need. It never touches the site.

    python3 tqf3.py check  spec.json              -> validate: weights, hours, CLO/PLO links, unsupported characters
    python3 tqf3.py text   spec.json [--section 1|32|5|6]  -> plain texts to paste (form_input / type)
    python3 tqf3.py js     spec.json --section 1|2|31|41|42|5|6 [--clo N] [--objective N] [--no-save]
                                                  -> JavaScript for the open edit page (javascript_exec)

Spec JSON: see examples/tqf3_spec.json. Weeks are the system's row numbers
(สัปดาห์ที่ 1..33); hours should add up to the credit's lecture hours
(3(3-0-6) -> 45). CLO numbers are the ลำดับ typed into หมวด 2 and must match
what the system shows as "N. ..." in its option lists.

HARD-WON DETAILS (tqf.buu.ac.th, verified 01.11.2026):
- A course appears under อาจารย์ → มคอ.3 only after "ปรับปรุงรายวิชาจากระบบทะเบียน"
  (the link under the empty list); all groups of a course share one มคอ.3.
- The database drops characters outside Thai/Latin: Greek letters and math
  symbols (∇ × μ Γ λ η δ √ π ≥ ²) come back as "?". Write them as words
  (grad, Gamma, lambda, delta, sqrt, "80 ขึ้นไป"). `check` flags them.
- หมวด 2: CLOs are added one per form (ลำดับที่, รายละเอียด, radio หลัก/รอง) under
  the TQF domain's "เพิ่มผลการเรียนรู้ของรายวิชา" link; the left column shows the
  curriculum the system maps the course to (it can be another department's),
  with ●/○ per PLO. There is no edit: a CLO can only be deleted, which breaks
  its links in 3.1 and 4.1, so get the texts right before 3.1.
- หมวด 3.1: fields DOC331_DETAIL[w], DOC331_ACTIVITY[w], DOC331_HOUR[w] and a
  chosen multi-select DOC331_LOC[w][] whose option texts are "N. <CLO text>";
  after setting options trigger jQuery 'chosen:updated'. Rows with an empty
  topic are not saved. One บันทึก (input[name=btn_submit]) saves all rows.
- หมวด 4.1: one row per CLO (rows carry hidden ORDER[rowid]); fields
  DOC341N65_OBJECTIVE[rowid][] (objectives "N. ..."), _MEASURE, _DURATION and
  hidden _RATE (the %). The CLO cell holds the CLO text without its number.
- หมวด 4.2: DOC342_CONFIGURATION[i]/DOC342_RATE[i] (7 rows) and
  DOC343_GRADE[i]/DOC343_SCORE[i] (15 rows). หมวด 5: DOC35_MAINTEXT,
  DOC35_GUIDETEXT. หมวด 6: DOC36_PROBLEMS, DOC36_ISSUES, DOC36_VERIFICATION.
- หมวด 3.2: a file input (แนบแผนการสอน) for the PDF and a textarea (advising
  hours). "ดูรายละเอียด มคอ.3" renders everything; search it for "?" after saving.
- "ส่ง มคอ.3" (submit to the programme) is a separate action; the skill never
  presses it without the user's explicit word.
"""
import argparse
import json
import re
import sys

DOMAINS = {
    1: "คุณธรรม จริยธรรม",
    2: "ความรู้",
    3: "ทักษะทางปัญญา",
    4: "ทักษะความสัมพันธ์ระหว่างบุคคลและความรับผิดชอบ",
    5: "ทักษะการวิเคราะห์เชิงตัวเลข การสื่อสารและการใช้เทคโนโลยีสารสนเทศ",
    6: "ทักษะทางวิชาชีพและความเป็นผู้ประกอบการ",
}

# Characters the TQF database stores as "?", with plain replacements to suggest.
UNSUPPORTED = {
    "∇": "grad", "×": "x", "·": ".", "−": "-", "≥": ">=", "≤": "<=", "≈": "~", "≠": "!=",
    "√": "sqrt", "²": "^2", "³": "^3", "½": "1/2", "°": " องศา", "∞": "inf", "∂": "d", "∫": "int",
    "μ": "mu", "Γ": "Gamma", "γ": "gamma", "λ": "lambda", "η": "eta", "δ": "delta", "π": "pi",
    "σ": "sigma", "ε": "epsilon", "ω": "omega", "Ω": "ohm", "ρ": "rho", "θ": "theta", "φ": "phi",
    "Φ": "Phi", "Λ": "Lambda", "α": "alpha", "β": "beta", "τ": "tau", "ν": "nu", "κ": "kappa",
    "š": "s", "č": "c", "ž": "z", "ć": "c", "ñ": "n", "ü": "u", "ö": "o", "ä": "a", "é": "e", "è": "e",
}
OK_PUNCT = set("–—“”‘’…•·")  # en/em dash and curly quotes survive (observed)


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def walk_strings(obj, prefix=""):
    if isinstance(obj, str):
        yield prefix, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_strings(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_strings(v, f"{prefix}[{i}]")


def check(spec):
    errors, warnings = [], []
    clos = {c["n"]: c for c in spec.get("clos", [])}
    if not clos:
        errors.append("no clos")
    for c in spec.get("clos", []):
        if c.get("domain") not in DOMAINS:
            errors.append(f"CLO {c.get('n')}: domain must be 1-6")
        if not c.get("plos"):
            warnings.append(f"CLO {c.get('n')}: no PLO codes listed")
    objs = spec.get("section1", {}).get("objectives", [])
    # hours
    lec = spec.get("lecture_hours")
    hours = sum(int(w.get("h", 0)) for w in spec.get("weeks", []))
    if lec is not None and hours != lec:
        errors.append(f"weeks add up to {hours} h, expected {lec} (lecture hours of the credit x 15)")
    for w in spec.get("weeks", []):
        if not w.get("topic"):
            errors.append(f"week {w.get('w')}: empty topic (the system would not save the row)")
        for n in w.get("clo", []):
            if n not in clos:
                errors.append(f"week {w.get('w')}: unknown CLO {n}")
    # measures and weights
    total = 0
    for m in spec.get("measures", []):
        if m.get("clo") not in clos:
            errors.append(f"measure for unknown CLO {m.get('clo')}")
        for o in m.get("objectives", []):
            if not (1 <= int(o) <= len(objs)):
                errors.append(f"measure CLO {m.get('clo')}: objective {o} not in section1.objectives")
        total += float(m.get("rate", 0))
    if spec.get("measures") and abs(total - 100) > 1e-6:
        errors.append(f"measure rates add up to {total:g}, not 100")
    missing = [n for n in clos if n not in {m.get("clo") for m in spec.get("measures", [])}]
    if missing:
        warnings.append(f"CLOs without a measure row: {missing}")
    comp = sum(float(c.get("rate", 0)) for c in spec.get("components", []))
    if spec.get("components") and abs(comp - 100) > 1e-6:
        errors.append(f"components add up to {comp:g}, not 100")
    if len(spec.get("components", [])) > 7:
        errors.append("the system has 7 component rows")
    if len(spec.get("grades", [])) > 15:
        errors.append("the system has 15 grade rows")
    # characters
    for where, s in walk_strings(spec):
        bad = sorted({ch for ch in s if ch in UNSUPPORTED or (ord(ch) > 0x24F and not 0x0E00 <= ord(ch) <= 0x0E7F and ch not in OK_PUNCT)})
        if bad:
            hint = ", ".join(f"{b}->{UNSUPPORTED.get(b, '?')}" for b in bad)
            warnings.append(f"{where}: characters the TQF database drops: {hint}")
    return errors, warnings


def js_str(s):
    return json.dumps(s, ensure_ascii=False)


def js_section1(spec, objective=None):
    """One script per objective: fills the add-objective modal and saves (page reloads)."""
    objs = spec["section1"]["objectives"]
    out = []
    for i, text in enumerate(objs, 1):
        if objective and i != objective:
            continue
        out.append(
            "/* objective %d: click +++เพิ่มวัตถุประสงค์ first, then run */\n" % i +
            "const m=[...document.querySelectorAll('input[type=text],textarea')].filter(e=>e.offsetParent!==null&&/ลำดับ|วัตถุประสงค์/.test(e.placeholder||''));\n"
            "const o=m.find(e=>/ลำดับ/.test(e.placeholder)),t=m.find(e=>/วัตถุประสงค์/.test(e.placeholder));\n"
            f"o.value={js_str(str(i))};t.value={js_str(text)};\n"
            "const b=[...document.querySelectorAll('button[type=submit]')].find(b=>b.offsetParent!==null&&b.innerText.trim()==='บันทึก');\n"
            "b?b.click():'no save button';"
        )
    return "\n\n".join(out)


def js_section2(spec, clo=None):
    """One script per CLO: fills the add-CLO form (open the domain's เพิ่มผลการเรียนรู้ link first)."""
    out = []
    for c in spec["clos"]:
        if clo and c["n"] != clo:
            continue
        primary = "1" if c.get("primary", True) else "2"
        out.append(
            f"/* CLO {c['n']} -> domain {c['domain']} ({DOMAINS[c['domain']]}); PLOs {', '.join(c.get('plos', []))} */\n"
            f"document.querySelector('input[type=text]').value={js_str(str(c['n']))};\n"
            f"document.querySelector('textarea').value={js_str(c['text'])};\n"
            f"document.querySelector('input[type=radio][value=\"{primary}\"]').checked=true;\n"
            "document.querySelector('button[type=submit],input[type=submit]').click();"
        )
    return "\n\n".join(out)


def js_section31(spec, save=True):
    rows = [{"w": w["w"], "h": w.get("h", 0), "clo": w.get("clo", []), "topic": w["topic"], "method": w.get("method", "")}
            for w in spec["weeks"]]
    return (
        f"const W={json.dumps(rows, ensure_ascii=False)};\n"
        "let done=[];\n"
        "for(const r of W){\n"
        "  const d=document.getElementById(`DOC331_DETAIL[${r.w}]`),a=document.getElementById(`DOC331_ACTIVITY[${r.w}]`),"
        "h=document.getElementById(`DOC331_HOUR[${r.w}]`),s=document.getElementById(`DOC331_LOC[${r.w}][]`);\n"
        "  if(!d||!a||!h||!s){done.push('missing row '+r.w);continue;}\n"
        "  d.value=r.topic;a.value=r.method;h.value=String(r.h);\n"
        "  const want=new Set(r.clo.map(String));\n"
        "  for(const o of s.options){const n=(o.text.match(/^\\s*(\\d+)\\./)||[])[1];o.selected=!!n&&want.has(n);}\n"
        "  const got=[...s.selectedOptions].length;if(got!==want.size)done.push('week '+r.w+': CLO options matched '+got+'/'+want.size);\n"
        "  if(window.jQuery)jQuery(s).trigger('chosen:updated');\n"
        "  done.push(r.w+':'+got);\n"
        "}\n"
        + ("const ok=!done.some(x=>/missing|matched/.test(x));if(ok)document.querySelector('input[name=btn_submit]').click();\n"
           "done.join(' ')+(ok?' | SAVED':' | NOT SAVED (fix the problems above)');" if save else "done.join(' ')+' | not saved (--no-save)';")
    )


def js_section41(spec, save=True):
    clos = {c["n"]: c["text"] for c in spec["clos"]}
    rows = [{"clo": m["clo"], "text": clos[m["clo"]], "obj": [str(o) for o in m.get("objectives", [])],
             "measure": m.get("measure", ""), "duration": m.get("duration", ""), "rate": m.get("rate", 0)}
            for m in spec["measures"]]
    return (
        f"const R={json.dumps(rows, ensure_ascii=False)};\n"
        "const norm=s=>s.replace(/\\s+/g,' ').trim();\n"
        "const sels=[...document.querySelectorAll(\"select[name^='DOC341N65_OBJECTIVE[']\")];let out=[];\n"
        "for(const r of R){\n"
        "  const s=sels.find(s=>{const tr=s.closest('tr');return tr&&norm(tr.innerText).includes(norm(r.text).slice(0,60));});\n"
        "  if(!s){out.push('CLO '+r.clo+': row not found');continue;}\n"
        "  const id=s.name.match(/\\[(\\d+)\\]/)[1];const tr=s.closest('tr');\n"
        "  for(const o of s.options){const n=(o.text.match(/^\\s*(\\d+)\\./)||[])[1];o.selected=!!n&&r.obj.includes(n);}\n"
        "  if(window.jQuery)jQuery(s).trigger('chosen:updated');\n"
        "  tr.querySelector(`textarea[name='DOC341N65_MEASURE[${id}]']`).value=r.measure;\n"
        "  tr.querySelector(`textarea[name='DOC341N65_DURATION[${id}]']`).value=r.duration;\n"
        "  const rt=document.querySelector(`input[name='DOC341N65_RATE[${id}]']`);if(rt)rt.value=String(r.rate);\n"
        "  out.push('CLO '+r.clo+':'+[...s.selectedOptions].length+'/'+r.obj.length+' obj, '+r.rate+'%');\n"
        "}\n"
        + ("const ok=!out.some(x=>/not found/.test(x));if(ok)document.querySelector('input[name=btn_submit]').click();\n"
           "out.join(' ')+(ok?' | SAVED':' | NOT SAVED');" if save else "out.join(' ')+' | not saved (--no-save)';")
    )


def js_section42(spec, save=True):
    comps = [[c["name"], c["rate"]] for c in spec["components"]]
    grades = [[g[0], g[1]] for g in spec["grades"]]
    return (
        f"const C={json.dumps(comps, ensure_ascii=False)};const G={json.dumps(grades, ensure_ascii=False)};\n"
        "C.forEach((c,i)=>{document.querySelector(`input[name='DOC342_CONFIGURATION[${i+1}]']`).value=c[0];"
        "document.querySelector(`input[name='DOC342_RATE[${i+1}]']`).value=String(c[1]);});\n"
        "G.forEach((g,i)=>{document.querySelector(`input[name='DOC343_GRADE[${i+1}]']`).value=g[0];"
        "document.querySelector(`input[name='DOC343_SCORE[${i+1}]']`).value=g[1];});\n"
        + ("document.querySelector('input[name=btn_submit]').click();" if save else "")
        + "'components '+C.reduce((a,c)=>a+Number(c[1]),0)+'% , grades '+G.length"
    )


def js_section5(spec, save=True):
    r = spec["resources"]
    return (
        f"document.querySelector(\"textarea[name='DOC35_MAINTEXT']\").value={js_str(r['main'])};\n"
        f"document.querySelector(\"textarea[name='DOC35_GUIDETEXT']\").value={js_str(r['guide'])};\n"
        + ("document.querySelector('input[name=btn_submit]').click();" if save else "") + "'ok'"
    )


def js_section6(spec, save=True):
    r = spec["review"]
    return (
        f"document.querySelector(\"textarea[name='DOC36_PROBLEMS']\").value={js_str(r['problems'])};\n"
        f"document.querySelector(\"textarea[name='DOC36_ISSUES']\").value={js_str(r['issues'])};\n"
        f"document.querySelector(\"textarea[name='DOC36_VERIFICATION']\").value={js_str(r['verification'])};\n"
        + ("document.querySelector('input[name=btn_submit]').click();" if save else "") + "'ok'"
    )


def text(spec, section):
    s1 = spec.get("section1", {})
    if section in (None, "1"):
        print("# หมวด 1 (type into the form; items 1, 2, 4, 8 are prefilled by the system)")
        for k in ("curriculum_type", "coordinator", "semester_year", "place"):
            print(f"\n## {k}\n{s1.get(k, '')}")
        print("\n## date (datepicker; pick the day)\n" + s1.get("date", ""))
        for i, o in enumerate(s1.get("objectives", []), 1):
            print(f"\n## objective {i}\n{o}")
    if section in (None, "32"):
        print("\n# หมวด 3.2 advising hours\n" + spec.get("advising", ""))
        if spec.get("plan_pdf"):
            print("\n# หมวด 3.2 file to upload\n" + spec["plan_pdf"])
    if section in (None, "5"):
        print("\n# หมวด 5 main\n" + spec["resources"]["main"] + "\n\n# หมวด 5 guide\n" + spec["resources"]["guide"])
    if section in (None, "6"):
        r = spec["review"]
        print("\n# หมวด 6\n" + r["problems"] + "\n\n" + r["issues"] + "\n\n" + r["verification"])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("spec")
    t = sub.add_parser("text"); t.add_argument("spec"); t.add_argument("--section", choices=["1", "32", "5", "6"])
    j = sub.add_parser("js"); j.add_argument("spec"); j.add_argument("--section", required=True, choices=["1", "2", "31", "41", "42", "5", "6"])
    j.add_argument("--clo", type=int); j.add_argument("--objective", type=int); j.add_argument("--no-save", action="store_true")
    a = ap.parse_args()
    spec = load(a.spec)
    if a.cmd == "check":
        errors, warnings = check(spec)
        for w in warnings:
            print("WARN", w)
        for e in errors:
            print("ERROR", e)
        print(f"{len(spec.get('clos', []))} CLOs, {len(spec.get('weeks', []))} weeks, "
              f"{sum(int(w.get('h', 0)) for w in spec.get('weeks', []))} h, {len(spec.get('measures', []))} measure rows")
        sys.exit(1 if errors else 0)
    if a.cmd == "text":
        text(spec, a.section); return
    save = not a.no_save
    fn = {"1": lambda: js_section1(spec, a.objective), "2": lambda: js_section2(spec, a.clo),
          "31": lambda: js_section31(spec, save), "41": lambda: js_section41(spec, save),
          "42": lambda: js_section42(spec, save), "5": lambda: js_section5(spec, save), "6": lambda: js_section6(spec, save)}
    print(fn[a.section]())


if __name__ == "__main__":
    main()

---
name: tqf3
description: Fill in a มคอ.3 (TQF 3, รายละเอียดของรายวิชา / course specification) in BUU's TQF system tqf.buu.ac.th from a course spec JSON — all eight sections (ข้อมูลรายวิชา, CLOs per TQF domain, กำหนดการสอน week table, แผนการสอน PDF, การวัดผล per CLO, องค์ประกอบคะแนนและเกณฑ์เกรด, ทรัพยากร, การประเมินและปรับปรุง) — in the user's own signed-in Chrome, checking the saved result page afterwards. Use when the user says "กรอก มคอ.3", "บันทึก มคอ.3 ในระบบ TQF", "ทำ มคอ.3", "ใส่ CLO ในระบบ TQF", "fill in the TQF 3", "enter the course spec in TQF BUU", "มคอ.3 ของวิชา…", or has a มคอ.3 draft (PDF/LaTeX/notes) that must go into tqf.buu.ac.th. Never presses ส่ง มคอ.3 by itself.
version: 1.0.0
---

# มคอ.3 into tqf.buu.ac.th

The TQF BUU system has no API. Work in the user's own Chrome through Claude in
Chrome (load the browser tools first; `javascript_tool` and `file_upload` too).
A helper checks the spec and prints the texts and page scripts; it never
touches the site:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tqf3.py" check spec.json
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tqf3.py" text  spec.json [--section 1|32|5|6]
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tqf3.py" js    spec.json --section 1|2|31|41|42|5|6 [--clo N] [--objective N] [--no-save]
```

If `CLAUDE_PLUGIN_ROOT` is not set, the script is in `<plugin-root>/scripts/`.
The spec schema is `examples/tqf3_spec.json`: section 1 texts and objectives,
`clos` (number, TQF domain 1–6, PLO codes, text), `weeks` (the system's
สัปดาห์ที่ rows, hours, CLO numbers, topic, activity), `measures` per CLO
(objectives, measure, timing, %), `components`, `grades`, `resources`, `review`,
`advising`, `plan_pdf`. Build it from the user's draft (a มคอ.3 PDF or LaTeX
from the course project, the outline, the curriculum notes). Keep it in the
course project, not in this plugin.

## Rules

- **The user signs in.** Open `https://tqf.buu.ac.th`; if the header does not
  show the user's name, stop and let them log in.
- **Run `check` first and fix every ERROR.** Hours must add up to the credit's
  lecture hours (3(3-0-6) → 45), measure rates and components to 100. Replace
  the characters it flags: the database stores Greek letters and math symbols
  (∇ × μ Γ λ η δ √ π ≥ ²) as "?". Write grad, Gamma, lambda, delta, sqrt,
  "80 ขึ้นไป".
- **Read the system's PLO mapping before entering CLOs** (หมวดที่ 2, left
  column). The course may be mapped to another department's curriculum
  (course codes carry the owning department) with ● primary / ○ secondary per
  PLO. If the draft's CLOs leave a primary domain empty, or map to PLOs the
  system does not list, show the user the system's list and agree the CLO set
  and domains before adding anything.
- **CLOs cannot be edited, only deleted**, and deleting one breaks its links in
  3.1 and 4.1. Get texts right before filling 3.1. Type the plain text; the
  system adds "N." itself (don't write "CLO 6 …" into the text).
- **Save per section and check the banner** (เพิ่มข้อมูลเรียบร้อยแล้ว /
  แก้ไขข้อมูลเรียบร้อยแล้ว). The page scripts save only when every row was
  matched; use `--no-save` first when unsure.
- **Never press ส่ง มคอ.3** (submit to the programme) unless the user says so
  for this course; saving the sections is not submitting.
- Formal Thai (อาจารย์, นิสิต); Arabic numerals (BUU rule from 01.11.2569).

## Navigation

- Left menu **อาจารย์ → มคอ.3**: set ปีการศึกษา and ภาค, ค้นหา. A course missing
  from the list: follow **"คลิกที่นี่ หากไม่มีรายวิชาปรากฏ…"**, choose the
  year/semester, and press **ปรับปรุงรายวิชาจากระบบทะเบียน** (imports the user's
  reg courses; all groups of a course share one มคอ.3). Then search again and
  click the course's **บันทึก มคอ.3** icon.
- The course page has tabs **หมวดที่ 1, 2, 3.1, 3.2, 4.1, 4.2, 5, 6**,
  **ดูรายละเอียด มคอ.3** (rendered preview) and **คัดลอก มคอ.3** (copy from an
  earlier semester — use it when the user taught the course before and only
  wants changes). Tab URLs embed the course's DOC3_ID; `read_page` gives them.

## 1. หมวดที่ 1 ข้อมูลของรายวิชา

Items 1, 2, 4, 8 and the instructor list come from reg. Type (click + `type`,
or `form_input` on the textbox refs) item 3 (curriculum/type), 6 (ผู้รับผิดชอบ),
7 (ภาค/ชั้นปี/กลุ่ม/เวลา), 9 (สถานที่); pick item 10 in the date picker (Thai
year). **บันทึก**. Then objectives: click **+++เพิ่มวัตถุประสงค์ของรายวิชา**, fill
ลำดับ and text (or run `js --section 1 --objective N` once the modal is open),
บันทึก; the page reloads after each one.

## 2. หมวดที่ 2 ผลลัพธ์การเรียนรู้ (CLOs)

For each CLO: click the domain's **เพิ่มผลการเรียนรู้ของรายวิชา** link (or
navigate to its href), then run `js --section 2 --clo N` (fills ลำดับที่,
รายละเอียด, radio หลัก/รอง and saves) or type the fields. Check the list
afterwards: every CLO under the right domain, numbered as in the spec.

## 3. หมวดที่ 3.1 กำหนดการสอน

The table has 33 week rows (`DOC331_*[w]`) and a chosen multi-select of the
CLOs per week (option texts "N. …"). Run `js --section 31` on the page: it
fills topic, activity, hours and CLOs for every week in the spec and clicks
บันทึก only if every row and CLO matched (the result string says SAVED). Rows
without a topic are not stored, so spare/exam weeks need a topic text (hours
may be 0).

## 4. หมวดที่ 3.2 แผนการสอน and advising hours

`form_input` the advising textarea with the `text --section 32` output. If
`plan_pdf` is set, `file_upload` it to the แนบแผนการสอน input (never click the
file button), then **บันทึก**; the page shows a ไฟล์แนบ link.

## 5. หมวดที่ 4.1 การวัดผล

One row per CLO (created from หมวด 2). Run `js --section 41`: it finds each row
by its CLO text, selects the objectives ("N."), fills วิธีการวัด, ช่วงเวลา and
the hidden สัดส่วน, and saves if all rows were found.

## 6. หมวดที่ 4.2, 5, 6

`js --section 42` (components + grade scale), `--section 5` (ตำราหลัก /
เอกสารแนะนำ, APA 7), `--section 6` (ปัญหาที่พบ, ประเด็นที่ปรับปรุง, การทวนสอบ). Each
fills and saves one page.

## Check and report

Open **ดูรายละเอียด มคอ.3** and read it (`get_page_text`): every section
present, hours total, percentages, and **no "?" characters** (a sign of a
dropped symbol — fix the spec and re-save that section). Report per section
what was saved, anything the user must confirm (grade cut-offs, PLO mapping
the system imposed, CLO wording), and that ส่ง มคอ.3 is still theirs to press.
Record the DOC3_ID and the spec path in the course project's notes.

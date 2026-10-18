---
name: exam-paper
description: Prepare, submit and mark a multiple-choice exam at BUU Faculty of Engineering — build the exam paper (one or several authors), a machine-readable bubble answer sheet (กระดาษคำตอบแบบระบาย), the department's submission forms (ใบปะหน้าข้อสอบ, ใบนำส่งรายละเอียดข้อสอบ), sign-in sheets per exam room (ใบเซ็นชื่อเข้าสอบ) from the reg.buu.ac.th roster, and after the exam read the scanned answer sheets, mark them and list unclear marks for review. Use when the user says "ออกข้อสอบ", "รวมข้อสอบ", "ส่งข้อสอบ", "ส่งต้นฉบับข้อสอบ", "ใบปะหน้าข้อสอบ", "ใบนำส่ง", "ใบเซ็นชื่อเข้าสอบ", "กระดาษคำตอบ", "ตรวจข้อสอบ", "ตรวจกระดาษคำตอบ", "draft the final exam", "bubble sheet", "OMR", "mark the exam with AI", "scan and mark the answer sheets", or asks what the exam-submission protocol needs. Also for selection tests (e.g. an applicant aptitude test) that use an applicant number instead of a student ID.
version: 1.0.0
---

# Multiple-choice exam: paper → submission → marking

Seven scripts ship with the plugin (`uv run` for the image ones, `python3` for the rest):

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/exam_paper.py"      build|check ...   # paper + pre-print checks
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/exam_omr_sheet.py"  SPEC --out DIR    # bubble answer sheet
uv run  "${CLAUDE_PLUGIN_ROOT}/scripts/exam_omr_read.py"   --spec --key ...  # read + mark scans
uv run  "${CLAUDE_PLUGIN_ROOT}/scripts/exam_omr_test.py"   --spec --sheet .. # synthetic self-test
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/exam_cover_form.py" SPEC --out DIR    # ใบปะหน้าข้อสอบ (.docx/.pdf)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/exam_transmittal.py" SPEC --roster R --out DIR   # ใบนำส่ง
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/exam_signin.py"     SPEC ROSTER --out DIR        # ใบเซ็นชื่อ
```

If `CLAUDE_PLUGIN_ROOT` is not set, they sit in `<plugin-root>/scripts/`. Each script's
docstring has the details (and a HARD-WON DETAILS block where it matters). They need
`xelatex` with the **Sarabun** font, `pdftoppm` (poppler), `uv`, and LibreOffice for the
cover sheet's PDF.

## Ground rules

- **Everything course-specific lives in one spec file** (`examples/exam_spec.json` shows every
  key). Keep the filled-in spec, the questions, the key and every output **with the course**
  (its own folder or private repo), never in this public plugin repo: they carry a phone
  number, exam rooms, student names, and the answers.
- **The answer key and the paper are confidential.** Never post either to Classroom or a shared
  folder; send the paper only to the colleague who prints it.
- **Never name the exam room in anything students see** (paper, slides, Classroom). Students
  look it up in reg. The department's forms may carry rooms.
- **Emails are drafts.** Draft in Gmail, show the user, send only on an explicit yes for that
  email. PDFs too large for the Gmail connector are attached in Chrome (Claude in Chrome
  `file_upload` on the compose window's file input), never by uploading to a shared Drive
  without being asked.
- **Every number in a question or worked answer is computed in Python**, never typed.

## The department's protocol (EE dept, Oct 2026 — check the current email each term)

The department emails the term's deadline (e.g. "กำหนดการส่งข้อสอบปลายภาค", faculty memo
อว 8116/…). Originals go to the department in one envelope, usually ~10 days before the
exam (the form's footer: 10 working days before the university's exam date):

1. **ใบนำส่งรายละเอียดข้อสอบ** stuck on the front of the envelope (lecturer signs by hand);
2. **ต้นฉบับข้อสอบ**, printed single-sided, clear pictures, with the **ใบปะหน้าข้อสอบ** on top;
3. the **ใบปะหน้าข้อสอบ** (instructions for students);
4. **ใบรายชื่อนิสิต 2 ชุด** = the sign-in sheets, per room.

With a bubble sheet also include its original, and say on the ใบนำส่ง that it must be copied
at 100 %. Copies = students sitting + spares (e.g. 160 → 170).

## Step 1 — Spec

Ask for (or read from the department email, reg and the user's notes): course code and names,
exam name, semester/year, date, time, duration, number of questions, choices (4 or 5;
`"ABCD"`, `"ABCDE"`, or Thai letters), points per question, parts (ranges, authors), ID digits
and label (8 = BUU student ID; 13 = Thai national ID for applicants), lecturers, submitter,
department, phone and LINE ID for the form, closed book, calculator rule, extra rule (e.g. no
AI/phones), copies, rooms → groups, optional logo path (official seal). Write it as JSON in
the course folder.

## Step 2 — Paper

- Questions go in a `.tex` file of `question` environments (format in `exam_paper.py`'s
  docstring). When several lecturers contribute, keep each author's text as sent (layout may
  change, wording may not); list anything you'd change for them to decide.
- Good items: one clear best answer; distractors from real mistakes (forgot √3, used ×3, line vs
  phase, rpm instead of rad/s); numeric options in ascending order; correct letters balanced;
  the correct option never conspicuously the longest; no "all of the above".
- `exam_paper.py check SPEC questions.tex key.txt` before building, then
  `exam_paper.py build SPEC questions.tex --out DIR`. Render every page with `pdftoppm` and look
  at it. Keep the key and a per-item blueprint (outcome, difficulty, minutes, working) in a
  separate instructor-only file.

## Step 3 — Answer sheet

`exam_omr_sheet.py SPEC --out DIR` → `answer_sheet.pdf` (+ `layout.json`). It fits 1–75
questions, 4–5 choices, 4–13 ID digits, and prints a layout code and a fingerprint row; the
reader refuses any sheet whose fingerprint doesn't match the spec. Then:

- run `exam_omr_test.py --spec SPEC --sheet answer_sheet.pdf --work TMP` (40 fake scans; must
  say PASS);
- **before the exam, one real test**: print ~10 sheets, fill them by hand (some messy, one
  erased, one double), scan on the copier that will be used, and read them. Synthetic tests
  don't show real pencil or a real copier.

## Step 4 — Roster from reg (Chrome)

reg.buu.ac.th, teacher login (the user signs in; never type passwords) → รายชื่อนิสิต → the
course. Each group's link opens its list. With Claude in Chrome, fetch each group page in the
page context (`fetch(link.href, {credentials:'include'})`, decode as `windows-874`), take only
student ID, title, name and the grade column (W = withdrawn) — **never GPA** — and read the
result back in chunks (the tool output truncates near 1 500 characters). Save as CSV
`group,student_id,title,name,reg_status` in the course's student-data folder and check the
per-group counts against reg's own "ลง" column. The same course page lists each group's exam
room and time ("สอบปลายภาค: … อาคาร … ห้อง …"); put rooms → groups into the spec.

## Step 5 — Forms and sign-in sheets

```
exam_cover_form.py  SPEC --out DIR                 # ใบปะหน้าข้อสอบ: pages = paper_pages + 1
exam_transmittal.py SPEC --roster ROSTER --out DIR # ใบนำส่ง: rooms, counts (minus W), copies, contact
exam_signin.py      SPEC ROSTER --out DIR          # one section per room; withdrawn left off
```

Look at each PDF. Tell the user the ใบนำส่ง still needs their signature, the withdrawn students
left off, and the counts per room. Then draft the email to whoever prints and hands in the set,
listing each file with its print instruction (single-sided; answer sheet at 100 %; sign-in
sheets ×2), the deadline, and that the key is not included; attach the PDFs in Chrome.

## Step 6 — Marking day

1. Scan all answer sheets (grayscale, 200–300 dpi, 100 %) into one PDF.
2. `uv run exam_omr_read.py --spec SPEC --key KEY.txt scans.pdf --out DIR --roster ROSTER.csv`
3. Go through `review.csv` with the crops in `review/`: double, faint, half-erased marks; IDs
   unreadable, not on the roster, withdrawn, or duplicated. Look at each crop (you can read the
   images), propose a decision per item, and let the user confirm; write them to
   `overrides.csv` (`page,item,value`). Re-run with `--overrides` until `pending` is 0.
4. Spot-check a few `annotated/` pages (green = counted, red = review), then hand over
   `results.csv` (per-question answers, a column per part, total). A sheet the reader refused
   ("does not match spec") is never marked by hand-guessing: find the right spec or re-scan.

Finish each step with a short summary: what was made, where, what the user still has to do
(sign, approve the email, run the real scan test).

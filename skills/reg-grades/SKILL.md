---
name: reg-grades
description: Set up score items (ช่วงคะแนน / เก็บคะแนน) and enter marks in BUU's registration system reg.buu.ac.th (ระบบบริการการศึกษา → ระบบสำหรับอาจารย์ → บันทึกเกรด), for every section/group of a course, matching marks to student IDs and reading every saved column back. Use when the user says "กรอกคะแนน reg", "บันทึกคะแนน", "ใส่คะแนนในระบบ reg", "ตั้งช่วงคะแนน", "เพิ่มรายการเก็บคะแนน", "กรอกคะแนนสอบลง reg", "enter marks in reg", "put my scores in the system", "set up score items in reg", "upload grades to reg". Works in the user's own signed-in browser (Claude in Chrome); the user signs in.
version: 1.0.0
---

# Marks into reg.buu.ac.th

reg.buu.ac.th has no API. Work in the user's own Chrome through Claude in Chrome
(load the browser tools first). A helper prepares what the pages need and never
touches the site itself:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reg_grades.py" paste    marks.csv --item final [--group N]
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reg_grades.py" fill     marks.csv --group N --item final --point P [--no-save]
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reg_grades.py" readback marks.csv --group N --items att,hw,final
```

If `CLAUDE_PLUGIN_ROOT` is not set, the script is in `<plugin-root>/scripts/`.
`marks.csv` = `student_id,group,<one column per item>` (placeholder example:
`examples/reg_marks.csv`). An empty cell means **no mark** (absent, make-up,
withdrawn): it is never entered and must read back blank. Build it from the
user's own roster/marks file and check the counts per group against reg's
"ลง" column before starting. Keep it outside any git repo (student data).

## Rules

- **The user signs in.** Never type a password; open `https://reg.buu.ac.th`
  and let them log in and reach the course.
- **Confirm before the first save** of each course: show the score items
  (name, total, type, %, status) and, for marks, the source file and counts.
  After that, a save per group/item that passes the checks below needs no
  further question.
- **Keep new items `NOT SHOW`** until marks and weights are final; switching to
  `SHOW` is the user's decision.
- **Never invent a mark.** Blank stays blank: no zero for an absent or
  make-up student, nothing for a withdrawn (W) one (reg gives them no box).
- **Check the weight total in every group** and tell the user when it is not
  100 %. Co-teachers' items differ between groups (e.g. a Lab item only in
  some groups), so one group's total says nothing about another's. Don't change
  or delete a co-teacher's item ([ลบ]); report it and, if asked, draft an email.
- Grades reg shows (T-score) are provisional until the weights total 100 %.
  Say so; never press "A,B Ent." / submit grades unless the user asks.

## Navigation

- ระบบสำหรับอาจารย์ → **บันทึกเกรด**: courses by semester, one row per
  group with **1,2 Ent.** (score entry), **A,B Ent.** (grade entry) and the
  grade-cutting mode (ตัดแยก = each group graded separately).
- **1,2 Ent.** opens the score page (`enrollpoint.asp`). Its left menu has
  **บันทึกช่วงคะแนน** (score-item setup) and **ถอยกลับ** (back one level).
- From the setup page, ถอยกลับ goes to the score page, then to the course
  list; one more lands on ภาระการสอน (click บันทึกเกรด to return).
- Always confirm the page's **กลุ่ม** number before acting; the group buttons
  sit at fixed positions, so a misclick opens the wrong group.

## 1. Score items (บันทึกช่วงคะแนน, `entry_gradepoint.asp`)

Table: NO. / SCORE EVALUATION / TOTAL / TYPE (QUIZ, MIDTERM, FINAL) /
STATUS (SHOW, NOT SHOW) / RAW / % / INSTRUCTOR, with empty rows below the
existing items. Instructor defaults to the signed-in lecturer.

1. Scroll to the table and screenshot it; note existing items and their %.
2. In each empty row type NO. (next number), name, TOTAL and %; set TYPE with
   `form_input` (find the select by "the row whose name is X"). STATUS is
   already NOT SHOW. Clicking each field and typing was reliable; the `find`
   tool's labels for this table's inputs can be shuffled.
3. Zoom on the table to check, click the lower **บันทึก**, scroll down and
   check again: RAW and the % total appear only after saving.
4. Repeat for every group (each group has its own setup). The item numbers
   (Point:N) differ between groups when co-teachers have different items.

## 2. Marks (`enrollpoint.asp`)

Each item is a column **EDIT Point:N**. Clicking EDIT reloads with
`EDITCLASSPOINTID=N` and turns that column into number boxes
(`step=any`, `min=0`, `max=` item total) with one **Save** button in the
column header.

Two ways to fill a column:

- **Bulk paste** (the site's own tool): **Import File** shows a textarea; set
  it (`form_input`) to the `paste` output for that group and item
  ("studentID<TAB>score" per line), click **Import**. This only fills the
  boxes; it still needs **Save**.
- **Page script** (faster for many columns): open EDIT Point:N, run the `fill`
  output with `javascript_exec`. It fills each box by the row's student ID,
  checks every value and `checkValidity()`, and clicks **Save** only if the
  page's group and Point number match the arguments and nothing is wrong.
  Use `--no-save` the first time and show the user the result.

Either way, check before saving that every student with a mark got it and
nobody else got anything, then **Save**. To reach the next item, follow the
`EDIT` link whose href has `EDITCLASSPOINTID=<next>` (a short script:
find it and set `location.href`).

## 3. Read back

After the last item of a group, run the `readback` output on the score page.
It compares every row's columns for the user's items (the last *K* point
columns before the total) with the CSV, numerically (reg shows 0.93 as
".93"), lists students on the page but not in the CSV (`extra`, e.g. a W
student, which must be blank) and in the CSV but not on the page
(`missing`). Report per group: rows, matches, blanks left on purpose.

## Report

Lead with the outcome per group in a short table (students, all match / what
differs), then what is still open: items still NOT SHOW, weight totals that
are not 100 %, marks still to come (make-up). Record those in the project's
handover notes.

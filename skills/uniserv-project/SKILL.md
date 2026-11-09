---
name: uniserv-project
description: Work out and check the budget of a BUU academic-service project (โครงการบริการวิชาการ) under ระเบียบมหาวิทยาลัยบูรพา ว่าด้วยการบริหารโครงการบริการวิชาการ พ.ศ. 2565 — the ค่าธรรมเนียมบริการวิชาการ (university 7% + faculty share, reckoned on the project's expenditure, each part rounded up to the ten), how fixed revenue splits into expenditure + fee, the ข้อ 19 cap on committee pay, the Thai baht words, and the proposal's structure and approval route (ข้อ 25). Use when the user says "โครงการบริการวิชาการ", "งบประมาณโครงการบริการวิชาการ", "ค่าธรรมเนียมบริการวิชาการ", "หักร้อยละ 15", "ค่าตอบแทนคณะกรรมการบริหารโครงการ", "academic service project budget", "how much is the university fee", "check the budget table", "finance changed the numbers", or is writing or amending such a proposal.
version: 1.0.0
---

# Academic-service projects (โครงการบริการวิชาการ)

One script does the arithmetic:

```
S="${CLAUDE_PLUGIN_ROOT}/scripts/uniserv_budget.py"
python3 "$S" solve 195600              # revenue → expenditure + fee (the usual question)
python3 "$S" fee 170080                # fee on an expenditure total
python3 "$S" cap 170080                # ข้อ 19 ceiling for committee pay
python3 "$S" check BUDGET.json         # whole budget: products, fee, balance, cap, words (exit 1 on problems)
python3 "$S" words 170080              # หนึ่งแสนเจ็ดหมื่นแปดสิบบาทถ้วน
python3 "$S" selftest
```

If `CLAUDE_PLUGIN_ROOT` is not set, the script is in `<plugin-root>/scripts/`. Stdlib only. The BUDGET.json
schema is in the script's docstring; `examples/uniserv_budget.json` is a worked example. The regulation's full text
(transcribed from the scan) is `regulation-2565.md` beside this file: quote clauses from there, not from memory.

## The fee rule (ค่าธรรมเนียมบริการวิชาการ)

- **Base is the expenditure, not the revenue.** ข้อ 16 วรรคสอง: the fee is a percentage of the sum of the project's
  costs (1)–(7) — every budget line, committee pay and licence fees included. That sum is the
  "ค่าบริการวิชาการ" / ค่าใช้จ่ายดำเนินโครงการ (E).
- **Floors (ข้อ 17):** university ≥ 7% of E, faculty ≥ 5% of E, total ≥ 12%.
- **Rounding:** each part separately, rounded **up** to the next ten ("มีเศษไม่ถึงสิบ ให้ปัดขึ้นเป็นจำนวนเต็มสิบ").
- **Faculty of Engineering practice** (finance, Nov 2026): university 7% + faculty 8% = **15% of E**. These are the
  script's defaults; pass `--uni`/`--fac` (or `university_rate`/`faculty_rate`) when a unit uses other rates.
- **With revenue fixed** (registration fees, a grant), E and the fee must satisfy E + fee(E) = R. So the fee is
  *not* 15% of R. Worked case: R = 195,600 → E = 170,080, fee = 7% 11,910 + 8% 13,610 = 25,520
  (15% of R would be 29,340 and leave the budget 3,820 short). `solve` finds the largest E that fits and reports any
  few baht left over; put those into a line item or leave them as surplus (ข้อ 20).
- A fee **above** the minimum is allowed (the floors say "ไม่น้อยกว่า"); `check` flags only a fee below it.
- **Label it with its base.** Write "หัก ค่าธรรมเนียมบริการวิชาการ (ร้อยละ 15 ของค่าใช้จ่ายดำเนินโครงการ)", not a bare
  "(ร้อยละ 15)", which reads as 15% of revenue.
- Reductions or waivers: faculty share per ข้อ 18 วรรคหนึ่ง (head of unit); university share by at most 2% of E
  (ข้อ 18 วรรคสอง, revenue committee + President).

## Committee pay (ข้อ 16 (6), ข้อ 19)

- Capped on E by a sliding scale: 20% of the first 1M, 15% of the next 1M, 10% of the next 1M, 5% above 3M
  (`cap`). E = 5,971,120 → 598,556; E = 170,080 → 34,016.
- Items (1)–(5) and (7) may be averaged against each other (ถัวจ่าย); **item (6) may not**. The budget note must say
  so — keep the carve-out ("สำหรับรายการ … ค่าตอบแทนคณะกรรมการ ให้เบิกจ่ายตามหลักเกณฑ์ในข้อ 19") when editing.
- Changing the committee list needs approval again (ข้อ 25 วรรคสอง).

## When finance changes the numbers

1. Read their marked-up copy (scans are often handwritten; render at 250 dpi and crop the budget table).
2. Put their figures into a BUDGET.json and run `check`. If the balance fails, run `solve` on the revenue and show
   the user where the difference comes from before editing anything.
3. Amend every place the figures appear: the budget tables, the amount-in-words lines, the cover memo's body
   (it usually quotes the fee and the net amount), and any merged PDF. A changed amount means the cover memo must be
   signed again.
4. If a marginal calculation can't be traced to the rules above, say so and ask; don't invent a basis.

## Writing the proposal

Documents are XeLaTeX per the user's global rules (Sarabun, `Script=Thai`); the cover memo is a บันทึกข้อความ via
`thai-memo`. A proposal usually has: 1 ชื่อโครงการ, 2 หน่วยรับผิดชอบ, 3 ผู้รับผิดชอบ, 4 หลักการและเหตุผล,
5 วัตถุประสงค์, 6 คณะกรรมการบริหารโครงการ (ประธาน … กรรมการและเลขานุการ last), 7 กลุ่มเป้าหมาย, 8 รูปแบบกิจกรรม,
9 สถานที่, 10 ระยะเวลา, 11 ผลที่คาดว่าจะได้รับ, 12 ตัวชี้วัด, 13 งบประมาณ (รายรับ: revenue, หัก fee, รวมรายรับ;
รายจ่าย: items, รวมรายจ่าย = รวมรายรับ, with words), then the schedule (กำหนดการ).

Approval route (ข้อ 25): the project lead submits the proposal **with the committee list** through the owning unit and
สำนักบริการวิชาการ to the President, or to the head of unit the President has delegated to. Ask who signs at
faculty level when it is unclear.

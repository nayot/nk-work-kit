---
name: edu-claim
description: Claim child education costs (ค่าเล่าเรียนบุตร / เงินสวัสดิการเกี่ยวกับการศึกษาของบุตร) at Burapha University from a school receipt — work out how much can be claimed through each channel, fill in the government form แบบ 7223 (ข้าราชการ / สิทธิข้าราชการบำนาญ) and the BUU welfare-fund form (กองทุนสวัสดิการมหาวิทยาลัยบูรพา, พนักงานมหาวิทยาลัย), and assemble each submission pack in the order finance expects, with every copy marked สำเนาถูกต้อง and the "for this claim only" line, plus the wording the user must write by hand. Use when the user says "เบิกค่าเล่าเรียนบุตร", "เบิกค่าการศึกษาบุตร", "ใบเบิกสวัสดิการการศึกษาบุตร", "แบบ 7223", "claim my child's school fees", "how much can I claim for this receipt", "fill the education claim forms", "prepare the claim packs", or drops a Satit (โรงเรียนสาธิต "พิบูลบำเพ็ญ") receipt and asks what to do with it.
version: 1.0.0
---

# Child-education claims

A single script handles the forms and the packs:

```
S="${CLAUDE_PLUGIN_ROOT}/scripts/edu_claim.py"
python3 "$S" where                       # the claims folder (EDU_CLAIM_DIR in the nk-work-kit .env)
python3 "$S" fields [--form gov]         # every fillable field name
python3 "$S" check SPEC.json             # amounts add up, words match figures
python3 "$S" fill  SPEC.json OUT.pdf     # filled form (runs check first; writes *_words itself)
python3 "$S" pack  PACK.json             # filled form + certified attachments → one PDF
python3 "$S" words 20500                 # สองหมื่นห้าร้อยบาทถ้วน
python3 "$S" blank OUT.pdf [--form gov]  # empty form
```

If `CLAUDE_PLUGIN_ROOT` is not set, the script is in `<plugin-root>/scripts/`. It needs `xelatex` with the
TH SarabunPSK font, `qpdf` and `pdfinfo`. The schemas for SPEC and PACK are in the script's docstring.
Worked placeholder examples are `examples/edu_claim_welfare.json`, `examples/edu_claim_gov.json` and
`examples/edu_claim_pack.json`. `reference.md`, beside this file, records the rules, page order and notes. Read it
before the first claim of a session.

## Ground rules

- **Personal data stays in the claims folder** (`edu_claim.py where`). It holds names, ID-card and certificate scans
  and the claim history. Never copy any of it into this plugin repo (it is public) or anywhere shared.
- **No invented rates.** The Satit fee regulation says what the school charges. It does not say what can be claimed.
  - Take each channel's amount from the profile's `split_precedent` for the same child, programme and receipt, or
    from a previous approved claim in the claims folder.
  - If neither covers the receipt (a new programme, a new grade band, a different total), say so. Ask the user, or
    suggest asking finance, instead of guessing.
- **Titles come from the profile, never from an old sample.** Forms signed before the user's current post carry
  old titles: fill in today's ตำแหน่ง and the current approver (`propose_to`).
- **Never draw a signature or a date the user must write.** Leave the signing dates blank. The user signs the
  forms and every สำเนาถูกต้อง block by hand.
- **The receipt is not printed into the pack.** The user writes the notes on the original receipt copy by hand.
  Give them the exact wording (see `reference.md`) and say where in the pack the receipt goes.
- Use Arabic numerals in everything you write in (BUU rule from 01.11.2569). The printed form text keeps its own
  numerals.

## Step 0: the profile

Read `<claims folder>/profile.json`. If it is missing, build it with the user from their documents:
- **claimant:** name as filled in, name in the สำเนาถูกต้อง block, name on the ID card, ตำแหน่ง, unit, start date,
  welfare-form status box, and which channels they have (`gov`, `welfare`).
- **spouse:** name, position, unit, and the spouse box on the form.
- **propose_to**, `relation` (father/mother) and `married`.
- **documents:** paths to the ID card, the marriage certificate and the fee regulation.
- **children:** name, birth date as on the birth certificate, birth order, school, amphoe, province, programme, and
  the birth-certificate path.
- **split_precedent:** the amounts approved before for each channel.

Check birth dates and spouse names against the certificates, not against old forms (old forms have had typos).
File new certificates or scans under the user's personal documents (ask where) and record the paths in the profile.

## Step 1: read the receipt

Read the receipt: the child, term (ภาค/ปีการศึกษา), grade, programme (แผนการเรียน), each line and the total.
- Tuition (ค่าธรรมเนียมการศึกษา…) can be claimed.
- Lunch (ค่าอาหารกลางวัน) has never been claimed: leave it out.
- Compare the figures with the fee regulation (`reference.md`). If a line doesn't match a regulation item, flag it.

## Step 2: the split

Report the total that can be claimed and what each channel pays, in a few lines:
- the government form (แบบ 7223)
- the welfare-fund form, by clause (ข้อ 5 (8) and ข้อ 5 (9),(10)), with the government amount entered as
  "ใช้สิทธิเบิกจากหน่วยงานอื่นแล้ว"

Say which precedent the figures come from, and ask before filling if anything differs from it.

## Step 3: fill both forms

Create `<claims folder>/<term>_<child key>/` (e.g. `2569-2_warittha`). Write `welfare.json` and `gov.json`
following the examples and the profile, then run `check` and `fill`.
- Welfare form ticks:
  - section 1: the status box
  - section 2: the spouse box
  - section 3: (ก) and/or (ค) as they apply (ค is the Satit clause), เป็นบิดา/เป็นมารดา, จดทะเบียนสมรส or not
  - sections 5–6: ตามสิทธิ and the sole-claimant box
- Gov form ticks:
  - the spouse box, เป็นบิดาชอบด้วยกฎหมาย/เป็นมารดา
  - (2) เงินค่าเล่าเรียน, with the receipt total as the amount
  - ตามสิทธิ, and the three statements in section 6
- Long names overflow the bracketed signature lines. Use the short form (ผศ.ดร.…) there.

Render both forms and look at them (`pdftoppm`) before going on.

## Step 4: the packs

Write `pack_gov.json` and `pack_welfare.json`, in the page order in `reference.md`, then run `pack` for each.
- Each certificate gets `"diagonal": true` and the title "รับรองสำเนาถูกต้อง".
- The ID card scan is a full A4 sheet: use `"layout": "full"`, the ID-card name and an empty role.
- The regulation pages get "สำเนาถูกต้อง".

Look at every page. Open both packs for the user.

## Step 5: hand over

In a few lines:
- the two pack files;
- the receipt wording to write by hand, and where the receipt goes (page 3, after the form);
- what to sign: both forms, every สำเนาถูกต้อง block, the receipt;
- anything still uncertain.

Append the claim to the profile's `split_precedent` only after the user confirms finance approved it.

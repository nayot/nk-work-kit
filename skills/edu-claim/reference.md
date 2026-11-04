# Child-education claims at BUU: what we know (Nov 2026)

These notes come from the claim packs finance approved in 2567–2569 and from the Satit fee regulation. Nothing
here is a claim rate: those come from the user's approved precedents (see SKILL.md).

## The two channels

| Channel | Form | Who | Paid from |
|---|---|---|---|
| Government | **แบบ 7223**, ใบเบิกเงินสวัสดิการเกี่ยวกับการศึกษาของบุตร (2 pages) | ข้าราชการ, and staff who keep ข้าราชการบำนาญ rights | the พ.ร.ฎ. เงินสวัสดิการเกี่ยวกับการศึกษาของบุตร |
| University welfare fund | ใบเบิกเงินสวัสดิการเกี่ยวกับการศึกษาของบุตร **กองทุนสวัสดิการมหาวิทยาลัยบูรพา** (2 pages) | พนักงานมหาวิทยาลัย (incl. สิทธิข้าราชการบำนาญ), ลูกจ้าง | ประกาศคณะกรรมการสวัสดิการ, ข้อ 5 (8) and ข้อ 5 (9),(10) |

A claimant with both rights files both forms: the government form first. On the welfare form, the government amount
goes under "ใช้สิทธิเบิกจากหน่วยงานอื่นแล้ว". The welfare-form's section 3 clause (ค) covers children at
โรงเรียนสาธิต "พิบูลบำเพ็ญ" from ภาคปลาย 2560 on.

## Pack order (as approved)

**Government pack (แบบ 7223)**
1. The form (2 pages)
2. The receipt, with the handwritten notes (the user adds it)
3. The fee regulation, every page สำเนาถูกต้อง
4. The birth certificate
5. The marriage certificate

**Welfare-fund pack**
1. The form (2 pages)
2. The receipt, with the handwritten notes (the user adds it)
3. The claimant's ID card
4. The marriage certificate
5. The birth certificate
6. The fee regulation, every page สำเนาถูกต้อง

The welfare form's section 3 lists the documents: the receipt with the fee notice, the ID card, the birth
certificate, and for a father the marriage certificate (or ทะเบียนรับรองบุตร if not married).

## Notes on the pages

- **Every copy:** a สำเนาถูกต้อง (or รับรองสำเนาถูกต้อง) block in blue, with the signature space, (name) and
  position. The claimant signs each one.
- **Certificates and the ID card:** a diagonal line, "ใช้เพื่อแนบเบิกสวัสดิการเกี่ยวกับการศึกษาบุตร <child>
  เท่านั้น".
- **The receipt, written by hand in its blank rows:**
  > ใช้สิทธิเบิกจากหน่วยงานอื่นแล้ว <gov> บาท (<words>)
  > ขอเบิกจากสวัสดิการมหาวิทยาลัย ข้อ 5 (8) จำนวนเงิน <a> บาท (<words>)
  > ขอเบิกจากสวัสดิการมหาวิทยาลัย ข้อ 5 (9),(10) จำนวนเงิน <b> บาท (<words>)

  Below the rows: สำเนาถูกต้อง, the signature, (name) and position. Both packs carry the same receipt notes.

## Satit Pibulbumpen fees (council regulation 2558, amended 2559 ×2 and 2560)

Source: council.buu.ac.th, regulation 41/2558 and amendments 4/2559, 20/2559 and 18/2560. Amounts are per
semester.

**Fee levels**

| Level / programme | Fee |
|---|---|
| ปฐมวัย | 24,000 (+15,000 for the language programme) |
| ประถม, มัธยม: base fee | 15,000 |
| JIP (primary) | +15,000 |
| LIP, SAM (secondary) | +20,000 |
| Inclusive education | +50,000 |
| International (IEP), ข้อ 5 of 2558, never amended | ค่าธรรมเนียมการศึกษาและกิจกรรมนักเรียน 75,000 |

**Other charges (ค่าใช้จ่ายอื่น ๆ)**

| Item | Amount |
|---|---|
| Activity fee | 1,500 (primary), 2,000 (secondary) |
| ค่ารักษาสภาพนักเรียน | 2,000 per semester; IEP 10,000, semester 1 only |

**What to attach**

The IEP claims attach the 2558 regulation, since ข้อ 5 is the IEP fee clause. A claim under the ข้อ 3–4 fees
attaches the 2560 amendment, which sets the current ข้อ 3–4.

## Form fields

`python3 edu_claim.py fields [--form gov]` lists them. The main ones:

**Welfare form**
- Claimant: `claimant_*`, `status_*`
- Spouse: `spouse_*`
- Section 3: `right_a`, `right_c`, `is_father`/`is_mother`, `father_married`/`father_unmarried`
- Each child: `childN_name`, `childN_born`, `childN_order_father`, `childN_order_mother`, `childN_school`,
  `childN_amphoe`, `childN_province`, `childN_grade`, `childN_paid`, `childN_other_source`, `childN_claim_5_8`,
  `childN_claim_5_9_10`, `childN_total`
- Sections 5–9: `receive_full`, `receive_amount`, `propose_to`, `sole_claimant`, `claimant_sign_name`,
  `received_amount`, `receiver_name`

**Gov form**
- The same claimant and spouse fields, plus `is_father`/`is_mother`
- Each child: `childN_type1_fee` or `childN_type2_tuition`, and `childN_amount`
- Sections 5–8: `receive_full`, `receive_amount`, `propose_to`, `true_statement`, `child_eligible`,
  `sole_claimant`, `received_amount`, `receiver_name`

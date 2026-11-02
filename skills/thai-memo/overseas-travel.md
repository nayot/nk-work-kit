# Overseas trips (ลาไปปฏิบัติงาน ณ ต่างประเทศ): the Faculty of Engineering procedure

Source: the EE department admin's guide "การจัดทำคู่มือปฏิบัติงาน การลาไปปฏิบัติงาน ณ ต่างประเทศ งบ 2569
(เฉพาะบันทึก ตย.)", a Word file with three sample documents (received Nov 2026). These notes record what
each document must say, so the memos can be built with `build_memo.py` (`type: nai`) instead of filling in
the Word form. `examples/overseas_travel_nai.json` is a worked request memo with placeholders.

Write numbers with Arabic digits (BUU rule from 01.11.2569). The sample still shows Thai digits.

## 1. Before the trip: บันทึกข้อความ ขออนุมัติเดินทางไปปฏิบัติงาน ณ ต่างประเทศ

- ส่วนงาน: `คณะวิศวกรรมศาสตร์ ภาควิชาวิศวกรรม…` + โทร. (internal extension)
- ที่: `อว 8116.…/` (department sub-number; leave the number blank or use `doc-number`)
- เรื่อง: `ขออนุมัติเดินทางไปปฏิบัติงาน ณ ต่างประเทศ`
- เรียน: `คณบดีคณะวิศวกรรมศาสตร์`

**Paragraph 1.** The form offers tick boxes; write out only the options that apply:

> ด้วยข้าพเจ้า (name in Thai) (name in English, with Mr./Mrs./Miss or academic title)
> [พนักงานมหาวิทยาลัย | ข้าราชการ] เลขที่อัตรา … ตำแหน่ง … สังกัด … คณะวิศวกรรมศาสตร์ มหาวิทยาลัยบูรพา
> [ได้รับการตอบรับ | ได้รับเชิญ] จาก … ให้เดินทางไป [ปฏิบัติงาน | ประชุม/สัมมนา | ดูงาน | นำเสนอผลงานทางวิชาการ |
> ฝึกอบรม | ปฏิบัติการวิจัย | เจรจาความร่วมมือทางวิชาการ | เป็นวิทยากร | ผู้บรรยายรับเชิญ (Invited speaker) | อื่น ๆ]
> ในงานประชุม “…” ในหัวข้อเรื่อง “…” ณ … ประเทศ …
> ด้วยทุนจาก [ทุนประชุมและนำเสนอผลงานทางวิชาการระดับนานาชาติต่างประเทศ ประจำปีงบประมาณ พ.ศ. … (ครั้งที่ …)
> | เงินรายได้มหาวิทยาลัยบูรพา (คณะวิศวกรรมศาสตร์) | ทุนส่วนตัว | ทุนอื่น ๆ …]
> มีกำหนด … วัน ตั้งแต่วันที่ … ถึงวันที่ … ซึ่งรวมระยะเวลาเดินทางไป-กลับไว้เรียบร้อยแล้ว นั้น

Optional, only when it applies: `และได้รับอนุญาตให้ลาพักผ่อน ณ ประเทศ … มีกำหนดอีก … วัน ตั้งแต่วันที่ … ถึงวันที่ …`

**Paragraph 2 (required in 2569): the Middle East urgent-measures justification.**

> ตามประกาศมหาวิทยาลัยบูรพา เรื่อง มาตรการเร่งด่วน รับมือผลกระทบจากสถานการณ์ความไม่สงบในตะวันออกกลาง
> ลงวันที่ 12 มีนาคม พ.ศ. 2569 ในการลา(ประเภทการลา)ในครั้งนี้ เนื่องจาก…

The sample's reason reads: ข้าพเจ้ามีความจำเป็นเร่งด่วนและเป็นโอกาสสำคัญในการพบปะ ประชุม แลกเปลี่ยนองค์ความรู้…
นำมาซึ่งการสร้างเครือข่ายความร่วมมือทางวิชาการกับผู้เชี่ยวชาญและสถาบันชั้นนำในต่างประเทศ… รวมถึงสร้างชื่อเสียง
ให้กับมหาวิทยาลัยบูรพา ซึ่งจะเกิดประโยชน์สูงสุดต่อคณะวิศวกรรมศาสตร์และมหาวิทยาลัยบูรพาต่อไป. Write the trip's own reason
(why attendance is required, what the faculty gains).

**Paragraph 3, only if needed:** ทั้งนี้ ขอให้มหาวิทยาลัยออกหนังสืออนุเคราะห์อำนวยความสะดวกในการจัดทำหนังสือเดินทางราชการ
และหนังสือตรวจลงตราให้ด้วย (official passport or visa).

**Attachments** (`พร้อมนี้ได้แนบเอกสารเพื่อประกอบการพิจารณา ดังนี้`), the ones that apply, each `จำนวน 1 ชุด`:
1. แบบฟอร์มใบลาไปศึกษา ฝึกอบรม ดูงาน ปฏิบัติการวิจัย
2. แบบฟอร์มรายละเอียดประกอบการพิจารณาให้ลาศึกษา หรือฝึกอบรม หรือปฏิบัติการวิจัย ณ ต่างประเทศ
3. หนังสือเชิญ หรือ หนังสือตอบรับ
4. หลักฐานการได้ทุนฯ (ประกาศทุนฯ / สัญญารับทุนฯ / โครงการที่ขอทุนฯ)
5. กำหนดการเดินทาง หรือ Itinerary
6. บทคัดย่อผลงาน (when the invitation/acceptance doesn't name the paper)
7. โครงการที่ได้รับอนุมัติจากอธิการบดี (research trips, and trips paid by the university)
8. สำเนาคำสั่งจ้างฯ (foreign employees only)

The two forms in items 1–2 are not in the guide; ask the department admin for them.

Closing: `จึงเรียนมาเพื่อโปรดพิจารณาอนุมัติ จะขอบพระคุณยิ่ง`

**Signatures: two blocks.** The applicant (name; ตำแหน่ง on the line below), then the ผู้บังคับบัญชาขั้นต้น
(`หัวหน้าภาควิชาวิศวกรรม…`). Use `signer_name`/`signer_roles` for the applicant and `endorsers` for the head of
department; an endorser with an empty `name` gets a dotted line. With the body above, the memo runs to two
pages (the sample does too); `build_memo.py` moves จึงเรียนมา… to page 2 with the signatures.

## 2. After the trip: บันทึกข้อความ ขอรายงานตัวกลับและรายงานผลการลาจากการเดินทางไปต่างประเทศ

Same header; เรื่อง `ขอรายงานตัวกลับและรายงานผลการลาจากการเดินทางไปต่างประเทศ`, เรียน คณบดีคณะวิศวกรรมศาสตร์.

> ตามที่มหาวิทยาลัยอนุมัติให้ข้าพเจ้า … เลขที่อัตรา … ตำแหน่ง … สังกัด … เดินทางไป … (the same trip details as
> paragraph 1 of the request) … ซึ่งรวมระยะเวลาเดินทางไป-กลับไว้เรียบร้อยแล้ว นั้น
>
> บัดนี้ การเดินทางดังกล่าวได้เสร็จสิ้น และได้เดินทางกลับถึงประเทศไทย เมื่อวันที่ … พร้อมมีความประสงค์
> ขอรายงานตัวกลับเข้าปฏิบัติงานในตำแหน่งและสังกัดเดิม ตั้งแต่วันที่ … และขอรายงานผลการลาไปต่างประเทศมาด้วยแล้ว

If the report-back day is not the day after return (weekend or holiday), say why, e.g.
`ทั้งนี้ ในวันเสาร์ที่ … และวันอาทิตย์ที่ … เป็นวันหยุดประจำสัปดาห์` or `ทั้งนี้ ในวัน…ที่ … เป็นวันหยุดนักขัตฤกษ์`.

Attachments:
1. แบบฟอร์มรายงานตัวกลับจากต่างประเทศ (ดูงาน, ปฏิบัติการวิจัย or ฝึกอบรม trips only)
2. รายงานการศึกษา ฝึกอบรม ดูงาน ประชุม/สัมมนา ปฏิบัติการวิจัย และการไปปฏิบัติงานในองค์การระหว่างประเทศ (every trip;
   section 3 below)
3. สำเนาหนังสือเดินทาง with the Thai exit/entry stamps and the photo page. With the automatic gates, attach the
   boarding pass or another record of the exit and entry date and time; they must match the approved request.
   Sign สำเนาถูกต้อง on every copy.
4. สำเนาหนังสือที่ได้รับอนุมัติให้เดินทางลาไปต่างประเทศ

Closing and signatures as in the request memo.

## 3. The trip report (รายงานการศึกษา ฝึกอบรม ดูงาน ประชุม/สัมมนา ปฏิบัติการวิจัย และการไปปฏิบัติงานในองค์การระหว่างประเทศ)

A form, not a memo; build it with XeLaTeX (the default document tool) using these headings:

- **ส่วนที่ 1 ข้อมูลทั่วไป**
  - 1.1 ชื่อ/นามสกุล, อายุ, การศึกษา, ความเชี่ยวชาญเฉพาะด้าน
  - 1.2 ตำแหน่ง, หน้าที่ความรับผิดชอบ (โดยย่อ)
  - 1.3 ชื่อเรื่อง/หลักสูตร, สาขา, เพื่อ [ศึกษา | ฝึกอบรม | ดูงาน | ประชุม/สัมมนา | ปฏิบัติงานวิจัย | ไปปฏิบัติงานใน
    องค์การระหว่างประเทศ], แหล่งผู้ให้ทุน, ประเทศ, งบประมาณ, ระหว่างวันที่, รวมระยะเวลาการรับทุน, ภายใต้โครงการ,
    ของหน่วยงาน, คุณวุฒิ/วุฒิบัตรที่ได้รับ
- **ส่วนที่ 2 ข้อมูลที่ได้รับ** (academic content; a separate report may be attached as a file)
  - 2.1 วัตถุประสงค์
  - 2.2 เนื้อหา (โดยย่อ)
  - 2.3 ประโยชน์ที่ได้รับ: ต่อตนเอง, ต่อหน่วยงาน, อื่น ๆ (ระบุ)
- **ส่วนที่ 3 ปัญหา/อุปสรรค**
- **ส่วนที่ 4 ข้อคิดเห็นและข้อเสนอแนะ**
  - signed by the reporter: `(ลงชื่อ) … ผู้รายงาน`, then `(name)` and `ตำแหน่ง`
- **ส่วนที่ 5 ความคิดเห็นของผู้บังคับบัญชา**: left blank, signed by the คณบดีคณะวิศวกรรมศาสตร์

## Also check

- An overseas trip may also need a request in e-Leave (`e-leave` skill, e.g. ไปราชการต่างประเทศ or
  ลาพักผ่อนไปต่างประเทศ); confirm with the department admin which one applies.
- Look for clashes in the user's calendar during the trip (teaching, grade deadlines, meetings) and mention them.

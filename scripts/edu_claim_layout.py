"""Geometry of the BUU welfare-fund form ใบเบิกเงินสวัสดิการเกี่ยวกับการศึกษาของบุตร (2 pages).

Measured from a 200-dpi scan of the printed form (Nov 2026). Every position is in scan pixels
(200 dpi) in page 1's frame; ``mm()`` converts to millimetres on A4. Page 2 was scanned at a
slightly different offset and scale, so its numbers are written in its own scan frame and
mapped by ``P2``.

Items, per page, as tuples:
  ("t", x, y, text, bold, pt)  text, baseline-left at (x, y), in TH SarabunPSK at pt
  ("c", x, y, text, bold, pt)  text centred on x
  ("d", x0, x1, y, field)      dotted leader on baseline y; ``field`` names it for filling (or None)
  ("b", x, y, field)           check box, bottom-left at (x, y baseline)
  ("B", x0, y0, x1, y1, text)  boxed letter (the ก / ข references)
  ("h", x0, x1, y)             horizontal rule
  ("v", x, y0, y1)             vertical rule
The fill skill writes into ``field`` leaders and boxes; keep the field names stable.
"""

PX = 25.4 / 200          # mm per scan pixel
LEFT_MM = 9.0            # page-1 box left edge on A4 (box centred; the scan crops the right side)
TOP_MM = 1.2             # scan top → page top
BOX_L, BOX_R = 89, 1610  # page-1 frame
FILL_PT = 13.5           # filled-in values; the form's lines are only ~5 mm apart


def mm(x, y):
    return (LEFT_MM + (x - BOX_L) * PX, TOP_MM + y * PX)


def P2(x, y):
    """Page-2 scan frame → page-1 frame (left border 76 → 89, scale 1507 → 1515 px box width)."""
    k = 1515 / 1507
    return 89 + (x - 76) * k, y * k


def _child_block(n, y, xs, numeral_x, pt=13.0, pt_money=None):
    """One child (sub-item of section 4). ``y`` = list of 9 baselines, ``xs`` = dict of tab stops."""
    p = f"child{n}_"
    T = lambda x, yy, s, b=True: ("t", x, yy, s, b, pt)
    D = lambda a, b, yy, f: ("d", a, b, yy, p + f if f else None)
    L = xs["L"]
    pm = pt_money or pt
    M = lambda x, yy, s: ("t", x, yy, s, True, pm)
    return [
        T(numeral_x, y[0], "๑๒๓"[n - 1] + ("" if n == 1 else "."), True),
        T(L, y[0], "ชื่อ"), D(L + 30, xs["born"] - 3, y[0], "name"),
        T(xs["born"], y[0], "เกิดเมื่อ"), D(xs["born"] + 78, xs["end1"], y[0], "born"),
        T(L, y[1], "เป็นบุตรลำดับที่ (ของบิดา)"), D(L + 265, xs["mother"] - 3, y[1], "order_father"),
        T(xs["mother"], y[1], "เป็นบุตรลำดับที่ (ของมารดา)"), D(xs["mother"] + 292, xs["end2"], y[1], "order_mother"),
        T(L, y[2], "(กรณีเป็นบุตรแทนที่บุตรซึ่งถึงแก่กรรมแล้ว) แทนที่บุตรลำดับที่", False),
        D(xs["inplace"], xs["end3"], y[2], "replaces_order"),
        T(L, y[3], "ชื่อ", False), D(L + 30, xs["born2"] - 3, y[3], "deceased_name"),
        T(xs["born2"], y[3], "เกิดเมื่อ", False), D(xs["born2"] + 73, xs["died"] - 3, y[3], "deceased_born"),
        T(xs["died"], y[3], "ถึงแก่กรรมเมื่อ", False), D(xs["died"] + 140, xs["end3"], y[3], "deceased_died"),
        T(L, y[4], "สถานศึกษา"), D(L + 108, xs["amphoe"] - 3, y[4], "school"),
        T(xs["amphoe"], y[4], "อำเภอ"), D(xs["amphoe"] + 62, xs["province"] - 3, y[4], "amphoe"),
        T(xs["province"], y[4], "จังหวัด"), D(xs["province"] + 68, xs["end3"], y[4], "province"),
        T(L, y[5], "ชั้นที่ศึกษา"), D(L + 104, xs["amount"] - 3, y[5], "grade"),
        T(xs["amount"], y[5], "จำนวน"), D(xs["amount"] + 68, xs["baht"] - 3, y[5], "paid"),
        T(xs["baht"], y[5], "บาท (จำนวนเงินที่จ่ายจริงตามใบเสร็จ)"),
        M(L, y[6], "ใช้สิทธิเบิกจากหน่วยงานอื่นแล้ว จำนวนเงิน"), D(L + 426, xs["c58"] - 3, y[6], "other_source"),
        M(xs["c58"], y[6], "บาท ขอเบิกจากสวัสดิการมหาวิทยาลัยข้อ ๕ (๘)"),
        M(xs["amt"], y[6], "จำนวนเงิน"), D(xs["amt"] + 97, xs["bahtR"] - 3, y[6], "claim_5_8"),
        M(xs["bahtR"], y[6], "บาท"),
        M(xs["c59"], y[7], "ขอเบิกจากสวัสดิการมหาวิทยาลัยข้อ ๕ (๙),(๑๐) จำนวนเงิน"),
        D(xs["c59"] + 590, xs["bahtR"] - 3, y[7], "claim_5_9_10"), M(xs["bahtR"], y[7], "บาท"),
        M(xs["total"], y[8], "รวมเป็นจำนวนเงิน"), D(xs["total"] + 182, xs["bahtR"] - 3, y[8], "total"),
        M(xs["bahtR"], y[8], "บาท"),
    ]


def page1():
    T = lambda x, y, s, b=True, pt=13.0: ("t", x, y, s, b, pt)
    D = lambda a, b, y, f=None: ("d", a, b, y, f)
    Bx = lambda x, y, f=None: ("b", x, y, f)
    it = [
        ("c", 863, 100, "ใบเบิกเงินสวัสดิการเกี่ยวกับการศึกษาของบุตร กองทุนสวัสดิการมหาวิทยาลัยบูรพา", True, 14.0),
        ("c", 863, 143, "โปรดทำเครื่องหมาย / ลงในช่อง \\cbox{} พร้อมทั้งกรอกรายละเอียดให้ครบถ้วน", True, 13.6),
        ("h", BOX_L, BOX_R, 186),
        # 1
        T(144, 240, "๑."), T(192, 240, "ข้าพเจ้า"), D(262, 643, 240, "claimant_name"),
        T(646, 240, "ตำแหน่ง"), D(732, 1062, 240, "claimant_position"),
        T(192, 282, "สังกัด"), D(250, 548, 282, "claimant_unit"),
        T(550, 282, "วันที่เริ่มบรรจุเข้าทำงาน"), D(815, 1055, 282, "claimant_start_date"),
        Bx(1118, 240, "status_civil"), T(1157, 240, "ข้าราชการ/ลูกจ้างประจำ", True, 12.85),
        Bx(1118, 282, "status_staff_pension"), T(1157, 282, "พนักงานมหาวิทยาลัย (สิทธิข้าราชการบำนาญ)", True, 12.85),
        Bx(1118, 322, "status_staff"), T(1157, 322, "พนักงานมหาวิทยาลัย", True, 12.85),
        Bx(1118, 364, "status_employee"), T(1157, 364, "ลูกจ้างมหาวิทยาลัย", True, 12.85),
        ("h", BOX_L, BOX_R, 392),
        # 2
        T(142, 450, "๒."), T(193, 450, "คู่สมรสของข้าพเจ้าชื่อ"), D(430, 1477, 450, "spouse_name"),
        Bx(193, 492, "spouse_none"), T(240, 492, "ไม่เป็นข้าราชการประจำหรือลูกจ้างประจำ", True, 12.5),
        Bx(193, 534, "spouse_civil"), T(240, 534, "เป็นข้าราชการ", True, 12.4),
        Bx(395, 534, "spouse_permanent"), T(431, 534, "ลูกจ้างประจำ  ตำแหน่ง"),
        D(653, 990, 534, "spouse_civil_position"), T(993, 534, "สังกัด"), D(1052, 1487, 534, "spouse_civil_unit"),
        Bx(193, 578, "spouse_other"),
        T(243, 578, "เป็นพนักงานหรือลูกจ้างในรัฐวิสาหกิจ / หน่วยงานของทางราชการ ราชการส่วนท้องถิ่น กรุงเทพมหานคร องค์กรอิสระ", True, 12.45),
        T(243, 619, "องค์การมหาชน หรือหน่วยงานอื่นใด  ตำแหน่ง"), D(690, 990, 619, "spouse_other_position"),
        T(993, 619, "สังกัด"), D(1052, 1480, 619, "spouse_other_unit"),
        ("h", BOX_L, BOX_R, 652),
        # 3
        T(144, 696, "๓."), T(193, 696, "ข้าพเจ้าเป็นผู้มีสิทธิและขอใช้สิทธิ"),
        Bx(194, 736, "right_a"),
        T(228, 736, "(ก) สำหรับผู้ปฏิบัติงานที่เริ่มปฏิบัติงานตั้งแต่วันที่ ๒๖ มีนาคม พ.ศ. ๒๕๖๑ หรือ ผู้ปฏิบัติงานที่ปฏิบัติงานก่อนประกาศนี้มีผลใช้บังคับ", False, 12.1),
        T(228, 782, "และมีบุตรที่เริ่มเข้าศึกษาตั้งแต่ปีการศึกษา ๒๕๖๑", False, 12.1),
        T(228, 820, "(ข) สำหรับผู้ปฏิบัติงานที่ปฏิบัติงานก่อนวันที่ ๒๖ มีนาคม พ.ศ. ๒๕๖๑ และมีบุตรที่เริ่มเข้าศึกษาอยู่ก่อนปีการศึกษา ๒๕๖๑", False, 12.1),
        Bx(194, 851, "right_c"),
        T(228, 851, "(ค) สำหรับผู้ปฏิบัติงานที่มีบุตร ที่เริ่มเข้าศึกษาในโรงเรียนสาธิต “พิบูลบำเพ็ญ” มหาวิทยาลัยบูรพา โดยเข้าศึกษาตั้งแต่ภาคปลายปีการศึกษา ๒๕๖๐ เป็นต้นไป", False, 12.0),
        T(191, 886, "โดยแนบเอกสารประกอบการเบิกจ่าย ตามเงื่อนไขดังนี้", True, 12.0),
    ]
    docs_m = ["ใบเสร็จรับเงินและประกาศค่าธรรมเนียมการศึกษา", "สำเนาบัตรประจำตัวประชาชน (ผู้เบิก)", "สำเนาสูติบัตร (บุตร)"]
    for role, y0, field in (("เป็นมารดา", 928, "mother"), ("เป็นบิดา", 1133, "father")):
        it += [Bx(193, y0, f"is_{field}"), T(243, y0, role, True, 11.8),
               Bx(251, y0 + 41, f"{field}_married"), T(291, y0 + 41, "จดทะเบียนสมรสโดยแนบเอกสารดังนี้", True, 12.0),
               Bx(842, y0 + 41, f"{field}_unmarried"), T(879, y0 + 41, "ไม่จดทะเบียนสมรสโดยแนบเอกสารดังนี้", True, 12.1)]
        left = docs_m + (["สำเนาทะเบียนสมรส (ผู้เบิก)"] if field == "father" else [])
        right = docs_m + (["สำเนาทะเบียนรับรองบุตร"] if field == "father" else [])
        for k, (a, b) in enumerate(zip(left, right)):
            yy = y0 + 82 + 41 * k
            it += [T(309, yy, "–", False), T(347, yy, a, False), T(901, yy, "–", False), T(939, yy, b, False)]
    it += [
        ("h", BOX_L, BOX_R, 1361),
        T(153, 1412, "๔."), T(193, 1412, "ข้าพเจ้าได้จ่ายเงินสำหรับการศึกษาของบุตร  และขอเบิกเงินจากสวัสดิการมหาวิทยาลัย ดังนี้"),
    ]
    it += _child_block(1, [1454, 1494, 1534, 1574, 1614, 1654, 1690, 1732, 1772],
                       dict(L=250, born=903, end1=1508, mother=833, end2=1520, inplace=838, end3=1510,
                            born2=692, died=1070, amphoe=718, province=1052, amount=727, baht=1062,
                            c58=790, amt=1333, bahtR=1558, c59=843, total=1239), 213)
    it += _child_block(2, [1859, 1899, 1940, 1980, 2019, 2059, 2095, 2136, 2174],
                       dict(L=252, born=868, end1=1515, mother=810, end2=1515, inplace=838, end3=1503,
                            born2=693, died=1070, amphoe=752, province=1142, amount=692, baht=1117,
                            c58=790, amt=1333, bahtR=1558, c59=844, total=1239), 213)
    it += [("h", BOX_L, BOX_R, 2201), ("v", BOX_L, 186, 2201)]
    return it


def page2():
    def T(x, y, s, b=False, pt=12.2):
        x, y = P2(x, y); return ("t", x, y, s, b, pt)
    def D(a, b, y, f=None):
        return ("d", P2(a, 0)[0], P2(b, 0)[0], P2(0, y)[1], f)
    def Bx(x, y, f=None):
        x, y = P2(x, y); return ("b", x, y, f)
    def BL(x0, y0, x1, y1, s):
        return ("B", *P2(x0, y0), *P2(x1, y1), s)
    it = [("h", BOX_L, BOX_R, P2(0, 90)[1])]
    blk = _child_block(3, [134, 172, 209, 244, 280, 316, 354, 394, 434],
                       dict(L=221, born=785, end1=1474, mother=736, end2=1467, inplace=760, end3=1468,
                            born2=627, died=970, amphoe=680, province=1032, amount=622, baht=1012,
                            c58=755, amt=1297, bahtR=1520, c59=811, total=1163), 182, 12.0, 12.9)
    for e in blk:  # child block 3 was written in page-2 scan coordinates
        if e[0] == "t":
            x, y = P2(e[1], e[2]); it.append(("t", x, y, e[3], e[4], e[5]))
        else:
            it.append(("d", P2(e[1], 0)[0], P2(e[2], 0)[0], P2(0, e[3])[1], e[4]))
    it += [
        ("h", BOX_L, BOX_R, P2(0, 458)[1]),
        # 5
        T(166, 511, "๕.", True), T(216, 511, "ข้าพเจ้าขอรับเงินสวัสดิการเกี่ยวกับการศึกษาของบุตร", True),
        Bx(216, 553, "receive_full"), T(245, 553, "ตามสิทธิ"),
        Bx(465, 553, "receive_partial"), T(490, 553, "เฉพาะส่วนที่ยังขาดจากสิทธิ"),
        T(768, 553, "เป็นเงิน"), D(835, 1300, 553, "receive_amount"), T(1302, 553, "บาท"),
        T(214, 584, "("), D(222, 1150, 584, "receive_amount_words"), T(1153, 584, ")"),
        BL(1238, 566, 1286, 610, "ก"),
        ("h", BOX_L, BOX_R, P2(0, 634)[1]),
        # 6
        T(166, 694, "๖.", True), T(215, 694, "เสนอ"), D(255, 755, 694, "propose_to"),
        BL(765, 650, 813, 700, "ข"),
        Bx(216, 741, "sole_claimant"),
        T(266, 741, "เป็นผู้ใช้สิทธิเบิกเงินช่วยเหลือตามสิทธิกองทุนสวัสดิการ แต่เพียงฝ่ายเดียว"),
        Bx(217, 782, "spouse_received_less"),
        T(266, 782, "คู่สมรสของข้าพเจ้าและข้าพเจ้าได้รับการช่วยเหลือจากรัฐวิสาหกิจ  หน่วยงานของทางราชการ  ราชการส่วนท้องถิ่น กรุงเทพมหานคร องค์กรอิสระ  องค์การ"),
        T(267, 820, "มหาชน  หรือหน่วยงานอื่นใด  ต่ำกว่าจำนวนที่ได้รับจากทางกองทุนสวัสดิการ"),
        T(267, 860, "จำนวน"), D(330, 565, 860, "spouse_received_amount"), T(567, 860, "บาท"),
        T(410, 892, "ข้าพเจ้าขอรับรองว่า ข้าพเจ้ามีสิทธิได้รับเงินตามประกาศคณะกรรมการสวัสดิการมหาวิทยาลัยบูรพา"),
        T(567, 963, "(ลงชื่อ)"), D(630, 920, 963, "claimant_sign"), T(922, 963, "ผู้ขอรับเงินสวัสดิการ"),
        T(567, 1001, "("), D(575, 945, 1001, "claimant_sign_name"), T(947, 1001, ")"),
        T(567, 1038, "วันที่"), D(615, 688, 1038, "claim_day"), T(690, 1038, "เดือน"),
        D(745, 842, 1038, "claim_month"), T(845, 1038, "พ.ศ."), D(890, 938, 1038, "claim_year"),
        ("h", BOX_L, BOX_R, P2(0, 1074)[1]),
        # 7
        T(168, 1107, "๗.", True), T(209, 1107, "การตรวจสอบ", True),
        T(265, 1146, "ข้าพเจ้าได้ตรวจสอบใบขอเบิกสวัสดิการฉบับนี้แล้ว ขอรับรองว่าผู้ขอรับเงินสวัสดิการฯ มีสิทธิเบิกเงินสวัสดิการ ได้ตามประกาศ"),
        T(208, 1184, "คณะกรรมการสวัสดิการ มหาวิทยาลัยบูรพา"),
        T(567, 1222, "(ลงชื่อ)"), D(630, 920, 1222, None), T(922, 1222, "ผู้ตรวจสอบ"),
        T(617, 1260, "("), D(625, 988, 1260, None), T(990, 1260, ")"),
        T(595, 1296, "ตำแหน่ง"), D(665, 1010, 1296, None),
        T(610, 1333, "วันที่"), D(655, 728, 1333, None), T(730, 1333, "เดือน"),
        D(785, 868, 1333, None), T(870, 1333, "พ.ศ."), D(912, 1000, 1333, None),
        ("h", BOX_L, BOX_R, P2(0, 1357)[1]),
        # 8
        T(172, 1404, "๘.", True), T(222, 1404, "คำอนุมัติ", True),
        T(266, 1448, "อนุมัติให้เบิกได้"),
        T(595, 1489, "(ลงชื่อ)"), D(660, 960, 1489, None),
        T(595, 1529, "("), D(603, 956, 1529, None), T(958, 1529, ")"),
        T(562, 1569, "ตำแหน่ง"), D(632, 993, 1569, None),
        ("h", BOX_L, BOX_R, P2(0, 1607)[1]),
        # 9
        T(172, 1643, "๙.", True), T(220, 1643, "ใบรับเงิน", True),
        T(368, 1682, "ได้รับเงินสวัสดิการเกี่ยวกับการศึกษาของบุตร  จำนวน"), D(840, 1225, 1682, "received_amount"),
        T(1227, 1682, "บาท"),
        T(237, 1719, "("), D(245, 795, 1719, "received_amount_words"), T(797, 1719, ")ไว้ถูกต้องแล้ว"),
        T(668, 1792, "(ลงชื่อ)"), D(730, 1048, 1792, None), T(1050, 1792, "ผู้รับเงิน"),
        T(735, 1830, "("), D(743, 1068, 1830, "receiver_name"), T(1070, 1830, ")"),
        T(668, 1902, "(ลงชื่อ)"), D(730, 1048, 1902, None), T(1050, 1902, "ผู้จ่ายเงิน"),
        T(734, 1940, "("), D(742, 1076, 1940, None), T(1078, 1940, ")"),
        T(712, 1977, "วันที่"), D(752, 808, 1977, None), T(810, 1977, "เดือน"),
        D(862, 998, 1977, None), T(1000, 1977, "พ.ศ."), D(1040, 1099, 1977, None),
        T(770, 2013, "(ลงชื่อต่อเมื่อได้รับเงินแล้วเท่านั้น)"),
        ("h", BOX_L, BOX_R, P2(0, 2036)[1]), ("v", BOX_L, P2(0, 90)[1], P2(0, 2036)[1]),
        T(172, 2082, "คำชี้แจง", True),
        BL(189, 2094, 242, 2150, "ก"), T(267, 2120, "ให้ระบุการมีสิทธิเพียงใด เมื่อเทียบเท่ากับสิทธิที่ได้รับตามสิทธิกองทุนสวัสดิการ"),
        BL(189, 2156, 242, 2212, "ข"), T(266, 2186, "ให้เสนอต่อผู้มีอำนาจอนุมัติ"),
    ]
    return it


PAGES = [page1, page2]

#!/usr/bin/env python3
"""
Build Thai official documents from OTT templates.

Usage:
    python3 build_memo.py <data.json>

The JSON file describes all fields for the document.
See skills/draft-memo/SKILL.md for the full schema.
"""

import json, os, shutil, sys, zipfile
from datetime import datetime
from lxml import etree

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(SCRIPT_DIR, "..", "templates")

NAI_TEMPLATE = os.path.join(TEMPLATE_DIR, "แบบหนังสือภายใน.ott")
NOK_TEMPLATE = os.path.join(TEMPLATE_DIR, "แบบหนังสือภายนอก.ott")

# ── namespace helpers ─────────────────────────────────────────
NS = {
    "office":  "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "text":    "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "table":   "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "style":   "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "fo":      "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "draw":    "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "xlink":   "http://www.w3.org/1999/xlink",
    "svg":     "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0",
    "loext":   "urn:org:documentfoundation:names:experimental:office:xmlns:loext:1.0",
}

def q(ns, tag):
    return f"{{{NS[ns]}}}{tag}"


def today_thai():
    """Return today as a Thai Buddhist Era date string."""
    months = [
        "", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน",
        "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม",
        "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
    ]
    THAI = str.maketrans("0123456789", "๐๑๒๓๔๕๖๗๘๙")
    now = datetime.today()
    d = str(now.day).translate(THAI)
    m = months[now.month]
    y = str(now.year + 543).translate(THAI)
    return f"{d} {m} พ.ศ. {y}"


# ── ODT package helpers ───────────────────────────────────────

def extract_ott(template_path, work_dir):
    if os.path.exists(work_dir):
        shutil.rmtree(work_dir)
    with zipfile.ZipFile(template_path) as zf:
        zf.extractall(work_dir)


def pack_odt(work_dir, out_path):
    if os.path.exists(out_path):
        os.remove(out_path)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(os.path.join(work_dir, "mimetype"), "mimetype",
                 compress_type=zipfile.ZIP_STORED)
        for dirpath, _, filenames in os.walk(work_dir):
            for fname in filenames:
                if fname == "mimetype":
                    continue
                full = os.path.join(dirpath, fname)
                arcname = os.path.relpath(full, work_dir)
                zf.write(full, arcname)


# ── XML element builders ──────────────────────────────────────

def span(parent, style, text):
    el = etree.SubElement(parent, q("text", "span"),
                           {q("text", "style-name"): style})
    el.text = text
    return el


def para(parent, style):
    return etree.SubElement(parent, q("text", "p"),
                             {q("text", "style-name"): style})


def add_table(parent, headers, rows, col_widths=None):
    """Append an ODT table to parent element."""
    n_cols = len(headers)
    col_widths = col_widths or ["3cm"] + [f"{9/max(n_cols-1,1):.2f}cm"] * (n_cols - 1)

    # ── inject table styles into automatic-styles ─────────────
    root = parent
    while root.getparent() is not None:
        root = root.getparent()
    auto = root.find(f".//{q('office','automatic-styles')}")

    tbl_style = etree.SubElement(auto, q("style", "style"),
        {q("style", "name"): "MemoTbl", q("style", "family"): "table"})
    etree.SubElement(tbl_style, q("style", "table-properties"),
        {q("style", "width"): "14cm", q("fo", "margin-left"): "1.5cm"})

    for i, w in enumerate(col_widths[:n_cols]):
        cs = etree.SubElement(auto, q("style", "style"), {
            q("style", "name"): f"MemoTbl.C{i}",
            q("style", "family"): "table-column"})
        etree.SubElement(cs, q("style", "table-column-properties"),
            {q("style", "column-width"): w})

    for cell_sn, bg in [("MemoTbl.Hdr", "#d9d9d9"), ("MemoTbl.Cell", "#ffffff")]:
        cs = etree.SubElement(auto, q("style", "style"), {
            q("style", "name"): cell_sn, q("style", "family"): "table-cell"})
        etree.SubElement(cs, q("style", "table-cell-properties"), {
            q("fo", "border"): "0.05pt solid #000000",
            q("fo", "padding"): "0.1cm",
            q("style", "vertical-align"): "middle",
            q("fo", "background-color"): bg,
        })

    for psn, bold in [("MemoTblP", False), ("MemoTblPB", True)]:
        ps = etree.SubElement(auto, q("style", "style"), {
            q("style", "name"): psn, q("style", "family"): "paragraph",
            q("style", "parent-style-name"): "Standard"})
        etree.SubElement(ps, q("style", "paragraph-properties"), {
            q("fo", "text-align"): "center",
            q("style", "justify-single-word"): "false"})
        tp_attrs = {
            q("style", "font-name"): "TH SarabunPSK",
            q("fo", "font-size"): "16pt",
            q("style", "font-size-asian"): "16pt",
            q("style", "font-name-complex"): "TH SarabunPSK1",
            q("style", "font-size-complex"): "16pt",
        }
        if bold:
            tp_attrs.update({
                q("fo", "font-weight"): "bold",
                q("style", "font-weight-asian"): "bold",
                q("style", "font-weight-complex"): "bold",
            })
        etree.SubElement(ps, q("style", "text-properties"), tp_attrs)

    # ── build table element ───────────────────────────────────
    tbl = etree.SubElement(parent, q("table", "table"), {
        q("table", "name"): "ContentTable",
        q("table", "style-name"): "MemoTbl",
    })
    for i in range(n_cols):
        etree.SubElement(tbl, q("table", "table-column"),
                         {q("table", "style-name"): f"MemoTbl.C{i}"})

    def add_row(cells, cell_sn, psn, bold=False):
        tr = etree.SubElement(tbl, q("table", "table-row"))
        for txt in cells:
            td = etree.SubElement(tr, q("table", "table-cell"),
                                  {q("table", "style-name"): cell_sn})
            p_el = etree.SubElement(td, q("text", "p"),
                                    {q("text", "style-name"): psn})
            if bold:
                sp = etree.SubElement(p_el, q("text", "span"),
                                      {q("text", "style-name"): "T3"})
                sp.text = txt
            else:
                p_el.text = txt

    add_row(headers, "MemoTbl.Hdr", "MemoTblPB", bold=True)
    for row in rows:
        add_row(row, "MemoTbl.Cell", "MemoTblP")

    return tbl


# ══════════════════════════════════════════════════════════════
# Internal memo (บันทึกข้อความภายใน)
# ══════════════════════════════════════════════════════════════

def build_nai(data, work_dir):
    tree = etree.parse(os.path.join(work_dir, "content.xml"))
    root = tree.getroot()
    body_text = root.find(f".//{q('office','text')}")

    # preserve sequence-decls, clear the rest
    seq = body_text.find(q("text", "sequence-decls"))
    for child in list(body_text):
        body_text.remove(child)
    if seq is not None:
        body_text.insert(0, seq)

    # ── title line with logo ──────────────────────────────────
    title_p = etree.SubElement(body_text, q("text", "p"),
                                {q("text", "style-name"): "P1"})
    frame = etree.SubElement(title_p, q("draw", "frame"), {
        q("draw", "style-name"):  "fr1",
        q("draw", "name"):        "Picture 0",
        q("text", "anchor-type"): "char",
        q("svg", "x"):   "-0.0071in",
        q("svg", "y"):   "-0.2661in",
        q("svg", "width"):  "0.5783in",
        q("svg", "height"): "0.6043in",
        q("draw", "z-index"): "0",
    })
    etree.SubElement(frame, q("draw", "image"), {
        q("xlink", "href"):    "Pictures/100000000000038E000003BE60E9CB12.jpg",
        q("xlink", "type"):    "simple",
        q("xlink", "show"):    "embed",
        q("xlink", "actuate"): "onLoad",
    })
    span(title_p, "T2", "บันทึกข้อความ")

    para(body_text, "P2")   # spacer

    # ── ส่วนงาน ───────────────────────────────────────────────
    sw = para(body_text, "Standard")
    span(sw, "T3", "ส่วนงาน  ")
    dept = data.get("department", "")
    phone = data.get("phone", "")
    sw_text = dept + (f"   โทร. {phone}" if phone else "")
    span(sw, "T4", sw_text)

    # ── ที่ / วันที่ ──────────────────────────────────────────
    td = para(body_text, "P3")
    span(td, "T3", "ที่")
    span(td, "T1", " ")
    span(td, "T4", data.get("doc_number", ""))
    t = etree.SubElement(td, q("text", "tab"))
    t2_span = etree.SubElement(td, q("text", "span"),
                                {q("text", "style-name"): "T1"})
    etree.SubElement(t2_span, q("text", "tab"))
    span(td, "T3", "วันที่")
    t3_span = etree.SubElement(td, q("text", "span"),
                                {q("text", "style-name"): "T1"})
    etree.SubElement(t3_span, q("text", "tab"))
    span(td, "T4", data.get("date", today_thai()))

    # ── เรื่อง ────────────────────────────────────────────────
    re_p = para(body_text, "Standard")
    span(re_p, "T3", "เรื่อง")
    span(re_p, "T5", " ")
    span(re_p, "T4", data.get("subject", ""))

    # ── เรียน ─────────────────────────────────────────────────
    rian = para(body_text, "เรียน")
    rian.text = "เรียน  "
    span(rian, "T6", data.get("to", ""))

    # ── body paragraphs ───────────────────────────────────────
    for paragraph_text in data.get("body", []):
        bp = para(body_text, "เนื้อความ")
        span(bp, "T6", paragraph_text)

    # ── optional table ────────────────────────────────────────
    tbl_data = data.get("table")
    if tbl_data:
        add_table(body_text,
                  headers=tbl_data.get("headers", []),
                  rows=tbl_data.get("rows", []))
        para(body_text, "P6")   # gap after table

    # ── attachments ───────────────────────────────────────────
    THAI_DIGITS = str.maketrans("0123456789", "๐๑๒๓๔๕๖๗๘๙")
    attachments = data.get("attachments", [])
    if attachments:
        att_intro = para(body_text, "เนื้อความ")
        span(att_intro, "T6",
             "ทั้งนี้ได้แนบหลักฐานประกอบมาด้วย ดังนี้")
        for i, item in enumerate(attachments, 1):
            num = str(i).translate(THAI_DIGITS)
            li = para(body_text, "เนื้อความ")
            span(li, "T6", f"    {num}. {item}")

    # ── blank lines before signature ──────────────────────────
    for _ in range(4):
        para(body_text, "P4")

    # ── signature ─────────────────────────────────────────────
    sig_p = para(body_text, "ลงชื่อ")
    span(sig_p, "T7", "(")
    span(sig_p, "T8", data.get("signer_name", ""))
    span(sig_p, "T7", ")")

    for role in data.get("signer_roles", []):
        rp = para(body_text, "P5")
        span(rp, "T8", role)

    para(body_text, "Standard")

    # pretty_print must stay off: the newline + indentation lxml would insert
    # between sibling spans is rendered by ODF as a visible space, e.g.
    # "( ผู้ช่วยศาสตราจารย์ ... )" instead of "(ผู้ช่วยศาสตราจารย์ ...)".
    tree.write(os.path.join(work_dir, "content.xml"),
               xml_declaration=True, encoding="UTF-8")


# ══════════════════════════════════════════════════════════════
# External letter (หนังสือภายนอก)
# ══════════════════════════════════════════════════════════════

def build_nok(data, work_dir):
    tree = etree.parse(os.path.join(work_dir, "content.xml"))
    root = tree.getroot()
    body_text = root.find(f".//{q('office','text')}")

    seq = body_text.find(q("text", "sequence-decls"))
    for child in list(body_text):
        body_text.remove(child)
    if seq is not None:
        body_text.insert(0, seq)

    # ── logo frame (page-anchored, positioned via absolute coords) ──
    logo_p = para(body_text, "P1")
    frame = etree.SubElement(logo_p, q("draw", "frame"), {
        q("draw", "style-name"):  "fr1",
        q("draw", "name"):        "Picture 27",
        q("text", "anchor-type"): "char",
        q("svg", "x"):   "3.3874in",
        q("svg", "y"):   "0.8917in",
        q("svg", "width"):  "1.1772in",
        q("svg", "height"): "1.1772in",
        q("draw", "z-index"): "0",
    })
    etree.SubElement(frame, q("draw", "image"), {
        q("xlink", "href"):    "Pictures/100000000000010300000103F0C23EE7.jpg",
        q("xlink", "type"):    "simple",
        q("xlink", "show"):    "embed",
        q("xlink", "actuate"): "onLoad",
    })

    para(body_text, "P2")  # spacer

    # ── ที่ / from_org ────────────────────────────────────────
    # The signed precedent keeps the number on the same line as "ที่ อว",
    # with the tab jumping to the sender block on the right.
    thi_p = para(body_text, "เลขหนังสือ")
    doc_num = data.get("doc_number", "")
    span(thi_p, "T3", f"ที่  อว {doc_num}".rstrip())
    etree.SubElement(thi_p, q("text", "tab"))
    span(thi_p, "T4", data.get("from_org", ""))
    if "from_org_suffix" in data:
        span(thi_p, "T3", f" {data['from_org_suffix']}")

    for addr_line in data.get("from_address", []):
        ap = para(body_text, "เลขหนังสือ")
        etree.SubElement(ap, q("text", "tab"))
        span(ap, "T3", addr_line)

    para(body_text, "P3")

    # ── วันที่ ────────────────────────────────────────────────
    date_p = para(body_text, "วันที่")
    span(date_p, "T3", data.get("date", today_thai()))

    # ── เรื่อง ────────────────────────────────────────────────
    re_p = para(body_text, "เรื่องเรียนอ้างถึงสิ่งที่ส่งมาด้วย")
    span(re_p, "T5", "เรื่อง")
    etree.SubElement(re_p, q("text", "tab"))
    span(re_p, "T6", data.get("subject", ""))

    # ── เรียน ─────────────────────────────────────────────────
    rian_p = para(body_text, "เรื่องเรียนอ้างถึงสิ่งที่ส่งมาด้วย")
    span(rian_p, "T5", "เรียน")
    etree.SubElement(rian_p, q("text", "tab"))
    span(rian_p, "T5", data.get("to", ""))

    # ── สิ่งที่ส่งมาด้วย ──────────────────────────────────────
    for enc in data.get("enclosures", []):
        enc_p = para(body_text, "เรื่องเรียนอ้างถึงสิ่งที่ส่งมาด้วย")
        span(enc_p, "T5", "สิ่งที่ส่งมาด้วย")
        etree.SubElement(enc_p, q("text", "tab"))
        span(enc_p, "T6", enc)

    # ── body ──────────────────────────────────────────────────
    for paragraph_text in data.get("body", []):
        bp = para(body_text, "เนื้อความ")
        span(bp, "T6", paragraph_text)

    # ── optional table ────────────────────────────────────────
    tbl_data = data.get("table")
    if tbl_data:
        add_table(body_text,
                  headers=tbl_data.get("headers", []),
                  rows=tbl_data.get("rows", []))
        para(body_text, "P4")

    # ── attachments ───────────────────────────────────────────
    THAI_DIGITS = str.maketrans("0123456789", "๐๑๒๓๔๕๖๗๘๙")
    for i, item in enumerate(data.get("attachments", []), 1):
        num = str(i).translate(THAI_DIGITS)
        li = para(body_text, "เนื้อความ")
        span(li, "T6", f"    {num}. {item}")

    # ── คำลงท้าย ──────────────────────────────────────────────
    # Indented to the right by tabs, as in the signed precedent.
    # Pass "closing": "" to leave it out.
    closing = data.get("closing", "ขอแสดงความนับถือ")
    if closing:
        cp = para(body_text, "เนื้อความ")
        csp = etree.SubElement(cp, q("text", "span"),
                               {q("text", "style-name"): "T6"})
        tabs = [etree.SubElement(csp, q("text", "tab")) for _ in range(6)]
        tabs[-1].tail = closing

    # ── blank lines before signature ──────────────────────────
    for _ in range(4):
        para(body_text, "P3")

    # ── signature ─────────────────────────────────────────────
    # The leading tab hits the centre tab stop of the "ลงชื่อ" style.
    sig_p = para(body_text, "ลงชื่อ")
    etree.SubElement(sig_p, q("text", "tab"))
    span(sig_p, "T5", "(")
    span(sig_p, "T6", data.get("signer_name", ""))
    span(sig_p, "T5", ")")

    for role in data.get("signer_roles", []):
        rp = para(body_text, "P6")
        etree.SubElement(rp, q("text", "tab"))
        span(rp, "T6", role)

    # pretty_print must stay off: the newline + indentation lxml would insert
    # between sibling spans is rendered by ODF as a visible space, e.g.
    # "( ผู้ช่วยศาสตราจารย์ ... )" instead of "(ผู้ช่วยศาสตราจารย์ ...)".
    tree.write(os.path.join(work_dir, "content.xml"),
               xml_declaration=True, encoding="UTF-8")


# ══════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("Usage: build_memo.py <data.json>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)

    doc_type = data.get("type", "nai").lower()
    output = data.get("output") or os.path.join(
        os.getcwd(), "memo_output.odt")
    if not output.endswith(".odt"):
        output += ".odt"

    work_dir = f"/tmp/memo_build_{os.getpid()}"

    if doc_type == "nai":
        extract_ott(NAI_TEMPLATE, work_dir)
        build_nai(data, work_dir)
    elif doc_type == "nok":
        extract_ott(NOK_TEMPLATE, work_dir)
        build_nok(data, work_dir)
    else:
        print(f"Unknown type '{doc_type}'. Use 'nai' or 'nok'.", file=sys.stderr)
        sys.exit(1)

    pack_odt(work_dir, output)
    shutil.rmtree(work_dir, ignore_errors=True)
    print(output)


if __name__ == "__main__":
    main()

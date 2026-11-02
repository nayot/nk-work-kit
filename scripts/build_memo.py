#!/usr/bin/env python3
"""
Build Thai official documents from OTT templates.

Usage:
    python3 build_memo.py <data.json>

The JSON file describes all fields for the document.
See skills/draft-memo/SKILL.md for the full schema.

Numerals: from 01.11.2569 BUU official documents use Arabic digits (0-9);
Thai digits (๐-๙) only for documents addressed to สำนักพระราชวัง (BUU
administrative committee 10/2569, agenda 5.4.5; circular อว 8100/ว 13719,
22.10.2569). "numerals": "arabic" (default) turns every Thai digit in the
document into an Arabic one; "numerals": "thai" writes the generated numbers
(default date, attachment list) in Thai digits and leaves the given text as is.
"""

import json, os, re, shutil, sys, zipfile
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


TO_THAI = str.maketrans("0123456789", "๐๑๒๓๔๕๖๗๘๙")
TO_ARABIC = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
NUMERALS = ("arabic", "thai")


def num(text, numerals):
    """Write the digits of a generated number in the document's numerals."""
    return str(text).translate(TO_THAI if numerals == "thai" else TO_ARABIC)


def apply_numerals(body_text, numerals):
    """With Arabic numerals, turn every Thai digit in the body into an Arabic one.

    The JSON may still carry Thai digits (older drafts, copied text); the
    rule is enforced here so none reaches the document. Thai numerals leave
    the given text untouched: Arabic digits in e-mail addresses, URLs and
    English course names must survive.
    """
    if numerals != "arabic":
        return
    changed = 0
    for el in body_text.iter():
        for attr in ("text", "tail"):
            v = getattr(el, attr)
            if v and v != v.translate(TO_ARABIC):
                changed += sum(c in "๐๑๒๓๔๕๖๗๘๙" for c in v)
                setattr(el, attr, v.translate(TO_ARABIC))
    if changed:
        print(f"note: {changed} Thai digit(s) written as Arabic numerals "
              "(set \"numerals\": \"thai\" only for สำนักพระราชวัง)", file=sys.stderr)


def today_thai(be_prefix=True, numerals="arabic"):
    """Return today as a Thai Buddhist Era date string.

    บันทึกข้อความ dates read "8 ตุลาคม พ.ศ. 2569"; a หนังสือภายนอก date drops
    "พ.ศ." and reads "8 ตุลาคม 2569" (be_prefix=False). numerals="thai" gives
    "๘ ตุลาคม พ.ศ. ๒๕๖๙".
    """
    months = [
        "", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน",
        "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม",
        "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
    ]
    now = datetime.today()
    d = num(now.day, numerals)
    m = months[now.month]
    y = num(now.year + 543, numerals)
    return f"{d} {m} พ.ศ. {y}" if be_prefix else f"{d} {m} {y}"


def nok_date(date):
    """A หนังสือภายนอก date never carries "พ.ศ.": "8 ตุลาคม พ.ศ. 2569" -> "8 ตุลาคม 2569"."""
    return re.sub(r"\s*พ\.\s*ศ\.\s*", " ", date).strip()


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
    """A text:span. Runs of spaces are kept as typed: ODF collapses them to
    one unless the extra ones are <text:s text:c="n"/>, and the templates
    use double spaces ("ที่  อว", "ส่วนงาน  ", "ณยศ  คุรุกิจโกศล")."""
    el = etree.SubElement(parent, q("text", "span"),
                           {q("text", "style-name"): style})
    parts = re.split(r"( {2,})", text or "")
    el.text = parts[0]
    prev = None
    for i in range(1, len(parts), 2):
        run, after = parts[i], parts[i + 1]
        if prev is None:
            el.text = (el.text or "") + " "
        else:
            prev.tail = (prev.tail or "") + " "
        prev = etree.SubElement(el, q("text", "s"), {q("text", "c"): str(len(run) - 1)})
        prev.tail = after
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


# บันทึกข้อความ: where the subject / addressee starts, from the margin
# ("เรื่อง " bold and "เรียน " at 16pt TH SarabunPSK, as rendered from the .dotx).
NAI_SUBJECT_INDENT = "0.3264in"   # 23.5pt
NAI_TO_INDENT = "0.3403in"        # 24.5pt


def add_hanging_style(root, name, parent, indent):
    """A paragraph style with a tab stop at indent and a hanging indent to it."""
    auto = root.find(q("office", "automatic-styles"))
    st = etree.SubElement(auto, q("style", "style"), {
        q("style", "name"): name,
        q("style", "family"): "paragraph",
        q("style", "parent-style-name"): parent,
    })
    pp = etree.SubElement(st, q("style", "paragraph-properties"), {
        q("fo", "margin-left"): indent,
        q("fo", "text-indent"): f"-{indent}",
        q("style", "auto-text-indent"): "false",
    })
    stops = etree.SubElement(pp, q("style", "tab-stops"))
    etree.SubElement(stops, q("style", "tab-stop"), {q("style", "position"): indent})


def add_keep_styles(root, styles):
    """Add keep-with-next copies of paragraph styles: {new name: parent}.
    An automatic style (P4, P5) is copied with its properties; a common
    style is used as the parent."""
    auto = root.find(q("office", "automatic-styles"))
    by_name = {s.get(q("style", "name")): s for s in auto.findall(q("style", "style"))}
    for name, parent in styles.items():
        if parent in by_name:
            st = etree.fromstring(etree.tostring(by_name[parent]))
            st.set(q("style", "name"), name)
            auto.append(st)
        else:
            st = etree.SubElement(auto, q("style", "style"), {
                q("style", "name"): name,
                q("style", "family"): "paragraph",
                q("style", "parent-style-name"): parent,
            })
        pp = st.find(q("style", "paragraph-properties"))
        if pp is None:
            pp = etree.Element(q("style", "paragraph-properties"))
            st.insert(0, pp)
        pp.set(q("fo", "keep-with-next"), "always")


# ══════════════════════════════════════════════════════════════
# Internal memo (บันทึกข้อความภายใน)
# ══════════════════════════════════════════════════════════════

def build_nai(data, work_dir, numerals="arabic"):
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
    sw_text = dept + (f"  โทร. {phone}" if phone else "")
    span(sw, "T4", sw_text)

    # ── ที่ / วันที่ ──────────────────────────────────────────
    # As in แบบหนังสือภายใน-TH Sarabun.dotx: "ที่" + two spaces + number,
    # one tab to วันที่ at 3.15in, then a tab (default stop, 3.5in) and
    # three spaces before the date.
    td = para(body_text, "P3")
    span(td, "T3", "ที่")
    span(td, "T4", "  " + data.get("doc_number", ""))
    etree.SubElement(td, q("text", "tab"))
    span(td, "T3", "วันที่")
    t3_span = etree.SubElement(td, q("text", "span"),
                                {q("text", "style-name"): "T1"})
    etree.SubElement(t3_span, q("text", "tab"))
    span(td, "T4", "   " + data.get("date", today_thai(numerals=numerals)))

    # ── เรื่อง ────────────────────────────────────────────────
    # The text starts where the template's single space puts it (measured
    # on แบบหนังสือภายใน-TH Sarabun.dotx), set by a tab stop with a hanging
    # indent so a long subject wraps under itself, as on the หนังสือภายนอก.
    add_hanging_style(root, "PNaiSubj", "Standard", NAI_SUBJECT_INDENT)
    add_hanging_style(root, "PNaiTo", "เรียน", NAI_TO_INDENT)
    re_p = para(body_text, "PNaiSubj")
    span(re_p, "T3", "เรื่อง")
    etree.SubElement(re_p, q("text", "tab"))
    span(re_p, "T4", data.get("subject", ""))

    # ── เรียน ─────────────────────────────────────────────────
    rian = para(body_text, "PNaiTo")
    rian.text = "เรียน"
    etree.SubElement(rian, q("text", "tab"))
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
    attachments = data.get("attachments", [])
    if attachments:
        att_intro = para(body_text, "เนื้อความ")
        span(att_intro, "T6",
             "ทั้งนี้ได้แนบหลักฐานประกอบมาด้วย ดังนี้")
        for i, item in enumerate(attachments, 1):
            li = para(body_text, "เนื้อความ")
            span(li, "T6", f"    {num(i, numerals)}. {item}")

    # ── blank lines + signature, kept together ────────────────
    # On a full page the paragraph before the signature (normally
    # "จึงเรียนมาเพื่อ…"), the blank lines, name and roles move to the next
    # page as one block (Nayot's rule, 02.11.2026).
    add_keep_styles(root, {"PBodyKeep": "เนื้อความ", "P4K": "P4",
                           "PSigK": "ลงชื่อ", "P5K": "P5"})
    last = body_text[-1]
    if last.tag == q("text", "p") and last.get(q("text", "style-name")) == "เนื้อความ":
        last.set(q("text", "style-name"), "PBodyKeep")
    for _ in range(4):
        para(body_text, "P4K")

    sig_p = para(body_text, "PSigK")
    span(sig_p, "T7", "(")
    span(sig_p, "T8", data.get("signer_name", ""))
    span(sig_p, "T7", ")")

    for role in data.get("signer_roles", []):
        rp = para(body_text, "P5K")
        span(rp, "T8", role)

    # ── endorsers (e.g. ผู้บังคับบัญชาขั้นต้น), each below the signer ──
    # "endorsers": [{"name": "...", "roles": ["หัวหน้าภาควิชา..."]}]; an
    # empty name leaves a dotted line to sign and fill in by hand.
    for e in data.get("endorsers", []):
        for _ in range(3):
            para(body_text, "P4K")
        ep = para(body_text, "PSigK")
        span(ep, "T7", "(")
        span(ep, "T8", e.get("name") or "." * 50)
        span(ep, "T7", ")")
        for role in e.get("roles", []):
            rp = para(body_text, "P5K")
            span(rp, "T8", role)

    para(body_text, "Standard")

    apply_numerals(body_text, numerals)

    # pretty_print must stay off: the newline + indentation lxml would insert
    # between sibling spans is rendered by ODF as a visible space, e.g.
    # "( ผู้ช่วยศาสตราจารย์ ... )" instead of "(ผู้ช่วยศาสตราจารย์ ...)".
    tree.write(os.path.join(work_dir, "content.xml"),
               xml_declaration=True, encoding="UTF-8")


# Page geometry of แบบหนังสือภายนอก.ott (A4), in inches.
NOK_TEXT_WIDTH = 6.2996      # 8.2681 page - 1.1811 left - 0.7874 right
CONTACT_LINE_HEIGHT = 0.27   # one 14pt TH Sarabun New line
CONTACT_SPACE_ABOVE = 0.111  # หน่วยงานเจ้าของเรื่อง: 8pt above, contextual (first line only)


# เรื่อง / เรียน / อ้างถึง / สิ่งที่ส่งมาด้วย: the text starts two "M" widths
# after its label and wrapped lines align under the text (Nayot's choice,
# 02.11.2026; the .dotx's single tab stop at 0.5909in left a wider gap).
# Label widths are TH Sarabun New 14pt advances + 2 x M (7.672pt each).
LABEL_INDENT = {
    "เรื่อง": "0.4476in",            # 16.884pt + 15.344pt
    "เรียน": "0.4698in",             # 18.480pt + 15.344pt
    "อ้างถึง": "0.5376in",           # 23.366pt + 15.344pt
    "สิ่งที่ส่งมาด้วย": "0.9125in",   # 50.358pt + 15.344pt
}


# Numbered อ้างถึง / สิ่งที่ส่งมาด้วย items: the number sits at the label's
# text position and the item text one column further on, so wrapped lines
# align under the item text. 0.22in (15.8pt) fits "๙." (8.6pt) plus a gap.
LIST_NUMBER_COLUMN = 0.22


def _label_style(auto, name, stops_in, space_above=True):
    """A เรื่องเรียนอ้างถึงสิ่งที่ส่งมาด้วย paragraph style whose wrapped lines
    hang at the last tab stop (positions in inches). space_above=False drops
    the style's 8pt above (list items after the first)."""
    st = etree.SubElement(auto, q("style", "style"), {
        q("style", "name"): name,
        q("style", "family"): "paragraph",
        q("style", "parent-style-name"): "เรื่องเรียนอ้างถึงสิ่งที่ส่งมาด้วย",
    })
    hang = f"{stops_in[-1]:.4f}in"
    props = {
        q("fo", "margin-left"): hang,
        q("fo", "text-indent"): f"-{hang}",
        q("style", "auto-text-indent"): "false",
    }
    if not space_above:
        props[q("fo", "margin-top")] = "0in"
    pp = etree.SubElement(st, q("style", "paragraph-properties"), props)
    stops = etree.SubElement(pp, q("style", "tab-stops"))
    for pos in stops_in:
        etree.SubElement(stops, q("style", "tab-stop"),
                         {q("style", "position"): f"{pos:.4f}in"})


def add_label_styles(root):
    """Add one paragraph style per label ("PLbl0".."PLbl3"), each with its own
    hanging indent and tab stop at LABEL_INDENT[label], and a numbered-list
    variant ("PLbl0N"..) with a second stop LIST_NUMBER_COLUMN further on.
    Returns {label: style name} and {label: list style name}."""
    auto = root.find(q("office", "automatic-styles"))
    names, list_names = {}, {}
    for n, (label, indent) in enumerate(LABEL_INDENT.items()):
        pos = float(indent.removesuffix("in"))
        names[label] = f"PLbl{n}"
        _label_style(auto, names[label], [pos])
        list_names[label] = (f"PLbl{n}N", f"PLbl{n}C")
        _label_style(auto, f"PLbl{n}N", [pos, pos + LIST_NUMBER_COLUMN])
        _label_style(auto, f"PLbl{n}C", [pos, pos + LIST_NUMBER_COLUMN],
                     space_above=False)
    return names, list_names


def add_labelled_items(body_text, lbl, lbl_list, label, items, numerals):
    """One item: "label<tab>text". Several: the label once, then a numbered
    list, "label<tab>1.<tab>text" and "<tab>2.<tab>text" on the next lines."""
    if len(items) == 1:
        p = para(body_text, lbl[label])
        span(p, "T5", label)
        etree.SubElement(p, q("text", "tab"))
        span(p, "T6", items[0])
        return
    for i, item in enumerate(items, 1):
        p = para(body_text, lbl_list[label][0 if i == 1 else 1])
        if i == 1:
            span(p, "T5", label)
        etree.SubElement(p, q("text", "tab"))
        span(p, "T6", f"{num(i, numerals)}.")
        etree.SubElement(p, q("text", "tab"))
        span(p, "T6", item)


def add_sig_style(root):
    """Add "PSig": the template's ลงชื่อ lines (centre tab at 3.5437in), no
    spacing above or below and 14pt, so the blank lines between the closing
    and the signer's name are 14pt lines as in แบบหนังสือภายนอก.dotx. The
    lines keep together, so a full page moves the whole block to page 2."""
    auto = root.find(q("office", "automatic-styles"))
    st = etree.SubElement(auto, q("style", "style"), {
        q("style", "name"): "PSig",
        q("style", "family"): "paragraph",
        q("style", "parent-style-name"): "ลงชื่อ",
    })
    # keep-with-next: the closing, blank lines, name and roles move to the
    # next page as one block, never splitting the name from the closing.
    etree.SubElement(st, q("style", "paragraph-properties"), {
        q("fo", "margin-top"): "0in",
        q("fo", "margin-bottom"): "0in",
        q("style", "contextual-spacing"): "false",
        q("fo", "keep-with-next"): "always",
    })
    keep = etree.SubElement(auto, q("style", "style"), {
        q("style", "name"): "PBodyKeep",
        q("style", "family"): "paragraph",
        q("style", "parent-style-name"): "เนื้อความ",
    })
    etree.SubElement(keep, q("style", "paragraph-properties"),
                     {q("fo", "keep-with-next"): "always"})
    etree.SubElement(st, q("style", "text-properties"), {
        q("style", "font-name"): "TH Sarabun New",
        q("fo", "font-size"): "14pt",
        q("style", "font-size-asian"): "14pt",
        q("style", "font-name-complex"): "TH Sarabun New1",
        q("style", "font-size-complex"): "14pt",
    })


def add_contact_box(root, body_text, data):
    """Add the borderless contact box right after the signature block.

    The box is a frame anchored as a character in its own paragraph, the
    letter's last: it flows like a line of text, so it always follows the
    signer's last line and, through the signature block's keep-with-next,
    moves to the next page with it (the template's หน่วยงานเจ้าของเรื่อง
    lines follow the signature the same way; Nayot asked for a text box).

    Its lines use the template's หน่วยงานเจ้าของเรื่อง style (8pt above the
    first line, none between lines), 14pt TH Sarabun New as in the .dotx.

    Lines come from "contact_box"; without it, the box falls back to
    from_org alone and a warning asks for the real contact details.
    """
    lines = data.get("contact_box")
    if not lines:
        lines = [data.get("from_org", "")]
        print("warning: no contact_box given; the contact box shows from_org only",
              file=sys.stderr)

    auto = root.find(q("office", "automatic-styles"))
    st = etree.SubElement(auto, q("style", "style"), {
        q("style", "name"): "frContact",
        q("style", "family"): "graphic",
    })
    etree.SubElement(st, q("style", "graphic-properties"), {
        q("fo", "border"): "none",
        q("fo", "padding"): "0in",
        q("fo", "margin-left"): "0in",
        q("fo", "margin-right"): "0in",
        q("fo", "margin-top"): "0in",
        q("fo", "margin-bottom"): "0in",
        q("fo", "background-color"): "transparent",
        q("draw", "fill"): "none",
        q("draw", "stroke"): "none",
        q("style", "vertical-pos"): "top",
        q("style", "vertical-rel"): "line",
    })
    # The paragraph holding the box carries the 8pt gap above the first
    # contact line (inside a frame the style's own space above is dropped):
    # signer's last line -> contact line = one line + 8pt, as in the .dotx.
    ps = etree.SubElement(auto, q("style", "style"), {
        q("style", "name"): "PContact",
        q("style", "family"): "paragraph",
        q("style", "parent-style-name"): "Standard",
    })
    etree.SubElement(ps, q("style", "paragraph-properties"), {
        q("fo", "margin-top"): f"{CONTACT_SPACE_ABOVE}in",
        q("fo", "margin-bottom"): "0in",
        q("fo", "margin-left"): "0in",
        q("fo", "text-indent"): "0in",
    })

    height = CONTACT_LINE_HEIGHT * len(lines)
    anchor_p = para(body_text, "PContact")
    frame = etree.SubElement(anchor_p, q("draw", "frame"), {
        q("draw", "style-name"): "frContact",
        q("draw", "name"): "ContactBox",
        q("text", "anchor-type"): "as-char",
        q("svg", "width"): f"{NOK_TEXT_WIDTH}in",
        q("draw", "z-index"): "1",
    })
    box = etree.SubElement(frame, q("draw", "text-box"),
                           {q("fo", "min-height"): f"{height:.4f}in"})
    for line in lines:
        lp = etree.SubElement(box, q("text", "p"),
                              {q("text", "style-name"): "หน่วยงานเจ้าของเรื่อง"})
        span(lp, "T6", line)


# ══════════════════════════════════════════════════════════════
# External letter (หนังสือภายนอก)
# ══════════════════════════════════════════════════════════════

def build_nok(data, work_dir, numerals="arabic"):
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
    span(date_p, "T3", nok_date(data.get("date") or today_thai(be_prefix=False, numerals=numerals)))

    # ── เรื่อง ────────────────────────────────────────────────
    lbl, lbl_list = add_label_styles(root)
    re_p = para(body_text, lbl["เรื่อง"])
    span(re_p, "T5", "เรื่อง")
    etree.SubElement(re_p, q("text", "tab"))
    span(re_p, "T6", data.get("subject", ""))

    # ── เรียน ─────────────────────────────────────────────────
    rian_p = para(body_text, lbl["เรียน"])
    span(rian_p, "T5", "เรียน")
    etree.SubElement(rian_p, q("text", "tab"))
    span(rian_p, "T5", data.get("to", ""))

    # ── อ้างถึง / สิ่งที่ส่งมาด้วย (several items: a numbered list) ──
    for key, label in (("references", "อ้างถึง"), ("enclosures", "สิ่งที่ส่งมาด้วย")):
        items = [x for x in data.get(key, []) if x]
        if items:
            add_labelled_items(body_text, lbl, lbl_list, label, items, numerals)

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
    for i, item in enumerate(data.get("attachments", []), 1):
        li = para(body_text, "เนื้อความ")
        span(li, "T6", f"    {num(i, numerals)}. {item}")

    # ── คำลงท้าย / ลงชื่อ: as in แบบหนังสือภายนอก.dotx ─────────────
    # One blank 14pt line after the body, then the closing, two blank
    # lines, the signer's name and roles. All of them are ลงชื่อ lines with
    # no spacing whose leading tab hits the centre tab stop (3.5437in).
    # Pass "closing": "" to leave the closing out.
    # On a full page the block moves to the next page together with the
    # paragraph before it (normally "จึงเรียนมาเพื่อ…"), never alone.
    add_sig_style(root)
    last = body_text[-1]
    if last.tag == q("text", "p") and last.get(q("text", "style-name")) == "เนื้อความ":
        last.set(q("text", "style-name"), "PBodyKeep")
    para(body_text, "PSig")
    closing = data.get("closing", "ขอแสดงความนับถือ")
    if closing:
        cp = para(body_text, "PSig")
        etree.SubElement(cp, q("text", "tab"))
        span(cp, "T6", closing)

    for _ in range(2):
        para(body_text, "PSig")

    sig_p = para(body_text, "PSig")
    etree.SubElement(sig_p, q("text", "tab"))
    span(sig_p, "T5", "(")
    span(sig_p, "T6", data.get("signer_name", ""))
    span(sig_p, "T5", ")")

    for role in data.get("signer_roles", []):
        rp = para(body_text, "PSig")
        etree.SubElement(rp, q("text", "tab"))
        span(rp, "T6", role)

    # ── contact box (ส่วนราชการเจ้าของเรื่อง / โทร / อีเมล) ─────────
    # Always present on a หนังสือภายนอก: a borderless text box right
    # after the signature block, kept on the same page as it.
    add_contact_box(root, body_text, data)

    apply_numerals(body_text, numerals)

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

    numerals = (data.get("numerals") or "arabic").lower()
    if numerals not in NUMERALS:
        print(f"Unknown numerals '{numerals}'. Use 'arabic' or 'thai'.", file=sys.stderr)
        sys.exit(1)
    if numerals == "arabic" and "สำนักพระราชวัง" in data.get("to", ""):
        print("warning: addressed to สำนักพระราชวัง, which takes Thai numerals; "
              "set \"numerals\": \"thai\"", file=sys.stderr)

    work_dir = f"/tmp/memo_build_{os.getpid()}"

    if doc_type == "nai":
        extract_ott(NAI_TEMPLATE, work_dir)
        build_nai(data, work_dir, numerals)
    elif doc_type == "nok":
        extract_ott(NOK_TEMPLATE, work_dir)
        build_nok(data, work_dir, numerals)
    else:
        print(f"Unknown type '{doc_type}'. Use 'nai' or 'nok'.", file=sys.stderr)
        sys.exit(1)

    pack_odt(work_dir, output)
    shutil.rmtree(work_dir, ignore_errors=True)
    print(output)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build a vCard 3.0 (.vcf) file from extracted business-card JSON.

Usage: python3 make_vcf.py contact.json output.vcf
"""
import json
import sys


def esc(value):
    """Escape characters that are special in vCard text values."""
    return (str(value).replace("\\", "\\\\").replace(",", "\\,")
            .replace(";", "\\;").replace("\n", "\\n"))


def build(c):
    given, family = c.get("given_name", ""), c.get("family_name", "")
    prefix = c.get("prefix", "")
    full = " ".join(p for p in [prefix, given, family] if p).strip()
    lines = ["BEGIN:VCARD", "VERSION:3.0",
             f"N:{esc(family)};{esc(given)};;{esc(prefix)};",
             f"FN:{esc(full or c.get('alt_name', 'Unknown'))}"]
    if c.get("alt_name"):
        lines.append(f"NICKNAME:{esc(c['alt_name'])}")
    if c.get("org") or c.get("department"):
        lines.append(f"ORG:{esc(c.get('org', ''))};{esc(c.get('department', ''))}")
    if c.get("title"):
        lines.append(f"TITLE:{esc(c['title'])}")
    type_map = {"mobile": "CELL", "cell": "CELL", "work": "WORK",
                "fax": "FAX", "home": "HOME"}
    for p in c.get("phones", []):
        t = type_map.get(str(p.get("type", "work")).lower(), "VOICE")
        lines.append(f"TEL;TYPE={t}:{p['number']}")
    for e in c.get("emails", []):
        t = str(e.get("type", "work")).upper()
        lines.append(f"EMAIL;TYPE=INTERNET,{t}:{e['address']}")
    for u in c.get("urls", []):
        lines.append(f"URL:{u}")
    a = c.get("address")
    if a:
        parts = [a.get(k, "") for k in ("street", "city", "region", "postcode", "country")]
        lines.append("ADR;TYPE=WORK:;;" + ";".join(esc(x) for x in parts))
    if c.get("note"):
        lines.append(f"NOTE:{esc(c['note'])}")
    lines.append("END:VCARD")
    return "\r\n".join(lines) + "\r\n"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as f:
        contact = json.load(f)
    with open(sys.argv[2], "w", encoding="utf-8", newline="") as f:
        f.write(build(contact))
    print(f"Wrote {sys.argv[2]}")

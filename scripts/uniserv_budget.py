#!/usr/bin/env python3
"""Budget arithmetic for a BUU academic-service project (โครงการบริการวิชาการ).

Rules: ระเบียบมหาวิทยาลัยบูรพา ว่าด้วยการบริหารโครงการบริการวิชาการ พ.ศ. 2565
(text in skills/uniserv-project/regulation-2565.md).

  ข้อ 16  ค่าใช้จ่าย (1)–(7) = the project's expenditure E ("ค่าบริการวิชาการ").
          ค่าธรรมเนียมบริการวิชาการ is reckoned on E (not on gross revenue), at least 12% in total.
  ข้อ 17  of which ≥ 7% of E goes to the university and ≥ 5% of E to the faculty;
          each part, if it has a remainder below ten, is rounded UP to the next ten.
  ข้อ 19  committee pay (item (6)) is capped on E by a sliding scale:
          20% of the first 1M, 15% of the next 1M, 10% of the next 1M, 5% above 3M.

Faculty of Engineering practice (finance, Nov 2026): university 7% + faculty 8% = 15% of E.
With revenue R fixed, E and the fee must satisfy E + fee(E) = R, so the fee is NOT 15% of R:
R = 195,600 → E = 170,080, fee = 11,910 + 13,610 = 25,520.

Usage
  python3 uniserv_budget.py fee E [--uni 7] [--fac 8]       fee on an expenditure total
  python3 uniserv_budget.py solve R [--uni 7] [--fac 8]     split revenue R into E + fee
  python3 uniserv_budget.py cap E                           ข้อ 19 ceiling for committee pay
  python3 uniserv_budget.py check BUDGET.json [--json]      check a whole budget (exit 1 on problems)
  python3 uniserv_budget.py words N                         Thai baht words
  python3 uniserv_budget.py selftest

BUDGET.json
  {
    "university_rate": 7, "faculty_rate": 8,          # percent of E; defaults 7 and 8
    "revenue": [ {"label": "...", "qty": 40, "unit": 4890, "amount": 195600} ],
    "fee": 25520,                                     # optional: the fee as written in the proposal
    "items": [
      {"label": "ค่าตอบแทนวิทยากร", "qty": [5, 14], "unit": 1700, "amount": 119000},
      {"label": "ค่าตอบแทนคณะกรรมการบริหารโครงการ", "committee": true, "amount": 9880}
    ]
  }
  qty may be a number or a list of factors; amount must equal product(qty) * unit when both are given.
"""
import json
import math
import sys

UNI_MIN, FAC_MIN, TOTAL_MIN = 7, 5, 12          # ข้อ 16 วรรคสอง, ข้อ 17 (percent of E)
CAP_TIERS = [(1_000_000, 20), (1_000_000, 15), (1_000_000, 10), (None, 5)]  # ข้อ 19 วรรคสาม

THAI_DIGIT = ["", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
THAI_PLACE = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน"]


def _thai_int(n):
    if n == 0:
        return "ศูนย์"
    if n >= 1_000_000:
        hi, lo = divmod(n, 1_000_000)
        return _thai_int(hi) + "ล้าน" + (_thai_int(lo) if lo else "")
    out, digits = "", str(n)
    for i, ch in enumerate(digits):
        d, place = int(ch), len(digits) - i - 1
        if d == 0:
            continue
        if place == 1 and d == 1:
            out += "สิบ"
        elif place == 1 and d == 2:
            out += "ยี่สิบ"
        elif place == 0 and d == 1 and len(digits) > 1:
            out += "เอ็ด"
        else:
            out += THAI_DIGIT[d] + THAI_PLACE[place]
    return out


def baht_words(amount):
    """170080 → 'หนึ่งแสนเจ็ดหมื่นแปดสิบบาทถ้วน'."""
    satang = round(float(amount) * 100)
    b, s = divmod(satang, 100)
    return _thai_int(b) + "บาท" + (_thai_int(s) + "สตางค์" if s else "ถ้วน")


def ceil10(x):
    """Round up to the next ten (ข้อ 16–17: 'มีเศษไม่ถึงสิบ ให้ปัดขึ้นเป็นจำนวนเต็มสิบ').

    Works in satang so 11905.6 → 11910 and an exact 11900 stays 11900.
    """
    satang = round(x * 100)
    return math.ceil(satang / 1000) * 10


def fee(E, uni=7, fac=8):
    """(university part, faculty part, total) on expenditure E; each part rounded up to ten."""
    u = ceil10(E * uni / 100)
    f = ceil10(E * fac / 100)
    return u, f, u + f


def solve(R, uni=7, fac=8):
    """Largest whole-baht E with E + fee(E) <= R. Returns (E, u, f, remainder R - E - fee)."""
    E = int(R / (1 + (uni + fac) / 100)) + 20       # start just above the real-valued solution
    while E > 0:
        u, f, t = fee(E, uni, fac)
        if E + t <= R:
            return E, u, f, R - E - t
        E -= 1
    raise ValueError("revenue too small")


def committee_cap(E):
    """ข้อ 19 วรรคสาม: ceiling for committee pay on expenditure E (ค่าบริการวิชาการ)."""
    cap, left = 0.0, E
    for size, pct in CAP_TIERS:
        part = left if size is None else min(left, size)
        cap += part * pct / 100
        left -= part
        if left <= 0:
            break
    return round(cap, 2)


def _prod(q):
    if isinstance(q, list):
        return math.prod(q)
    return q


def check(b):
    """Return (report dict, problems list)."""
    uni, fac = b.get("university_rate", 7), b.get("faculty_rate", 8)
    probs = []
    if uni < UNI_MIN:
        probs.append(f"university_rate {uni}% is below the ข้อ 17 floor of {UNI_MIN}%")
    if fac < FAC_MIN:
        probs.append(f"faculty_rate {fac}% is below the ข้อ 17 floor of {FAC_MIN}%")
    for group in ("revenue", "items"):
        for it in b.get(group, []):
            if "qty" in it and "unit" in it:
                want = _prod(it["qty"]) * it["unit"]
                if "amount" not in it:
                    it["amount"] = want
                elif abs(want - it["amount"]) > 0.005:
                    probs.append(f"{it['label']}: amount {it['amount']:,} ≠ {it['qty']} × {it['unit']:,} = {want:,}")
            if "amount" not in it:
                probs.append(f"{it['label']}: no amount")
                it["amount"] = 0
    R = sum(it["amount"] for it in b.get("revenue", []))
    E = sum(it["amount"] for it in b.get("items", []))
    u, f, t = fee(E, uni, fac)
    stated = b.get("fee", t)
    if stated < t:
        probs.append(f"fee {stated:,} is below {uni}% + {fac}% of expenditure {E:,} = {u:,} + {f:,} = {t:,}")
    if R and abs(R - stated - E) > 0.005:
        probs.append(f"revenue {R:,} − fee {stated:,} = {R - stated:,} ≠ expenditure {E:,}")
        if R:
            sE, su, sf, rem = solve(R, uni, fac)
            probs.append(f"  for revenue {R:,}: expenditure {sE:,}, fee {su:,} + {sf:,} = {su + sf:,}"
                         + (f", {rem:,} left over" if rem else ""))
    comm = sum(it["amount"] for it in b.get("items", []) if it.get("committee"))
    cap = committee_cap(E)
    if comm > cap:
        probs.append(f"committee pay {comm:,} exceeds the ข้อ 19 cap {cap:,.2f} on expenditure {E:,}")
    rep = {
        "revenue": R, "expenditure": E, "fee_stated": stated,
        "fee_minimum": {"university": u, "faculty": f, "total": t, "rates": [uni, fac]},
        "committee": comm, "committee_cap": cap,
        "words": {"revenue": baht_words(R) if R else "", "expenditure": baht_words(E)},
        "fee_label": f"ร้อยละ {uni + fac} ของค่าใช้จ่ายดำเนินโครงการ",
    }
    return rep, probs


def _rates(argv):
    uni, fac = 7, 8
    if "--uni" in argv:
        uni = float(argv[argv.index("--uni") + 1])
    if "--fac" in argv:
        fac = float(argv[argv.index("--fac") + 1])
    return uni, fac


def selftest():
    assert ceil10(11905.6) == 11910 and ceil10(11900) == 11900 and ceil10(13606.4) == 13610
    assert fee(170080) == (11910, 13610, 25520)
    assert solve(195600) == (170080, 11910, 13610, 0)
    assert committee_cap(5_971_120) == 598_556          # DCI 2026 ceiling
    assert committee_cap(170_080) == 34_016
    assert baht_words(170080) == "หนึ่งแสนเจ็ดหมื่นแปดสิบบาทถ้วน"
    assert baht_words(195600) == "หนึ่งแสนเก้าหมื่นห้าพันหกร้อยบาทถ้วน"
    ex = {"revenue": [{"label": "reg", "qty": 40, "unit": 4890}], "fee": 25520,
          "items": [{"label": "a", "qty": [5, 14], "unit": 1700}, {"label": "b", "amount": 41200},
                    {"label": "c", "committee": True, "amount": 9880}]}
    rep, probs = check(ex)
    assert not probs and rep["expenditure"] == 170080, probs
    ex["fee"] = 29340                                    # 15% of revenue: must be flagged
    assert check(ex)[1]
    print("selftest: ok")


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[1]
    if cmd == "selftest":
        selftest()
        return 0
    if cmd == "words":
        print(baht_words(float(argv[2].replace(",", ""))))
        return 0
    if cmd in ("fee", "solve", "cap"):
        n = float(argv[2].replace(",", ""))
        n = int(n) if n.is_integer() else n
        uni, fac = _rates(argv)
        if cmd == "fee":
            u, f, t = fee(n, uni, fac)
            print(f"expenditure {n:,.0f}: university {uni:g}% {u:,} + faculty {fac:g}% {f:,} = fee {t:,}")
        elif cmd == "solve":
            E, u, f, rem = solve(n, uni, fac)
            print(f"revenue {n:,.0f} = expenditure {E:,} + fee {u + f:,} (university {u:,} + faculty {f:,})"
                  + (f" + {rem:,} left over" if rem else ""))
            print(f"expenditure in words: {baht_words(E)}")
        else:
            print(f"committee pay cap on expenditure {n:,.0f}: {committee_cap(n):,.2f}")
        return 0
    if cmd == "check":
        with open(argv[2], encoding="utf-8") as fh:
            b = json.load(fh)
        rep, probs = check(b)
        if "--json" in argv:
            print(json.dumps({"report": rep, "problems": probs}, ensure_ascii=False, indent=1))
        else:
            m = rep["fee_minimum"]
            print(f"revenue      {rep['revenue']:>12,}  {rep['words']['revenue']}")
            print(f"fee          {rep['fee_stated']:>12,}  (minimum {m['university']:,} + {m['faculty']:,} = {m['total']:,}; "
                  f"label: {rep['fee_label']})")
            print(f"expenditure  {rep['expenditure']:>12,}  {rep['words']['expenditure']}")
            print(f"committee    {rep['committee']:>12,}  (ข้อ 19 cap {rep['committee_cap']:,.2f})")
            print("OK" if not probs else "PROBLEMS:\n- " + "\n- ".join(probs))
        return 1 if probs else 0
    print(f"unknown command {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

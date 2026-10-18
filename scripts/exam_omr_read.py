# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "opencv-python-headless"]
# ///
"""Read scanned bubble answer sheets, mark them, and list what needs a human (or AI) decision.

    uv run exam_omr_read.py --spec SPEC.json --key KEY.txt SCANS.pdf [more.pdf | page.png ...] --out DIR
        [--roster roster.csv] [--overrides DIR/overrides.csv] [--dpi 200]

Scan: grayscale, 200-300 dpi, 100 % scale, the whole stack as one PDF; orientation doesn't matter.
KEY.txt: the answers as letters from the spec's `choices`, in order; lines starting with # are skipped.
roster.csv: student_id plus name (optional title, reg_status; W = withdrawn is flagged).
Writes to DIR:
  results.csv      one row per sheet: page, student_id, name, Q1..Qn, one column per part, total, pending, flags
  review.csv       every item that needs a decision, with the measured fill of each bubble
  review/          a cropped image per review item (page-item.png)
  annotated/       each sheet with what was read: green = counted, red = needs review
  overrides.csv    created empty; decisions go here (page,item,value; item = ID or Q1..Qn,
                   value = the ID, a choice letter, or - for blank). Re-run with --overrides.

HARD-WON DETAILS (synthetic tests, Oct 2026: 60 sheets, 3 480 clear answers, 0 counted wrongly)
- Fill = mean darkness inside the printed ring (0 = this sheet's paper, 1 = black), sampled at
  0.7 x the ring radius so the outline itself never counts.
- A row is counted when exactly one bubble is >= MARK (0.40) and leads the runner-up by GAP (0.25).
  Blank when every bubble is < BLANK (0.08): true blanks read < 0.03, while faint pencil marks
  read 0.17-0.22, so a faint mark always goes to review instead of silently scoring as blank.
  Erased smudges read up to ~0.14 and are ignored when a real mark is in the same row.
- Anything else is never guessed: it goes to review.csv with a crop.
- Upside-down scans are turned: the printed title sits top-left, and the strip at y 271-279 mm
  (between the last answer row and the fingerprint) is blank on a right-way-up sheet.
- Before reading, every sheet is checked against the spec, twice: the 18-square fingerprint at the
  bottom must equal the layout's, and the printed rings must sit where the layout puts them
  (median ring darkness >= RING_MIN). The fingerprint is the check that matters: two layouts can
  have rings one option-pitch apart, which the ring check alone accepts while every answer reads
  one column off. A failure stops with "sheet does not match spec" and nothing on that sheet is
  read. The sheet's grey layout code (e.g. 60/ABCD/8) says which spec it needs.
"""
import argparse
import csv
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exam_omr_layout as G  # noqa: E402

PX = 10.0          # canonical resolution, px per mm
MARK, BLANK, GAP = 0.40, 0.08, 0.25
RING_MIN = 0.05    # printed outlines read well above this; bare paper ~0.01


def rasterise(paths, dpi, tmp):
    pages = []
    for p in map(Path, paths):
        if p.suffix.lower() == ".pdf":
            stem = Path(tmp) / p.stem
            subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png", str(p), str(stem)], check=True)
            pages += [(f"{p.name}:{i + 1}", q) for i, q in enumerate(sorted(Path(tmp).glob(p.stem + "-*.png")))]
        else:
            pages.append((p.name, p))
    return pages


def find_fiducials(gray, dpi):
    side = G.FID_SIZE * dpi / 25.4
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    cnts, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cands = []
    for c in cnts:
        (cx, cy), (w, h), _ = cv2.minAreaRect(c)
        if not (0.6 * side < w < 1.5 * side and 0.6 * side < h < 1.5 * side):
            continue
        if not 0.75 < w / h < 1.33 or cv2.contourArea(c) < 0.85 * w * h:
            continue
        cands.append((cx, cy))
    if len(cands) < 4:
        return None
    H, W = gray.shape
    corners = {"tl": (0, 0), "tr": (W, 0), "bl": (0, H), "br": (W, H)}
    pts = {k: min(cands, key=lambda p: (p[0] - x0) ** 2 + (p[1] - y0) ** 2) for k, (x0, y0) in corners.items()}
    return pts if len(set(pts.values())) == 4 else None


def warp(gray, pts):
    dst = G.Layout.fiducial_centres()
    keys = ["tl", "tr", "bl", "br"]
    M = cv2.getPerspectiveTransform(np.float32([pts[k] for k in keys]),
                                    np.float32([[dst[k][0] * PX, dst[k][1] * PX] for k in keys]))
    return cv2.warpPerspective(gray, M, (int(G.PAGE_W * PX), int(G.PAGE_H * PX)), borderValue=255)


def darkness(img):
    white = float(np.percentile(img, 90))
    return np.clip((white - img.astype(np.float32)) / max(white, 1.0), 0, 1)


def region_dark(dk, x0, y0, x1, y1):
    return float(dk[int(y0 * PX):int(y1 * PX), int(x0 * PX):int(x1 * PX)].mean())


class Sampler:
    def __init__(self, L):
        r = int(round(L.read_r * PX))
        yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
        self.r, self.disk = r, (xx ** 2 + yy ** 2) <= r * r
        R = int(round((L.bubble_r + 0.5) * PX))
        yy, xx = np.mgrid[-R:R + 1, -R:R + 1]
        d = np.sqrt(xx ** 2 + yy ** 2)
        self.R, self.ring = R, np.abs(d - L.bubble_r * PX) <= 0.4 * PX

    def fill(self, dk, x, y):
        cx, cy = int(round(x * PX)), int(round(y * PX))
        return float(dk[cy - self.r:cy + self.r + 1, cx - self.r:cx + self.r + 1][self.disk].mean())

    def ring_dark(self, dk, x, y):
        cx, cy = int(round(x * PX)), int(round(y * PX))
        return float(dk[cy - self.R:cy + self.R + 1, cx - self.R:cx + self.R + 1][self.ring].mean())


def decide(vals, labels):
    """(value, status), status in ok | blank | multiple | unclear."""
    order = sorted(range(len(vals)), key=lambda i: -vals[i])
    top, second = vals[order[0]], vals[order[1]]
    if top < BLANK:
        return "-", "blank"
    marked = [i for i in range(len(vals)) if vals[i] >= MARK]
    if len(marked) == 1 and top - second >= GAP:
        return labels[order[0]], "ok"
    return "?", ("multiple" if len(marked) >= 2 else "unclear")


def read_page(gray, dpi, L, S):
    pts = find_fiducials(gray, dpi)
    if pts is None:
        return None, None, "corner squares not found"
    img = warp(gray, pts)
    dk = darkness(img)
    if region_dark(dk, 40, 12, 150, 26) < region_dark(dk, 60, 271, 170, 279):
        img = cv2.rotate(img, cv2.ROTATE_180)
        dk = darkness(img)
    fp = [1 if region_dark(dk, x + 0.5, y + 0.5, x + L.FP_SIZE - 0.5, y + L.FP_SIZE - 0.5) > 0.5 else 0
          for x, y in (L.fp_square(i) for i in range(L.FP_N))]
    if fp != L.fingerprint():
        return img, None, (f"sheet does not match spec {L.code()} (layout fingerprint differs); check the layout "
                           "code printed on the sheet, the spec, and that it was copied at 100 %")
    rings = [S.ring_dark(dk, *L.answer_bubble(q, i)) for q in range(1, L.n_q + 1) for i in range(len(L.choices))]
    ring = float(np.median(rings))
    if ring < RING_MIN:
        return img, None, (f"sheet does not match spec {L.code()} (ring {ring:.3f}); check the layout code "
                           "printed on the sheet and that it was copied at 100 %")
    res = {"id_cols": [], "q": {}, "ring": ring}
    for c in range(L.id_digits):
        vals = [S.fill(dk, *L.id_bubble(c, d)) for d in range(10)]
        res["id_cols"].append((decide(vals, "0123456789"), vals))
    for q in range(1, L.n_q + 1):
        vals = [S.fill(dk, *L.answer_bubble(q, i)) for i in range(len(L.choices))]
        res["q"][q] = (decide(vals, L.choices), vals)
    return img, res, ""


def crop_row(img, L, q):
    x, y = L.answer_label(q)
    return img[int((y - 4) * PX):int((y + 4) * PX), int((x - 3) * PX):int((x + L.block_w + 3) * PX)]


def crop_id(img, L):
    x0 = L.id_x0 - L.id_col_pitch
    return img[int((L.id_box_y - 1) * PX):int((L.id_bubble(0, 9)[1] + 4) * PX),
               int(x0 * PX):int((L.id_right + L.id_col_pitch) * PX)]


def annotate(img, res, L):
    out = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    r = int(L.bubble_r * PX) + 6

    def mark(xy, colour):
        cv2.circle(out, (int(xy[0] * PX), int(xy[1] * PX)), r, colour, 3)
    for c, ((v, st), vals) in enumerate(res["id_cols"]):
        if st == "ok":
            mark(L.id_bubble(c, int(v)), (0, 160, 0))
        else:
            for d in range(10):
                if vals[d] >= BLANK:
                    mark(L.id_bubble(c, d), (0, 0, 230))
    for q, ((v, st), vals) in res["q"].items():
        if st == "ok":
            mark(L.answer_bubble(q, L.choices.index(v)), (0, 160, 0))
        elif st != "blank":
            for i in range(len(L.choices)):
                if vals[i] >= BLANK:
                    mark(L.answer_bubble(q, i), (0, 0, 230))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("scans", nargs="+")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--roster", help="CSV with student_id,name (optional title, reg_status)")
    ap.add_argument("--overrides")
    ap.add_argument("--dpi", type=int, default=200)
    a = ap.parse_args()

    spec = G.load_spec(a.spec)
    L = G.Layout(spec)
    S = Sampler(L)
    key = "".join(ch for line in Path(a.key).read_text(encoding="utf-8").splitlines() if not line.startswith("#")
                  for ch in line if ch in L.choices)
    if len(key) != L.n_q:
        sys.exit(f"key has {len(key)} answers, spec says {L.n_q}")
    ppq = float(spec.get("points_per_question", 1))
    parts = spec.get("parts") or []
    roster, withdrawn = {}, set()
    if a.roster:
        for r in csv.DictReader(open(a.roster, encoding="utf-8-sig")):
            sid = r["student_id"].strip()
            roster[sid] = " ".join(x for x in (r.get("title", ""), r.get("name", "")) if x).strip()
            if (r.get("reg_status") or "").strip().upper() == "W":
                withdrawn.add(sid)
    over = {}
    if a.overrides and Path(a.overrides).exists():
        for r in csv.DictReader(open(a.overrides, encoding="utf-8-sig")):
            over[(r["page"].strip(), r["item"].strip().upper())] = r["value"].strip().upper()

    out = Path(a.out)
    (out / "review").mkdir(parents=True, exist_ok=True)
    (out / "annotated").mkdir(exist_ok=True)
    for old in (out / "review").glob("*.png"):
        old.unlink()
    print(f"reading against layout {L.code()}")
    rows, review, seen, mismatch = [], [], {}, 0
    with tempfile.TemporaryDirectory() as tmp:
        for page, path in rasterise(a.scans, a.dpi, tmp):
            gray = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            img, res, err = read_page(gray, a.dpi, L, S)
            safe = page.replace(":", "_p").replace("/", "_")
            if err:
                mismatch += "does not match" in err
                review.append(dict(page=page, item="PAGE", status=err, read="", fills=""))
                rows.append(dict(page=page, flags=err))
                continue
            cv2.imwrite(str(out / "annotated" / f"{safe}.jpg"), annotate(img, res, L), [cv2.IMWRITE_JPEG_QUALITY, 80])
            sid = "".join(v if st == "ok" else "?" for (v, st), _ in res["id_cols"])
            id_status = "ok" if "?" not in sid else "unclear"
            if (page, "ID") in over:
                sid, id_status = over[(page, "ID")], "override"
            elif id_status == "ok" and roster and sid not in roster:
                id_status = "not in roster"
            elif id_status == "ok" and sid in withdrawn:
                id_status = "withdrawn (W)"
            if id_status not in ("ok", "override"):
                review.append(dict(page=page, item="ID", status=id_status, read=sid,
                                   fills=" | ".join(",".join(f"{x:.2f}" for x in vals) for _, vals in res["id_cols"])))
                cv2.imwrite(str(out / "review" / f"{safe}-ID.png"), crop_id(img, L))
            ans, flags = {}, []
            for q, ((v, st), vals) in res["q"].items():
                if (page, f"Q{q}") in over:
                    v = over[(page, f"Q{q}")]
                elif st in ("multiple", "unclear"):
                    review.append(dict(page=page, item=f"Q{q}", status=st, read=v,
                                       fills=",".join(f"{c}={x:.2f}" for c, x in zip(L.choices, vals))))
                    cv2.imwrite(str(out / "review" / f"{safe}-Q{q}.png"), crop_row(img, L, q))
                    flags.append(f"Q{q}:{st}")
                ans[q] = v
            blanks = sum(1 for q in ans if ans[q] == "-")
            if blanks > L.n_q // 6:
                flags.append(f"{blanks} blanks")
            if sid in seen and "?" not in sid:
                flags.append(f"duplicate ID (also {seen[sid]})")
            seen[sid] = page
            row = dict(page=page, student_id=sid, id_status=id_status, name=roster.get(sid, ""))
            row.update({f"Q{q}": ans[q] for q in range(1, L.n_q + 1)})
            total = 0.0
            for p in parts:
                sc = sum(ans[q] == key[q - 1] for q in range(p["first"], p["last"] + 1)) * ppq
                row[p["name"]] = sc
                total += sc
            if not parts:
                total = sum(ans[q] == key[q - 1] for q in range(1, L.n_q + 1)) * ppq
            row.update(total=total, pending=sum(1 for q in ans if ans[q] == "?"), flags="; ".join(flags))
            rows.append(row)

    cols = ["page", "student_id", "id_status", "name"] + [f"Q{q}" for q in range(1, L.n_q + 1)] + \
           [p["name"] for p in parts] + ["total", "pending", "flags"]
    with open(out / "results.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    with open(out / "review.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, ["page", "item", "status", "read", "fills"])
        w.writeheader()
        w.writerows(review)
    if not (out / "overrides.csv").exists():
        (out / "overrides.csv").write_text("page,item,value\n", encoding="utf-8")
    print(f"{len(rows)} sheets, {len(review)} items to review -> {out}")
    if mismatch:
        sys.exit(f"STOP: {mismatch} sheet(s) do not match layout {L.code()}; nothing on them was read")


if __name__ == "__main__":
    main()

# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "opencv-python-headless", "pillow"]
# ///
"""Make fake filled-in scans of an answer sheet, read them with exam_omr_read.py, and score the reader.

    uv run exam_omr_test.py --spec SPEC.json --sheet answer_sheet.pdf --work DIR [--n 40] [--seed 11]

Each fake sheet has pencil-grey marks of uneven size, plus deliberate trouble: a blank, a double
mark, a faint mark, an erased answer with a remaining smudge, and on some sheets a stray tick.
Pages are rotated (+-2.5 deg), scaled (95-102 %), shifted, blurred and noised; one is upside down.
Passing means: every ID right, 0 clear answers read wrongly, every trouble item sent to review,
no false alarms. Run it after any change to the layout or the reader, and before an exam on the
real sheet. It does not replace one real test: print ~10 sheets, fill them by hand, scan on the
copier that will be used, and read them.
"""
import argparse
import csv
import random
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exam_omr_layout as G  # noqa: E402

DPI = 200
MM = DPI / 25.4


def blob(img, L, x, y, grey, cover, rng):
    r = L.bubble_r * MM * cover
    cx, cy = int(x * MM + rng.uniform(-0.4, 0.4) * MM), int(y * MM + rng.uniform(-0.4, 0.4) * MM)
    mask = np.zeros_like(img)
    cv2.ellipse(mask, (cx, cy), (int(r * rng.uniform(0.9, 1.1)), int(r * rng.uniform(0.85, 1.05))),
                rng.uniform(0, 180), 0, 360, 255, -1)
    tex = np.clip(grey + np.asarray(rng.normal(0, 25, img.shape)), 0, 255).astype(np.uint8)
    img[mask > 0] = np.minimum(img[mask > 0], tex[mask > 0])


def distort(img, rng, flip):
    h, w = img.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), rng.uniform(-2.5, 2.5), rng.uniform(0.95, 1.02))
    M[:, 2] += rng.uniform(-40, 40, 2)
    out = cv2.warpAffine(img, M, (w, h), borderValue=int(rng.uniform(225, 250)))
    out = cv2.GaussianBlur(out, (3, 3), rng.uniform(0.3, 1.0))
    out = np.clip(out.astype(np.float32) * rng.uniform(0.88, 1.0) + rng.normal(0, 6, out.shape), 0, 255).astype(np.uint8)
    return cv2.rotate(out, cv2.ROTATE_180) if flip else out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--spec", required=True)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    L = G.Layout(G.load_spec(a.spec))
    C = L.choices
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    subprocess.run(["pdftoppm", "-r", str(DPI), "-gray", "-png", "-singlefile", a.sheet, str(work / "blank")], check=True)
    blank = cv2.imread(str(work / "blank.png"), cv2.IMREAD_GRAYSCALE)
    rng, prng = np.random.default_rng(a.seed), random.Random(a.seed)
    key = "".join(prng.choice(C) for _ in range(L.n_q))
    (work / "key.txt").write_text(key + "\n", encoding="utf-8")
    pages, truth = [], []
    for s in range(a.n):
        img = blank.copy()
        sid = "".join(str(prng.randrange(10)) for _ in range(L.id_digits))
        for c, d in enumerate(sid):
            blob(img, L, *L.id_bubble(c, int(d)), rng.uniform(40, 110), rng.uniform(0.8, 1.05), rng)
        ans = {q: prng.choice(C) for q in range(1, L.n_q + 1)}
        expect = dict(ans)
        trouble = prng.sample(range(1, L.n_q + 1), min(5, L.n_q))
        ans[trouble[0]] = expect[trouble[0]] = "-"                                   # left blank
        expect[trouble[1]] = "?"                                                     # double mark
        other = prng.choice([c for c in C if c != ans[trouble[1]]])
        blob(img, L, *L.answer_bubble(trouble[1], C.index(other)), rng.uniform(50, 100), 0.95, rng)
        expect[trouble[2]] = "?"                                                     # very faint mark
        for q, v in ans.items():
            if v != "-":
                grey, cover = (205, 0.8) if q == trouble[2] else (rng.uniform(40, 120), rng.uniform(0.75, 1.05))
                blob(img, L, *L.answer_bubble(q, C.index(v)), grey, cover, rng)
        e = trouble[3]                                                               # erased smudge
        old = prng.choice([c for c in C if c != ans[e]])
        blob(img, L, *L.answer_bubble(e, C.index(old)), 228, 0.9, rng)
        if s % 4 == 0:                                                               # stray tick
            x, y = L.answer_label(trouble[4])
            cv2.line(img, (int((x + L.block_w) * MM), int(y * MM)), (int((x + L.block_w + 2) * MM), int((y - 2) * MM)), 60, 3)
        pages.append(distort(img, rng, flip=(s == 3)))
        truth.append(dict(page=f"fake.pdf:{s + 1}", student_id=sid, **{f"Q{q}": expect[q] for q in expect}))
    Image.fromarray(pages[0]).save(work / "fake.pdf", save_all=True,
                                   append_images=[Image.fromarray(p) for p in pages[1:]], resolution=DPI)
    reader = Path(__file__).resolve().parent / "exam_omr_read.py"
    subprocess.run([sys.executable, str(reader), "--spec", a.spec, "--key", str(work / "key.txt"),
                    str(work / "fake.pdf"), "--out", str(work / "out")], check=True)
    R = {r["page"]: r for r in csv.DictReader(open(work / "out" / "results.csv", encoding="utf-8-sig"))}
    c = dict(sheets=len(R), id_wrong=0, correct=0, silent_wrong=0, flagged=0, missed=0, false_alarm=0)
    for t in truth:
        r = R.get(t["page"], {})
        c["id_wrong"] += r.get("student_id") != t["student_id"]
        for q in range(1, L.n_q + 1):
            e, g = t[f"Q{q}"], r.get(f"Q{q}")
            if e == "?":
                c["flagged" if g == "?" else "missed"] += 1
            elif g == e:
                c["correct"] += 1
            elif g == "?":
                c["false_alarm"] += 1
            else:
                c["silent_wrong"] += 1
    ok = c["id_wrong"] == 0 and c["silent_wrong"] == 0 and c["missed"] == 0 and c["sheets"] == a.n
    print(f"layout {L.code()}: {c} -> {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

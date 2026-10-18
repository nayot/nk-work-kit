"""Geometry of the bubble answer sheet, computed from an exam spec (see examples/exam_spec.json).

Shared by exam_omr_sheet.py (draws it) and exam_omr_read.py (reads scans), so the two can't drift.
All coordinates are millimetres on A4 portrait (210 x 297), origin top-left, y pointing down.

Spec keys used: n_questions (1-75), choices (4 or 5 distinct single characters, e.g. "ABCD",
"ABCDE", "กขคง"), id_digits (4-13).
Limits: 3 answer blocks; rows shrink from 6.3 mm to no less than 5.0 mm, so 60 questions fit at
full size and 75 is the maximum. Bubbles are 4.6 mm across, and shrink with the rows so that
neighbouring rows always keep a 1.2 mm gap. 5 choices use a 7 mm pitch.

Every sheet prints its layout code (code(), e.g. "60/ABCD/8") in grey at the bottom, and a row of
18 small squares above it: a fingerprint of the exact geometry (guard bits + 16 hash bits).
exam_omr_read.py refuses a sheet whose fingerprint differs. This is essential, not decoration:
two layouts can put rings within a millimetre of each other one option-pitch apart (the 2026
Funda EE sheet vs this layout's 60/ABCD/8), so a ring check alone would read every answer one
column off without a single flag.
"""
import hashlib
import json
import math
from pathlib import Path

PAGE_W, PAGE_H = 210.0, 297.0
FID_SIZE = 8.0
FIDUCIALS = {"tl": (12.0, 12.0), "tr": (190.0, 12.0), "bl": (12.0, 277.0), "br": (190.0, 277.0)}
BUBBLE_R = 2.3          # printed circle radius at full size (shrinks with tight rows)


def load_spec(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class Layout:
    def __init__(self, spec):
        self.n_q = int(spec["n_questions"])
        self.choices = spec.get("choices", "ABCD")
        self.id_digits = int(spec.get("id_digits", 8))
        assert 1 <= self.n_q <= 75, "the sheet holds 1-75 questions"
        assert len(self.choices) in (4, 5) and len(set(self.choices)) == len(self.choices), \
            "choices must be 4 or 5 distinct characters"
        assert 4 <= self.id_digits <= 13, "id_digits must be 4-13"
        # student ID block: columns of digits 0-9
        self.id_x0, self.id_col_pitch = 22.0, 7.5
        self.id_box_y = 64.0
        self.id_y0, self.id_row_pitch = 76.0, 5.6
        self.id_right = self.id_x0 + (self.id_digits - 1) * self.id_col_pitch
        # answers: up to 3 blocks side by side
        self.blocks = 3 if self.n_q > 40 else (2 if self.n_q > 20 else 1)
        self.rows = math.ceil(self.n_q / self.blocks)
        self.row_pitch = min(6.3, 126.0 / max(self.rows, 1))
        assert self.row_pitch >= 5.0
        self.bubble_r = min(BUBBLE_R, (self.row_pitch - 1.2) / 2)
        self.read_r = 0.7 * self.bubble_r
        self.ans_y0 = 145.0
        self.opt_pitch = 8.0 if len(self.choices) == 4 else 7.0
        self.opt_dx0 = 10.0
        self.block_w = self.opt_dx0 + (len(self.choices) - 1) * self.opt_pitch + 7
        gap = (PAGE_W - 2 * 21 - self.blocks * self.block_w) / max(self.blocks, 1)
        self.block_x = [21 + gap / 2 + 3 + b * (self.block_w + gap) for b in range(self.blocks)]

    def code(self):
        return f"{self.n_q}/{self.choices}/{self.id_digits}"

    def as_dict(self):
        return {"code": self.code(), "n_questions": self.n_q, "choices": self.choices,
                "id_digits": self.id_digits, "rows": self.rows, "row_pitch": self.row_pitch,
                "block_x": self.block_x, "bubble_r": self.bubble_r,
                "fingerprint": "".join(map(str, self.fingerprint()))}

    FP_N, FP_X0, FP_PITCH, FP_Y, FP_SIZE = 18, 42.0, 7.0, 281.0, 3.0

    def fingerprint(self):
        """18 bits: 1 at both ends (guards), 16 bits of a hash of the geometry in between."""
        geo = f"{self.code()}|{self.rows}|{self.row_pitch:.3f}|" + ",".join(f"{x:.2f}" for x in self.block_x) + \
              f"|{self.opt_pitch}|{self.bubble_r:.3f}|{self.id_x0}|{self.id_y0}|{self.ans_y0}"
        h = int(hashlib.sha1(geo.encode()).hexdigest()[:4], 16)
        return [1] + [(h >> (15 - i)) & 1 for i in range(16)] + [1]

    def fp_square(self, i):
        """Top-left corner (mm) of fingerprint square i."""
        return (self.FP_X0 + i * self.FP_PITCH, self.FP_Y)

    @staticmethod
    def fiducial_centres():
        h = FID_SIZE / 2
        return {k: (x + h, y + h) for k, (x, y) in FIDUCIALS.items()}

    def id_bubble(self, col, digit):
        return (self.id_x0 + col * self.id_col_pitch, self.id_y0 + digit * self.id_row_pitch)

    def answer_label(self, q):
        block, row = divmod(q - 1, self.rows)
        return (self.block_x[block], self.ans_y0 + row * self.row_pitch)

    def answer_bubble(self, q, choice):
        x, y = self.answer_label(q)
        return (x + self.opt_dx0 + choice * self.opt_pitch, y)

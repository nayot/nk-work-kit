#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Offline tests for projects.py's Kanban board (temp vault, fixed date).

    uv run scripts/projects_test.py
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "projects", Path(__file__).resolve().parent / "projects.py")
m = importlib.util.module_from_spec(_spec)
sys.modules["projects"] = m           # dataclasses look the module up
_spec.loader.exec_module(m)

TODAY = "2026-11-02"   # a Monday


def hub(status="active", next_action="", next_action_due="", waiting_on="", waiting_since="",
        priority="normal", body=""):
    return (f"---\ntype: project\nstatus: {status}\npriority: {priority}\n"
            f"next_action: \"{next_action}\"\nnext_action_due: {next_action_due}\n"
            f"waiting_on: {waiting_on or '[]'}\nwaiting_since: {waiting_since}\nupdated: 2026-10-20\n---\n"
            f"# Hub\n\n{body}\n")


NOTES = {
    "Late": hub(body="- [ ] Old task 📅 2026-10-28\n- [ ] Older task [[Some note|alias]] 📅 2026-10-20\n"),
    "Soon": hub(next_action="Send draft", next_action_due="2026-11-05"),
    # Next action restates the task's date: the task wins (dated_items dedup).
    "Dedup": hub(next_action="Restated", next_action_due="2026-11-04",
                 body="- [ ] The real task 📅 2026-11-04\n"),
    "Wait": hub(waiting_on="\n  - {who: Registrar, what: room list, since: 2026-10-26}", waiting_since="2026-10-26"),
    # Overdue beats waiting.
    "WaitLate": hub(waiting_on="Dean office", waiting_since="2026-10-01", body="- [ ] Chase 📅 2026-10-30\n"),
    "Calm": hub(body="- [ ] Far task 📅 2026-12-15\n"),
    "Bare": hub(next_action="Think about it"),
    "Idea": hub(status="idea", next_action="Maybe later"),
    "Finished": hub(status="done", body="- [ ] Leftover 📅 2026-10-01\n"),
}


class Kanban(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.vault = Path(cls.tmp.name)
        (cls.vault / ".obsidian").mkdir()
        proj = cls.vault / "Projects"
        proj.mkdir()
        for name, text in NOTES.items():
            (proj / f"{name}.md").write_text(text, encoding="utf-8")
        (proj / "To-do.md").write_text("---\ntype: todo\n---\n- [ ] Loose 📅 2026-10-01\n", encoding="utf-8")
        os.environ.update(PM_TODAY=TODAY, PM_FOLDER="Projects", PM_HOLIDAYS_FILE="")
        os.environ.pop("PM_KANBAN_NAME", None)
        cls.projects = m.scan(cls.vault)
        cls.lanes = m.kanban_lanes(cls.vault, cls.projects)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def lane_of(self, name):
        hits = [k for k, cards in self.lanes.items() for c in cards if c.startswith(f"[[Projects/{name}|")]
        self.assertLessEqual(len(hits), 1, name)
        return hits[0] if hits else None

    def card(self, name):
        return next(c for cards in self.lanes.values() for c in cards if c.startswith(f"[[Projects/{name}|"))

    def test_lanes(self):
        expect = {"Late": "overdue", "WaitLate": "overdue", "Soon": "week", "Dedup": "week",
                  "Wait": "waiting", "Calm": "on_track", "Bare": "on_track", "Idea": "parked"}
        for name, lane in expect.items():
            self.assertEqual(self.lane_of(name), lane, name)

    def test_excluded(self):
        self.assertIsNone(self.lane_of("Finished"))
        self.assertIsNone(self.lane_of("To-do"))

    def test_overdue_card_is_earliest_with_count(self):
        c = self.card("Late")
        self.assertIn("Older task alias · 20.10 (13d late) +1 more late", c)
        self.assertNotIn("📅", c)
        self.assertNotIn("[[Some note", c)

    def test_dedup_prefers_task(self):
        self.assertIn("The real task · 04.11", self.card("Dedup"))

    def test_waiting_card(self):
        self.assertIn("⏳ Registrar — room list · 5 working days", self.card("Wait"))

    def test_overdue_sorted_by_date(self):
        names = [c.split("|")[0][len("[[Projects/"):] for c in self.lanes["overdue"]]
        self.assertEqual(names, ["Late", "WaitLate"])

    def test_board_format(self):
        text = m.render_kanban(self.vault, self.projects)
        meta, body = m.split_frontmatter(text)
        self.assertEqual(meta["kanban-plugin"], "board")
        self.assertEqual(meta["type"], "kanban")
        heads = [ln[3:] for ln in body.splitlines() if ln.startswith("## ")]
        self.assertEqual(heads, [t for _, t in m.KANBAN_LANES])
        self.assertTrue(text.rstrip().endswith("```\n%%"))
        settings = json.loads(text.split("%% kanban:settings\n```\n")[1].split("\n```")[0])
        self.assertEqual(settings["kanban-plugin"], "board")
        self.assertEqual(settings["list-collapse"], [False, False, False, False, True])
        cards = [ln for ln in body.splitlines() if ln.startswith("- ")]
        self.assertTrue(cards and all(ln.startswith("- [ ] [[") for ln in cards))

    def test_parked_lane_only_when_needed(self):
        active = [p for p in self.projects if p.status != "idea"]
        text = m.render_kanban(self.vault, active)
        self.assertNotIn(m.KANBAN_LANES[-1][1], text)
        self.assertIn('"list-collapse": [false, false, false, false]', text)

    def test_scan_skips_board(self):
        path = m.kanban_path(self.vault)
        m.write_atomic(path, m.render_kanban(self.vault, self.projects))
        try:
            again = {p.name: len(p.items) for p in m.scan(self.vault)}
            self.assertEqual(again, {p.name: len(p.items) for p in self.projects})
        finally:
            path.unlink()

    def test_scan_skips_board_without_type(self):
        # The Kanban plugin may rewrite the frontmatter on a drag-save.
        path = self.vault / "Projects" / "Other board.md"
        path.write_text(m.render_kanban(self.vault, self.projects).replace("type: kanban\n", ""), encoding="utf-8")
        try:
            again = {p.name: len(p.items) for p in m.scan(self.vault)}
            self.assertEqual(again, {p.name: len(p.items) for p in self.projects})
        finally:
            path.unlink()

    def test_kanban_name(self):
        os.environ["PM_KANBAN_NAME"] = "../Board"
        try:
            self.assertEqual(m.kanban_path(self.vault), self.vault / "Projects" / "Board.md")
        finally:
            del os.environ["PM_KANBAN_NAME"]


if __name__ == "__main__":
    unittest.main()

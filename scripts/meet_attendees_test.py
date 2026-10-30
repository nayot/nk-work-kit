#!/usr/bin/env python3
"""Offline tests for meet_attendees.py's invite matching (stdlib only).

    python3 scripts/meet_attendees_test.py
"""
import importlib.util
import sys
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "meet_attendees", Path(__file__).resolve().parent / "meet_attendees.py")
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

# Invite as Calendar returns it for external guests: bare addresses, no names.
INVITE = [{"email": e} for e in (
    "petchtinnabal@example.com", "kerwin_hing@example.sg", "schalam@example.com",
    "jkong@example.com", "ghoh@example.com", "anna.lee@example.org", "nguyenvan@example.org")]


def match(name, attendees=INVITE, taken=frozenset()):
    return m.match_invitee(name, attendees, set(taken))


class LocalPart(unittest.TestCase):
    def test_first_last(self):
        self.assertEqual(match("Petch Tinnabal")[:2], ("petchtinnabal@example.com", "invite (name≈email)"))

    def test_first_underscore_last(self):
        self.assertEqual(match("Kerwin Hing")[0], "kerwin_hing@example.sg")

    def test_initial_last(self):
        self.assertEqual(match("Sunitha Chalam")[0], "schalam@example.com")
        self.assertEqual(match("Janessa Kong")[0], "jkong@example.com")

    def test_first_dot_last(self):
        self.assertEqual(match("Anna Lee")[0], "anna.lee@example.org")

    def test_last_first(self):
        self.assertEqual(match("Van Nguyen")[0], "nguyenvan@example.org")

    def test_case_and_digits(self):
        self.assertEqual(match("KERWIN HING 2")[0], "kerwin_hing@example.sg")

    def test_single_letter_surname_stays_unmatched(self):
        self.assertEqual(match("Gloria H"), (None, None, False))

    def test_no_match(self):
        self.assertEqual(match("Eileen O"), (None, None, False))
        self.assertEqual(match("Somchai"), (None, None, False))

    def test_ambiguous(self):
        inv = INVITE + [{"email": "j.kong@other.com"}]
        self.assertEqual(match("Janessa Kong", inv), (None, None, True))

    def test_taken_email_is_skipped(self):
        inv = INVITE + [{"email": "j.kong@other.com"}]
        self.assertEqual(match("Janessa Kong", inv, {"j.kong@other.com"})[0], "jkong@example.com")


class DisplayName(unittest.TestCase):
    def test_named_invitee_exact(self):
        inv = [{"email": "x1@example.com", "displayName": "Kerwin  Hing"}]
        self.assertEqual(match("kerwin hing", inv)[:2], ("x1@example.com", "invite"))

    def test_named_invitees_ambiguous(self):
        inv = [{"email": "a@x.sg", "displayName": "Eileen O"}, {"email": "b@x.sg", "displayName": "Eileen  O"}]
        self.assertEqual(match("Eileen O", inv), (None, None, True))

    def test_local_part_ignored_when_invitee_has_name(self):
        inv = [{"email": "kerwin_hing@x.sg", "displayName": "K. Hing (ITE)"}]
        self.assertEqual(match("Kerwin Hing", inv), (None, None, False))


class Build(unittest.TestCase):
    """End to end through build() with a fake API session."""

    class R:
        def __init__(self, d):
            self.d, self.status_code, self.reason = d, 200, "OK"

        def json(self):
            return self.d

    class S:
        def __init__(self, event, parts):
            self.event, self.parts = event, parts

        def get(self, url, params=None, timeout=0):
            if "/calendars/" in url:
                return Build.R({"items": [self.event]})
            if url.endswith("/participants"):
                return Build.R({"participants": self.parts})
            if "batchGet" in url:
                return Build.R({"responses": []})
            raise AssertionError(url)

    def test_two_names_claiming_one_invitee_get_neither(self):
        event = {"summary": "T", "hangoutLink": "https://meet.google.com/abc-defg-hij",
                 "start": {"dateTime": "2026-10-29T13:30:00+07:00"},
                 "attendees": [{"email": "jkong@example.com"}]}
        parts = [{"signedinUser": {"user": f"users/{i}", "displayName": n},
                  "earliestStartTime": "2026-10-29T06:31:00Z", "latestEndTime": "2026-10-29T07:00:00Z"}
                 for i, n in enumerate(["Janessa Kong", "Jamie Kong", "Gloria H"])]
        rec = {"name": "conferenceRecords/X", "startTime": "2026-10-29T06:28:00Z",
               "endTime": "2026-10-29T07:25:00Z", "space": "spaces/s"}
        d = m.build(self.S(event, parts), rec, "abc-defg-hij", None, [])
        got = {r["name"]: (r["email"], r["invited"]) for r in d["participants"]}
        self.assertEqual(got, {"Janessa Kong": (None, None), "Jamie Kong": (None, None),
                               "Gloria H": (None, None)})
        self.assertEqual([a["email"] for a in d["invited_absent"]], ["jkong@example.com"])


if __name__ == "__main__":
    sys.exit(unittest.main())

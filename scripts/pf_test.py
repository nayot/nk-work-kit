#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["google-auth", "google-auth-oauthlib", "requests", "markdown"]
# ///
"""Offline tests for pf.py's Txn IDs (no sheet, no PDFs).

    uv run scripts/pf_test.py
"""
import collections
import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location("pf", Path(__file__).resolve().parent / "pf.py")
pf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pf)


def row(file, date, amount, desc='TRF | x', key='10:00', acct='KTB-CUR'):
    return dict(kind='ktb-deposit', acct=acct, date=date, key=key, desc=desc, amount=amount,
                src=Path(file).name, file=file)


def old_ids(out):
    """The IDs the importer gave before 01.11.2026 (one counter over every file in the run)."""
    seen, ids = collections.Counter(), []
    for r in out:
        b = f"{r['acct']}|{r['date']}|{r['key']}|{r['amount']:.2f}|{r['desc']}"
        seen[b] += 1
        ids.append(f"{r['acct']}-{r['date'].replace('-', '')}-" + hashlib.sha1(f'{b}|{seen[b]}'.encode()).hexdigest()[:6])
    return ids


OLD = 'Statements/KTB/KTB-Current-3682_2026-01-01_2026-10-04.pdf'
NEW = 'Statements/KTB/Statement_01NOV2026_x.pdf'


class TxnIds(unittest.TestCase):
    def test_single_file_ids_unchanged(self):
        out = [row(OLD, '2026-10-01', -80), row(OLD, '2026-10-01', -80), row(OLD, '2026-10-02', 500)]
        want = old_ids([dict(r) for r in out])
        rows, dropped = pf.assign_ids(out)
        self.assertEqual([r['id'] for r in rows], want)
        self.assertEqual(dropped, 0)

    def test_genuine_twins_in_one_statement_kept(self):
        rows, dropped = pf.assign_ids([row(NEW, '2026-10-05', -80), row(NEW, '2026-10-05', -80)])
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({r['id'] for r in rows}), 2)
        self.assertEqual(dropped, 0)

    def test_overlapping_statements_counted_once(self):
        old = [row(OLD, '2026-10-01', -80), row(OLD, '2026-10-02', -80, desc='TRF | y'),
               row(OLD, '2026-10-03', 119000)]
        new = [row(NEW, '2026-10-01', -80), row(NEW, '2026-10-02', -80, desc='TRF | y'),
               row(NEW, '2026-10-03', 119000), row(NEW, '2026-10-20', -45)]
        old_alone, _ = pf.assign_ids([dict(r) for r in old])          # what is already in the sheet
        rows, dropped = pf.assign_ids(old + new)
        self.assertEqual(dropped, 3)
        self.assertEqual(len(rows), 4)
        self.assertEqual({r['id'] for r in old_alone} - {r['id'] for r in rows}, set())
        # the new file on its own (old one moved away) gives the same IDs for the overlap days
        new_alone, _ = pf.assign_ids([dict(r) for r in new])
        self.assertEqual({r['id'] for r in new_alone} - {r['id'] for r in rows}, set())

    def test_overlap_keeps_extra_twin(self):
        # old file ends mid-day with one copy; the new file has both twins of that day
        old = [row(OLD, '2026-10-03', -80)]
        new = [row(NEW, '2026-10-03', -80), row(NEW, '2026-10-03', -80)]
        rows, dropped = pf.assign_ids(old + new)
        self.assertEqual((len(rows), dropped), (2, 1))
        self.assertEqual(len({r['id'] for r in rows}), 2)

    def test_order_of_files_does_not_matter(self):
        old = [row(OLD, '2026-10-01', -80), row(OLD, '2026-10-01', -80)]
        new = [row(NEW, '2026-10-01', -80)]
        a, _ = pf.assign_ids([dict(r) for r in old + new])
        b, _ = pf.assign_ids([dict(r) for r in new + old])
        self.assertEqual({r['id'] for r in a}, {r['id'] for r in b})

    def test_same_name_in_two_folders_is_two_files(self):
        rows, dropped = pf.assign_ids([row('Statements/a/s.pdf', '2026-10-01', -80),
                                       row('Statements/b/s.pdf', '2026-10-01', -80)])
        self.assertEqual((len(rows), dropped), (1, 1))

    def test_uob_card_overlap(self):
        r = lambda f: dict(kind='uob-card', acct='UOB-1', date='2026-09-28', key='2026-09-29',
                           desc='SHOP', amount=-1200.0, src=Path(f).name, file=f)
        rows, dropped = pf.assign_ids([r('Statements/UOB/sep.pdf'), r('Statements/UOB/sep-copy.pdf')])
        self.assertEqual((len(rows), dropped), (1, 1))


if __name__ == '__main__':
    unittest.main(verbosity=2)

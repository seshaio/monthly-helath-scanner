"""
Run-folder allocation. Offline.

A run folder is the unit everything else points at: reports name it,
fingerprints live in it, consensus files are named after it. Reissuing a
number does not just confuse a listing — it makes an earlier artifact refer
to a run whose contents have been replaced.
"""

import os
import tempfile
import unittest

import common


class RunNumbering(unittest.TestCase):

    DATE = "2026-08-25"

    def _make(self, tmp, *numbers):
        for n in numbers:
            os.makedirs(os.path.join(tmp, f"{self.DATE}-run-{n}"))

    def test_first_run_of_the_day_is_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(common.next_run_index(tmp, self.DATE), 1)

    def test_counts_up_from_the_highest_not_from_how_many(self):
        """
        The incident: runs 1, 4 and 5 were deleted leaving 2 and 3, and a
        count returned 3 — allocating run-3 a second time and writing over
        the report already in it.
        """
        with tempfile.TemporaryDirectory() as tmp:
            self._make(tmp, 2, 3)
            self.assertEqual(common.next_run_index(tmp, self.DATE), 4)

    def test_a_gap_stays_a_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._make(tmp, 1, 5)
            self.assertEqual(common.next_run_index(tmp, self.DATE), 6)

    def test_deleting_the_highest_does_reissue_it(self):
        """
        The one case the high-water mark does not cover, recorded rather than
        claimed fixed. Deleting the newest run frees its number, so the next
        run takes it — and output/consensus/<date>-run-3.md, if one exists,
        now names a run whose contents are different.

        It is a far narrower hole than the one it replaced: a number is only
        reused after its folder is deliberately deleted, and run_dir refuses
        outright rather than writing into a folder that still exists.
        """
        with tempfile.TemporaryDirectory() as tmp:
            self._make(tmp, 1, 2, 3)
            self.assertEqual(common.next_run_index(tmp, self.DATE), 4)
            os.rmdir(os.path.join(tmp, f"{self.DATE}-run-3"))
            self.assertEqual(common.next_run_index(tmp, self.DATE), 3)

    def test_an_existing_folder_is_never_written_into(self):
        """makedirs without exist_ok: silent overwrite becomes a loud stop."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, f"{self.DATE}-run-1")
            os.makedirs(path)
            with self.assertRaises(FileExistsError):
                os.makedirs(path)

    def test_other_dates_do_not_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "2026-08-24-run-9"))
            self.assertEqual(common.next_run_index(tmp, self.DATE), 1)

    def test_unrelated_folders_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "consensus"))
            os.makedirs(os.path.join(tmp, f"{self.DATE}-run-2"))
            self.assertEqual(common.next_run_index(tmp, self.DATE), 3)

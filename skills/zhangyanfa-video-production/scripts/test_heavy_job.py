from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import heavy_job


class HeavyLockMigrationTest(unittest.TestCase):
    def test_migrated_alias_uses_the_same_lock_inode(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);canonical=root/'new.lock';legacy=root/'old.lock'
            canonical.write_text('');legacy.symlink_to(canonical)
            with patch.object(heavy_job,'DEFAULT_LOCK',canonical),patch.object(heavy_job,'LEGACY_LOCK',legacy):
                with heavy_job.heavy_lock() as fd:
                    self.assertTrue(canonical.samefile(legacy))
                    with self.assertRaises(RuntimeError):
                        with heavy_job.heavy_lock():pass

    def test_distinct_or_unmigrated_legacy_lock_blocks_new_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);canonical=root/'new.lock';legacy=root/'old.lock';legacy.write_text('existing')
            with patch.object(heavy_job,'DEFAULT_LOCK',canonical),patch.object(heavy_job,'LEGACY_LOCK',legacy):
                with self.assertRaisesRegex(RuntimeError,'storage migration'):
                    with heavy_job.heavy_lock():pass
                self.assertFalse(canonical.exists())
                canonical.write_text('another')
                with self.assertRaisesRegex(RuntimeError,'storage migration'):
                    with heavy_job.heavy_lock():pass
                self.assertEqual(canonical.read_text(),'another')
                self.assertEqual(legacy.read_text(),'existing')


if __name__=='__main__':unittest.main()

from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
import signal
import time
from unittest.mock import patch
import heavy_job


class HeavyLockMigrationTest(unittest.TestCase):
    def test_cancel_during_wait_reaps_child_and_releases_same_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); lock=root/'stable.lock'; ready=root/'ready'
            child = f"from pathlib import Path; import time; Path({str(ready)!r}).touch(); time.sleep(30)"
            script = (f"import sys; from pathlib import Path; sys.path.insert(0,{str(Path(heavy_job.__file__).parent)!r}); "
                      f"import heavy_job; heavy_job.DEFAULT_LOCK=Path({str(lock)!r}); "
                      f"heavy_job.LEGACY_LOCK=Path({str(root/'absent.lock')!r}); "
                      f"raise SystemExit(heavy_job.run([{sys.executable!r}, '-c', {child!r}]))")
            proc=subprocess.Popen([sys.executable,'-c',script])
            try:
                deadline=time.monotonic()+5
                while not ready.exists() and time.monotonic()<deadline:
                    time.sleep(.02)
                self.assertTrue(ready.exists())
                inode=lock.stat().st_ino
                proc.send_signal(signal.SIGTERM)
                self.assertEqual(proc.wait(timeout=3),128+signal.SIGTERM)
                self.assertEqual(lock.stat().st_ino,inode)
                with heavy_job.heavy_lock(lock):pass
            finally:
                if proc.poll() is None:proc.kill();proc.wait()

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

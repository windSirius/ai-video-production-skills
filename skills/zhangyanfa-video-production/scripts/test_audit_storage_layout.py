import json
from pathlib import Path
import tempfile
import unittest
from audit_storage_layout import audit


class StorageAuditTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name).resolve()
        self.root=self.base/'workspace';self.media=self.root/'media';self.cache=self.root/'cache'
        self.media.mkdir(parents=True);self.cache.mkdir()
        self.old=self.base/'CodexScratch';self.old.symlink_to(self.cache,target_is_directory=True)
        self.manifest=self.root/'storage.json'
        self.config={'schema':'video_storage_roots_v1','workspace_root':str(self.root),
                     'media_root':str(self.media),'cache_root':str(self.cache),
                     'legacy_aliases':[{'source':str(self.old),'target':str(self.cache)}],
                     'watch_roots':[{'path':str(self.base),'patterns':['CodexScratch*']}]}
        self.write()

    def tearDown(self):self.temp.cleanup()
    def write(self):self.manifest.write_text(json.dumps(self.config))

    def test_legacy_alias_passes_without_modifying_files(self):
        file=self.cache/'keep';file.write_bytes(b'preserved')
        before=file.stat()
        self.assertEqual(audit(self.manifest)['status'],'PASS')
        self.assertEqual(file.read_bytes(),b'preserved')
        self.assertEqual(file.stat().st_mtime_ns,before.st_mtime_ns)

    def test_new_scattered_directory_fails(self):
        (self.base/'CodexScratch-new').mkdir()
        result=audit(self.manifest)
        self.assertEqual(result['status'],'FAIL')
        self.assertTrue(any('new scattered' in e for e in result['errors']))

    def test_replaced_legacy_alias_fails(self):
        self.old.unlink();self.old.mkdir()
        self.assertEqual(audit(self.manifest)['status'],'FAIL')

    def test_new_payload_in_compatibility_bridge_fails(self):
        bridge=self.root/'compat';bridge.mkdir()
        self.config['compatibility_roots']=[str(bridge)]
        self.config['compatibility_allowlist']=[];self.write()
        self.assertEqual(audit(self.manifest)['status'],'PASS')
        (bridge/'new-media.mp4').write_bytes(b'new payload')
        self.assertEqual(audit(self.manifest)['status'],'FAIL')

    def test_cloud_and_overlapping_roots_fail(self):
        self.config['cache_root']=str(self.media/'nested');(self.media/'nested').mkdir();self.write()
        self.assertEqual(audit(self.manifest)['status'],'FAIL')
        self.config['workspace_root']=str(self.base/'Mobile Documents/workspace');self.write()
        self.assertEqual(audit(self.manifest)['status'],'FAIL')


if __name__=='__main__':unittest.main()

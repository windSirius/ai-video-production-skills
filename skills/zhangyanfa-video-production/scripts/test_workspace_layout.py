"""Behavioral checks for canonical output routing and non-destructive legacy views."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import workspace_layout as ws
from media_registry import register as register_media

WORKFLOW=Path(__file__).with_name('workflow.py')


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name).resolve()
        self.root=self.base/'episode';self.media=self.base/'media';self.cache=self.base/'cache'

    def tearDown(self):self.temp.cleanup()

    def create(self,**kwargs):return ws.create(self.root,'GI71_EP004',self.media,self.cache,**kwargs)

    def cli(self,*args,expected=0):
        r=subprocess.run([sys.executable,str(WORKFLOW),args[0],'--root',str(self.root),*args[1:]],text=True,capture_output=True)
        self.assertEqual(r.returncode,expected,r.stdout+r.stderr);return r

    def initialize(self):
        self.cli('init','--title','目录契约测试','--theme','固定路径','--width','2560','--height','1440','--fps','60',
                 '--cut-policy','per_caption_refresh','--tracks','A,B,C,BGM','--b-output-mode','green','--c-output-mode','green',
                 '--assembly-tool','hyperframes','--episode-key','GI71_EP004','--media-root',str(self.media),'--cache-root',str(self.cache))

    def test_canonical_folders_and_distinct_cache_ownership(self):
        config=self.create();self.assertEqual(ws.doctor(self.root)['status'],'PASS')
        for kind,folder in config['project_dirs'].items():self.assertTrue((self.root/folder).is_dir())
        self.assertEqual(ws.resolve(self.root,'cache:render','v002'),self.cache/'GI71_EP004/render/v002')
        with self.assertRaises(ValueError):ws.create(self.base/'another','GI71_EP004',self.media,self.cache)
        self.assertFalse((self.base/'another/workspace_paths.json').exists())

    def test_next_version_preserves_previous_content(self):
        self.create();first=ws.new_version(self.root,'script');(first/'稿件.md').write_text('approved bytes')
        second=ws.new_version(self.root,'script')
        self.assertEqual(first.name,'v001');self.assertEqual(second.name,'v002')
        self.assertEqual((first/'稿件.md').read_text(),'approved bytes')
        with self.assertRaises(ValueError):ws.resolve(self.root,'script','../escape')

    def test_relocated_roots_preserve_frozen_contract_via_legacy_aliases(self):
        config=self.create();before=ws.digest(self.root/'workspace_paths.json')
        new_media=self.base/'workspace/media';new_cache=self.base/'workspace/cache'
        new_media.parent.mkdir()
        self.media.rename(new_media);self.media.symlink_to(new_media,target_is_directory=True)
        self.cache.rename(new_cache);self.cache.symlink_to(new_cache,target_is_directory=True)
        self.assertEqual(ws.create(self.root,'GI71_EP004',new_media,new_cache),config)
        self.assertEqual(ws.digest(self.root/'workspace_paths.json'),before)
        path=ws.new_version(self.root,'cache:render')
        self.assertEqual(path.resolve(),new_cache/'GI71_EP004/render/v001')
        self.assertEqual(ws.doctor(self.root)['status'],'PASS')

    def test_doctor_detects_cache_redirected_into_cloud(self):
        self.create()
        cloud=self.base/'Mobile Documents/cache';cloud.parent.mkdir()
        self.cache.rename(cloud);self.cache.symlink_to(cloud,target_is_directory=True)
        self.assertEqual(ws.doctor(self.root)['status'],'FAIL')

    def test_storage_drift_blocks_resolver_before_writing(self):
        workspace=self.base/'workspace';media=workspace/'media';cache=workspace/'cache'
        media.mkdir(parents=True);cache.mkdir();(workspace/'00_管理').mkdir()
        alias=self.base/'old-cache';alias.symlink_to(cache,target_is_directory=True)
        config={'schema':'video_storage_roots_v1','workspace_root':str(workspace),
                'media_root':str(media),'cache_root':str(cache),
                'legacy_aliases':[{'source':str(alias),'target':str(cache)}]}
        (workspace/'00_管理/storage_roots.json').write_text(json.dumps(config))
        with patch.object(ws,'DEFAULT_WORKSPACE',workspace):
            ws.create(self.root,'GI71_EP004',media,cache)
            alias.unlink();alias.mkdir()
            with self.assertRaisesRegex(ValueError,'storage layout drift'):
                ws.new_version(self.root,'cache:render')
            self.assertFalse((cache/'GI71_EP004/render/v001').exists())

    def test_legacy_adoption_does_not_change_controls_or_media(self):
        self.root.mkdir();folder=self.root/'03_脚本_v4';folder.mkdir()
        script=folder/'口播.md';script.write_text('unchanged')
        current=self.root/'CURRENT.json';current.write_text(json.dumps({'title':'旧期'}))
        ledger=self.root/'deliverables.json';ledger.write_text(json.dumps({'items':{'script':{'path':'03_脚本_v4/口播.md','sha256':ws.digest(script)}}}))
        before={p:ws.digest(p) for p in (script,current,ledger)}
        self.create(mode='legacy_indexed',legacy_map={'script':['03_脚本_v4']})
        self.assertEqual(before,{p:ws.digest(p) for p in before})
        alias=self.root/'00_工作台/03_脚本/03_脚本_v4'
        self.assertTrue(alias.is_symlink());self.assertEqual(alias.resolve(),folder)
        self.assertEqual(ws.doctor(self.root)['status'],'PASS')
        with self.assertRaises(ValueError):ws.new_version(self.root,'script')

    def test_icloud_and_overlapping_cache_roots_are_rejected(self):
        for cache in (self.base/'Mobile Documents/com~apple~CloudDocs/cache', self.root/'cache', self.media/'cache'):
            with self.assertRaises(ValueError):ws.create(self.root,'GI71_EP004',self.media,cache)

    def test_user_cloud_request_is_project_scoped_and_preserves_other_guards(self):
        workspace=self.base/'Mobile Documents/workspace'
        media=workspace/'media';cache=workspace/'cache'
        media.mkdir(parents=True);cache.mkdir();(workspace/'00_管理').mkdir()
        alias=self.base/'old-cache';alias.symlink_to(cache,target_is_directory=True)
        (workspace/'00_管理/storage_roots.json').write_text(json.dumps({
            'schema':'video_storage_roots_v1','workspace_root':str(workspace),
            'media_root':str(media),'cache_root':str(cache),
            'legacy_aliases':[{'source':str(alias),'target':str(cache)}]}))
        with patch.object(ws,'DEFAULT_WORKSPACE',workspace):
            with self.assertRaises(ValueError):ws.create(self.root,'GI71_EP004',media,cache)
            config=ws.create(self.root,'GI71_EP004',media,cache,cloud_cache_user_quote='全部都放在icloud路径')
            self.assertEqual(ws.doctor(self.root)['status'],'PASS')
            self.assertTrue(ws.doctor(self.root)['warnings'])
            self.assertEqual(ws.new_version(self.root,'voice').name,'v001')
            with self.assertRaises(ValueError):ws.create(self.base/'another','GI71_EP005',media,cache)
            with self.assertRaises(ValueError):ws.cloud_authorized(config['storage_authorization'],self.base/'another',media,cache)
            alias.unlink();alias.mkdir()
            with self.assertRaisesRegex(ValueError,'storage layout drift'):ws.new_version(self.root,'cache:voice')

    def test_controller_rejects_wrong_folder_and_tracks_contract_drift(self):
        self.initialize();config=json.loads((self.root/'workspace_paths.json').read_text())
        contract=json.loads((self.root/'request_contract.json').read_text())
        self.assertEqual(contract['workspace_layout']['sha256'],ws.digest(self.root/'workspace_paths.json'))
        bad=self.root/'随便起一个目录';bad.mkdir();file=bad/'evidence.tsv';file.write_text('actual evidence fixture')
        meta={'qa_schema_version':1,'evidence_count':1,'counterevidence_count':0,'counterevidence_reviewed':True,'qa_pass':True}
        r=self.cli('register','--stage','02_research_scout','--role','evidence_ledger','--path',str(file),'--meta-json',json.dumps(meta),expected=2)
        self.assertIn('must live under',r.stderr)
        directory=ws.new_version(self.root,'research');good=directory/'evidence.tsv';good.write_text('actual evidence fixture')
        self.cli('register','--stage','02_research_scout','--role','evidence_ledger','--path',str(good),'--meta-json',json.dumps(meta))
        self.assertTrue((self.root/'00_开始这里.md').exists())
        config['media_root']=str(self.base/'changed');(self.root/'workspace_paths.json').write_text(json.dumps(config))
        r=self.cli('register','--stage','02_research_scout','--role','evidence_ledger','--path',str(good),'--meta-json',json.dumps(meta),expected=2)
        self.assertIn('workspace path contract',r.stderr)

    def test_role_and_version_gate_cannot_escape_through_symlink(self):
        self.create();directory=ws.new_version(self.root,'script')
        external=self.cache/'bad.md';external.write_text('outside durable project')
        (directory/'linked.md').symlink_to(external)
        self.assertTrue(ws.registration_errors(self.root,'script',directory/'linked.md'))
        self.assertTrue(ws.registration_errors(self.root,'script',self.root/'03_脚本/no-version.md'))
        self.assertFalse(ws.registration_errors(self.root,'script',directory/'稿件.md'))

    def test_registry_deduplicates_identity_without_moving_sources(self):
        self.base.mkdir(exist_ok=True);first=self.base/'one.mp4';second=self.base/'two.mp4'
        first.write_bytes(b'media fixture');second.write_bytes(first.read_bytes())
        a=register_media(self.media,first,'SOURCE_A','原神')
        b=register_media(self.media,second,'OTHER_NAME','原神')
        self.assertEqual(a['asset']['asset_id'],b['asset']['asset_id']);self.assertTrue(b['reused_existing_identity'])
        self.assertEqual(len(json.loads((self.media/'registry.json').read_text())['assets']),1)
        self.assertTrue(first.exists());self.assertTrue(second.exists())
        second.write_bytes(b'different bytes')
        with self.assertRaises(ValueError):register_media(self.media,second,'SOURCE_A','原神')

    def test_user_authored_entry_is_not_silently_replaced(self):
        self.create();entry=self.root/'00_开始这里.md';entry.write_text('user-authored content')
        with self.assertRaises(ValueError):ws.refresh(self.root)
        self.assertEqual(entry.read_text(),'user-authored content')

    def test_new_project_and_title_changes_update_existing_catalog(self):
        self.root=self.base/'series'/'04_topic'
        catalog=self.base/'00_制作管理/项目索引.json'
        ws.write_json(catalog,{'schema':'video_project_navigation_v1','navigation_is_authority':False,'projects':[]})
        self.create()
        rows=json.loads(catalog.read_text())['projects']
        self.assertEqual(len(rows),1)
        self.assertEqual(Path(rows[0]['workbench']).resolve(),self.root)
        (self.root/'CURRENT.json').write_text(json.dumps({'title':'updated title'}))
        ws.refresh(self.root)
        rows=json.loads(catalog.read_text())['projects']
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['title'],'updated title')
        self.assertIn('updated title',(catalog.parent/'00_开始这里.md').read_text())

    def test_catalog_changes_refresh_central_portal_without_media_copy(self):
        workspace=self.base/'workspace';workspace.mkdir()
        media=workspace/'media';cache=workspace/'cache';media.mkdir();cache.mkdir()
        manifest=workspace/'00_管理/storage_roots.json';manifest.parent.mkdir()
        catalog=self.base/'00_制作管理/项目索引.json'
        manifest.write_text(json.dumps({'schema':'video_storage_roots_v1','workspace_root':str(workspace),
            'media_root':str(media),'cache_root':str(cache),'project_catalog':str(catalog)}))
        root=self.base/'series/01_title';delivery=root/'11_交付';delivery.mkdir(parents=True)
        row={'episode_key':'EP001','original_root':str(root),'title':'original','delivery_index':str(delivery/'index.md')}
        with patch.object(ws,'DEFAULT_WORKSPACE',workspace):
            ws.sync_storage_portal(catalog,[row])
            alias=workspace/'01_项目/series/01_title'
            self.assertTrue(alias.is_symlink());self.assertEqual(alias.resolve(),root)
            self.assertEqual((workspace/'05_交付/EP001').resolve(),delivery)
            row['title']='changed';ws.sync_storage_portal(catalog,[row])
            self.assertIn('changed',(workspace/'00_项目列表.md').read_text())

    def test_controller_requires_stable_episode_identity(self):
        result=self.cli('init','--title','固定编号','--theme','路径归属','--width','2560','--height','1440','--fps','60',
                        '--cut-policy','per_caption_refresh','--tracks','A,B,C,BGM','--b-output-mode','green','--c-output-mode','green',
                        '--assembly-tool','hyperframes','--media-root',str(self.media),'--cache-root',str(self.cache),expected=2)
        self.assertIn('--episode-key',result.stderr)
        self.assertFalse((self.root/'CURRENT.json').exists())
        self.assertFalse(self.cache.exists())


if __name__=='__main__':unittest.main()

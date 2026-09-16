"""Contract regressions using synthetic artifacts, not claims of media/audio QA."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('workflow.py')
SKILLS = SCRIPT.parents[2]
loader = importlib.util.spec_from_file_location('workflow_v2_test', SCRIPT)
workflow = importlib.util.module_from_spec(loader)
loader.loader.exec_module(workflow)


class WorkflowV2Test(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)/'project'
        self.root.mkdir()
        self.counter = 0
        self.canonical = self.file('canonical.md', '合成契约测试。\n那，以上，我是狐久，我们下期视频再见。')
        self.voice = self.file('reference.wav', 'synthetic bytes; not real speech')
        self.rule = self.file('rule.json', {'sha256': self.ref(self.voice)['sha256'], 'transcript': '测试参考文字'})
        profile = json.loads((SCRIPT.parent.parent/'assets/house_style.v2.json').read_text())
        # These fixtures isolate production v2 gates; canonical paths have a separate integration suite.
        profile.pop('workspace_layout',None)
        profile['profile_id'] = 'synthetic_v2_contract_fixture'
        profile['delivery_defaults']['voice_reference_sha256'] = self.ref(self.voice)['sha256']
        self.profile = self.file('test_profile.json', profile)
        self.evidence = self.file('review_evidence.md', 'Synthetic review fixture; this test does not perform human or codec QA.')
        self.init()

    def tearDown(self):
        self.temp.cleanup()

    def init(self, mode='independent_tracks'):
        self.cli('init', '--title', '契约测试', '--theme', '防止生产流程回归', '--width', '2560', '--height', '1440',
                 '--fps', '60', '--cut-policy', 'per_caption_refresh', '--tracks', 'A,B,C,BGM',
                 '--b-output-mode', 'green', '--c-output-mode', 'green', '--assembly-tool', 'hyperframes',
                 '--house-style', str(self.profile), '--delivery-mode', mode)

    def cli(self, *args, expected=0):
        result = subprocess.run([sys.executable, str(SCRIPT), args[0], '--root', str(self.root), *args[1:]], capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout+'\n'+result.stderr)
        return result

    def file(self, name, value):
        path = self.root/'fixtures'/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) if isinstance(value, (dict, list)) else value)
        return path

    def ref(self, path):
        return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def items(self):
        return json.loads((self.root/'deliverables.json').read_text())['items']

    def spec(self):
        return json.loads((self.root/'authority_bundle.json').read_text())['delivery_spec']

    def itemref(self, role):
        item = self.items()[role]
        return self.ref(self.root/item['path'])

    def register(self, role, meta=None, path=None, expected=0):
        self.counter += 1
        path = path or self.file(f'{role}_{self.counter}.dat', role+str(self.counter))
        stage = json.loads((self.root/'CURRENT.json').read_text())['current_stage']
        self.cli('register', '--stage', stage, '--role', role, '--path', str(path), '--meta-json', json.dumps(meta or {}), expected=expected)
        return path

    def review(self):
        return {'status':'pass', 'reviewer':'synthetic-test', 'notes':'Fixture representing an actual review receipt.', 'evidence':[self.ref(self.evidence)]}

    def presentation(self, roles, extra=None):
        when = datetime.now(timezone.utc).isoformat()
        self.counter += 1
        value = {'schema':'artifact_presentation_v2', 'shown_at':when,
                 'display_evidence':{'type':'chat','locator':'synthetic-test-display'},
                 'items':[{'role':role, 'artifact':self.itemref(role)} for role in roles]}
        value.update(extra or {})
        return self.file(f'presentation_{self.counter}.json', value), when

    def approve(self, role, quote='审核通过'):
        receipt, when = self.presentation([role])
        self.cli('approve', '--role', role, '--quote', quote, '--shown-at', when,
                 '--presentation', str(receipt), '--scope', 'synthetic current artifact')

    def advance(self):
        self.cli('advance')

    def through_07(self):
        if not self.canonical.is_relative_to(self.root):
            self.canonical = self.file('canonical.md', self.canonical.read_text())
        self.register('evidence_ledger', {'qa_schema_version':1,'evidence_count':1,'counterevidence_count':0,'counterevidence_reviewed':True,'qa_pass':True})
        self.register('source_scout', {'qa_schema_version':1,'existing_asset_count':3,'gap_count':0,'inventory_reviewed':True,'gaps_reviewed':True,'qa_pass':True})
        self.advance()
        self.register('script', path=self.canonical)
        report = {'schema':'editorial_submission_v2','status':'PASS','bindings':{'script':self.itemref('script'),'canonical_text':self.ref(self.canonical)}}
        for key in ('thesis_and_evidence','character_motivation','counterexplanation_and_falsifier','full_referent_and_readaloud_review','opening_promise','ending_payoff'):
            report[key] = self.review()
        report_path = self.file('editorial_review.json', report)
        self.register('script_qa', {'qa_schema_version':2,'script_sha256':self.itemref('script')['sha256'],'qa_pass':True,'traditional_chinese_pass':True,
                                 'author_voice_pass':True,'visual_anchors_pass':True,'submission_review':self.ref(report_path)}, path=report_path)
        self.advance()
        self.approve('script')
        self.advance()
        self.register('narration', {'duration_frame_count':600})
        source = self.file('voice_input.json', {'reference_audio':str(self.voice),'reference_audio_sha256':self.ref(self.voice)['sha256'],
                         'reference_rule_sha256':self.ref(self.rule)['sha256'],'reference_transcript':'测试参考文字',
                         'canonical_text_sha256':self.ref(self.canonical)['sha256'],
                         'generation_config':{'prompt_wav_path':str(self.voice),'reference_wav_path':str(self.voice),'prompt_text':'测试参考文字'}})
        smoke = self.file('opening_review.json', {'schema':'voice_opening_smoke_v2','status':'PASS','source_manifest':self.ref(source),
                          'canonical_text':self.ref(self.canonical),'sample_audio':self.ref(self.voice), 'reviewer':'synthetic-test','notes':'not an actual audition',
                          'checks':dict.fromkeys(('opening_prosody','pause_naturalness','pronunciation_hotspots','listened_to_actual_sample'), True)})
        preflight = self.root/'fixtures/voice_preflight.json'
        cmd = [sys.executable,str(SKILLS/'voxcpm-batch-dubbing/scripts/verify_voice_reference.py'),'--source-manifest',str(source),
               '--rule',str(self.rule),'--phase','bulk','--smoke-review',str(smoke),'--output-json',str(preflight)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        report = {'schema':'voice_submission_v2','status':'PASS','bindings':{r:self.itemref(r) for r in ('script','narration')}, 'reference_preflight':self.ref(preflight)}
        for key in ('fixed_reference_preflight','opening_prosody','pronunciation_hotspots','joins_and_tail'):
            report[key] = self.review()
        report_path = self.file('voice_submission.json', report)
        self.register('voice_release', {'lexical_pass':True,'prosody_pass':True,'full_length_file':True,'submission_review':self.ref(report_path)})
        self.approve('narration')
        self.advance()
        self.register('subtitle', {'cue_count':3,'final_end_frame':600,'target_frame_count':600})
        self.register('timing_contract', path=self.file('timing.json',{'fps':60,'target_frame_count':600}))
        self.approve('subtitle')
        self.advance()
        freeze = self.file('source_freeze.json', {'sources':['S1','S2','S3']})
        report = {'schema':'source_capacity_v2','status':'PASS','bindings':{'subtitle':self.itemref('subtitle'),'source_freeze':self.ref(freeze)},
                  'capacities':[{'subject':'测试CG','required_slots':3,'eligible_physical_groups':['F1','F2','F3'],'planned_callbacks':0}],
                  'unresolved_capacity_gaps':0,'capacity_review':self.review()}
        report_path = self.file('capacity.json',report)
        self.register('source_freeze', {'p0_gap_count':0,'frozen':True,'submission_review':self.ref(report_path)}, path=freeze)
        self.advance()

    def stage_08(self, approve=True):
        self.register('track_plan', {'cue_count':3,'cut_policy':'per_caption_refresh'})
        segments = [{'segment_id':f'SEG{i}','cue_id':str(i),'source_id':f'S{i}','source_sha256':hashlib.sha256(str(i).encode()).hexdigest(),
                     'source_in':0,'source_out':10/3,'start_frame':(i-1)*200,'end_frame':i*200,'visual_family_id':f'F{i}',
                     'visual_type':'official_cg','production_caption_baked':False,'production_card_baked':False} for i in range(1,4)]
        self.selected = self.file('selected.json', segments)
        ui_dir = SKILLS/'zhangyanfa-track-design/assets/review-ui-v1'
        report = {'schema':'a_submission_v2','status':'PASS',
                  'bindings':{r:self.itemref(r) for r in ('track_plan','narration','subtitle','timing_contract')},
                  'review_ui':{'framework_id':'foxjiu-review-ui-v1','version_namespace':'test-v2','previous_version_namespace':'test-v1',
                               'framework_manifest':self.ref(ui_dir/'framework_manifest.json'),
                               'framework_files':{n:self.ref(ui_dir/n) for n in ('index.html','review.css','review.js')}}}
        report['bindings']['selected_segments'] = self.ref(self.selected)
        for key in ('near_visual_review','whole_episode_review','opening_review','auxiliary_overlay_review'):
            report[key] = self.review()
        report['opening_review'].update(watched_with_frozen_narration=True,
            shot_purposes=[{'segment_id':s['segment_id'],'purpose':'fixture','new_information':'fixture'} for s in segments])
        self.a_report = self.file('a_submission.json',report)
        self.a_meta = {'cue_count':3,'identity_error_count':0,'semantic_coverage_pass':True,'unexplained_boundary_reuse_count':0,
                       'selected_segments_sha256':self.ref(self.selected)['sha256'],'submission_review':self.ref(self.a_report)}
        self.register('a_review', self.a_meta)
        for role in ('b_review','c_review'):
            self.register(role, {'identity_error_count':0,'visual_gain_pass':True})
        self.register('bgm_review', {'candidate_id':'A'})
        if approve:
            roles = ['a_review','b_review','c_review','bgm_review']
            presentation, when = self.presentation(roles)
            data = {'schema':'approval_batch_v2','user_quote':'A审核通过、B审核通过、C审核通过，BGM选择A',
                    'decisions':[{'role':r,'scope':r,'presentation':str(presentation),'shown_at':when} for r in roles]}
            self.cli('approve-batch','--decisions',str(self.file('batch.json',data)))
            self.advance()

    def stage_09(self):
        master = self.file('bgm_master.wav','synthetic BGM')
        report = {'schema':'bgm_derivation_v2','status':'PASS','candidate_id':'A','target_frame_count':600,
                  'bindings':{r:self.itemref(r) for r in ('bgm_review','narration','subtitle','timing_contract')},
                  'chapter_coverage_pass':True,'narration_intelligibility_pass':True}
        report['bindings']['bgm_master'] = self.ref(master)
        self.derivation = self.file('derivation.json',report)
        self.register('bgm_master', {'derivation':self.ref(self.derivation)},path=master)
        self.register('integrated_proxy_720',{'full_length':True,'width':1280,'height':720,'fps':60,'target_frame_count':600,
                                            'components':['A','B','C','BGM','narration','subtitle'],'bgm_master_sha256':self.ref(master)['sha256']})
        self.proxy_display, self.proxy_shown = self.presentation(['integrated_proxy_720'],
            {'next_action':{'action':'formal_render','delivery_spec_sha256':workflow.contracts.json_digest(self.spec())}})
        self.cli('approve','--role','integrated_proxy_720','--quote','审核通过，进入下一步','--scope','current proxy',
                 '--presentation',str(self.proxy_display),'--shown-at',self.proxy_shown)
        self.advance()
        self.cli('authorize-render','--quote','审核通过，进入下一步','--scope','presented formal rendering',
                 '--presentation',str(self.proxy_display),'--shown-at',self.proxy_shown)

    def preflight(self, expected=0):
        result = subprocess.run([sys.executable,str(SKILLS/'zhangyanfa-track-renderer/scripts/formal_render_preflight.py'),
                                 '--project-root',str(self.root)],capture_output=True,text=True)
        self.assertEqual(result.returncode, expected, result.stdout+result.stderr)
        return result

    def stage_10_11(self):
        spec = {key:self.spec()[key] for key in ('width','height','fps','target_frame_count')}
        for role in ('a_master','b_master','c_master'):
            self.register(role,{**spec,'subtitle_baked':False,'audio_baked':False,'auxiliary_overlays_baked':False})
        self.register('render_qa',{**spec,'sequential_render':True,'full_decode':True})
        self.advance()
        mode = self.spec()['delivery_mode']
        if mode in ('independent_tracks','both'):
            bundle = self.file('split_delivery.json', {'schema':'independent_delivery_v2','status':'ready',**spec,
                'assets':{r:self.itemref(r) for r in ('narration','subtitle','timing_contract','bgm_master','render_qa','a_master','b_master','c_master')},
                'a_subtitle_baked':False,'a_audio_baked':False,'a_auxiliary_overlays_baked':False})
            self.register('split_delivery',path=bundle)
            qa = self.file('split_delivery_qa.json',{'status':'PASS','delivery':self.ref(bundle),'audio_tail_pass':True,'asset_clock_pass':True})
            self.register('split_delivery_qa',path=qa)
        if mode in ('integrated','both'):
            self.register('final_video')
            self.register('final_video_qa',{'full_decode':True,'target_frame_count':600,'black_flash_count':0,'subtitle_coverage_pass':True,
                                           'audio_tail_pass':True,'components':['A','B','C','BGM','narration']})
            self.approve('final_video')
        self.advance()

    def covers_and_seal(self):
        self.register('cover_candidates',{'candidate_count':6})
        self.approve('cover_candidates','选择A')
        roles = []
        for role,ratio in (('cover_16_9','16:9'),('cover_4_3','4:3'),('cover_3_4','3:4')):
            self.register(role,{'ratio':ratio,'layout_pass':True,'aspect_ratio_pass':True,'thumbnail_pass':True})
            roles.append(role)
        if self.spec()['delivery_mode'] in ('independent_tracks','both'):
            roles.append('split_delivery')
        receipt,when = self.presentation(roles)
        data = {'schema':'approval_batch_v2','user_quote':'所有交付审核通过，这期结束了',
                'decisions':[{'role':r,'scope':r,'shown_at':when,'presentation':str(receipt)} for r in roles]}
        self.cli('approve-batch','--decisions',str(self.file('delivery_decisions.json',data)))
        self.advance()
        self.cli('seal')

    def test_independent_pipeline_seals_without_combined_video(self):
        self.through_07(); self.stage_08(); self.stage_09(); self.preflight(); self.stage_10_11(); self.covers_and_seal()
        self.assertNotIn('final_video',self.items())
        self.assertEqual(json.loads((self.root/'CURRENT.json').read_text())['status'],'sealed')
        old = {r:self.itemref(r) for r in ('a_master','b_master','c_master','bgm_review')}
        self.cli('invalidate','--role','bgm_master','--reason','change full score mix')
        self.assertEqual(json.loads((self.root/'CURRENT.json').read_text())['current_stage'],'09_integrated_720_review')
        for role,ref in old.items(): self.assertEqual(ref,self.itemref(role))
        self.assertNotIn('split_delivery',self.items())

    def test_integrated_and_both_modes(self):
        for mode in ('integrated','both'):
            with self.subTest(mode=mode):
                if mode == 'both':
                    self.root = Path(self.temp.name)/'both'
                    self.root.mkdir()
                else:
                    # A fresh project; no edits to a frozen contract.
                    self.root = Path(self.temp.name)/'integrated'
                    self.root.mkdir()
                self.init(mode)
                self.through_07(); self.stage_08(); self.stage_09(); self.preflight(); self.stage_10_11(); self.covers_and_seal()
                self.assertIn('final_video',self.items())
                self.assertEqual('split_delivery' in self.items(),mode=='both')

    def test_nested_review_drift_blocks_formal_preflight(self):
        self.through_07(); self.stage_08(); self.stage_09()
        self.evidence.write_text('changed after review')
        result = self.preflight(expected=1)
        self.assertIn('missing or changed bound file',result.stdout)

    def test_missing_editorial_receipt_fails_at_registration(self):
        self.register('evidence_ledger',{'qa_schema_version':1,'evidence_count':1,'counterevidence_count':0,'counterevidence_reviewed':True,'qa_pass':True})
        self.register('source_scout',{'qa_schema_version':1,'existing_asset_count':1,'gap_count':0,'inventory_reviewed':True,'gaps_reviewed':True,'qa_pass':True})
        self.advance(); self.register('script',path=self.canonical)
        self.register('script_qa',{'qa_pass':True},expected=2)
        self.assertNotIn('script_qa',self.items())

    def test_batch_wrong_display_is_atomic_and_selection_must_match(self):
        self.through_07(); self.stage_08(approve=False)
        receipt,when = self.presentation(['b_review'])
        before = (self.root/'approvals/approval_ledger.jsonl').read_bytes()
        decisions = [{'role':r,'scope':r,'shown_at':when,'presentation':str(receipt)} for r in ('b_review','c_review')]
        data = {'schema':'approval_batch_v2','user_quote':'B通过、C通过','decisions':decisions}
        self.cli('approve-batch','--decisions',str(self.file('bad_batch.json',data)),expected=2)
        self.assertEqual(before,(self.root/'approvals/approval_ledger.jsonl').read_bytes())
        self.cli('approve','--role','b_review','--quote','BGM选择A','--shown-at',when,'--presentation',str(receipt),'--scope','B',expected=2)
        receipt,when = self.presentation(['bgm_review'])
        self.cli('approve','--role','bgm_review','--quote','BGM选择B','--shown-at',when,'--presentation',str(receipt),'--scope','BGM',expected=2)

    def test_same_bytes_shown_before_registration_can_be_approved(self):
        self.through_07(); self.stage_08(approve=False)
        receipt,when = self.presentation(['b_review'])
        old_path = self.root/self.items()['b_review']['path']
        copy = self.file('b_delivery_copy.dat',old_path.read_text())
        self.register('b_review',{'identity_error_count':0,'visual_gain_pass':True},path=copy)
        self.cli('approve','--role','b_review','--quote','B通过','--shown-at',when,'--presentation',str(receipt),'--scope','same bytes')
        self.assertIn('approval_id',self.items()['b_review'])

    def test_cards_reused_namespace_and_excess_replays_cannot_register(self):
        self.through_07(); self.stage_08(approve=False)
        baseline = json.loads(self.selected.read_text())
        original_report = json.loads(self.a_report.read_text())
        mutations = ('card','namespace','three_replays')
        for kind in mutations:
            with self.subTest(kind=kind):
                segments = json.loads(json.dumps(baseline))
                report = json.loads(json.dumps(original_report))
                if kind == 'card': segments[0]['visual_type']='text_card'
                elif kind == 'namespace': report['review_ui']['previous_version_namespace']='test-v2'
                else:
                    segments = []
                    for i in range(5):
                        s = dict(baseline[i%3]); s.update(segment_id=f'replay{i}',start_frame=i*120,end_frame=(i+1)*120)
                        if i%2==0: s.update(visual_family_id='REPEAT',source_id='R',source_sha256='a'*64)
                        else: s.update(visual_family_id=f'U{i}',source_id=f'U{i}',source_sha256=str(i)*64)
                        segments.append(s)
                    report['opening_review']['shot_purposes']=[{'segment_id':s['segment_id'],'purpose':'fixture','new_information':'fixture'} for s in segments]
                self.selected.write_text(json.dumps(segments))
                report['bindings']['selected_segments']=self.ref(self.selected)
                self.a_report.write_text(json.dumps(report))
                meta={**self.a_meta,'selected_segments_sha256':self.ref(self.selected)['sha256'],'submission_review':self.ref(self.a_report)}
                self.register('a_review',meta,expected=2)

    def test_negative_and_partial_scope_decisions(self):
        for quote in ('不通过','还没审核','还没审批','等待审批','未审核通过','继续','先别渲染'):
            with self.assertRaises(workflow.WorkflowError): workflow.decision_text('a_review',quote)
        self.assertEqual(workflow.decision_text('b_review','A不通过，B通过','B通过'),'B通过')
        self.assertEqual(workflow.decision_text('b_review','A不通过、B通过','B通过'),'B通过')
        with self.assertRaises(workflow.WorkflowError): workflow.decision_text('a_review','A不通过','通过')

    def test_default_new_profile_and_missing_display(self):
        fresh=Path(self.temp.name)/'default'
        result=subprocess.run([sys.executable,str(SCRIPT),'init','--root',str(fresh),'--title','默认模板测试','--theme','冻结默认规格',
                               '--width','2560','--height','1440','--fps','60','--cut-policy','per_caption_refresh',
                               '--tracks','A,B,C,BGM','--b-output-mode','green','--c-output-mode','green','--assembly-tool','hyperframes',
                               '--episode-key','TEST_EP001','--cache-root',str(Path(self.temp.name)/'cache'),'--media-root',str(Path(self.temp.name)/'media')],
                              capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        spec=json.loads((fresh/'authority_bundle.json').read_text())['delivery_spec']
        self.assertEqual(spec['production_contract_version'],2)
        self.assertEqual(spec['delivery_mode'],'independent_tracks')
        self.assertFalse(spec['a_subtitle_baked'])
        with self.assertRaises(workflow.WorkflowError): workflow.validate_presentation(self.root,None,'b_review',{},'')


if __name__ == '__main__':
    unittest.main()

"""Verify pre-model reference and real-file binding gates without generating speech."""
import json
from pathlib import Path
import tempfile
import unittest
from verify_voice_reference import verify, binding


class VoicePreflightTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.audio = self.write('voice.wav', 'reference fixture bytes')
        self.canonical = self.write('canonical.md', '测试正典')
        self.rule = self.write('rule.json', {'sha256':binding(self.audio)['sha256'],'transcript':'reference transcript'})
        self.source_data = {'reference_audio':str(self.audio),'reference_audio_sha256':binding(self.audio)['sha256'],
                            'reference_rule_sha256':binding(self.rule)['sha256'],'reference_transcript':'reference transcript',
                            'canonical_text_sha256':binding(self.canonical)['sha256'],
                            'generation_config':{'prompt_wav_path':str(self.audio),'reference_wav_path':str(self.audio),'prompt_text':'reference transcript'}}
        self.source = self.write('source.json',self.source_data)
        self.smoke_data = {'schema':'voice_opening_smoke_v2','status':'PASS','source_manifest':binding(self.source),'sample_audio':binding(self.audio),
                           'canonical_text':binding(self.canonical),'reviewer':'synthetic test','notes':'binding check only, not real listening',
                           'checks':dict.fromkeys(('opening_prosody','pause_naturalness','pronunciation_hotspots','listened_to_actual_sample'),True)}
        self.smoke = self.write('smoke.json', self.smoke_data)

    def tearDown(self): self.temp.cleanup()

    def write(self,name,value):
        p=self.root/name; p.write_text(json.dumps(value) if isinstance(value,dict) else value); return p

    def test_reference_only_remains_compatible_but_bulk_needs_sample(self):
        self.assertTrue(verify(self.source,self.rule)['passed'])
        self.assertFalse(verify(self.source,self.rule,'bulk')['passed'])
        self.assertTrue(verify(self.source,self.rule,'bulk',self.smoke)['passed'])

    def test_wrong_audio_or_reference_text_is_blocked(self):
        wrong=self.write('wrong.wav','different speaker')
        self.source_data['generation_config']['reference_wav_path']=str(wrong)
        self.write('source.json',self.source_data)
        self.assertFalse(verify(self.source,self.rule)['passed'])
        self.source_data['generation_config']['reference_wav_path']=str(self.audio)
        self.source_data['reference_transcript']='paraphrased reference'
        self.write('source.json',self.source_data)
        self.assertFalse(verify(self.source,self.rule)['passed'])

    def test_config_changes_or_unreviewed_pauses_block_bulk(self):
        self.smoke_data['checks']['pause_naturalness']=False
        self.write('smoke.json',self.smoke_data)
        self.assertFalse(verify(self.source,self.rule,'bulk',self.smoke)['passed'])
        self.smoke_data['checks']['pause_naturalness']=True
        self.write('smoke.json',self.smoke_data)
        self.source_data['generation_config']['temperature']=0.9
        self.write('source.json',self.source_data)
        self.assertFalse(verify(self.source,self.rule,'bulk',self.smoke)['passed'])

    def test_modified_sample_invalidates_pass(self):
        self.audio.write_text('changed bytes')
        self.assertFalse(verify(self.source,self.rule,'bulk',self.smoke)['passed'])


if __name__=='__main__': unittest.main()

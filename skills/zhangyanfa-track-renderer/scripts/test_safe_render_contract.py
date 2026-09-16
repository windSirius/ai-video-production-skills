"""Regression checks for shared locking and stale-input cache reuse."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from safe_render_supervisor import task_fingerprint, valid_receipt, sha256_file, _job_guard


class RenderContractTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.source=self.root/'source.dat'; self.source.write_text('input')
        self.output=self.root/'output.dat'; self.output.write_text('output')
        self.task={'task_id':'test','output':str(self.output),'track':'A','start_frame':0,'end_frame':60,
                   'input_bindings':[{'path':str(self.source),'sha256':sha256_file(self.source)}],
                   'tool_versions':{'test-engine':'1'}, 'attempts':[{'command':['test-engine','render']}], 'color':'rgb24'}
        self.receipt=self.root/'receipt.json'
        self.receipt.write_text(json.dumps({'status':'PASS','task_id':'test','output_sha256':sha256_file(self.output),
                                            'task_fingerprint':task_fingerprint(self.task)}))

    def tearDown(self): self.temp.cleanup()

    def test_unchanged_inputs_can_resume(self):
        self.assertTrue(valid_receipt(self.receipt,self.task))

    def test_config_tool_or_input_change_cannot_reuse_output(self):
        for key,value in (('color','bt709-limited'),('end_frame',120),('tool_versions',{'test-engine':'2'})):
            altered=copy.deepcopy(self.task); altered[key]=value
            self.assertFalse(valid_receipt(self.receipt,altered))
        self.source.write_text('changed source')
        self.assertFalse(valid_receipt(self.receipt,self.task))

    def test_old_output_only_receipt_is_insufficient(self):
        self.receipt.write_text(json.dumps({'status':'PASS','task_id':'test','output_sha256':sha256_file(self.output)}))
        self.assertFalse(valid_receipt(self.receipt,self.task))

    def test_shared_lock_blocks_other_process_and_releases_on_exit(self):
        path=self.root/'shared.lock'
        code="import fcntl,sys; f=open(sys.argv[1],'a+'); fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)"
        with _job_guard.heavy_lock(path):
            blocked=subprocess.run([sys.executable,'-c',code,str(path)],capture_output=True)
            self.assertNotEqual(blocked.returncode,0)
        released=subprocess.run([sys.executable,'-c',code,str(path)],capture_output=True)
        self.assertEqual(released.returncode,0)


if __name__=='__main__': unittest.main()

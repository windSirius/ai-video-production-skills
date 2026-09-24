"""Scoped cover adoption must retain real presentation and artifact checks."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import workflow

class CoverAdoptionTest(unittest.TestCase):
    quote = 'OK保留这个设计，把这个迭代进skill'
    def test_exact_scoped_acceptance(self):
        for role in ('cover_16_9', 'cover_4_3', 'cover_3_4'):
            self.assertEqual(workflow.decision_text(role, self.quote, 'OK保留这个设计'), 'OK保留这个设计')
    def test_question_work_request_and_other_roles_are_not_approval(self):
        for quote in ('OK保留这个设计吗？', '先保留这个设计再改一下', '不要保留这个设计', 'OK保留这个设计，但还没有确认'):
            self.assertFalse(workflow.approval_quote_is_explicit('cover_3_4', quote))
        for role in ('narration', 'split_delivery', 'a_review', 'cover_candidates'):
            self.assertFalse(workflow.approval_quote_is_explicit(role, 'OK保留这个设计'))
    def test_adoption_cannot_replace_display_or_approve_changed_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); image=root/'cover.dat';image.write_bytes(b'synthetic-cover')
            sha=hashlib.sha256(image.read_bytes()).hexdigest();when='2026-09-20T13:00:00+00:00'
            item={'path':'cover.dat','sha256':sha}
            with self.assertRaises(workflow.WorkflowError):
                workflow.validate_presentation(root, 'missing.json', 'cover_3_4', item, when)
            doc={'schema':'artifact_presentation_v2','shown_at':when,'display_evidence':{'type':'webui','locator':'http://localhost/cover'},'items':[{'role':'cover_3_4','artifact':item}]}
            (root/'shown.json').write_text(json.dumps(doc))
            workflow.validate_presentation(root,'shown.json','cover_3_4',item,when)
            image.write_bytes(b'changed-cover')
            with self.assertRaises(workflow.WorkflowError):
                workflow.validate_presentation(root,'shown.json','cover_3_4',item,when)
if __name__=='__main__':unittest.main()

import copy
import unittest

from audit_bgm_diversity import audit


class DiversityTest(unittest.TestCase):
    def setUp(self):
        self.catalog = {"tracks": [
            {"track_id": f"t{i}", "composition_id": f"work{i}",
             "sha256": f"{i:064x}", "palette": f"palette{i % 4}", "vocal_content": "instrumental"}
            for i in range(12)]}
        self.history = {"scope": "three actual episodes", "episodes": [
            {"candidate_track_ids": ["t0", "t1", "t2", "t3"], "selected_track_ids": ["t0"]}
            for _ in range(3)]}
        self.plan = {"shortlist": [{"track_id": f"t{i}", "fit_reason": "evaluated for this chapter"}
                                    for i in range(12)], "candidates": [
            {"candidate_id": letter, "lead_track_id": f"t{i}", "track_ids": [f"t{i}"],
             "rationale": "distinct narrative role", "evidence_strategy": "sparse bed",
             "turn_strategy": "shift at conclusion"}
            for i, letter in zip(range(4, 8), "ABCD")]}

    def test_fresh_sources_pass(self):
        result = audit(self.catalog, self.history, self.plan)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["fresh_lead_count"], 4)

    def test_different_bytes_same_composition_fail(self):
        self.catalog["tracks"][5]["composition_id"] = "work4"
        result = audit(self.catalog, self.history, self.plan)
        self.assertTrue(any("duplicate_lead_composition" in e for e in result["errors"]))

    def test_relabeling_recent_tracks_does_not_create_novelty(self):
        for row, i in zip(self.plan["candidates"], range(4)):
            row.update(lead_track_id=f"t{i}", track_ids=[f"t{i}"])
        result = audit(self.catalog, self.history, self.plan)
        self.assertEqual(result["fresh_lead_count"], 0)
        self.assertEqual(result["status"], "FAIL")

    def test_same_sha_different_identity_cannot_escape_history(self):
        self.catalog["tracks"][4]["sha256"] = self.catalog["tracks"][0]["sha256"]
        self.assertEqual(audit(self.catalog, self.history, self.plan)["status"], "FAIL")

    def test_source_swap_in_actual_audition_fails(self):
        manifest = {"source_receipts": [], "candidates": []}
        for i, letter in zip(range(4, 8), "ABCD"):
            digest = f"{i:064x}"
            manifest["source_receipts"].append({"source_id": letter, "sha256": digest})
            manifest["candidates"].append({"candidate_id": letter, "checkpoints": [
                {"source_id": letter, "source_sha256": digest}]})
        self.assertEqual(audit(self.catalog, self.history, self.plan, manifest)["status"], "PASS")
        manifest["candidates"][0]["checkpoints"][0]["source_sha256"] = f"{0:064x}"
        self.assertEqual(audit(self.catalog, self.history, self.plan, manifest)["status"], "FAIL")

    def test_editorial_exception_is_visible_not_approval(self):
        plan = copy.deepcopy(self.plan)
        plan["shortlist"] = plan["shortlist"][4:8]
        plan["exceptions"] = [{"code": "shortlist_too_small", "reason": "four mandatory diegetic themes"}]
        result = audit(self.catalog, self.history, plan)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["warnings"])
        self.assertNotIn("approval", result)


if __name__ == "__main__":
    unittest.main()

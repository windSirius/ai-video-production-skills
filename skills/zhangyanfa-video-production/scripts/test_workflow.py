#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("workflow.py")


class WorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "episode"
        self.cli(
            "init",
            "--root", str(self.root),
            "--title", "测试视频",
            "--theme", "测试十三阶段",
            "--width", "2560",
            "--height", "1440",
            "--fps", "60",
            "--cut-policy", "per_caption_refresh",
            "--tracks", "A,B,C,BGM",
            "--b-output-mode", "green",
            "--c-output-mode", "green",
            "--assembly-tool", "jianying",
            "--house-style", str(SCRIPT.parent.parent / "assets/house_style.v1.json"),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def cli(self, *arguments: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
        # These regression cases exercise the frozen v1 contract. v2 has its own suite.
        if arguments[0] == "init" and "--house-style" not in arguments:
            arguments = (*arguments, "--house-style", str(SCRIPT.parent.parent / "assets/house_style.v1.json"))
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != expected:
            self.fail(
                f"command returned {result.returncode}, expected {expected}\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            )
        return result

    def artifact(self, name: str, content: str | None = None) -> Path:
        path = self.root / "artifacts" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content if content is not None else name, encoding="utf-8")
        return path

    def register(self, stage: str, role: str, meta: dict | None = None) -> Path:
        path = self.artifact(f"{role}.dat")
        self.cli(
            "register",
            "--root", str(self.root),
            "--stage", stage,
            "--role", role,
            "--path", str(path),
            "--meta-json", json.dumps(meta or {}, ensure_ascii=False),
        )
        return path

    def approve(self, role: str, quote: str | None = None, scope: str | None = None) -> None:
        self.cli(
            "approve",
            "--root", str(self.root),
            "--role", role,
            "--shown-at", datetime.now(timezone.utc).isoformat(),
            "--quote", quote or f"{role}通过",
            "--scope", scope or f"只批准{role}",
        )

    def authorize_render(self, quote: str = "720终审通过，授权开始2K60正式渲染") -> None:
        self.cli(
            "authorize-render",
            "--root", str(self.root),
            "--shown-at", datetime.now(timezone.utc).isoformat(),
            "--quote", quote,
            "--scope", "只授权当前720整合代理对应的正式分轨渲染",
        )

    def advance(self) -> None:
        self.cli("advance", "--root", str(self.root))

    def current(self) -> dict:
        return json.loads((self.root / "CURRENT.json").read_text(encoding="utf-8"))

    def deliverables(self) -> dict:
        return json.loads((self.root / "deliverables.json").read_text(encoding="utf-8"))

    def artifact_sha256(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def register_research_stage(self) -> tuple[Path, Path]:
        evidence = self.register(
            "02_research_scout",
            "evidence_ledger",
            {
                "qa_schema_version": 1,
                "evidence_count": 1,
                "counterevidence_count": 0,
                "counterevidence_reviewed": True,
                "qa_pass": True,
            },
        )
        scout = self.register(
            "02_research_scout",
            "source_scout",
            {
                "qa_schema_version": 1,
                "existing_asset_count": 0,
                "gap_count": 0,
                "inventory_reviewed": True,
                "gaps_reviewed": True,
                "qa_pass": True,
            },
        )
        return evidence, scout

    def register_script_stage(self) -> Path:
        script = self.register("03_script_build", "script")
        self.register(
            "03_script_build",
            "script_qa",
            {
                "qa_schema_version": 1,
                "script_sha256": self.artifact_sha256(script),
                "qa_pass": True,
                "traditional_chinese_pass": True,
                "author_voice_pass": True,
                "visual_anchors_pass": True,
            },
        )
        return script

    def build_through_stage_07(self) -> None:
        self.register_research_stage()
        self.advance()

        self.register_script_stage()
        self.advance()
        self.approve("script", "稿件通过", "当前稿件")
        self.advance()

        self.register("05_narration", "narration", {"duration_frame_count": 100})
        self.register(
            "05_narration",
            "voice_release",
            {"lexical_pass": True, "prosody_pass": True, "full_length_file": True},
        )
        self.approve("narration", "完整听完，通过", "实际完整口播母带")
        self.advance()

        self.register(
            "06_subtitle",
            "subtitle",
            {"cue_count": 2, "final_end_frame": 99, "target_frame_count": 100},
        )
        self.register("06_subtitle", "timing_contract")
        self.approve("subtitle", "这是最终版字幕", "最终SRT及时间轴")
        self.advance()

        self.register("07_source_freeze", "source_freeze", {"p0_gap_count": 0, "frozen": True})
        self.advance()

    def register_and_approve_stage_08(self, bgm_content: str = "bgm-v1") -> None:
        self.register(
            "08_track_design",
            "track_plan",
            {"cue_count": 2, "cut_policy": "per_caption_refresh"},
        )
        self.register(
            "08_track_design",
            "a_review",
            {
                "cue_count": 2,
                "identity_error_count": 0,
                "semantic_coverage_pass": True,
                "unexplained_boundary_reuse_count": 0,
            },
        )
        self.register(
            "08_track_design",
            "b_review",
            {"identity_error_count": 0, "visual_gain_pass": True},
        )
        self.register(
            "08_track_design",
            "c_review",
            {"identity_error_count": 0, "visual_gain_pass": True},
        )
        bgm_path = self.artifact("bgm_master.dat", bgm_content)
        self.cli(
            "register",
            "--root", str(self.root),
            "--stage", "08_track_design",
            "--role", "bgm_master",
            "--path", str(bgm_path),
            "--meta-json", json.dumps(
                {"narration_intelligibility_pass": True, "duration_frame_count": 100}
            ),
        )
        for role in ("a_review", "b_review", "c_review", "bgm_master"):
            self.approve(role)

    def register_and_approve_stage_09(self, suffix: str = "v1") -> None:
        path = self.artifact(f"integrated_proxy_720_{suffix}.dat")
        self.cli(
            "register",
            "--root", str(self.root),
            "--stage", "09_integrated_720_review",
            "--role", "integrated_proxy_720",
            "--path", str(path),
            "--meta-json", json.dumps(
                {
                    "full_length": True,
                    "width": 1280,
                    "height": 720,
                    "fps": 60,
                    "target_frame_count": 100,
                    "components": ["A", "B", "C", "BGM", "narration", "subtitle"],
                }
            ),
        )
        self.approve("integrated_proxy_720")

    def register_stage_10(self) -> None:
        for role in ("a_master", "b_master", "c_master"):
            self.register("10_formal_render", role)
        self.register(
            "10_formal_render",
            "render_qa",
            {
                "sequential_render": True,
                "full_decode": True,
                "width": 2560,
                "height": 1440,
                "fps": 60,
                "target_frame_count": 100,
            },
        )

    def register_and_approve_stage_11(self, suffix: str = "v1") -> None:
        path = self.artifact(f"final_video_{suffix}.dat")
        self.cli(
            "register",
            "--root", str(self.root),
            "--stage", "11_final_assembly",
            "--role", "final_video",
            "--path", str(path),
        )
        self.register(
            "11_final_assembly",
            "final_video_qa",
            {
                "full_decode": True,
                "target_frame_count": 100,
                "black_flash_count": 0,
                "subtitle_coverage_pass": True,
                "audio_tail_pass": True,
                "components": ["A", "B", "C", "BGM", "narration", "subtitle"],
            },
        )
        self.approve("final_video")

    def register_and_approve_stage_12(self) -> None:
        self.register("12_cover", "cover_candidates", {"candidate_count": 6})
        self.approve("cover_candidates", "选择A", "六稿中选择A")
        for role, ratio in (
            ("cover_16_9", "16:9"),
            ("cover_4_3", "4:3"),
            ("cover_3_4", "3:4"),
        ):
            self.register(
                "12_cover",
                role,
                {
                    "ratio": ratio,
                    "layout_pass": True,
                    "aspect_ratio_pass": True,
                    "thumbnail_pass": True,
                },
            )
            self.approve(role)

    def build_and_seal(self) -> None:
        self.build_through_stage_07()
        self.register_and_approve_stage_08()
        self.advance()
        self.register_and_approve_stage_09()
        self.advance()
        self.authorize_render()
        self.register_stage_10()
        self.advance()
        self.register_and_approve_stage_11()
        self.advance()
        self.register_and_approve_stage_12()
        self.advance()
        self.cli("seal", "--root", str(self.root))

    def test_full_pipeline_and_bgm_only_invalidation(self) -> None:
        self.build_and_seal()
        current = self.current()
        self.assertEqual(current["status"], "sealed")
        self.assertEqual(current["current_stage"], "13_seal")

        self.cli(
            "invalidate",
            "--root", str(self.root),
            "--role", "bgm_master",
            "--reason", "用户改选BGM",
        )
        self.assertEqual(self.current()["current_stage"], "08_track_design")
        items = self.deliverables()["items"]
        self.assertNotIn("bgm_master", items)
        self.assertNotIn("integrated_proxy_720", items)
        self.assertNotIn("final_video", items)
        self.assertIn("a_master", items)
        self.assertIn("b_master", items)
        self.assertIn("c_master", items)
        self.assertIn("cover_16_9", items)

        bgm_path = self.artifact("bgm_master_v2.dat", "bgm-v2")
        self.cli(
            "register",
            "--root", str(self.root),
            "--stage", "08_track_design",
            "--role", "bgm_master",
            "--path", str(bgm_path),
            "--meta-json", json.dumps(
                {"narration_intelligibility_pass": True, "duration_frame_count": 100}
            ),
        )
        self.approve("bgm_master", "BG=D", "新BGM母带")
        self.advance()
        self.register_and_approve_stage_09("v2")
        self.advance()
        self.assertEqual(self.current()["current_stage"], "11_final_assembly")
        self.register_and_approve_stage_11("v2")
        self.advance()
        self.assertEqual(self.current()["current_stage"], "13_seal")
        self.cli("seal", "--root", str(self.root))
        self.assertEqual(self.current()["status"], "sealed")

    def test_track_approvals_are_separate_and_force_is_absent(self) -> None:
        self.build_through_stage_07()
        self.register_and_approve_stage_08()
        # Replace B after approval; replacement must clear B and all downstream approval state.
        replacement = self.artifact("b_review_v2.dat")
        self.cli(
            "register",
            "--root", str(self.root),
            "--stage", "08_track_design",
            "--role", "b_review",
            "--path", str(replacement),
            "--meta-json", json.dumps({"identity_error_count": 0, "visual_gain_pass": True}),
        )
        failed = self.cli("advance", "--root", str(self.root), expected=2)
        self.assertIn("b_review", failed.stderr)
        self.approve("b_review", "B通过", "只批准新版B轨")
        self.advance()
        self.cli("advance", "--root", str(self.root), "--force", expected=2)

    def test_sha_drift_blocks_progress(self) -> None:
        evidence, _ = self.register_research_stage()
        evidence.write_text("changed after registration", encoding="utf-8")
        result = self.cli("advance", "--root", str(self.root), expected=2)
        self.assertIn("SHA drift", result.stderr)

    def test_request_contract_is_frozen_and_drift_blocks_progress(self) -> None:
        contract_path = self.root / "request_contract.json"
        current = self.current()
        self.assertTrue(contract_path.is_file())
        self.assertEqual(current["request_contract"]["path"], "request_contract.json")
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        self.assertEqual(contract["house_style"]["profile_id"], "zhangyanfa_house_style_v1")
        contract["delivery_spec"]["fps"] = 30
        contract_path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
        result = self.cli("advance", "--root", str(self.root), expected=2)
        self.assertIn("request-contract pointer", result.stderr)

    def test_approval_must_follow_registration(self) -> None:
        self.register_research_stage()
        self.advance()
        self.register_script_stage()
        self.advance()
        result = self.cli(
            "approve",
            "--root", str(self.root),
            "--role", "script",
            "--shown-at", "2000-01-01T00:00:00+00:00",
            "--quote", "通过",
            "--scope", "稿件",
            expected=2,
        )
        self.assertIn("shown_at cannot precede", result.stderr)

    def test_work_authorization_cannot_be_recorded_as_approval(self) -> None:
        self.register_research_stage()
        self.advance()
        self.register_script_stage()
        self.advance()
        self.assertEqual(self.current()["stage_status"], "awaiting_user")
        result = self.cli(
            "approve",
            "--root", str(self.root),
            "--role", "script",
            "--shown-at", datetime.now(timezone.utc).isoformat(),
            "--quote", "开始制作",
            "--scope", "当前稿件",
            expected=2,
        )
        self.assertIn("work authorization", result.stderr)

        for quote in ("不通过", "未批准", "还没确认", "不选择A"):
            rejected = self.cli(
                "approve",
                "--root", str(self.root),
                "--role", "script",
                "--shown-at", datetime.now(timezone.utc).isoformat(),
                "--quote", quote,
                "--scope", "当前稿件",
                expected=2,
            )
            self.assertIn("not an explicit artifact decision", rejected.stderr)

    def test_init_rejects_blank_and_placeholder_title_or_theme(self) -> None:
        cases = (
            (" ", "真实主题"),
            ("未命名10分钟障眼法", "真实主题"),
            ("真实标题", "待用户确认（测试占位）"),
            ("真实标题", "TBD"),
        )
        for index, (title, theme) in enumerate(cases):
            root = Path(self.temporary.name) / f"bad-intake-{index}"
            result = self.cli(
                "init",
                "--root", str(root),
                "--title", title,
                "--theme", theme,
                "--width", "2560",
                "--height", "1440",
                "--fps", "60",
                "--cut-policy", "per_caption_refresh",
                "--tracks", "A,B,C,BGM",
                "--b-output-mode", "green",
                "--c-output-mode", "green",
                "--assembly-tool", "jianying",
                expected=2,
            )
            self.assertRegex(result.stderr, r"must not be blank|not a placeholder")
            self.assertFalse((root / "CURRENT.json").exists())

    def test_research_gate_requires_nonempty_structured_qa(self) -> None:
        evidence = self.artifact("empty_evidence.json", "")
        self.cli(
            "register",
            "--root", str(self.root),
            "--stage", "02_research_scout",
            "--role", "evidence_ledger",
            "--path", str(evidence),
            "--meta-json", "{}",
        )
        self.register(
            "02_research_scout",
            "source_scout",
            {
                "qa_schema_version": 1,
                "existing_asset_count": 0,
                "gap_count": 0,
                "inventory_reviewed": True,
                "gaps_reviewed": True,
                "qa_pass": True,
            },
        )
        result = self.cli("advance", "--root", str(self.root), expected=2)
        self.assertIn("evidence_ledger artifact must not be empty", result.stderr)
        self.assertIn("evidence_ledger.meta.qa_schema_version", result.stderr)
        self.assertIn("evidence_ledger.meta.evidence_count", result.stderr)

    def test_script_and_qa_must_be_nonempty_and_sha_bound(self) -> None:
        self.register_research_stage()
        self.advance()
        script = self.register("03_script_build", "script")
        self.register(
            "03_script_build",
            "script_qa",
            {
                "qa_schema_version": 1,
                "script_sha256": "0" * 64,
                "qa_pass": True,
                "traditional_chinese_pass": True,
                "author_voice_pass": True,
                "visual_anchors_pass": True,
            },
        )
        mismatch = self.cli("advance", "--root", str(self.root), expected=2)
        self.assertIn("script_sha256 must match", mismatch.stderr)

        # A fresh project proves that a hash-bound but empty script is still rejected.
        empty_root = Path(self.temporary.name) / "empty-script-project"
        self.cli(
            "init",
            "--root", str(empty_root),
            "--title", "空稿测试",
            "--theme", "验证空稿门禁",
            "--width", "2560",
            "--height", "1440",
            "--fps", "60",
            "--cut-policy", "per_caption_refresh",
            "--tracks", "A,B,C,BGM",
            "--b-output-mode", "green",
            "--c-output-mode", "green",
            "--assembly-tool", "jianying",
        )
        self.root = empty_root
        self.register_research_stage()
        self.advance()
        empty_script = self.artifact("script.md", "")
        self.cli(
            "register",
            "--root", str(self.root),
            "--stage", "03_script_build",
            "--role", "script",
            "--path", str(empty_script),
        )
        self.register(
            "03_script_build",
            "script_qa",
            {
                "qa_schema_version": 1,
                "script_sha256": self.artifact_sha256(empty_script),
                "qa_pass": True,
                "traditional_chinese_pass": True,
                "author_voice_pass": True,
                "visual_anchors_pass": True,
            },
        )
        empty = self.cli("advance", "--root", str(self.root), expected=2)
        self.assertIn("script artifact must not be empty", empty.stderr)

    def test_optional_target_duration_range_is_frozen_and_enforced(self) -> None:
        range_root = Path(self.temporary.name) / "duration-range-project"
        self.cli(
            "init",
            "--root", str(range_root),
            "--title", "十分钟范围测试",
            "--theme", "验证显式时长范围",
            "--width", "2560",
            "--height", "1440",
            "--fps", "60",
            "--target-duration-min-seconds", "600",
            "--target-duration-max-seconds", "600",
            "--house-style", str(SCRIPT.parent.parent / "assets/house_style.v1.json"),
            "--cut-policy", "per_caption_refresh",
            "--tracks", "A,B,C,BGM",
            "--b-output-mode", "green",
            "--c-output-mode", "green",
            "--assembly-tool", "jianying",
        )
        contract = json.loads((range_root / "request_contract.json").read_text(encoding="utf-8"))
        self.assertEqual(
            contract["delivery_spec"]["target_duration_range_seconds"],
            {"min": 600, "max": 600},
        )

        self.root = range_root
        self.register_research_stage()
        self.advance()
        self.register_script_stage()
        self.advance()
        self.approve("script", "稿件通过", "当前稿件")
        self.advance()
        self.register("05_narration", "narration", {"duration_frame_count": 35999})
        self.register(
            "05_narration",
            "voice_release",
            {"lexical_pass": True, "prosody_pass": True, "full_length_file": True},
        )
        self.approve("narration", "完整母带通过", "完整口播母带")
        result = self.cli("advance", "--root", str(self.root), expected=2)
        self.assertIn("outside target duration range 600-600 seconds", result.stderr)

        incomplete_root = Path(self.temporary.name) / "incomplete-duration-range"
        incomplete = self.cli(
            "init",
            "--root", str(incomplete_root),
            "--title", "时长参数测试",
            "--theme", "验证不完整时长范围",
            "--width", "2560",
            "--height", "1440",
            "--fps", "60",
            "--target-duration-min-seconds", "600",
            "--cut-policy", "per_caption_refresh",
            "--tracks", "A,B,C,BGM",
            "--b-output-mode", "green",
            "--c-output-mode", "green",
            "--assembly-tool", "jianying",
            expected=2,
        )
        self.assertIn("requires both", incomplete.stderr)
        self.assertFalse((incomplete_root / "CURRENT.json").exists())

    def test_formal_render_requires_proxy_bound_explicit_authorization(self) -> None:
        self.build_through_stage_07()
        self.register_and_approve_stage_08()
        self.advance()
        self.register_and_approve_stage_09()
        self.advance()
        self.assertEqual(self.current()["current_stage"], "10_formal_render")

        generic = self.cli(
            "authorize-render",
            "--root", str(self.root),
            "--shown-at", datetime.now(timezone.utc).isoformat(),
            "--quote", "继续",
            "--scope", "正式渲染",
            expected=2,
        )
        self.assertIn("must explicitly authorize", generic.stderr)

        self.authorize_render("三个轨道通过，现在可以进入2K60正式渲染")
        ledger = [
            json.loads(line)
            for line in (self.root / "approvals/approval_ledger.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        authorization = ledger[-1]
        proxy = self.deliverables()["items"]["integrated_proxy_720"]
        self.assertEqual(authorization["gate"], "formal_render_authorization")
        self.assertEqual(authorization["integrated_proxy_sha256"], proxy["sha256"])

        self.register_stage_10()
        self.advance()


if __name__ == "__main__":
    unittest.main()

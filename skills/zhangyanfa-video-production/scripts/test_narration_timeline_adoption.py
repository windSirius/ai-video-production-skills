import unittest

from workflow import approval_quote_is_explicit


class NarrationTimelineAdoptionTests(unittest.TestCase):
    def test_completed_audition_and_subtitle_adoption(self):
        quote = "以 **1× 速度完整听完，初版字幕以加载，按照初版字幕的时间轴冻结，然后修复字幕**"
        self.assertTrue(approval_quote_is_explicit("narration", quote))
        self.assertFalse(approval_quote_is_explicit("script", quote))
        self.assertFalse(approval_quote_is_explicit("a_review", quote))

    def test_requested_or_rejected_audition_does_not_approve(self):
        for quote in (
            "请以1×速度完整听完，然后修复字幕",
            "未完整听完，修复字幕",
            "以1×速度完整听完，初版字幕已加载，按照初版字幕的时间轴冻结，然后修复字幕，但配音不通过",
        ):
            self.assertFalse(approval_quote_is_explicit("narration", quote))


if __name__ == "__main__":
    unittest.main()

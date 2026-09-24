from pathlib import Path
import unittest

from index_bgm_library import audio_metadata, apply_supplied_metadata


class LibraryMetadataTest(unittest.TestCase):
    def probe(self, codec="vorbis", tags=None):
        return {"format": {"duration": "313.3", "format_name": "ogg"},
                "streams": [{"codec_type": "video", "tags": {"title": "cover art"}},
                            {"codec_type": "audio", "codec_name": codec,
                             "sample_rate": "44100", "channels": 2,
                             "tags": tags or {"TITLE": "Lifeline", "ARTIST": "Zeraphym"}}]}

    def test_stream_only_ogg_credits_are_preserved(self):
        row = audio_metadata(self.probe(), Path("Zeraphym-Lifeline.ogg"))
        self.assertEqual((row["title"], row["artist"]), ("Lifeline", "Zeraphym"))
        self.assertEqual(row["raw_tags"]["audio_stream"]["artist"], "Zeraphym")

    def test_filename_version_survives_generic_title_tag(self):
        row = audio_metadata(self.probe("flac", {"TITLE": "My Color"}),
                             Path("DAIKI (AWSM.)-My Color (In the night ver.).flac"))
        self.assertEqual(row["version_hint_from_filename"], "In the night ver.")
        self.assertEqual(row["title"], "My Color")

    def test_wrong_extension_and_conflicting_tags_are_visible(self):
        data = self.probe("aac")
        data["format"].update(format_name="mov,mp4,m4a,3gp,3g2,mj2", tags={"artist": "Uploader"})
        row = audio_metadata(data, Path("music.mp3"))
        self.assertTrue(row["extension_mismatch"])
        self.assertEqual(row["tag_conflicts"]["artist"]["format"], "Uploader")

    def test_old_unknown_cannot_erase_stream_artist_or_actual_duration(self):
        row = {**audio_metadata(self.probe(), Path("music.ogg")), "bytes": 100}
        out = apply_supplied_metadata(row, {"artist": "unknown", "duration_s": 2,
                                           "track_id": "stable_id", "suggested_roles": ["turn"]})
        self.assertEqual(out["artist"], "Zeraphym")
        self.assertEqual(out["duration_s"], 313.3)
        self.assertEqual(out["track_id"], "stable_id")
        self.assertEqual(out["suggested_roles"], ["turn"])


if __name__ == "__main__":
    unittest.main()

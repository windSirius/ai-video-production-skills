# Objective verification environment

## Precise request contract

Translate the user's request into one deliverable that can be disproved. Avoid goals such as `make it better`. Prefer claims such as:

```text
Deliverable: a saved Jianying draft named X with a 1920×1080 picture-only track,
320 preserved captions, zero adjacent duplicate SRT entries, BGM at the verified
house setting, and a non-black final frame at the stated timecode.
```

Every success criterion must reference one check in `verification_plan.json`. If a criterion cannot be checked automatically, label it `human_judgment`, define the exact screenshot or audition range, and keep it separate from objective completion.

## One-assumption batches

Each batch must have:

- one assumption;
- a bounded input set;
- one mutation class;
- one expected observable result;
- one named check;
- a stop-on-failure rule.

Do not combine `generate narration + import + match captions`, `replace picture + restyle captions`, or `change BGM + extend ending` in one batch. These combinations hide which assumption failed.

## Verification-plan checks

Use `scripts/run_objective_checks.py` with only these safe check types:

- `file_exists`: path exists.
- `file_nonempty`: regular file exists and has nonzero size.
- `glob_count`: matching files fall within `min_count` and optional `max_count`.
- `json_fields`: required dotted fields exist and are nonempty.
- `text_contains`: every required string occurs in a text file.
- `tsv_status`: selected TSV rows use accepted status prefixes.
- `tsv_row_count_match`: two TSV files contain the same number of data rows; use it to prove every sampled frame has one Vision result.
- `mission_flow_coverage`: mission-flow ranges cover the declared source duration within a maximum gap and required evidence fields are nonempty.
- `srt_no_adjacent_duplicates`: parsed adjacent subtitle texts are not identical.
- `bgm_sources_within_root`: every `sections[].source` in a BGM manifest is an absolute existing file whose resolved path is inside the declared source root. For this skill, always set `source_root` to the absolute root resolved from `AI_VIDEO_MUSIC_ROOT`, defaulting to `$HOME/Music`.
- `media_probe`: ffprobe metadata satisfies declared duration, resolution, FPS, and stream-count bounds.

Paths are relative to the run directory unless absolute. The checker never executes commands supplied by the plan.

Example:

```json
{
  "checks": [
    {
      "id": "picture_v4_metadata",
      "type": "media_probe",
      "path": "visuals/picture_only_v4.mp4",
      "expect": {
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "duration_min": 623.50,
        "duration_max": 623.57,
        "audio_streams": 0
      }
    }
  ]
}
```

BGM provenance example:

```json
{
  "id": "bgm_sources_within_music",
  "type": "bgm_sources_within_root",
  "path": "audio/bgm_manifest.json",
  "source_root": "/absolute/path/to/Music",
  "required": true
}
```

This check follows symlinks. A symlink located in Music that resolves outside Music fails.

## Gate sequence

1. Run `validate_run.py RUN_DIR --contract-only` before production mutation.
2. Run the named check after every batch.
3. Run the relevant phase checks before moving to the next phase.
4. Set `run_manifest.json` status to `complete` only after all required criteria pass.
5. Run `validate_run.py RUN_DIR` as the final objective gate.

Manual review may judge emotion, timbre, composition, or legibility. Record it as supplementary evidence; never let it override a failed objective check.

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

Create and close batches only through `scripts/harness.py`. A live action uses the harness's before/after state verifier; an offline action may use a plan check only when the check explicitly lists the batch mutation in `observes_mutations` and names its `observed_targets`. Evidence must be created after the action begins. A manifest, ledger, unrelated file count, or agent-authored claim cannot verify a live mutation.

## Verification-plan checks

Use `scripts/run_objective_checks.py` with only these safe check types:

- `file_exists`: path exists.
- `file_nonempty`: regular file exists and has nonzero size.
- `glob_count`: matching files fall within `min_count` and optional `max_count`.
- `json_fields`: required dotted fields exist and are nonempty.
- `json_assert`: required JSON fields satisfy explicit equality, inequality, range, or nonempty assertions. Use this for audit files that must assert `status=PASS`; `file_nonempty` is insufficient.
- `text_contains`: every required string occurs in a text file.
- `tsv_status`: selected TSV rows use accepted status prefixes.
- `tsv_row_count_match`: two TSV files contain the same number of data rows; use it to prove every sampled frame has one Vision result.
- `mission_flow_coverage`: mission-flow ranges cover the declared source duration within a maximum gap and required evidence fields are nonempty.
- `srt_no_adjacent_duplicates`: parsed adjacent subtitle texts are not identical.
- `srt_integrity`: exact cue count, continuous indices, ordered text hash when supplied, lexical coverage against a locked reference, valid ranges, overlap policy, adjacent duplicates, and final-end tolerance all pass.
- `bgm_sources_within_root`: every `sections[].source` in a BGM manifest is an absolute existing file whose resolved path is inside the declared source root. For this skill, set `source_root` to the resolved configured BGM root (`AI_VIDEO_MUSIC_ROOT`, default `$HOME/Music`).
- `media_probe`: ffprobe metadata satisfies declared duration, resolution, FPS, and stream-count bounds.
- `media_frame_contract`: probed media frame count, FPS, duration, and stream policy match the canonical timing contract.
- `live_state_assert`: a captured Jianying state contains required project, timeline, timecode, and track fields and satisfies explicit assertions.
- `image_evidence_set`: opening/middle/ending images are numerous enough, distinct, non-black, and paired with live-state JSON.

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
  "source_root": "/absolute/resolved/configured/music/root",
  "required": true
}
```

This check follows symlinks. A symlink located in Music that resolves outside Music fails.

## Gate sequence

1. Run `validate_run.py RUN_DIR --contract-only` before production mutation.
2. Run `harness.py resume`, prepare and begin exactly one action, then verify or fail that token.
3. Seal relevant phase checks and accepted artifact hashes with `harness.py advance` before moving to the next phase.
4. Do not set `run_manifest.json` status manually. Run `harness.py close`; it performs a two-stage complete/validate commit and restores `in_progress` on failure.

Manual review may judge emotion, timbre, composition, or legibility. Record it as supplementary evidence; never let it override a failed objective check.

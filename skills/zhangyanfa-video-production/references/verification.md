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
- `visual_index_integrity`: independently recount the normalized shot/OCR index, resolve every source ID through the source manifest, verify source and index hashes, and require the declared contact-sheet evidence.
- `visual_match_plan_integrity`: compare the complete match sheet with the canonical SRT; verify order, text, time ranges, distinct stable candidate IDs, evidence/source validity, selected-candidate lineage, retained-pool binding, duration coverage, retry evidence, reuse limits, and current shot/OCR/source-index hashes.
- `visual_selection_review_integrity`: bind a versioned review manifest to the current match sheet and candidate pool; recompute cue/risk coverage, require listed selected evidence plus each risk cue's A/B/C × head/mid/tail frame matrix bound to stable candidate IDs/source ranges, identity-review records, and opening/ending sequence reviews. Use `allow_unresolved=true` only as the prerequisite to a declared repair action; render requires zero unresolved rows.
- `visual_match_repair_integrity`: compare the before and after match sheets and candidate pools, require the actual changed cue set to equal the repair manifest, verify base/result hashes and added-candidate lineage, rebind every after-row selection to an after-pool candidate with the same source ID/file/range, and reject hidden changes.
- `picture_master_integrity`: bind the output media and segment/render manifests to the current match sheet, review manifest, and timing contract; require exact frames/FPS/dimensions, one video stream, zero audio streams, full decode, and strict black-event review.
- `picture_patch_integrity`: verify base/output media hashes, exact declared cue/frame changes, renewed affected-row reviews, and the complete output frame contract. With the mandatory `verify_decoded_segment_hashes=true`, decode both videos, recompute every cue-span digest, and reject self-reported segment hashes, hidden changes, shifted spans, or declared patches whose pixels did not change.

Paths are relative to the run directory unless absolute. The checker never executes commands supplied by the plan.

For `indexed_bulk_reviewed_v1`, use the specialized visual checks as the primary checks for their registered Harness actions. Do not substitute `file_nonempty`, `json_assert`, or an agent-authored audit summary; those types cannot independently prove row coverage, evidence lineage, or hidden match-sheet changes.

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

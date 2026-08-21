# Objective verification environment

## Precise request contract

Translate the user's request into one deliverable that can be disproved. Avoid goals such as `make it better`. Prefer claims such as:

```text
Deliverable: a saved Jianying draft named X with a 2560×1440/60fps picture-only track,
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

- `authority_chain_integrity`: verify one frozen in-project script, actual-final narration and final SRT; their file hashes, lexical/human release states, delivery width/height/fps/frame count, and every required downstream binding. `allow_provisional=true` is never valid for a target-resolution master.
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
- `bgm_sources_within_root`: for `source_mode=local_library`, every `sections[].source` is an absolute existing file whose resolved path is inside the declared source root.
- `media_probe`: ffprobe metadata satisfies declared duration, resolution, FPS, and stream-count bounds.
- `media_frame_contract`: probed media frame count, FPS, duration, and stream policy match the canonical timing contract.
- `live_state_assert`: a captured Jianying state contains required project, timeline, timecode, and track fields and satisfies explicit assertions.
- `image_evidence_set`: opening/middle/ending images are numerous enough, distinct, non-black, and paired with live-state JSON.
- `source_proxy_manifest_integrity`: for v2, require local non-iCloud proxies keyed by source SHA/profile hash, bind every normalized proxy to its source SHA-256 and the request-contract profile, and verify proxy SHA-256 plus the required default `1080p_cfr30_h264_gop30_yuv420p_bt709_v1` media profile (1920×1080/CFR30/H.264/yuv420p/BT.709/GOP≤30) unless the contract explicitly freezes another profile.
- `visual_index_integrity`: independently recount the normalized shot/OCR index, resolve every source ID through the source manifest, verify source and index hashes, and require the declared contact-sheet evidence.
- `visual_match_plan_integrity`: compare the complete match sheet with the canonical SRT; verify order, text, time ranges, distinct stable candidate IDs, evidence/source validity, selected-candidate lineage, retained-pool binding, duration coverage, retry evidence, reuse limits, and current shot/OCR/source-index hashes. Under v2 require 4–8 second semantic visual units on the canonical SRT cue clock, 8–12 candidates for normal units, a risk-pool cap of 32, and at least three ranked A/B/C choices for each risk unit.
- `visual_selection_review_integrity`: bind a versioned review manifest to the current match sheet and candidate pool. Existing v1 runs recompute cue/risk-row coverage. V2 uses `review_granularity=semantic_visual_units_v2`: require selected evidence exactly once per visual unit, a separate exact cue/frame-to-unit mapping, and each derived risk unit's A/B/C × head/mid/tail matrix bound to stable candidate IDs, source ranges, timestamps, and evidence hashes, plus identity and opening/ending sequence reviews. Use `allow_unresolved=true` only as the prerequisite to a declared repair action; render requires zero unresolved units.
- `visual_match_repair_integrity`: compare the before and after match sheets and candidate pools, require the actual changed cue set to equal the repair manifest, verify base/result hashes and added-candidate lineage, rebind every after-row selection to an after-pool candidate with the same source ID/file/range, and reject hidden changes.
- `hyperframes_stress_test_integrity`: under v2, bind one real 30–60 second HyperFrames sample to the passing source-proxy manifest, current match sheet, HyperFrames composition, and integer-frame render plan; cover every declared proxy-profile/production-asset class plus shortest-unit, hard-cut, and media-element-activation risks, adding card/overlay coverage only when those classes are used. Require concrete range/frame evidence, full decode, black-frame, activation-frame, and transition-seam checks.
- `aesthetic_proxy_approval_integrity`: under workflow v3, bind a full-length HyperFrames 1280×720 proxy with frozen narration and its opening/middle/ending navigation reviews to authority, A/B static reviews, semantic/reuse QA, passing stress, match sheet, composition and render plan; require an artifact-bound user verdict. Legacy v2 retains its excerpt-proxy contract.
- `picture_master_integrity`: bind the output media and segment/render manifests to the current match sheet, review manifest, and timing contract; require exact frames/FPS/dimensions, one video stream, zero audio streams, full decode, and strict black-event review. Under v2 also bind the aesthetic-proxy approval, require `render_unit_mode=semantic_visual_units_v2`, check transition seams, and accept only the single target-resolution master authorized by the Harness.
- `picture_patch_integrity`: verify base/output lineage, exact declared cue/frame changes, renewed affected-row reviews, and the complete output frame contract. Under v2 require `patch_verification_mode=chunk_scoped_v2`, unchanged chunk file SHA equality, decoded-frame verification for changed chunks, adjacent seam checks, and one assembled-output full decode/black/seam pass; do not repeat a full decoded-frame hash pass over the accepted base. Existing `hyperframes_required_v1` runs retain segment manifests plus mandatory `verify_decoded_segment_hashes=true` over both videos.

Paths are relative to the run directory unless absolute. The checker never executes commands supplied by the plan.

Harness may cache a passing expensive check only when its full check configuration, checker-script SHA, and dependency SHA lineage are unchanged. Subsequent prerequisite checks first compare size, mtime, device, and inode; stable fingerprints reuse the prior full-decode/black/seam result without rereading the media, while drift invalidates the cache and reruns the check. Never treat an agent-authored PASS summary as this cache.

For `source_mode=generated_score`, do not run `bgm_sources_within_root`. Require `json_assert` checks for the generation manifest's model/service, prompt hash, source file, source SHA, duration, status and chapter coverage, plus the same lyric/intelligibility review used for local music. The manifest mode is mutually exclusive; never make a generated source pass by copying it into the Music directory.

For `indexed_bulk_reviewed_v1`, use the specialized visual checks as the primary checks for their registered Harness actions. For every new `hyperframes_proxy_gated_v2` run this includes, in order, `source_proxy_manifest_integrity`, the existing index/plan/review/repair checks, `hyperframes_stress_test_integrity`, `aesthetic_proxy_approval_integrity`, `picture_master_integrity` with `render_unit_mode=semantic_visual_units_v2`, and `picture_patch_integrity` with `patch_verification_mode=chunk_scoped_v2`. Do not substitute `file_nonempty`, `json_assert`, or an agent-authored audit summary; those types cannot independently prove profile binding, row coverage, evidence lineage, render approval, or hidden changes. Existing v1 runs continue to use the profile and check flags already frozen in their plans.

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
  "id": "bgm_provenance_current",
  "type": "bgm_sources_within_root",
  "path": "audio/bgm_manifest.json",
  "source_root": "$HOME/Music",
  "required": true
}
```

This check follows symlinks. A symlink located in Music that resolves outside Music fails.

For an explicitly authorized generated score, freeze `bgm_policy.source_mode=generated_score` and use the same check ID with `type=generated_bgm_manifest_integrity`. The BGM manifest must bind a passing generation manifest, provider/model, prompt or prompt hash, exact source path, duration and SHA-256. Do not mix local-library and generated-score provenance inside one frozen run.

## Manual visual gates that objective checks cannot replace

- Obtain the user's explicit verdict on the actual final narration pronunciation/full-audio audition before formal subtitle, A/B/C or BGM release. A producer-authored or machine-authored PASS is not this verdict.
- Review every B/C asset in the pre-render review bundle, including original source and proposed treatment.
- Review every HyperFrames boundary contact-sheet page at original detail and run the global exact-range reuse, significant-overlap, adjacent-source, source-concentration and black-frame audit.
- Continuously play the entire workflow-v3 720p A/A+B proxy at 1× before target render. Opening, representative middle and ending checks are additional focused reviews, not a replacement for full playback.
- Compare cover characters and official models directly against frozen sources at both full size and thumbnail size.
- Record native/source transitions that trigger blackdetect separately from renderer-created empty frames.

## Gate sequence

1. Run `validate_run.py RUN_DIR --contract-only` before production mutation and freeze delivery width/height/fps.
2. Freeze `authority_bundle.json`, run `authority_chain_integrity` without provisional mode, and stop if script/audio/SRT, lexical/audition states or the target frame contract disagree.
3. Run `harness.py resume`, prepare and begin exactly one action, then verify or fail that token. For workflow v3 do not reorder or skip: authority/script-audio approval → local source-SHA/profile-hash proxy normalization → proxy-bound index → chapter source coverage and 4–8 second semantic-unit global match/reuse review on the sole final SRT → A/B static bundle approval → real 30–60 second HyperFrames stress test → full-length 720p A/A+B proxy with frozen narration and artifact-bound user approval → one frozen-resolution target master → one full master QA → chunk-scoped patch when repair is required.
4. Seal relevant phase checks and accepted artifact hashes with `harness.py advance` before moving to the next phase.
5. Do not set `run_manifest.json` status manually. Run `harness.py close`; it performs a two-stage complete/validate commit and restores `in_progress` on failure.

Manual review may judge emotion, timbre, composition, semantic matching or legibility. Record it as an independent required status; never let it override a failed objective check, and never let an objective check impersonate human acceptance.

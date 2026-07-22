# Production harness

Use `scripts/harness.py` as the sole authority for production order after the request contract exists. The harness is a fail-closed transaction manager: it authorizes one bounded action, captures the last-known-good state, and accepts the action only when fresh evidence proves the intended delta.

Do not edit `harness/state.json`, `harness/events.jsonl`, or harness-managed `H####` ledger rows by hand. Do not perform a live mutation before `begin`, and do not repeat a mutation after a crash or lost tool response.

## Required command loop

Run this loop for every production mutation:

1. `python3 scripts/harness.py resume RUN_DIR`
2. Obey the single `next_action` object. Ignore any remembered plan that conflicts with it.
3. If it says `prepare`, prepare exactly one registered action with a pre-observation and evidence. Preparation does not authorize a mutation.
4. Run the returned `begin` command. Its token authorizes only the named recipe and mutation class.
5. Perform that one mutation.
6. Capture a fresh post-observation and evidence, then call `verify`; or call `fail` immediately.
7. Resume again. Never choose a second action while one is prepared, in progress, awaiting repair, or blocked.

If `resume` returns `inspect_pending_action`, inspect the live project and verify or fail the existing token. Do not click the action again: the previous process may have completed the mutation before losing its response.

If it returns any `recover_*` action, run `python3 scripts/harness.py recover RUN_DIR`. Recovery reconciles the write-ahead action journal, ledger, and state; it never repeats a production mutation.

## Live observation schema

Every live pre-state, post-state, and rollback observation is a JSON object containing at least:

```json
{
  "app_bundle_version": "Jianying macOS bundle version",
  "window_signature": "stable geometry/layout signature",
  "ui_recipe_profile": "jianying-macos-observed-v1",
  "ui_recipe_calibrated": true,
  "draft_name": "列车组团魂_传承向_v4",
  "timeline_name": "时间线 01",
  "timeline_count": 1,
  "project_timecode": "00:10:16:19",
  "caption_track_count": 1,
  "caption_count": 331,
  "narration_track_count": 1,
  "narration_clip_count": 20,
  "picture_track_count": 1,
  "picture_clip_count": 1,
  "bgm_track_count": 1,
  "bgm_clip_count": 1,
  "protected_tracks_locked": true,
  "authoritative_timeline": true
}
```

Add action-specific observable fields such as `visible_picture_filename` or `reopened`. Obtain counts and names from fresh Jianying UI state, exported SRT, or an accessibility query. `window_signature` describes stable window geometry and panel layout, not changing video pixels. Recalibrate the registered recipe when bundle version or layout signature changes, and record that preflight before setting `ui_recipe_calibrated=true`. Do not copy expected values into the observation without measuring them.

Evidence files must exist, be nonempty, and, for post-state verification, be newer than `ACTION_BEGUN`. A narration file count, manifest, or BGM provenance report cannot prove a live caption, picture, or BGM mutation.

## Registered actions and recipes

The `ACTION_REGISTRY` in `scripts/harness.py` is the machine-readable source of truth. Unknown actions, recipes, or check bindings fail closed.

| Action key | Fixed recipe | Critical rule |
|---|---|---|
| `offline_artifact` | `offline.objective-check.v1` | Use a verification-plan check that explicitly declares the matching mutation and observed targets; the checked output must be newer than `ACTION_BEGUN`. |
| `adopt_verified_artifact` | `offline.adopt-objective-check.v1` | Read-only adoption of an existing artifact. Use a `none.adopt` check and strong hash; never claim the artifact was generated in this action. |
| `rename_unicode` | `jianying.ax-or-clipboard-unicode.v1` | Use a verified accessibility value setter or clipboard route for Chinese; do not retry raw keystroke guesses. |
| `append_narration_clip` | `jianying.media-identity-quick-add.v1` | Verify basename, probed duration, and SHA before selecting the media card; select the identified card, click its visible `+`, go to End, and prove clip count plus exact cumulative end. Never infer identity from left/right card position. |
| `append_narration_loop` | `jianying.media-identity-quick-add-loop.v1` | Available only after two consecutive single-item successes. Use `narration_loop_items_per_batch`, one manifest with every basename and expected cumulative end, and stop/undo at the first mismatch. |
| `caption_replace_atomic` | `jianying.caption-export-remove-import-export.v1` | Export raw backup → lock protected lanes → remove raw track → prove caption-track count 0 → import semantic SRT → export canonical SRT → run the bound `srt_integrity` objective check. Never allow raw and semantic tracks to coexist. Do not style before this passes. |
| `apply_picture_master` | `jianying.equal-duration-replace-clip.v1` | Verify the stable regular-file media identity and timing contract, use `替换片段`, and prove unchanged duration and protected lanes plus the visible new filename. Never use the timeline `+` control to add a track. |
| `apply_bgm_master` | `jianying.music-provenance-quick-add.v1` | Require canonical `audio/bgm_manifest.json` and a passing resolved-path provenance check before import. |
| `align_fullspan_tail` | `jianying.single-split-delete-tail.v1` | Use the canonical timing contract. Split once at the target frame and delete only the selected tail. This action can pass at most once in a run. |
| `cleanup_extra_timelines` | `jianying.delete-nonauthoritative-timeline.v1` | Delete only a verified non-authoritative timeline and prove the authoritative timeline remains with `timeline_count=1`. |
| `caption_canonical_export` | `jianying.caption-only-export.v1` | Confirm video/audio export is off and captions are on; bind `--objective-check-id` to an `srt_integrity` check for the fresh exported file. |
| `live_qa_capture` | `jianying.open-middle-final-evidence.v1` | Capture distinct non-black opening, representative middle, and final-spoken-line frames with companion live-state JSON; bind an `image_evidence_set` objective check. |
| `save_reopen_verify` | `jianying.save-home-reopen-verify.v1` | Save, return home or close the draft, reopen it, and remeasure project/timeline names, end time, counts, locks, and visible media. |

## Media identity rule

For every insert or replacement, identify the source by absolute resolved path, basename, byte size, SHA-256, and positive `ffprobe` duration. Do not select a media-bin item only because it is newest, leftmost, rightmost, highlighted, or near remembered coordinates.

If the inserted item or cumulative time is wrong, undo once and prove the pre-state was restored. Report `wrong_media`; do not try a different card position in the authoritative timeline.

## Caption transaction rule

The transaction log supplied to `verify --transaction-log` must contain:

```json
{
  "events": [
    "raw_backup_exported",
    "raw_track_removed",
    "semantic_imported",
    "canonical_exported"
  ],
  "caption_track_counts": [1, 0, 1],
  "exact_overlap_count": 0,
  "final_caption_count": 331,
  "raw_backup": "/absolute/path/raw_backup.srt",
  "canonical_export": "/absolute/path/canonical.srt"
}
```

Use the `srt_integrity` objective check before styling or picture matching. Require exact expected count, continuous indices, ordered-text SHA when known, lexical equality with the locked narration text, valid ordered time ranges, no forbidden overlap, no adjacent exact duplicate, and final-end tolerance. A nonempty audit JSON or “zero adjacent duplicate” check alone is not sufficient.

## One frame clock

Freeze one `timing_contract.json` before full-span picture or BGM work:

```json
{
  "fps": 60,
  "target_frame_count": 36979,
  "target_timecode": "00:10:16:19",
  "target_seconds": 616.3166666667
}
```

Use the actual run values. Narration end, picture master, BGM master, and live timeline must all derive from this contract. Do not independently trim narration, picture, and BGM by eye. A deviation greater than one frame requires rollback and regeneration; a one-frame import rounding error may use the single tail-alignment action once.

## Failure budget

- One logical batch keeps one ledger row across its repair attempt. Do not append a new speculative batch and do not rewrite failures later as `waived:superseded`.
- A waiver exists only for an action prepared with `--optional`, before `begin`, and after `skip --authorized-by user --reason "..."`. A success-criterion action cannot be optional.
- On the first recoverable failure, undo and prove the complete pre-state. The harness permits one retry of the same registered recipe.
- The second identical failure fingerprint blocks the phase.
- Three failures in one phase or six in the run block the harness.
- Protected-state change, inconclusive mutation state, contract/plan drift, BGM provenance failure, or an unrecoverable action blocks immediately.
- A block requires an explicit user decision. `unblock --authorized-by user` reopens the same logical action and does not erase history; a live action also requires a fresh observation/evidence proving the complete pre-state was restored.

Do not respond to failure by inventing a drag direction, hotspot, coordinate, keyboard shortcut, menu sequence, or new mutation class. Calibrate an unknown UI route only in an isolated scratch timeline, at most twice, and delete the scratch timeline with verified count restoration before touching the authoritative timeline. Record a proven route as a reviewed registry change before production use.

## Fast resume and phase seals

Use `advance` only after all named phase-gate checks pass. Supply every accepted phase artifact with `--artifact`; the harness records strong hashes in `harness/phase_seals/`.

On resume, reuse a sealed phase when its stat and hash remain valid. Do not rescan the workspace, regenerate accepted outputs, or rerun GUI setup. Contract, verification-plan, or sealed-artifact drift blocks the next mutation and requires deliberate revalidation.

When the user explicitly changes scope or acceptance criteria, update the contract/plan while no action is open, then run `harness.py rebind RUN_DIR --authorized-by user --reason "..."`. Rebinding records the old fingerprints, invalidates every phase seal, and clears the final-action cursor so affected gates and final persistence must be proved again. Never edit the saved fingerprints directly.

Perform offline generation, indexing, audits, and renders before opening one concentrated live-assembly window. Avoid alternating between asset generation and Jianying UI work.

## Final close order

The final four verified actions must be, in order and with no later mutation:

1. `cleanup_extra_timelines`
2. `caption_canonical_export`
3. `live_qa_capture`
4. `save_reopen_verify`

Then run `python3 scripts/harness.py close RUN_DIR`. Close runs the full objective plan, writes the canonical `qa/verification_results.json`, temporarily marks the manifest complete, invokes `validate_run.py`, and commits `complete` only if all checks pass. On failure it restores `in_progress` and blocks with evidence.

Final export remains outside the harness action registry while `export_authorized=false`. Do not add an export action merely to finish a run.

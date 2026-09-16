# Production harness

> **历史 Harness 参考。** 本文适用于既有 `run_manifest.json` 工程；其中 workflow v2/v2.2 是旧流程编号，不等于当前 `production_contract_version=2`。新项目使用 [十三阶段总控](../SKILL.md) 和 [当前提交契约](submission-contracts-v2.md)。保留本文用于旧工程核验，迁移按 [旧项目迁移](legacy-migration.md) 执行。

Use `scripts/harness.py` as the sole authority for production order after the request contract exists. The harness is a fail-closed transaction manager: it authorizes one bounded action, captures the last-known-good state, and accepts the action only when fresh evidence proves the intended delta.

For every newly initialized video-rendering run, require `workflow_profiles.video_rendering=hyperframes_proxy_gated_v2`. Existing runs already frozen under `hyperframes_required_v1` retain their v1 action and verification wording; do not relabel or silently migrate their accepted artifacts. The profile frozen in the request contract decides which rules below apply.

Do not edit `harness/state.json`, `harness/events.jsonl`, or harness-managed `H####` ledger rows by hand. Do not perform a live mutation before `begin`, and do not repeat a mutation after a crash or lost tool response.

## Permanent forbidden UI target

Treat controls whose accessible name, title, identifier, description, or visible text contains 「试试剪映助手」 or 「剪映助手」 as permanently forbidden. This applies to every phase, action, retry, recovery, QA step, and child Jianying Skill.

- Never click, open, dismiss, focus, test, confirm, drag, type into, or otherwise activate the assistant.
- Never click it to clear an overlay. Seeing it is not itself a failure; targeting or activating it is.
- If it overlaps a required control, use a previously verified accessibility, menu, keyboard, scrolling, or layout route whose target is not the assistant. If no such route exists, close the action with `forbidden_ui_route_unavailable`; do not improvise through its bounds.
- No harness token, recipe, user-interface guess, or later user unblock can waive this exclusion.

Every live `prepare` requires `--ui-route-preflight PATH`. The schema-v1 JSON is valid for at most ten minutes and binds the route to the exact action key, registered recipe, required-control name from `ACTION_REGISTRY`, window signature, UI recipe profile, pre-observation SHA-256, and all pre-evidence SHA-256 values. It must use that action's registered `ui_route_id`, and its observed targets must contain one of the action's registered semantic anchor terms. Actions with `ui_required_step_checkpoints` must match every checkpoint in order and with the registered action type; for example, a required local-subtitle-card `drag` cannot be replaced by a click. A recipe or route name is not evidence: if current Jianying does not expose the required semantic control, stop and calibrate it from read-only AX/hit-test evidence before production.

Every planned target requires a strong semantic identity, a nonempty accessibility ancestor path, and the allowed `window_signature` for that individual step. Multi-screen recipes such as save → home → reopen must declare their layout transition step by step; they are not forced to reuse the initial editor signature. Record currently visible Jianying Assistant regions with label and bounds. Role-only, generic, unrelated, or assistant-descended targets are rejected. Keep `"forbidden_targets_interacted": []`. A blocked, malformed, stale, or weak route persistently blocks the harness and receives no mutation token.

Do not hand-author the interaction trace. After `begin`, capture a hit-test snapshot no more than thirty seconds before each intended UI operation. Capture the hit-test and call `authorize-ui-step` in one execution envelope so model/tool latency cannot consume the freshness window. It must repeat the planned step with its actual semantic target, ancestor chain, bounds, hit point, current window signature, and all currently visible forbidden regions. Run `authorize-ui-step`; only a successful one-use authorization permits that exact next action. A stale hit-test authorizes nothing and leaves the action in progress so it can be recaptured without a user unblock. Immediately after the action, run `complete-ui-step` with fresh evidence. If a response is lost between authorization and completion, inspect the UI and do not repeat the action.

Every live `verify` or `fail` requires the canonical harness-managed trace path from `harness/ui_traces/`. The trace source is `harness_controlled_ui_executor` and it binds to the exact batch, token, action, recipe, preflight hash, pre-observation hash, window signature, UI profile, route ID, one-use authorizations, hit-test snapshots, and fresh step evidence. Successful verification requires an exact step-for-step match to the pre-approved route; failure may seal only its exact completed prefix. Unknown targets, incomplete coverage, extra or changed steps, an outstanding authorization, a hand-authored trace, or a normalized match to a forbidden label blocks the action. Unicode width, whitespace, punctuation, nested metadata, ancestor labels, and prefix variations do not bypass matching.

Minimal preflight:

```json
{
  "schema_version": 1,
  "captured_at": "2026-07-23T08:00:00+12:00",
  "action_key": "caption_canonical_export",
  "recipe_id": "jianying.caption-only-export.v2",
  "required_control": "仅导出字幕",
  "window_signature": "1920x1080-main-v1",
  "ui_recipe_profile": "jianying-macos-observed-v1",
  "pre_observation_sha256": "<sha256 of PRE_STATE.json>",
  "evidence_sha256": ["<sha256 of preflight screenshot or AX snapshot>"],
  "status": "available",
  "selected_route": {
    "route_id": "caption-export-accessibility-v2",
    "method": "accessibility",
    "steps": [
      {
        "sequence": 1,
        "action": "press",
        "window_signature": "1920x1080-main-v1",
        "target": {
          "role": "AXButton",
          "name": "导出",
          "identifier": "export-open",
          "visible_text": "导出",
          "ancestor_path": [
            {
              "role": "AXWindow",
              "name": "剪映专业版主窗口",
              "identifier": "jianying-main-window"
            }
          ]
        }
      },
      {
        "sequence": 2,
        "action": "press",
        "window_signature": "jianying-export-dialog-v1",
        "target": {
          "role": "AXButton",
          "name": "字幕导出",
          "identifier": "caption-export",
          "visible_text": "字幕导出",
          "ancestor_path": [
            {
              "role": "AXWindow",
              "name": "导出",
              "identifier": "jianying-export-window"
            }
          ]
        }
      },
      {
        "sequence": 3,
        "action": "confirm",
        "window_signature": "jianying-export-dialog-v1",
        "target": {
          "role": "AXButton",
          "name": "ExportOkBtn",
          "identifier": "caption-export-confirm",
          "visible_text": "导出",
          "ancestor_path": [
            {
              "role": "AXWindow",
              "name": "导出",
              "identifier": "jianying-export-window"
            }
          ]
        }
      }
    ]
  },
  "visible_forbidden_regions": [
    {
      "label": "试试剪映助手",
      "bounds": {"x": 1560, "y": 900, "width": 280, "height": 80}
    }
  ],
  "forbidden_targets_interacted": []
}
```

Minimal fresh hit-test snapshot submitted before the click:

```json
{
  "schema_version": 1,
  "observed_at": "2026-07-23T08:00:06+12:00",
  "window_signature": "jianying-export-dialog-v1",
  "step": {
    "sequence": 2,
    "action": "press",
    "window_signature": "jianying-export-dialog-v1",
    "target": {
      "role": "AXButton",
      "name": "字幕导出",
      "identifier": "caption-export",
      "visible_text": "字幕导出",
      "ancestor_path": [
        {
          "role": "AXWindow",
          "name": "导出",
          "identifier": "jianying-export-window"
        }
      ],
      "bounds": {"x": 1260, "y": 780, "width": 150, "height": 44},
      "hit_test_point": {"x": 1335, "y": 802}
    }
  },
  "visible_forbidden_regions": [
    {
      "label": "试试剪映助手",
      "bounds": {"x": 1560, "y": 900, "width": 280, "height": 80}
    }
  ]
}
```

The identifiers and coordinates above illustrate the schema only; they are not reusable evidence. The preflight freezes semantic targets, ancestor identity, order, and each step's allowed layout; the just-in-time hit-test supplies current geometry. Measure the target, ancestor chain, bounds, hit point, and forbidden regions from the live Jianying window before each step. If they do not match the registered route contract, stop.

If a token-bound preflight changes or disappears before `begin`, the open action is persistently blocked. `unblock` cannot reuse the old route: a live action requires restored-state evidence plus a fresh `--ui-route-preflight`. Harness-state schema v1 runs migrate to harness-state schema v2 automatically; any open legacy live action is blocked until that same restoration-and-fresh-route procedure succeeds.

`navigate_caption_ui` deliberately permits a measured window-signature change while all project fields remain identical. A legacy or already-open navigation action that was blocked solely because its frozen expectation required the window signature to stay the same may be closed with `resolve-caption-navigation --authorized-by user` only after its exact managed route is complete and a fresh post-observation proves the requested `visible_panel` plus unchanged timeline counts and protected lanes.

## Required command loop

Run this loop for every production mutation:

1. `python3 scripts/harness.py resume RUN_DIR`
2. Obey the single `next_action` object. Ignore any remembered plan that conflicts with it.
3. If it says `prepare`, prepare exactly one registered action with a pre-observation, evidence, and a non-assistant UI route preflight. Preparation does not authorize a mutation.
4. Run the returned `begin` command. Its token authorizes only the named recipe and mutation class.
5. For each planned UI step: capture a fresh hit-test JSON and run `authorize-ui-step RUN_DIR --token TOKEN --hit-test HIT_TEST.json` in one execution envelope; perform exactly the returned one step; then run `complete-ui-step RUN_DIR --token TOKEN --authorization UI_STEP_TOKEN --evidence FRESH_STEP_EVIDENCE`. Never batch multiple clicks under one authorization. If authorization rejects only `ui_evidence_stale`, recapture immediately; do not request a user decision because no UI step was authorized.
6. Capture a fresh post-observation and action evidence. Call `verify` with the canonical trace path emitted under `harness/ui_traces/`; or call `fail`, which may seal only a completed prefix of that same managed trace.
7. Resume again. Never choose a second action while one is prepared, in progress, awaiting repair, or blocked.

If `resume` returns `inspect_authorized_ui_step`, inspect the live project before doing anything else. Do not click that step again: the previous process may have completed it before losing its response. If it returns `inspect_pending_action`, inspect the live project and verify or fail the existing token without repeating the mutation.

If it returns any `recover_*` action, run `python3 scripts/harness.py recover RUN_DIR`. Recovery reconciles the write-ahead action journal, ledger, and state; it never repeats a production mutation.

If the user manually advances Jianying, stop the active recipe. Capture the current live observation and evidence, obtain explicit user authority, and run the following from either a ready run with no open action or an untouched open live action whose managed trace has no pending authorization and zero completed authorizations:

```bash
python3 scripts/harness.py adopt-live-baseline RUN_DIR \
  --authorized-by user \
  --reason "user manually advanced the live draft" \
  --observation CURRENT_STATE.json \
  --evidence CURRENT_SCREENSHOT.png
```

With an untouched open action, this closes it as `cancelled_no_mutation`; with a ready run, it records a `B####` baseline without adding a production ledger row. Both routes create a user-authored baseline checkpoint and make no claim about how the user's changes were produced. It is forbidden after any agent UI step was authorized or completed; those cases require inspection plus normal verify/fail recovery.

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

Add action-specific observable fields such as `visible_picture_filename`, `reopened`, or `narration_end_timecode`. Measure `narration_end_timecode` from the narration lane; do not reuse `project_timecode` after picture or BGM media exists because another lane may be longer. Obtain counts and names from fresh Jianying UI state, exported SRT, or an accessibility query. A user-authored baseline may declare an unmeasurable count as `null` only when the field is listed in `unresolved_measurements`. The registered `caption_backup_export` action alone may begin with `caption_count` unresolved; its post-observation must late-bind a measured integer from the exported SRT. `window_signature` describes stable window geometry and panel layout, not changing video pixels. Recalibrate the registered recipe when bundle version or layout signature changes, and record that preflight before setting `ui_recipe_calibrated=true`. Do not copy expected values into the observation without measuring them.

Evidence files must exist, be nonempty, and, for post-state verification, be newer than `ACTION_BEGUN`. A narration file count, manifest, or BGM provenance report cannot prove a live caption, picture, or BGM mutation.

## Registered actions and recipes

The `ACTION_REGISTRY` in `scripts/harness.py` is the machine-readable source of truth. Unknown actions, recipes, or check bindings fail closed.

All live registry actions inherit the permanent Jianying Assistant exclusion. It does not need to be repeated in each recipe row and cannot be overridden by a recipe.

| Action key | Fixed recipe | Critical rule |
|---|---|---|
| `offline_artifact` | `offline.objective-check.v1` | Use a verification-plan check that explicitly declares the matching mutation and observed targets; the checked output must be newer than `ACTION_BEGUN`. Under `indexed_bulk_reviewed_v1`, it cannot target anything in `visuals/` or any recognized visual-workflow artifact name. |
| `adopt_verified_artifact` | `offline.adopt-objective-check.v1` | Read-only adoption of an existing artifact. Use a `none.adopt` check and strong hash; never claim the artifact was generated in this action. |
| `normalize_source_proxies` | `offline.source-proxy-cache.v2` | Under `hyperframes_proxy_gated_v2`, normalize all source media into the contract profile in the local non-iCloud cache, key proxies by source SHA/profile hash, bind source and proxy SHA-256 values plus the contract profile in one manifest, and verify it only with `source_proxy_manifest_integrity` under `source_proxy_manifests_per_batch=1`. The default `1080p_cfr30_h264_gop30_yuv420p_bt709_v1` profile is 1920×1080, CFR 30, H.264, yuv420p, BT.709, GOP no greater than 30. |
| `build_visual_index` | `offline.indexed-vision-ocr-corpus.v1` | Build one normalized, source-identified Vision/OCR corpus under `visual_indexes_per_batch=1`; bind only to `visual_index_integrity`. Under v2 the index must resolve through the passing source-proxy manifest, never through mutable iCloud originals. |
| `build_match_plan` | `offline.indexed-three-candidate-plan.v1` | Build one complete provisional match generation under `match_plans_per_batch=1`; every row remains `machine_proposed` and binds only to `visual_match_plan_integrity`. Under v2, use 4–8 second semantic visual units on the canonical SRT cue clock, retain 8–12 candidates for a normal unit, cap risk pools at 32, and expose at least three ranked A/B/C choices for risk review. Existing v1 runs retain the preferred-32/fewer-with-expansion-evidence policy. |
| `review_match_plan` | `offline.selected-and-risk-contact-review.v1` | Produce one complete review bundle under `match_review_bundles_per_batch=1` and bind only to `visual_selection_review_integrity`. V2 requires `review_granularity=semantic_visual_units_v2`: selected evidence covers every visual unit exactly once, cue/frame mapping is audited separately, and A/B/C head/middle/tail plus identity evidence covers each derived risk unit. Existing v1 runs retain cue-row review granularity. |
| `repair_match_plan` | `offline.match-plan-incremental-repair.v1` | Apply one base-hash-bound repair set under `match_repair_sets_per_batch=1`; declare exact changed cues, preserve machine history, rebind every repaired selection to the after-candidate-pool, and bind only to `visual_match_repair_integrity`. V2 repairs retain the same 4–8 second semantic-unit and 8–12/32 pool limits. |
| `run_hyperframes_stress_test` | `offline.hyperframes-real-stress-test.v2` | Under v2, render one real 30–60 second HyperFrames stress sample under `hyperframes_stress_tests_per_batch=1`, covering every declared proxy-profile/production-asset class and the required shortest-unit, hard-cut, and media-element-activation risks; require card/overlay coverage only when used. Bind the current composition/render-plan hashes and verify concrete activation/boundary evidence with `hyperframes_stress_test_integrity`; full decode, black-frame, activation-frame, and transition-seam checks are mandatory. |
| `approve_aesthetic_proxy` | `offline.hyperframes-720p-aesthetic-proxy.v2` | Under v2, render and review one HyperFrames 1280×720 opening/middle/ending proxy under `aesthetic_proxy_approvals_per_batch=1`. Bind only to `aesthetic_proxy_approval_integrity`, and freeze opening/ending structure, UID, framing, geometry, typography, motion, and pace before the target-resolution render. |
| `render_picture_master` | `offline.equal-duration-picture-master.v1` | Render one current-generation, reviewed, exact-frame, video-only master under `picture_masters_per_batch=1`; bind only to `picture_master_integrity`. V2 additionally requires the passing aesthetic approval, `render_unit_mode=semantic_visual_units_v2`, full decode, and transition-seam QA, and permits only one successful target-resolution master per run. |
| `patch_picture_master` | `offline.picture-master-incremental-patch.v1` | Patch one declared set of cues/frame ranges under `picture_patches_per_batch=1` and bind only to `picture_patch_integrity`. V2 requires `patch_verification_mode=chunk_scoped_v2`: unchanged chunk file SHA equality, decoded-frame verification of changed chunks, adjacent-boundary seam checks, and one assembled-output decode/black/seam pass. It must not repeat a full decoded-frame hash comparison of the accepted base. Existing `hyperframes_required_v1` runs retain mandatory segment manifests and `verify_decoded_segment_hashes=true`. |
| `rename_unicode` | `jianying.ax-or-clipboard-unicode.v1` | Use a verified accessibility value setter or clipboard route for Chinese; do not retry raw keystroke guesses. |
| `append_narration_clip` | `jianying.media-identity-quick-add.v1` | Verify basename, probed duration, and SHA before selecting the media card; select the identified card, click its visible `+`, go to End, and prove clip count plus exact cumulative end. The first clip may create the narration track (`0 → 1`); later clips must keep it at one. Never infer identity from left/right card position. |
| `append_narration_loop` | `jianying.media-identity-quick-add-loop.v1` | Available only after two consecutive single-item successes. Use `narration_loop_items_per_batch`, one manifest with every basename and expected cumulative end, and stop/undo at the first mismatch. |
| `caption_replace_atomic` | `jianying.caption-text-local-import-drag-verify-remove-export.v3` | Require the ordered route `文本 → 新建文本 → 导入本地字幕 → 系统导入 → 拖动本地字幕素材卡 → 删除旧字幕轨 → 仅字幕再导出`. Verify that import first leaves track count at one while creating the named local-subtitle card, dragging changes tracks `1 → 2`, and old-track removal changes them `2 → 1`. Run the bound `srt_integrity` check with the exact terminal-punctuation policy. |
| `caption_backup_export` | `jianying.caption-only-export-backup.v2` | In the top-right export dialog disable video/audio, enable `字幕导出`, select `SRT` and `Unicode / UTF-8`, then export the untouched live subtitle track to `captions/captions_matched_raw.srt`. This action may late-bind an initially unresolved `caption_count`; all protected lanes and timeline duration must remain unchanged. |
| `navigate_caption_ui` | `jianying.caption-ui-navigation.v1` | Navigate or close one verified non-destructive caption-related panel while proving every timeline count and protected lane remains unchanged. Bind an exact `visible_panel` expectation; do not combine it with caption mutation. |
| `apply_picture_master` | `jianying.equal-duration-replace-clip.v1` | Verify the stable regular-file media identity and timing contract, use `替换片段`, and prove unchanged duration and protected lanes plus the visible new filename. Never use the timeline `+` control to add a track. |
| `apply_bgm_master` | `jianying.music-provenance-quick-add.v1` | Require canonical `audio/bgm_manifest.json` and a passing resolved-path provenance check before import. The first BGM clip may create its track (`0 → 1`). |
| `align_fullspan_tail` | `jianying.single-split-delete-tail.v1` | Use the canonical timing contract. Split once at the target frame and delete only the selected tail. This action can pass at most once in a run. |
| `cleanup_extra_timelines` | `jianying.delete-nonauthoritative-timeline.v1` | Delete only a verified non-authoritative timeline and prove the authoritative timeline remains with `timeline_count=1`. |
| `caption_canonical_export` | `jianying.caption-only-export.v2` | Confirm video/audio export is off, captions are on, format is `SRT`, and encoding is `Unicode / UTF-8`; bind `--objective-check-id` to an `srt_integrity` check for the fresh exported file with the exact terminal-punctuation policy. |
| `live_qa_capture` | `jianying.open-middle-final-evidence.v1` | Capture distinct non-black opening, representative middle, and final-spoken-line frames with companion live-state JSON; bind an `image_evidence_set` objective check. |
| `save_reopen_verify` | `jianying.save-home-reopen-verify.v1` | Save, return home or close the draft, reopen it, and remeasure project/timeline names, end time, counts, locks, and visible media. |

## Indexed bulk visual workflow

For a new v2 full picture rebuild, the Harness unit is one complete stage transaction, not one caption row:

```text
normalize_source_proxies
  → build_visual_index
  → build_match_plan
  → review_match_plan
  → zero or more repair_match_plan + renewed review
  → run_hyperframes_stress_test
  → approve_aesthetic_proxy
  → render_picture_master
  → zero or more repair_match_plan + patch_picture_master
  → apply_picture_master
```

That order is mandatory for `hyperframes_proxy_gated_v2`: source-SHA/profile-hash proxies in a local non-iCloud cache (default 1080p/CFR30/H.264/yuv420p/BT.709/GOP≤30) → proxy-bound index → 4–8 second semantic-unit match and review on the canonical SRT cue clock → real 30–60 second HyperFrames stress render → HyperFrames 720p opening/middle/ending aesthetic approval → one target-resolution master → one complete master QA → chunk-scoped repairs only. A normal semantic unit retains 8–12 candidates; a risk unit may expand to no more than 32 and must present at least three ranked A/B/C alternatives. The aesthetic approval freezes structure, UID, framing, geometry, typography, motion, and pace; changing a frozen decision requires returning through the appropriate repair/review and approval gates rather than silently altering the master.

For an existing `hyperframes_required_v1` run, continue its already-frozen v1 sequence and segment-hash verification. Do not insert v2 gates retrospectively unless the user explicitly changes the contract and the Harness accepts a rebind.

`scripts/init_run.py` writes `visuals/indexed_bulk_checks.template.json` with the registered strict check definitions. Copy the current stage checks into `verification_plan.json`, replace versioned snapshot/output paths, then `rebind`; do not omit required flags to simplify a run.

The registered offline actions require their primary check type and a currently passing prerequisite check from the preceding stage. `prepare`, `begin`, and `verify` rerun prerequisite checks and require their configured paths to match the current primary check. Under v2 the bindings are proxy manifest → index → plan → review/repair → stress sample → aesthetic proxy approval → target master, then repair plus the prior accepted master/patch → chunk patch. A renewed review after repair must bind to the repair check's `after_match_sheet_path`, `after_candidate_pool_path`, and identical source manifest; it may not relabel the original match-plan manifest. When several generations pass, Harness selects the passing prerequisite whose bound paths match the current generation instead of accepting the first old result. A full plan may not use `offline_artifact` to disguise hundreds of cue rows as one generic output. In the indexed profile, the generic action is denied for the entire visual target domain, including proxy, stress, aesthetic-proxy, render, and patch artifacts. Keep `match_rows_per_batch=1` only for the focused few-cue fallback.

For expensive source-proxy, stress, aesthetic-proxy, master, and patch checks, “rerun” may reuse the Harness-owned `objective_check_cache.json` only when the complete check configuration, checker-script SHA, and every dependency fingerprint remain current. Stable size/mtime/device/inode fingerprints reuse the earlier SHA-bound full-media result without another decode or full-file read; drift forces hashing and, when changed, the complete objective check. This is the only allowed way to avoid repeated accepted-base or proxy decoding during prerequisite and reporting steps.

The machine proposal is never the approval gate. Require:

- a retained candidate pool and exact canonical-SRT coverage;
- under v2, selected-shot evidence exactly once per semantic visual unit plus an exact cue/frame-to-unit mapping; under v1, selected evidence for every cue;
- under v2, A/B/C head/middle/tail evidence bound to each derived risk unit's candidate/source/range; under v1, the corresponding risk-row evidence;
- explicit visual identity review for named-character claims;
- separate sequence-level opening and ending reviews;
- zero unresolved semantic units under v2, or zero unresolved rows under v1, before render;
- current hashes for the SRT, proxy manifest, index, pool, match sheet, review, repair, timing contract, HyperFrames composition/render plan, stress result, aesthetic approval, and render as applicable;
- exact declared cue/frame deltas for every patch;
- under v2, unchanged chunk-file SHA equality, decoded changed chunks, adjacent seam evidence, and a single assembled-output decode/black/seam pass; do not repeat a full accepted-base decoded-frame hash;
- under an existing v1 run, decoded-frame hashes for every unchanged and changed patch span;
- path and hash lineage that prevents a PASS artifact from an older generation approving a newer sheet, pool, or picture.

Objective checks can prove coverage, source/range consistency, evidence existence, hashes, frame contracts, and whether a human-judgment field was recorded. They cannot infer that a character identification is semantically correct merely because an agent-authored JSON says `PASS`; the reviewer verdict and its concrete image evidence remain an explicit human-judgment gate.

## Media identity rule

For every insert or replacement, identify the source by absolute resolved path, basename, byte size, SHA-256, and positive `ffprobe` duration. Do not select a media-bin item only because it is newest, leftmost, rightmost, highlighted, or near remembered coordinates.

If the inserted item or cumulative time is wrong, undo once and prove the pre-state was restored. Report `wrong_media`; do not try a different card position in the authoritative timeline.

## Caption transaction rule

The transaction log supplied to `verify --transaction-log` must contain:

```json
{
  "events": [
    "raw_backup_verified",
    "semantic_srt_audited",
    "local_subtitle_card_verified",
    "semantic_track_dragged_verified",
    "raw_track_removed",
    "canonical_exported"
  ],
  "caption_track_counts": [1, 1, 2, 1],
  "exact_overlap_count": 0,
  "final_caption_count": 331,
  "raw_backup": "/absolute/path/raw_backup.srt",
  "imported_srt": "/absolute/path/audited_semantic.srt",
  "local_subtitle_card_name": "audited_semantic.srt",
  "canonical_export": "/absolute/path/canonical.srt",
  "subtitle_export_settings": {
    "video_export": false,
    "audio_export": false,
    "caption_export": true,
    "format": "SRT",
    "encoding": "Unicode / UTF-8"
  }
}
```

The first two track-count observations must both be one: choosing an SRT creates a `本地字幕` material card but does not add captions to the timeline. Only the card drag may create the second track. The `imported_srt` path must match the stable media identity prepared for the action, and `local_subtitle_card_name` must equal its basename.

Use the `srt_integrity` objective check before styling or picture matching. Require exact expected count, continuous indices, ordered-text SHA when known, punctuation-insensitive lexical equality with the locked narration text, valid ordered time ranges, no forbidden overlap, no adjacent exact duplicate, and final-end tolerance. The check must also declare this exact policy:

```json
{
  "forbidden_terminal_punctuation": ["，", "。", "：", "；", ",", ".", ":", ";"],
  "terminal_closing_marks": ["」", "』", "”", "’", "》", "〉", "）", "】"]
}
```

The gate rejects any caption whose effective ending is `，。；：,.;:`. It first skips trailing closing marks, so `；」` and `。」` also fail; `？！?!` remain valid. `caption_replace_atomic` and `caption_canonical_export` fail during `prepare` when the policy is absent or altered, and `srt_integrity` fails again if the exported file violates it. A nonempty audit JSON or “zero adjacent duplicate” check alone is not sufficient.

## One frame clock

Import and verify every narration WAV first. Then freeze one `timing_contract.json` from Jianying's measured live narration-end timecode before full-span picture or BGM work:

```json
{
  "fps": 60,
  "target_frame_count": 36979,
  "target_timecode": "00:10:16:19",
  "target_seconds": 616.3166666667
}
```

The live observation must contain an independently measured `narration_end_timecode`. Use `scripts/freeze_live_timing_contract.py --observation LIVE_STATE.json --output timing_contract.json --expected-narration-clips N`. Use the actual run values. Jianying can quantize every imported WAV independently, so the arithmetic sum of source durations is diagnostic only and must not define the full-span frame count. Caption cues govern sentence-level picture boundaries; a caption end before narration produces an intentional final-picture hold, while a caption end more than one frame after narration is invalid. Picture master, BGM master, and live timeline must derive from the frozen live end. Do not independently trim narration, picture, and BGM by eye.

Create or replace `timing_contract.json` only inside a prepared `offline_artifact` action bound to `timing_contract_live_clock`, using `offline_artifacts_per_batch=1`. If an existing contract predates that unit limit or check, update the request contract and verification plan only with explicit user authority, then `rebind` before opening the offline action. Run the freeze script with `--force` only when a contract already exists; it writes a timestamped recoverable backup and records that backup under `supersedes`. Then verify the fresh contract before rendering picture or BGM. A downstream deviation greater than one frame requires rollback and regeneration; a one-frame import rounding error may use the single tail-alignment action once.

## Failure budget

- One logical batch keeps one ledger row across its repair attempt. Do not append a new speculative batch and do not rewrite failures later as `waived:superseded`.
- A waiver exists only for an action prepared with `--optional`, before `begin`, and after `skip --authorized-by user --reason "..."`. A success-criterion action cannot be optional.
- On the first recoverable failure, undo and prove the complete pre-state. The harness permits one retry of the same registered recipe.
- The second identical failure fingerprint blocks the phase.
- Three failures in one phase or six in the run block the harness.
- Protected-state change, inconclusive mutation state, contract/plan drift, BGM provenance failure, or an unrecoverable action blocks immediately.
- `forbidden_ui_route_unavailable` and `forbidden_ui_interaction` block immediately and never receive an automatic retry.
- A stale pre-authorization hit-test is a retryable evidence error, not a block, because it authorized and executed nothing.
- A block requires an explicit user decision. `unblock --authorized-by user` reopens the same logical action and does not erase history; a live action also requires a fresh observation/evidence proving the complete pre-state was restored.
- When the user has independently changed the live draft, use `adopt-live-baseline` from a ready run, or from an untouched open action whose managed trace proves zero agent authorizations and completions, instead of forcing restoration. An untouched action receives the neutral ledger status `cancelled_no_mutation`; a ready run receives a baseline-only `B####` checkpoint. Neither route increments action success or recipe streaks.

Do not respond to failure by inventing a drag direction, hotspot, coordinate, keyboard shortcut, menu sequence, or new mutation class. Calibrate an unknown UI route only in an isolated scratch timeline, at most twice, and delete the scratch timeline with verified count restoration before touching the authoritative timeline. Record a proven route as a reviewed registry change before production use.

## Fast resume and phase seals

Use `advance` only after all named phase-gate checks pass. Supply every accepted phase artifact with `--artifact`; the harness records strong hashes in `harness/phase_seals/`.

Do not pass `run_manifest.json` as a phase artifact. It is mutable control-plane state: `advance` updates its current phase and timestamp, and `close` updates lifecycle metadata. The Harness rejects it before creating a seal so its own writes cannot create sealed-artifact drift. Seal the immutable production artifacts referenced by the manifest instead.

On resume, reuse a sealed phase when its stat and hash remain valid. Do not rescan the workspace, regenerate accepted outputs, or rerun GUI setup. Contract, verification-plan, or sealed-artifact drift blocks the next mutation and requires deliberate revalidation.

When the user explicitly changes scope or acceptance criteria, update the contract/plan while no action is open, then run `harness.py rebind RUN_DIR --authorized-by user --reason "..."`. Rebinding records the old fingerprints, invalidates every phase seal, and clears the final-action cursor so affected gates and final persistence must be proved again. Never edit the saved fingerprints directly.

For a blocked offline action only, `rebind` may retain that same open action and
the block when the user explicitly authorizes a verification-plan correction.
This recovery updates the saved fingerprints but does not pass, cancel, retry,
or unblock the action. Run `unblock --authorized-by user`, begin the returned
retry token, recreate fresh action evidence, and verify normally. A blocked
live action can never use this route; it still requires restoration evidence
and the normal live-action recovery path.

Perform offline generation, indexing, audits, and renders before opening one concentrated live-assembly window. Avoid alternating between asset generation and Jianying UI work.

## Final close order

The final four verified actions must be, in order and with no later mutation:

1. `cleanup_extra_timelines`
2. `caption_canonical_export`
3. `live_qa_capture`
4. `save_reopen_verify`

Then run `python3 scripts/harness.py close RUN_DIR`. Close runs the full objective plan, writes the canonical `qa/verification_results.json`, temporarily marks the manifest complete, invokes `validate_run.py`, and commits `complete` only if all checks pass. On failure it restores `in_progress` and blocks with evidence.

Final export remains outside the harness action registry while `export_authorized=false`. Do not add an export action merely to finish a run.

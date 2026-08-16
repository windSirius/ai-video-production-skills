# Output contract

## Run directory

Keep one run directory per video. Use stable filenames where practical:

```text
request_contract.json
authority_bundle.json
verification_plan.json
run_manifest.json
timing_contract.json
batch_ledger.tsv
harness/
  state.json
  events.jsonl
  pending_action.json
  objective_check_cache.json
  lock
  checkpoints/
  checks/
  phase_seals/
  close_result.json
recording_analysis/
  source_manifest.json
  media_probe.json
  sampling_plan.json
  frame_input.tsv
  vision_frame_index.tsv
  ocr_events.tsv
  mission_flow.tsv
  unresolved.tsv
  contact_sheets/
  claude_handoff.md
  claude_handoff.json
  qa_report.json
clean_script.md
segments.md
narration/
  01.wav
  ...
  manifest.json
captions/
  narration_backup.srt
  canonical.srt
tracks/
  track_plan.json
  review_manifest.json
  review_package/
  assets/
  b_track/
  c_track/
sources/
  proxy_manifest.json
hyperframes/
  project/
    index.html
  composition.json
  environment.json
  render_plan.json
  check_result.json
  render_manifest.json
  stress/
    stress_manifest.json
    stress_sample.mp4
    qa/
  proxy/
    aesthetic_proxy_720p.mp4
    qa/
  chunks/
  qa/
visuals/
  indexed_bulk_checks.template.json
  source_identity_manifest.json
  shot_index.tsv
  shot_ocr_index.tsv
  visual_index_manifest.json
  cue_profiles.json
  candidate_pool.jsonl
  contact_sheets/
    manifest.json
  match_sheet.tsv
  match_plan_manifest.json
  selected_evidence/
  contact_sheets_final/
  candidate_review/
    selected_evidence_manifest.tsv
    evidence/
    selected/
    risk/
  review_manifest.json
  aesthetic_review/
    approval.json
    opening/
    middle/
    ending/
  repair_manifest.json
  repair_result.json
  repair_history.jsonl
  generation_manifest.json
  snapshots/
  patches/
    base_segment_manifest.tsv
    output_segment_manifest.tsv
    chunks/
    chunk_verification_manifest.json
    patch_manifest.json
    picture_only_patched.mp4
  render_manifest.json
  render_segment_manifest.tsv
  picture_only_vN.mp4
  picture_render_report_vN.json
  cards_vN/
reference_analysis/
  intro_contact.jpg
  outro_contact.jpg
audio/
  bgm_manifest.json
  generation_manifest.json
  generated_sources/
  bgm_master_vN.wav
cover/
  cover_sources.json
  review_manifest.json
  previews/
  approved/
sources.tsv
edit_ledger.tsv
qa/
  acceptance_audit.json
  contact_sheet.jpg
  visual_rematch_vN/
    01_start.jpg
    02_middle.jpg
    03_end.jpg
  verification_results.json
acceptance_report.md
```

Existing project-specific names may be retained; register their paths in `run_manifest.json`.

## Manifest minimum

- title, created time, updated time, current phase, and status;
- frozen delivery width/height/fps, current authority-bundle path/revision/status, and separate objective/human release states;
- workspace and Jianying draft name;
- source manuscript, reference WAV, and reference transcript source;
- narration directory, immutable SRT snapshot, normalized visual-index manifest, retained candidate pool, current-generation match sheet, review and repair manifests, picture render lineage/report, reference analysis, live opening/middle/ending QA, BGM manifest/master, ledger, and report paths;
- `bgm_source_mode` with `local_library` or `generated_score`; when local, record the absolute root resolved from `AI_VIDEO_MUSIC_ROOT`, defaulting to `$HOME/Music`; when generated, record the generation-manifest path;
- `workflow_profiles.video_rendering=hyperframes_proxy_gated_v2` whenever a new run includes video generation; preserve `hyperframes_required_v1` only for an existing run whose contract was already frozen under v1;
- source-proxy contract/profile hash, proxy manifest, local non-iCloud cache root, HyperFrames project/environment, stress sample/manifest, 720p aesthetic proxy/approval, integer-frame plan, target render manifest, one full-master QA result, current output, and chunk-patch lineage paths when video generation is active under v2;
- exact project timecode when known;
- game-recording source manifest, Vision index, mission-flow timeline, Claude handoff, and recording-analysis QA paths when that module is active;
- export authorization and export path when applicable.
- track plan, B/C asset review, auxiliary render lineage, cover sources/reviews and storage-cleanup report when those modules are active.

Never store private credentials or browser session tokens in the manifest.

## Authority bundle minimum

For workflow v2.2, keep one `authority_bundle.json` as the only production dependency root. Follow [authority-chain-and-release-gates.md](authority-chain-and-release-gates.md) and record:

- one in-project canonical script path/SHA/status;
- one independent actual-final narration path/SHA/status, ffprobe-derived duration frame count, the final-master lexical verdict, and the user's pronunciation/full-audio audition verdict;
- one in-project final SRT path/SHA/status, cue count, quantized final frame, declared tail hold, and user approval verdict;
- frozen delivery width, height, fps and `target_frame_count`;
- one row per downstream artifact with file SHA, state, objective status, human status, and bindings back to the same script/audio/SRT hashes and frame contract.

Historical engineering SRTs, ASR-aligned SRTs, old masters and attempts may remain recoverable, but no downstream binding may point to them. Run `scripts/audit_authority_chain.py` without `--allow-provisional` before a target-resolution master. The `--allow-provisional` mode is limited to planning and low-resolution proxy work.

## HyperFrames render contract minimum

For every new `hyperframes_proxy_gated_v2` run, treat HyperFrames as the required composition, timing, validation, stress-test, proxy-approval, capture, and authored-render entry point. Direct FFmpeg invocation may normalize source proxies, probe media, and perform QA; it must not independently author, assemble, or replace the v2 picture master or any authored/output visual segment. An encoder invoked and controlled by HyperFrames remains part of the HyperFrames render path. Record:

- CLI, Node, Chrome, FFmpeg, and ffprobe versions plus detected hardware encoders;
- local non-iCloud proxy-cache root; source-SHA/profile-hash cache key, source SHA-256, proxy SHA-256, and contract-bound proxy profile; default `1080p_cfr30_h264_gop30_yuv420p_bt709_v1` parameters (1920×1080/CFR30/H.264/yuv420p/BT.709/GOP≤30) unless the request contract freezes another profile;
- authority-bundle revision/SHA, composition path and SHA-256, proxy-manifest/source-plan/review hashes, timing-contract hash, artifact role, frozen width, height, fps, target frame count, and color policy;
- free bytes before and after, estimated peak bytes, configured minimum reserve, frame-cache path, and selected profile;
- the exact HyperFrames execution profile used; `hyperframes_static_segment_fallback_v1` is not authorized for a v2 run;
- exact command arguments, actual encoder, worker count, cache policy, start/end timestamps, exit status, output path, media probe, output SHA-256, and QA evidence;
- one frame-plan row per 4–8 second semantic visual unit with integer `start_frame` and `frame_count`, using the canonical SRT cue clock as the sole matching clock; require their ordered sum to equal `timing_contract.target_frame_count`;
- the real 30–60 second HyperFrames stress manifest/sample, current composition/render-plan hashes, concrete activation/boundary ranges, and its full-decode, black-frame, transition-seam, declared proxy-profile/asset-class, and required-risk-class results; card/overlay coverage is conditional on those classes being used;
- the HyperFrames 1280×720 aesthetic proxy, current composition/render-plan and passing-stress hashes, plus opening/middle/ending evidence and frozen decisions for opening/ending structure, UID, framing, geometry, typography, motion, and pace;
- exactly one successful target-resolution master render followed by one accepted complete decode/black/seam QA result before any patch is authorized.

On macOS, request GPU encoding and prefer VideoToolbox, but record the encoder actually selected. Hardware encoding is not assumed byte-identical across rerenders; bind the produced artifact by its post-render hash and use decoded-frame QA for equivalence.

Use `hyperframes_low_disk_stream_v1` when projected free space would fall below the contract reserve. Disable persistent frame caching, use one worker and low-memory mode, and forbid `png-sequence`.

Compatibility: an existing `hyperframes_required_v1` run may continue using an already-frozen `hyperframes_static_segment_fallback_v1` contract and its disclosed FFmpeg-authored pixels. That permission does not carry into v2 and must not be used to create a new v2 master or patch.

Set `artifact_role=jianying_picture_master` for replacement media and require zero audio streams plus no burned captions. Permit captions and mixed audio only for `standalone_preview` or `authorized_final_export`; final export still requires explicit user authorization.

## Timing contract minimum

Create `timing_contract.json` only after the actual final narration is available as a stable independent file, has passed lexical and user-audition release, and is visible in order on the authoritative Jianying timeline. Generate it from a verified live-state observation with `scripts/freeze_live_timing_contract.py`. Record:

- `fps`, `target_frame_count`, `target_seconds`, and `target_timecode`;
- `clock_source=verified_live_jianying_narration_end`;
- the source live-observation path and SHA-256, including an independently measured `narration_end_timecode`;
- the verified narration clip count;
- source-WAV duration sum and caption final end as diagnostic values when known.
- authority-bundle revision plus exact final narration and final SRT SHA-256 values.

Do not use a simple sum of WAV durations or the overall project duration as the full-span frame authority. Jianying may quantize each imported clip separately, and picture/BGM media may extend the project beyond narration. If caption cues end before narration, record the remainder as `caption_tail_hold_frames`; if they extend more than one frame beyond narration, reject the contract. Replacing an existing timing contract requires a recoverable timestamped backup.

If the user edits narration after this contract is frozen, preserve the old contract as superseded and invalidate SRT, A/B/C, BGM and every time-bound downstream row. Do not trim the old master to the new end time or keep an old semantic-unit plan while changing only `target_frame_count`.

## BGM manifest minimum

Write `audio/bgm_manifest.json` before importing BGM. Require `source_mode` with exactly one of `local_library` or `generated_score` and a nonempty `sections` array. Each section must contain:

- `chapter` and `mood`;
- absolute `source` resolving to the frozen local or generated source file;
- `source_start` and `duration`;
- derived chapter `file` under the run directory;
- intended Jianying gain or automation note;
- `vocal_content` with one of `instrumental`, `wordless_vocal`, or `lyrics`.

The manifest also binds the current authority-bundle revision, final narration SHA, final SRT SHA, fps and target frame count. An audition mix must use that exact narration file; equal duration or tail trimming is not a valid binding.

Songs with lyrics are eligible BGM; lyric presence alone is not a rejection reason. When `vocal_content` is `lyrics`, also require:

- `lyrics_language` and a concise `lyric_meaning_summary` without reproducing the lyrics;
- `semantic_role` explaining why the words belong in this chapter;
- `narration_overlap_ranges`, using an empty list when the selected lyric is heard only during narration gaps;
- `mix_strategy` with one of `instrumental_window_under_narration`, `ducked_under_narration`, or `featured_in_narration_gap`;
- `semantic_conflict_review` and `narration_intelligibility_review`, each with a reviewer, status, and evidence or notes;
- a note for any unresolved licensing or final-export rights question.

Reject a lyric-bearing interval when either review is not `pass`. Review the exact source interval, not merely the song title or general theme. A foreign-language lyric still needs a meaning review, and a locally stored file does not by itself prove final-export rights.

For `local_library`, the source must resolve inside the configured music root. For `generated_score`, require `audio/generation_manifest.json` with service/model, prompt or prompt hash, generation time, source path, source SHA-256, duration and status. The master and chapter files are derivatives and never replace source provenance. Never list footage audio as BGM source.

## Auxiliary-track minimum

When B or C track is active, record:

- `tracks/track_plan.json` with ranges, narrative job, track, hold duration and output mode;
- one source/review row per screenshot, card, icon or silhouette;
- visible identity and source SHA for every character asset;
- approved alpha or green-screen mode;
- composition, asset, build-script and chunk input hashes;
- boundary audit, chunk receipts, concat receipt, full-decode result and manual review verdict.
- final fps and target frame count equal to the authority bundle, even when the auxiliary canvas resolution differs from A-track.

No unapproved review asset may appear in the render manifest.

## Cover minimum

Record the one-sentence episode-specific cover promise, then one `cover_sources.json` row per official/user/generated asset with distinct `identity_model`, `shot_camera`, `style_render` or `typography` role. Bind each output to its source hashes, local layout source, dimensions and thumbnail preview. Require a passing 16:9 no-text identity/thesis/same-space review before typography or other ratios; each ratio then receives its own human verdict. A previous episode's composition is style evidence only unless the current promise independently justifies the same shot.

## Success contract minimum

- one unambiguous objective and one concrete deliverable;
- explicit in-scope and out-of-scope lists;
- measurable success criteria, each bound to one unique check ID;
- positive small-batch limits;
- for new `hyperframes_proxy_gated_v2` runs, unit limits of one source-proxy manifest, one visual index, one match-plan generation, one review bundle, one repair set, one HyperFrames stress test, one aesthetic-proxy approval, one picture master, or one picture patch per corresponding Harness batch; keep cue-row limits only for the focused fallback;
- the mandatory v2 order: local source-SHA/profile-hash proxies → proxy-bound index → 4–8 second semantic-unit matching/review with normal pools of 8–12 and risk pools capped at 32 with at least A/B/C → real 30–60 second HyperFrames stress render → HyperFrames 720p opening/middle/ending approval → one target-resolution master → one full QA → chunk-scoped patch;
- existing v1 runs retain their frozen v1 unit limits and verification mode;
- stop conditions for failed checks, missing authority, or invalid inputs.

## Batch ledger minimum

Use:

```text
batch_id phase assumption scope mutation unit_limit_key unit_count check_id expected measured status evidence waiver_reason superseded_by opened_at closed_at
```

Let `scripts/harness.py` create and close `H####` rows. Require `unit_count` to be a positive integer no greater than the named limit in `request_contract.json`. Harness-managed status is an exact enum, not a prefix: only `pass` closes a required action. An optional action may be `waived` only before execution and must carry a reason plus user-authorization reference. Never use `done`, `waived:superseded`, or a retrospective mass waiver when the check was not executed.

## Harness minimum

- `state.json` contains one run ID, revision, lifecycle, current phase, frozen contract/plan fingerprints, at most one open action, failure budgets, phase seals, and the final action history;
- `events.jsonl` is append-only and records preparation, begin, pass/fail, recovery, phase advance, and close events;
- each live action has immutable before, failed/post, and rollback checkpoints when applicable;
- each live action records the action/recipe/pre-state-bound registered route fingerprint, exact semantic target/ancestor/per-step-layout sequence, just-in-time bounds and hit points, per-step pre-click authorization and evidence, and the complete harness-managed interaction-trace fingerprint;
- each verifier result records batch, mutation, check, observed target, fresh evidence hashes, metrics, and pass state;
- expensive v2 objective checks may be reused only through `harness/objective_check_cache.json`, keyed by check configuration plus checker SHA and bound to dependency SHA-256 values; unchanged size/mtime/device/inode fingerprints permit a lightweight reuse, while any fingerprint or checker change forces revalidation;
- visual review, repair, render, and patch artifacts bind to the exact current SRT/index/pool/match-sheet hashes; orphan contact sheets and stale audit files are never implicitly accepted;
- in v2, proxy/index lineage binds source and proxy SHA-256 plus the profile hash; stress evidence binds the current proxy manifest and match sheet; aesthetic approval binds the passing stress manifest and freezes structure, UID, framing, geometry, typography, motion, and pace; the target master binds that approval and uses `render_unit_mode=semantic_visual_units_v2`;
- a v2 patch uses `patch_verification_mode=chunk_scoped_v2`, proves unchanged chunk file SHA equality, decodes changed chunks, checks adjacent seams, and runs one assembled-output decode/black/seam QA; it does not rerun a full decoded-frame hash comparison over the accepted base;
- do not store the complete history only in `state.json`, and do not edit harness files manually.

## Reporting vocabulary

- `generated`: a local asset exists outside Jianying.
- `downloaded`: an external file exists locally and has provenance recorded.
- `imported`: Jianying media bin contains the asset.
- `applied`: the asset is used on the timeline or export-cover setting.
- `project updated`: the live timeline changed and was freshly verified.
- `saved`: the draft save action completed or autosave state was verified.
- `exported`: a final rendered video exists and was probed.

## Minimum acceptance report

Report:

- conclusion and explicit export state;
- authority-bundle revision/SHA, one current script/audio/SRT path and SHA each, lexical/audition/subtitle approval states, and confirmation that every accepted time-bound descendant uses those hashes;
- exact timeline duration, resolution, frame rate, picture duration, narration count, caption count, and disabled-caption count;
- OCR frame count, semantic visual-unit count, three-candidate audit result, strict black-gap result, and stable live replacement filename;
- source-proxy profile/profile hash, proxy-manifest SHA, local non-iCloud cache location, source/proxy SHA coverage, and proxy-integrity result;
- canonical SRT cue-clock binding, 4–8 second semantic-unit compliance, normal-pool 8–12 compliance, risk-pool maximum 32, and risk A/B/C coverage;
- real HyperFrames stress-sample duration, risk/asset-class coverage, decode/black/seam result, and stress-manifest SHA;
- HyperFrames 720p opening/middle/ending objective evidence plus the user's separate approval evidence and the frozen structure, UID, framing, geometry, typography, motion, and pace decisions;
- target-resolution master count, `semantic_visual_units_v2` render mode, target output SHA, and the single full-master decode/black/seam QA result;
- for each v2 patch, changed/unchanged chunk IDs, unchanged chunk SHA result, changed-chunk decoded-frame result, adjacent-seam result, assembled-output decode/black/seam result, and explicit confirmation that the accepted base was not subjected to a repeated full decoded-frame hash pass;
- chapter/BGM plan, Music-folder source paths, vocal-content classification, lyric semantic/intelligibility review when applicable, provenance-check result, and verified live settings;
- thesis/evidence-card time ranges and functions;
- QA results, inherited issues, low-confidence visual matches, and human-audition limits;
- opening hook, representative middle match, final spoken-line image, protected-lane preservation, draft-save state, and persistence check when required;
- harness lifecycle, final close result, failure-budget usage, and any explicit user unblock;
- links to the latest assets and reproducible scripts.

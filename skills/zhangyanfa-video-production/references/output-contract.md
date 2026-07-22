# Output contract

## Run directory

Keep one run directory per video. Use stable filenames where practical:

```text
request_contract.json
verification_plan.json
run_manifest.json
timing_contract.json
batch_ledger.tsv
harness/
  state.json
  events.jsonl
  pending_action.json
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
visuals/
  shot_index.tsv
  shot_ocr_index.tsv
  contact_sheets/
  match_sheet.tsv
  picture_only_vN.mp4
  picture_render_report_vN.json
  cards_vN/
reference_analysis/
  intro_contact.jpg
  outro_contact.jpg
audio/
  bgm_manifest.json
  bgm_master_vN.wav
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
- workspace and Jianying draft name;
- source manuscript, reference WAV, and reference transcript source;
- narration directory, immutable SRT snapshot, OCR index, match sheet, picture render/report, reference analysis, live opening/middle/ending QA, BGM manifest/master, ledger, and report paths;
- `bgm_source_root` fixed to the absolute root resolved from `AI_VIDEO_MUSIC_ROOT`, defaulting to `$HOME/Music`;
- exact project timecode when known;
- game-recording source manifest, Vision index, mission-flow timeline, Claude handoff, and recording-analysis QA paths when that module is active;
- export authorization and export path when applicable.

Never store private credentials or browser session tokens in the manifest.

## BGM manifest minimum

Write `audio/bgm_manifest.json` before importing BGM. Require a nonempty `sections` array. Each section must contain:

- `chapter` and `mood`;
- absolute `source` resolving to a regular file under the configured BGM root;
- `source_start` and `duration`;
- derived chapter `file` under the run directory;
- intended Jianying gain or automation note.

The master and chapter files may live under `RUN_DIR/audio/`, but they do not replace source provenance. Never list footage, Downloads, a generated file, or any path outside Music as `source`.

## Success contract minimum

- one unambiguous objective and one concrete deliverable;
- explicit in-scope and out-of-scope lists;
- measurable success criteria, each bound to one unique check ID;
- positive small-batch limits;
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
- exact timeline duration, resolution, frame rate, picture duration, narration count, caption count, and disabled-caption count;
- OCR frame count, semantic visual-unit count, three-candidate audit result, strict black-gap result, and stable live replacement filename;
- chapter/BGM plan, Music-folder source paths, provenance-check result, and verified live settings;
- thesis/evidence-card time ranges and functions;
- QA results, inherited issues, low-confidence visual matches, and human-audition limits;
- opening hook, representative middle match, final spoken-line image, protected-lane preservation, draft-save state, and persistence check when required;
- harness lifecycle, final close result, failure-budget usage, and any explicit user unblock;
- links to the latest assets and reproducible scripts.

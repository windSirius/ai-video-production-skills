# Pipeline and recovery map

## Picture-generation core order

Run long-form picture generation in this order. Do not use a full-length target-resolution render as a creative preview or skip an earlier gate because the later checks could theoretically catch the same defect.

1. **Normalize and cache source proxies.** Bind each original source SHA-256 to one stable, seek-safe profile—by default 1080p/CFR30/H.264/`yuv420p`/BT.709/GOP≤30—in a required local non-iCloud scratch/cache, and reuse a passing proxy/index while both hashes remain current. Preserve original-source provenance; a proxy is a render and retrieval derivative, not a new source identity.
2. **Retrieve and review semantic visual units.** Build 4–8 second units from complete narrative or dialogue beats, normally spanning several caption cues. Cues remain immutable clock mappings inside a unit; they do not force a new source seek, asset activation, or render segment.
3. **Pass a real 30–60 second HyperFrames stress sample.** Use the production composition path and representative cuts/assets. Check every sample boundary, first and last frame, and the first decodable/activated frames after each asset change. Repair black, stale, duplicated, or decoder-lag frames before continuing.
4. **Approve 720p aesthetic proxies.** Render the opening, ending, and at least one representative middle interval. Confirm hook, evidence density, continuity, shot cadence, emotional release, and final-image function before high-resolution production.
5. **Perform one planned full-length production render at the contract target resolution, normally 1080p.** Start it only after the technical and aesthetic gates pass. A retry is allowed only for an objective render failure with a recorded repair; do not rerender the full master for ordinary creative feedback.
6. **Run one complete final QA.** Probe, fully decode, and check frame count, duration, first/last frames, black gaps, transition seams, color, and audio policy once on the candidate production master. Store checker-versioned, hash-bound evidence and reuse it after lightweight fingerprint validation while inputs remain unchanged.
7. **Patch incrementally when feedback arrives.** Regenerate only declared changed semantic units/chunks. Prove the base SHA, changed frame ranges, unchanged chunk hashes, and neighboring seams; do not fully decode and frame-hash both the accepted base and patched output merely to prove unchanged content.

Keep timing-contract, source, proxy, index, match-plan, review, composition, chunk, and master hashes as one lineage across all seven stages. Keep the low-disk profile available without weakening any gate.

## Phase map

| Phase | Required input | Required output | Gate before continuing |
|---|---|---|---|
| Intake | target title or discoverable open draft | `request_contract.json`, `verification_plan.json`, `run_manifest.json` | contract-only validation passes |
| Recording analysis | complete game-mission recording | `recording_analysis/vision_frame_index.tsv`, `mission_flow.tsv`, Claude Markdown/JSON handoff | full-duration coverage, evidence links, and unresolved-gap audit pass |
| Manuscript | source MD/TXT/PDF/DOCX | `clean_script.md`, `segments.md` | ordered coverage exactly once |
| VoxCPM | reference WAV, exact transcript, segments | numbered WAVs, WAV manifest, QA | every clip valid; ASR coverage plausible |
| Caption spine | WAVs, clean script, open draft | sequential narration, live-derived `timing_contract.json`, captions, SRT backup | ordered WAV count, measured live integer-frame end, start/end coverage, and zero adjacent duplicates |
| Source proxy preparation | source footage and target timing profile | original-source manifest, hash-keyed seek-safe CFR proxies, proxy probe/cache manifest | every proxy is decodable, correctly attributed, current for its source/profile hashes, and reusable without reindexing |
| Visual retrieval | immutable user-adjusted SRT, cached proxy/index, optional reference video | semantic visual units with cue-to-frame mappings, retained candidate pool, provisional full match plan, selected/risk contact sheets, hash-bound review and repair manifests | every caption maps exactly once; all selected semantic units are reviewed; risk, identity, opening, ending, range, reuse, and lineage gates pass |
| Visual grammar freeze | reviewed current-generation match sheet, timing contract, style rules, optional reference | production HyperFrames composition with authored opening/middle/ending, cards, geometry, typography, motion, and pace | composition intent and current review lineage are complete before technical rendering |
| HyperFrames stress gate | reviewed current-generation match sheet, timing contract, frozen production composition | 30–60 second real HyperFrames stress sample and boundary/activation evidence | sample first/last frames, every asset activation, representative seams, and black/decode checks pass |
| Aesthetic proxy gate | passing stress gate and current composition | 720p opening, ending, and representative-middle proxies with review verdicts | hook, continuity, cadence, evidence, emotional release, and final-image reviews pass |
| Target-resolution production render | approved aesthetic proxies, disk preflight, current hashes | one planned full-length HyperFrames picture-only master and render lineage | required engine/profile, exact frame count, metadata, input-hash, review-hash, and audio-policy checks pass |
| Final picture QA | candidate production master | one complete probe/decode/black/seam/frame/audio-policy report | all full-output checks pass once against the current master hash |
| Incremental picture patch | accepted base master plus declared feedback delta | changed chunks, patched master, base/delta/unchanged-chunk lineage | changed chunks and adjacent seams pass; unchanged hashes match; no redundant full comparison of base and output |
| BGM selection | recursive inventory of the configured BGM root (`AI_VIDEO_MUSIC_ROOT`, default `$HOME/Music`) and stable narration | `audio/bgm_manifest.json`, chapter derivatives | every source resolves inside the configured root; provenance check passes |
| Acceptance | current draft and feedback | edit ledger, QA artifacts, report | every P0/P1 row has evidence-backed status |

## Resume rules

1. Run `scripts/harness.py resume RUN_DIR` before interpreting artifacts. It returns exactly one legal next action; do not continue a remembered plan around it.
2. Read the success contract and reuse valid phase seals. Inspect only unsealed or drifted inputs; prefer the latest artifact that has both a file and passing objective-check evidence.
3. A recording-analysis handoff is a factual prewriting artifact, not an approved narration manuscript.
4. Treat a file in a media bin as imported, not applied.
5. Treat an offline render as generated, not a project update.
6. Treat a changed timeline as updated only after a fresh screenshot/state check.
7. If an earlier gate or batch fails, repair that phase before continuing; do not silently compensate downstream.
8. Treat user-adjusted caption timing as immutable during picture work; never compensate for a weak match by moving captions.
9. If resume reports an in-progress action after a crash or lost response, inspect and verify/fail it. Never repeat it blindly.

## Small-batch defaults

- Manuscript: one transformation rule or one segment-boundary group per batch.
- Recording analysis: one source chunk, one Vision pass, one OCR event group, or one mission-flow chapter per batch; never combine frame extraction, semantic assembly, and manuscript writing.
- VoxCPM: one generated segment per batch.
- Caption repair: at most ten adjacent rows and one defect class per batch.
- Source preparation: one proxy profile/cache generation or one current-generation normalized index per Harness batch. Reuse valid source-SHA/profile-hash cache entries rather than regenerating them.
- Visual retrieval, long-form default: one complete index, one full semantic-unit match-plan generation, one review bundle, or one hash-bound repair set per Harness batch. Caption cues remain exact timing mappings inside semantic units, not separate default shot or render boundaries. Machine proposal, human/visual review, repair, and render are separate actions and may not be collapsed into `offline_artifact`.
- Visual retrieval, focused fallback: one semantic visual unit per batch under `match_rows_per_batch=1`; use this only for a few corrections when a complete normalized index is unavailable.
- Picture generation: one current-generation HyperFrames composition/render plan, one 30–60 second stress sample, one 720p opening/ending/middle proxy bundle, one planned target-resolution master, one final-QA report, or one declared incremental patch per batch. Picture application is one live replacement and never includes caption mutation.
- Evidence cards: one card per batch.
- BGM source selection: one Music-folder source decision per batch; record provenance before rendering derivatives.
- BGM automation: one rhetorical interval per batch.
- Live Jianying: one mutation class, then fetch fresh UI state and run the linked check.

The plan-level limits are still one-assumption limits: `visual_indexes_per_batch=1`, `match_plans_per_batch=1`, `match_review_bundles_per_batch=1`, `match_repair_sets_per_batch=1`, `picture_masters_per_batch=1`, and `picture_patches_per_batch=1`. Reduce limits further after any failed assumption. Do not increase them ad hoc. The only live production-loop promotion is the harness-registered narration quick-add loop after two consecutive identical successes and with per-item identity/end checks.

## Live-project recovery

- Record draft name, total duration, caption count, narration clip count, BGM count, BGM source paths, and final frame before major changes.
- Export SRT before destructive caption replacement.
- Retain the prior picture render or disabled track until replacement QA passes.
- Prefer equal-duration `替换片段` for complete picture rebuilds.
- Use a stable regular-file or hardlink source for `替换片段`; do not leave the saved draft dependent on a symlink or `/tmp`.
- If a Jianying action behaves unexpectedly, undo immediately and verify the prior lane returned.
- Record the unexpected state, rollback state, and fresh evidence through the same open harness token. A second identical failure blocks the phase; do not explore another coordinate or hotspot on the authoritative timeline.
- After replacement or reopening the app, verify the visible filename, duration, captions, narration, BGM, opening hook, representative middle match, and ending before resuming.

## Progress communication

- Send a short update before tool use and at least once per minute during long generation, indexing, rendering, or UI work.
- Report objective checks while work runs; do not imply subjective listening or full viewing when only ASR, signal, frames, or screenshots were inspected.
- Keep final export separate from draft completion.

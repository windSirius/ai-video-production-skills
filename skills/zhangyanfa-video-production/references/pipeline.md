# Pipeline and recovery map

## Picture-generation core order

Run long-form picture generation in this order. Do not use a full-length target-resolution render as a creative preview or skip an earlier gate because the later checks could theoretically catch the same defect.

1. **Freeze delivery and the one authority chain.** Lock width, height, fps and the final frame clock; bind one script, the independent actual final narration file and one final SRT in `authority_bundle.json`. Run `authority_chain_integrity` before target rendering. Alan's default is 2560×1440/60fps unless the user changes it.
2. **Normalize and cache source proxies.** Bind each original source SHA-256 to one stable, seek-safe profile—by default 1080p/CFR30/H.264/`yuv420p`/BT.709/GOP≤30—in a required local non-iCloud scratch/cache, and reuse a passing proxy/index while both hashes remain current. Preserve original-source provenance; a proxy is a render and retrieval derivative, not a new source identity.
3. **Retrieve and globally review semantic visual units.** Build 4–8 second units from complete narrative or dialogue beats, normally spanning several caption cues. Before authoring, freeze chapter source coverage and audit exact-range reuse, significant overlap, adjacency, source concentration, opening/ending budgets and black-frame hazards across the whole plan.
4. **Pass a real 30–60 second HyperFrames stress sample.** Use the production composition path and representative cuts/assets. Check every sample boundary, first and last frame, and the first decodable/activated frames after each asset change. Repair black, stale, duplicated, or decoder-lag frames before continuing.
5. **Obtain user approval on the full-length 720p aesthetic proxy.** Under workflow v3 render one continuous `[0,target_frame_count)` A/A+B proxy with frozen narration; opening, representative middle and ending excerpts remain navigation aids only. Confirm hook, evidence density, continuity, shot cadence, emotional release and final-image function across the actual full timeline. A producer or machine-authored PASS is not user approval.
6. **Perform one planned full-length production render at the frozen target resolution.** Start it only after authority, technical, global-reuse and human aesthetic gates pass. A retry is allowed only for an objective render failure with a recorded repair; do not render a target-resolution full master for ordinary creative feedback.
7. **Run one complete final QA.** Probe, fully decode, and check frame count, duration, first/last frames, black gaps, transition seams, color, and audio policy once on the candidate production master. Store checker-versioned, hash-bound evidence and reuse it after lightweight fingerprint validation while inputs remain unchanged.
8. **Patch incrementally when feedback arrives.** Regenerate only declared changed semantic units/chunks. Prove the base SHA, changed frame ranges, unchanged chunk hashes, and neighboring seams; do not fully decode and frame-hash both the accepted base and patched output merely to prove unchanged content.

Keep timing-contract, source, proxy, index, match-plan, review, composition, chunk, and master hashes as one lineage across all eight stages. Keep the low-disk profile available without weakening any gate.

## Phase map

| Phase | Required input | Required output | Gate before continuing |
|---|---|---|---|
| Intake | target title or discoverable open draft | `request_contract.json`, provisional `authority_bundle.json`, `verification_plan.json`, `run_manifest.json` | delivery width/height/fps, output roles and scope are locked before target rendering |
| Recording analysis | complete game-mission recording | `recording_analysis/vision_frame_index.tsv`, `mission_flow.tsv`, Claude Markdown/JSON handoff | full-duration coverage, evidence links, and unresolved-gap audit pass |
| Manuscript | source MD/TXT/PDF/DOCX | `clean_script.md`, `segments.md` | ordered coverage exactly once |
| VoxCPM | reference WAV, exact transcript, canonical segments, approved ASR aliases and pronunciation hotspots | numbered WAVs, per-segment lexical receipts, join audit, final-master lexical receipt, WAV manifest, QA | every accepted segment and the actual final master have zero insertions, zero substitutions and zero deletions; hotspots, joins, signal and secondary similarity pass |
| Authority release | frozen script and actual final narration file | frozen narration SHA, full-master lexical receipt, user pronunciation/full-audio verdict | lexical and human audition states both pass; any later audio edit invalidates this release |
| Caption spine | actual final narration, clean script, open draft | one final SRT, live-derived `timing_contract.json`, history backups | one SRT SHA is current; cue count/final frame agree with the authority bundle; no second effective caption clock exists |
| Source proxy preparation | source footage and target timing profile | original-source manifest, hash-keyed seek-safe CFR proxies, proxy probe/cache manifest | every proxy is decodable, correctly attributed, current for its source/profile hashes, and reusable without reindexing |
| Visual retrieval | authority-bound final SRT, cached proxy/index, chapter source-coverage matrix, optional reference video | semantic visual units with cue-to-frame mappings, retained candidate pool, provisional full match plan, selected/risk contact sheets, hash-bound review and repair manifests | every caption maps exactly once; global exact-range reuse, significant overlap, adjacency, source concentration, black risk, identity, opening, ending and lineage gates pass |
| Visual grammar freeze | reviewed current-generation match sheet, timing contract, style rules, optional reference | production HyperFrames composition with authored opening/middle/ending, cards, geometry, typography, motion, and pace | composition intent and current review lineage are complete before technical rendering |
| HyperFrames stress gate | reviewed current-generation match sheet, timing contract, frozen production composition | 30–60 second real HyperFrames stress sample and boundary/activation evidence | sample first/last frames, every asset activation, representative seams, and black/decode checks pass |
| Aesthetic proxy gate | passing stress gate and current composition | workflow-v3 full-length 720p A/A+B proxy with frozen narration, plus opening/middle/ending navigation evidence and separate objective/user verdicts | exact full-clock media checks pass and the user explicitly approves the displayed proxy SHA; legacy v2 keeps its frozen excerpt contract |
| Target-resolution production render | passing authority-chain audit, approved aesthetic proxies, disk preflight, current hashes | one planned full-length HyperFrames picture-only master and render lineage | frozen resolution/fps/frame count, required engine/profile, input/review hashes and audio policy pass |
| Final picture QA | candidate production master | one complete probe/decode/black/seam/frame/audio-policy report | all full-output checks pass once against the current master hash |
| Incremental picture patch | accepted base master plus declared feedback delta | changed chunks, patched master, base/delta/unchanged-chunk lineage | changed chunks and adjacent seams pass; unchanged hashes match; no redundant full comparison of base and output |
| Track architecture | final SRT, available footage and evidence needs | `tracks/track_plan.json`, A/B/C scope and review requirements | every non-A layer has a stated narrative job |
| B/C asset review | approved track plan and proposed screenshots/cards/silhouettes | `tracks/review_manifest.json`, contact sheets, source ledger | every used asset, identity and treatment is visibly approved |
| B/C render | approved review manifest and authority-bound timing contract | alpha or green-screen auxiliary master plus render receipts | fps and target frame count equal A-track authority; card holds, transition background and downstream mode pass |
| BGM preparation | authority-bound final SRT, exact final narration file and selected `local_library` or `generated_score` mode | `audio/bgm_manifest.json`, generated/local sources and chapter derivatives | narration/SRT hashes, frame clock, mode provenance, chapter, lyric, audition and intelligibility checks pass |
| Cover | one episode-specific click promise, identity/shot/style references and requested aspect ratios | `cover/cover_sources.json`, 16:9 no-text proof, previews and approved covers | identity → episode thesis shot → same-space → text → per-ratio gates pass in order |
| Acceptance | current draft and feedback | edit ledger, QA artifacts, report | every P0/P1 row has evidence-backed status |
| Storage lifecycle | accepted artifacts, source/reference graph and size inventory | cleanup plan and post-cleanup verification | only authorized, recoverable or reproducible data changes |

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
10. Recompute `authority_chain_integrity` on resume. If an authority hash or delivery spec drifted, mark every bound downstream artifact stale before doing further production work.

## Small-batch defaults

- Manuscript: one transformation rule or one segment-boundary group per batch.
- Recording analysis: one source chunk, one Vision pass, one OCR event group, or one mission-flow chapter per batch; never combine frame extraction, semantic assembly, and manuscript writing.
- VoxCPM: one generated segment plus its ASR, exact lexical receipt and hotspot adjudication per batch; final assembly and full-master lexical audit are a separate batch.
- Caption repair: at most ten adjacent rows and one defect class per batch.
- Source preparation: one proxy profile/cache generation or one current-generation normalized index per Harness batch. Reuse valid source-SHA/profile-hash cache entries rather than regenerating them.
- Visual retrieval, long-form default: one complete index, one full semantic-unit match-plan generation, one review bundle, or one hash-bound repair set per Harness batch. Caption cues remain exact timing mappings inside semantic units, not separate default shot or render boundaries. Machine proposal, human/visual review, repair, and render are separate actions and may not be collapsed into `offline_artifact`.
- Visual retrieval, focused fallback: one semantic visual unit per batch under `match_rows_per_batch=1`; use this only for a few corrections when a complete normalized index is unavailable.
- Picture generation: one current-generation HyperFrames composition/render plan, one 30–60 second stress sample, one workflow-v3 full-length 720p review proxy (or a legacy v2 excerpt bundle under its frozen contract), one explicit artifact-bound user verdict, one planned target-resolution master, one final-QA report, or one declared incremental patch per batch. Picture application is one live replacement and never includes caption mutation.
- Evidence cards: one card per batch.
- B/C asset review: one complete review bundle per episode; repair only declared asset IDs.
- BGM source selection: one chapter/source decision per batch; record `local_library` or `generated_score` provenance before rendering derivatives.
- BGM automation: one rhetorical interval per batch.
- Cover: one 16:9 no-text thesis/identity test first; only after it passes, one aspect-ratio layout per review batch. Share frozen identities and promise, not geometry.
- Storage: one declared cleanup class per batch; run a dry inventory before moving or deleting anything.
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

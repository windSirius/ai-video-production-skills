# Pipeline and recovery map

## Phase map

| Phase | Required input | Required output | Gate before continuing |
|---|---|---|---|
| Intake | target title or discoverable open draft | `request_contract.json`, `verification_plan.json`, `run_manifest.json` | contract-only validation passes |
| Recording analysis | complete game-mission recording | `recording_analysis/vision_frame_index.tsv`, `mission_flow.tsv`, Claude Markdown/JSON handoff | full-duration coverage, evidence links, and unresolved-gap audit pass |
| Manuscript | source MD/TXT/PDF/DOCX | `clean_script.md`, `segments.md` | ordered coverage exactly once |
| VoxCPM | reference WAV, exact transcript, segments | numbered WAVs, WAV manifest, QA | every clip valid; ASR coverage plausible |
| Caption spine | WAVs, clean script, open draft | sequential narration, live-derived `timing_contract.json`, captions, SRT backup | ordered WAV count, measured live integer-frame end, start/end coverage, and zero adjacent duplicates |
| Visual retrieval | immutable user-adjusted SRT, source footage, optional reference video | coarse/dense visual index, OCR index, contact sheets, audited three-candidate match sheet | every caption covered exactly once; OCR/visual/reuse audit passes |
| Picture rebuild | audited match sheet | equal-duration picture-only render | metadata, gaps, and duration verified |
| BGM selection | recursive configured BGM-root inventory (`AI_VIDEO_MUSIC_ROOT`, default `$HOME/Music`) and stable narration | `audio/bgm_manifest.json`, chapter derivatives | every source resolves inside the configured root; provenance check passes |
| Style | stable picture, narration, and verified Music-folder BGM | styled draft, cards, chapter BGM | visible hook/evidence/turn/thesis checks pass |
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
- Visual retrieval: one caption or sub-six-second semantic unit per batch; complete visual/OCR retrieval, three candidates, scoring, and reuse accounting before the next unit.
- Picture application: one narrative section or one equal-duration replacement per batch, never picture plus caption mutation together.
- Evidence cards: one card per batch.
- BGM source selection: one Music-folder source decision per batch; record provenance before rendering derivatives.
- BGM automation: one rhetorical interval per batch.
- Live Jianying: one mutation class, then fetch fresh UI state and run the linked check.

Reduce these limits further after any failed assumption. Do not increase them ad hoc. The only production-loop promotion is the harness-registered narration quick-add loop after two consecutive identical successes and with per-item identity/end checks.

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

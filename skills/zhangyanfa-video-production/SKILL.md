---
name: zhangyanfa-video-production
description: "Run Alan's modular ‘障眼法考据’ video-production pipeline from complete game-mission recording analysis to a verified Jianying Pro draft: use Apple Vision to parse a supplied recording from start to finish into an evidence-backed mission-flow and Claude handoff before manuscript writing; then adapt scripts, clone narration, build or freeze captions, match footage sentence by sentence with visual and OCR evidence, safely replace an equal-duration picture track, apply Alan's style, select BGM exclusively from the configured local music root, and perform acceptance QA. Use for 游戏任务录屏解析, Apple Vision剧情流程识别, 给Claude准备任务事实底稿, 一条龙制作, 从录屏到文稿再到剪映, 根据剪映字幕重新配画, 参考视频开头结尾, or continuing any verified production module."
---

# 障眼法视频一条龙

Produce a saved, reviewable Jianying draft while preserving recoverability and evidence for every stage.

Treat the pipeline as independently stoppable modules. Each active module must produce its own handoff artifacts and pass its own gate. Do not force later modules when the user only requested recording analysis, script preparation, picture rematching, BGM, or acceptance work.

## Operating contract

- Write a precise, machine-checkable success contract before any production mutation. Every success claim must name the objective check that proves it.
- Keep each work unit small enough to test one assumption before it can compound. Never combine unrelated narration, caption, picture, audio, and live-timeline mutations in one batch.
- Prefer automatic, objective verification. Use human visual or audio review only for irreducible aesthetic judgment, and never use it to replace an available file, timing, count, metadata, ASR, or duplication check.
- When complete game-mission recordings are supplied, analyze them before manuscript work. Use Apple Vision evidence to create a full chronological mission-flow and Claude handoff; do not invent missing dialogue or lore conclusions.
- Treat narration timing as the spine. Lock it before large picture edits.
- When the user has manually adjusted Jianying captions, treat the live timing and its exported SRT snapshot as the sole authority for picture matching. Do not rerun Manuscript Match, semantic resegmentation, duplicate repair, or caption styling unless explicitly requested.
- Resume from verified existing artifacts. Do not regenerate accepted narration, captions, or picture tracks merely to follow the nominal order.
- Preserve the user's open browser and Jianying state. Re-query UI after every meaningful action.
- Keep the previous picture track, subtitle backup, and generated media recoverable until final QA passes.
- Resolve the BGM root from `AI_VIDEO_MUSIC_ROOT`, defaulting to `$HOME/Music`. Use BGM source files exclusively from that directory or its subdirectories. Resolve symlinks before checking provenance. Never extract BGM from footage, generate it, download it, or substitute a file from another directory.
- Permit edited chapter copies and masters under the run directory only when every audible source is recorded in `audio/bgm_manifest.json` and resolves to a regular file inside the configured BGM root.
- If the configured BGM root has no suitable track, stop the BGM phase and ask the user to add or choose music there. Do not weaken this rule with a waiver.
- Do not export a final video, publish, upload, delete source data, or replace an unrecoverable asset unless the user explicitly authorizes that action.
- Never report a live-project change until it is visible in Jianying. Distinguish `generated`, `downloaded`, `imported`, `applied`, `project updated`, and `exported`.
- Never report final integrated LUFS without measuring an exported mix.
- For a full picture rebuild, preserve captions, narration, and BGM by rendering one equal-duration, video-only master and applying it with Jianying `替换片段`. Never rebuild the live timeline by deleting or re-adding protected lanes.
- Import live replacement media from a stable regular-file path, preferably a hardlink under `AI_VIDEO_MEDIA_ROOT`, defaulting to `$HOME/Movies/JianyingMedia`. Do not use a symlink or `/tmp` path as the lasting Jianying source.
- Continue through non-blocking uncertainties using documented best judgment. Stop only when a missing reference transcript, target project, or rights decision would materially change the result.

## Load the required modules

Read and follow each installed skill only when its phase is active:

1. `voxcpm-batch-dubbing` for narration generation.
2. `jianying-dubbing-postproduction` for audio placement, Manuscript Match, caption styling, cleanup, and SRT backup.
3. `jianying-sentence-visual-matching` for exhaustive sentence-to-shot retrieval, match-sheet auditing, and picture-track rebuilding.
4. `jianying-zhangyanfa-style` for Alan's narrative, subtitle, audio, evidence-card, and picture grammar.
5. `jianying-acceptance-polish` for the edit ledger, technical audit, focused refinements, and final pre-export QA.
6. Read and follow `computer-use` before live Jianying or Chrome interaction. Read `browser` before controlling a browser tab.

The active module's non-negotiable rules take precedence over shortcuts in this umbrella workflow.

## Start or resume a run

1. Inspect the workspace, mentioned files, open VoxCPM page, open Jianying draft, and existing output folders.
2. Identify the newest verified artifact for each phase: recording probe, Vision frame index, mission-flow handoff, clean manuscript, segments, WAV manifest, SRT, match sheet, picture-only render, BGM manifest, ledger, and acceptance report.
3. Recursively inventory the configured BGM root before planning BGM. Ignore library databases and non-media files. Record the absolute resolved path for every candidate actually used.
4. Define one concrete deliverable, explicit in-scope and out-of-scope boundaries, and measurable success criteria. Bind every criterion to a check ID. Keep the resolved BGM source root in the request contract.
5. Run `scripts/init_run.py` with the title, objective, deliverable, criterion/check pairs, and out-of-scope boundaries. For an existing run, update its contract instead of creating duplicate folders.
6. Complete `verification_plan.json`, including required check `bgm_sources_within_music`, then run `scripts/validate_run.py RUN_DIR --contract-only`. Do not mutate production state until this passes.
7. Write resolved paths, `bgm_source_root`, and the current phase to `run_manifest.json`.
8. Create a recoverable project/picture/subtitle state before any replacement or deletion.

Read [references/pipeline.md](references/pipeline.md) for phase inputs, gates, and recovery behavior.
Read [references/verification.md](references/verification.md) before defining batches or objective checks.
Read [references/game-recording-vision-analysis.md](references/game-recording-vision-analysis.md) whenever the user supplies a full game recording, asks to parse a mission from start to finish, or wants a fact package for Claude. This module precedes manuscript work and may be delivered independently.
Read [references/ocr-caption-visual-workflow.md](references/ocr-caption-visual-workflow.md) whenever matching or rebuilding pictures from captions, especially after the user has manually adjusted subtitles or supplied a reference video.

## Work in bounded batches

1. Add one row to `batch_ledger.tsv` before each batch. State the single assumption, exact scope, one mutation class, applicable `unit_limit_key`, actual `unit_count`, verifier, and expected result.
2. Respect the contract's unit limits. Default to one VoxCPM segment, one match row, one card, one BGM section, one live-timeline mutation, or at most ten caption rows per batch.
3. Apply only that batch.
4. Run its named objective check with `scripts/run_objective_checks.py RUN_DIR --check-id CHECK_ID`.
5. Record measured output and evidence path. Mark the batch `pass` only when the check passes.
6. On failure, stop that phase, repair or revise the assumption, and rerun the same check. Do not start the next batch while a required batch is open or failed.

## Execute the pipeline

### 1. Analyze complete game-mission recordings

- Probe every recording and cover it from its first through final frame, including menus, loading, travel, retries, combat, rewards, and ending state.
- Extract coarse, scene-change, and dense frames, then run `scripts/vision_mission_analyzer.swift` with Apple Vision.
- Preserve OCR regions and confidence, faces, saliency, classifications, feature-distance changes, source timecodes, and evidence-frame paths.
- Deduplicate persistent subtitles and objectives into chronological events.
- Build `recording_analysis/mission_flow.tsv` with player action, game response, objective changes, outcomes, fact/inference labels, confidence, and unresolved gaps.
- Visually inspect contact sheets and correct Vision errors before completing the module.
- Produce `recording_analysis/claude_handoff.md` and `.json`. Do not generate narration copy during this phase.
- Stop and report `audio_transcript_needed` when spoken-only dialogue cannot be recovered from visible subtitles.

### 2. Prepare the manuscript

- Extract narration only; remove document titles, page furniture, production notes, and shot instructions.
- Preserve wording, punctuation, names, quotes, and the intended narrative order.
- Split at semantic boundaries, normally 100–350 Chinese characters per VoxCPM segment.
- Verify that segments cover the narration exactly once.
- Produce `clean_script.md` and `segments.md` before generation.

### 3. Generate and verify narration

- Use Ultimate Cloning with the exact transcript of the reference WAV.
- Generate Target Text sequentially and save each changed result immediately as numbered WAV.
- Run signal and ASR checks per segment. Retry or split missing, repeated, truncated, silent, or invalid results.
- Produce a final WAV manifest. State subjective timbre/emotion limitations honestly.

### 4. Build the narration and caption spine

- Import numbered WAVs in order and append each at the current project end.
- Run Manuscript Match with the clean narration only.
- Apply the established ordinary-caption preset, then repair semantic breaks and adjacent duplicates.
- Export or retain an SRT backup before risky caption work.
- Freeze the verified narration/caption timing before picture retrieval.
- If the captions are already user-adjusted, export a fresh immutable SRT snapshot, record its caption count and final end time, and skip all automatic caption mutation.

### 5. Retrieve and match visuals

- Probe every source, then build coarse and dense visual indexes plus an OCR index of visible Chinese and English text. Use `scripts/vision_ocr.swift` on extracted frames when macOS Vision is available.
- Treat every caption or short semantic unit as an independent retrieval problem. Preserve every caption exactly once; merge adjacent lines only for visual continuity and normally keep a unit under six seconds.
- Retrieve at least three distinct candidates per unit whenever possible. Rank subject, action, location, emotion, narrative function, exact on-screen dialogue/evidence, source chronology, transition safety, and prior reuse.
- Penalize menus, task lists, settings, logos, loading screens, long UI text, black/overexposed transitions, source heads/tails, repeated emotional shots, and footage that merely shares a character while contradicting the sentence.
- If local candidates remain weak after the expansion ladder, use the external-sourcing rules in [references/external-sourcing.md](references/external-sourcing.md).
- Record exact source in/out, candidate scores, confidence, retry round, reuse group, and selection reason.
- Audit the completed match sheet before applying it.
- When a reference video is supplied, inspect its opening and ending separately and transfer only its structural grammar: hook density, evidence timing, emotional release, and final-image function. Do not copy its shot order blindly.
- Prefer an equal-duration, picture-only intermediate render for large deterministic rebuilds; replace the main picture clip without touching audio, BGM, or caption lanes.

### 6. Apply 障眼法 grammar

- Structure the cut as emotional hook → red central question → setup → claim → proof → return to character → slower reinterpretation → red closing thesis.
- Use story/game footage as the default layer and evidence cards only where they prove a claim.
- Reserve red for questions, proof, reversals, and the final thesis.
- Keep narration dominant, source/game audio muted by default, and BGM chapter-based.
- Preserve the target project's native resolution and existing 60 fps cadence when applicable.
- Force an opening audit: first frame non-black, recognizable motion/face/stakes inside three seconds, thesis or evidence inside the early hook, and no logo/menu lead-in.
- Force an ending audit: coherent emotional callback, slower visual cadence, intentional non-black final frame, and a last image that visually completes the spoken farewell.

### 7. Select and prepare BGM

- Search only the configured BGM root recursively. Base selection on the manuscript's rhetorical chapters and auditioned local candidates.
- Never treat source-video audio, a downloaded file, a generated tone, or music copied from another directory as eligible BGM.
- Record one manifest row per chapter with `chapter`, `mood`, absolute `source`, `source_start`, `duration`, derived `file`, and intended Jianying gain.
- Allow trimming, looping, fades, loudness preparation, and chapter/master renders under `RUN_DIR/audio/`; these are derivatives, not new source provenance.
- Add the required `bgm_sources_within_music` check using `bgm_sources_within_root` and run it before importing any derivative BGM into Jianying.
- If the provenance check fails, remove the invalid derivative and rebuild from an eligible Music-folder source. Do not import or apply the failed asset.

### 8. Run acceptance polish

- Convert every issue into `priority, category, timeline_range, planned_edit, acceptance_test, status` before editing.
- Apply the learned refinement patterns in [references/refinement-patterns.md](references/refinement-patterns.md) when the same risks occur.
- Make reversible edits, verify them in the live timeline, and mark each ledger row `done` only with visible or measured evidence.
- Save the draft. Leave the playhead at a useful review point.

## Quality gates

Do not advance past a failed gate:

- **Recording analysis:** source probe and sampling coverage pass; every input frame has a Vision result or explicit error; the mission-flow covers the full recording with evidence-linked rows; Claude handoffs exist; missing audio-only dialogue and uncertain OCR are unresolved rather than invented.
- **Narration:** every numbered WAV exists, opens, has nonzero duration, and covers its segment in order.
- **Captions:** coverage reaches the narration end; ordinary style is consistent; adjacent exact duplicates equal zero; an SRT backup exists when replacement risk exists.
- **Match plan:** every spoken unit has a selected source or intentional card; low-confidence rows completed a retry pass; reuse and duration audits pass.
- **Match plan evidence:** every row is backed by visual or OCR evidence, has three distinct candidates when possible, and records why the selected frame proves or supports the sentence.
- **Picture:** resolution, frame rate, frame count, and duration are plausible; strict black-gap detection passes; the render has no audio stream; live replacement filename is visible.
- **Audio provenance:** every BGM manifest source exists, is absolute, resolves inside the configured BGM root, and passes `bgm_sources_within_music`. No external, generated, downloaded, or footage-extracted source is allowed.
- **Audio mix:** narration remains foreground; BGM settings are verified on the intended track; no final-LUFS claim without export measurement.
- **Ending:** final frame is intentional and non-black; any requested breathing room is present.
- **Live replacement:** Jianying shows the new stable filename, unchanged total timecode, protected caption/narration/BGM lanes, and saved QA screenshots at the opening, a representative middle point, and the final spoken line. Reopen the draft when persistence is uncertain.
- **Contract:** every success criterion has a unique check ID present in `verification_plan.json`; contract-only validation passes before production edits.
- **Batch closure:** every required batch is `pass` or explicitly `waived` with a reason; no failed assumption is carried into a later phase.
- **Delivery:** `scripts/validate_run.py RUN_DIR` executes the objective plan and passes. Documentation alone cannot waive a required objective check.

Read [references/output-contract.md](references/output-contract.md) for required artifacts and reporting vocabulary.

## Finish

Return a concise completion summary with:

- live Jianying draft name and exact total timecode;
- completed recording-analysis range and links to the Claude handoff when that module was active;
- completed phase range and any intentionally skipped phase;
- narration, caption, visual-match, BGM, and ending QA facts;
- unresolved human-audition or rights questions;
- whether a final export was authorized and performed;
- clickable links to `run_manifest.json`, the edit ledger, acceptance report, latest picture render, BGM, SRT, and QA images.
- When superseded renders are no longer referenced after live QA, move them to a dated Trash folder instead of deleting them permanently. Keep the current render, its render segments, and the stable Jianying media hardlink until user acceptance.

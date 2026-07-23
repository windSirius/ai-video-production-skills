---
name: zhangyanfa-video-production
description: "Run Alan's modular ‘障眼法考据’ video-production pipeline from complete game-mission recording analysis to a verified Jianying Pro draft: use Apple Vision to parse a supplied recording from start to finish into an evidence-backed mission-flow and Claude handoff before manuscript writing; then adapt scripts, clone narration, build or freeze captions, match footage sentence by sentence with visual and OCR evidence, safely replace an equal-duration picture track, apply Alan's style, select BGM exclusively from the configured local music root, and perform acceptance QA. Use for 游戏任务录屏解析, Apple Vision剧情流程识别, 给Claude准备任务事实底稿, 一条龙制作, 从录屏到文稿再到剪映, 根据剪映字幕重新配画, 参考视频开头结尾, or continuing any verified production module."
---

# 障眼法视频一条龙

Produce a saved, reviewable Jianying draft while preserving recoverability and evidence for every stage.

Treat the pipeline as independently stoppable modules. Each active module must produce its own handoff artifacts and pass its own gate. Do not force later modules when the user only requested recording analysis, script preparation, picture rematching, BGM, or acceptance work.

## Operating contract

- Treat `scripts/harness.py` as the sole production-order authority after a run contract exists. Run `resume`, obey its one `next_action`, obtain a token with `prepare` → `begin`, then close that same action with `verify` or `fail`. Never mutate the live project outside an active token.
- Treat every control labeled 「试试剪映助手」 or 「剪映助手」 as a permanent forbidden UI target in every phase. Never click, open, dismiss, focus, test, or use it. No token or recipe can authorize it. If it obscures a required control, use a verified route that does not target the assistant; if none exists, fail and block the live action.
- Require a fresh non-assistant route preflight before every live token. Bind it to the action's registered route ID, action/recipe, pre-state, evidence hashes, and an exact sequence of strongly identified semantic targets with accessibility ancestry and an allowed window signature for each step; role-only, unrelated, or ad-hoc route claims are invalid. Every live UI operation then needs a fresh hit-test carrying current bounds, hit point, ancestry, per-step window signature, and visible forbidden regions plus one-use `authorize-ui-step` approval before execution and immediate `complete-ui-step` evidence afterward. Only the harness-managed trace may close `verify` or `fail`. Missing, unidentifiable, changed, extra, overlapping, self-authored, or assistant-targeted interaction evidence fails closed.
- Do not hand-edit harness state, events, checkpoints, or harness-managed `H####` batch rows. Do not convert failed attempts into retrospective waivers.
- If a tool response is lost after `begin`, inspect and resolve the pending action. Never repeat the mutation merely because its result is unknown.
- If the user manually advances Jianying, do not undo the user's work or pretend the agent performed it. With explicit user authority, use `harness.py adopt-live-baseline` from a ready run, or from an untouched open live action whose managed trace proves that zero agent UI steps were authorized or completed; then resume from the newly captured live state.
- Write a precise, machine-checkable success contract before any production mutation. Every success claim must name the objective check that proves it.
- Keep each work unit small enough to test one assumption before it can compound. Never combine unrelated narration, caption, picture, audio, and live-timeline mutations in one batch.
- Prefer automatic, objective verification. Use human visual or audio review only for irreducible aesthetic judgment, and never use it to replace an available file, timing, count, metadata, ASR, or duplication check.
- When complete game-mission recordings are supplied, analyze them before manuscript work. Use Apple Vision evidence to create a full chronological mission-flow and Claude handoff; do not invent missing dialogue or lore conclusions.
- Treat narration timing as the spine. Import every narration clip first, measure Jianying's live integer-frame end, and freeze that value before large picture or BGM work. Never derive the final frame clock only from the arithmetic sum of WAV durations because per-clip import quantization can accumulate.
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
- Continue through non-blocking uncertainties using documented best judgment. Stop when the harness blocks, or when a missing reference transcript, target project, authority, or rights decision would materially change the result.

Read [references/harness.md](references/harness.md) before initializing, resuming, or mutating any production run. Its transaction state, recipe registry, failure budget, caption transaction, frame clock, and final close order are mandatory. A harness block is a real stop condition, not a suggestion to improvise another UI route.

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

1. For an existing run, first run `python3 scripts/harness.py resume RUN_DIR`. If it reports a prepared, in-progress, repair, blocked, or complete state, obey that single result before inspecting anything else.
2. Inspect only inputs and artifacts not already covered by a valid phase seal. Identify the newest artifact that has both a file and passing objective evidence; do not repeatedly inventory an unchanged workspace.
3. Recursively inventory the configured BGM root before planning BGM. Ignore library databases and non-media files. Record the absolute resolved path for every candidate actually used.
4. Define one concrete deliverable, explicit in-scope and out-of-scope boundaries, and measurable success criteria. Bind every criterion to a check ID. Keep the resolved BGM source root in the request contract.
5. Run `scripts/init_run.py` with the title, objective, deliverable, criterion/check pairs, and out-of-scope boundaries. It creates the harness for a new run. For an existing run, update its contract deliberately instead of calling initialization as an implicit contract rewrite; with explicit user authority run `harness.py rebind` to record the change and invalidate prior phase seals.
6. Complete `verification_plan.json`, including required check `bgm_sources_within_music`, then run `scripts/validate_run.py RUN_DIR --contract-only`. Do not mutate production state until this passes.
7. Run `python3 scripts/harness.py resume RUN_DIR` again. Do not proceed until it returns one legal `prepare` action for the current phase.
8. Create a recoverable project/picture/subtitle state before any replacement or deletion.

Read [references/pipeline.md](references/pipeline.md) for phase inputs, gates, and recovery behavior.
Read [references/verification.md](references/verification.md) before defining batches or objective checks.
Read [references/game-recording-vision-analysis.md](references/game-recording-vision-analysis.md) whenever the user supplies a full game recording, asks to parse a mission from start to finish, or wants a fact package for Claude. This module precedes manuscript work and may be delivered independently.
Read [references/ocr-caption-visual-workflow.md](references/ocr-caption-visual-workflow.md) whenever matching or rebuilding pictures from captions, especially after the user has manually adjusted subtitles or supplied a reference video.

## Work in bounded batches

1. Use `scripts/harness.py prepare`; never append or close a harness batch row manually. State one assumption, exact scope, registered mutation and recipe, applicable unit limit, fresh pre-state, a verifier that observes that mutation, and `--ui-route-preflight` for every live action.
2. Run `begin` with the issued token. For every planned UI step, capture a current semantic hit-test and run `authorize-ui-step` in one execution envelope, perform only that returned step, and immediately close it with `complete-ui-step` plus fresh evidence. A stale hit-test authorizes nothing and is retryable without a user unblock; recapture it instead of blocking the run. A token authorizes one mutation class; a UI-step authorization authorizes exactly one target and cannot cover an exploratory sequence.
3. Run `verify` with a fresh post-state, evidence, and the canonical harness-managed `--ui-interaction-trace`. Live mutations must use `harness_live_state_delta`; an unrelated file count, provenance check, or agent-authored “not clicked” trace cannot prove a UI route was safe. Offline checks must declare `observes_mutations` and `observed_targets` in `verification_plan.json`.
4. On failure, undo immediately and prove restoration. Use `fail --rolled-back` or a failed `verify` with rollback evidence. The same batch receives at most one registered-recipe retry; a second identical failure, three phase failures, or six run failures blocks the harness.
5. After two consecutive successful identical narration quick-add actions, promote the remaining enumerable items to `append_narration_loop` with a per-item media identity and cumulative-end manifest. Stop and undo the first mismatching item.
6. Seal a completed phase with `harness.py advance`, passing every gate check and accepted artifact. Reuse an unchanged seal on resume.

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
- Permit the first imported WAV to create the narration track (`0 → 1`); every later single append must keep the track count at one while increasing only the clip count.
- After the final WAV is visible, measure and record `narration_end_timecode` independently from the overall project duration, then run `scripts/freeze_live_timing_contract.py`. Use this contract for subsequent picture and BGM renders; keep the source-duration sum only as diagnostic metadata. Caption cues govern sentence-level boundaries; when captions end before narration, hold the intentional final picture through the narration end. If captions extend more than one frame beyond narration, stop and repair the timing evidence.
- Run Manuscript Match with the clean narration only.
- Apply the established ordinary-caption preset, then repair semantic breaks and adjacent duplicates.
- Apply the established caption-ending rule to the canonical SRT: remove `，。；：,.;:` at the effective end, including immediately before trailing `」』”’）》〉）】`; preserve `？！?!`. Bind every semantic replacement or canonical export to an `srt_integrity` check that declares this exact policy.
- Export or retain an SRT backup before risky caption work. Use the top-right export dialog with video/audio off and `字幕导出 → SRT → Unicode / UTF-8`. When the live raw-caption count cannot be measured without that export, use the registered `caption_backup_export` action with only `caption_count` declared unresolved; late-bind the numeric count from the fresh exported SRT before any caption mutation.
- After offline AI resegmentation and SRT audit, use only `文本 → 新建文本 → 导入本地字幕`. Verify the audited filename becomes a `本地字幕` material card, drag that exact card into the timeline, prove caption tracks `1 → 2`, remove only the verified old track, then prove `2 → 1`. A material card alone is not a timeline change.
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
- **Harness:** no contract/plan/artifact drift, open token, pending repair, exhausted failure budget, or blocked state; every live mutation has fresh before/after evidence, an exact protected-state comparison, a verified non-assistant route, and a complete interaction trace with zero Jianying Assistant targets.
- **Batch closure:** every executed harness batch has exact status `pass`; an optional pre-declared `waived` row requires explicit reason and authorization reference. An untouched live action may be `cancelled_no_mutation` only when its managed trace proves zero agent UI authorizations and completions and an explicitly authorized user-authored baseline checkpoint exists. Failed or partially executed production attempts may not be washed into retrospective waivers or cancellations.
- **Delivery:** the final verified actions are timeline cleanup → canonical SRT export → opening/middle/ending evidence → save/reopen persistence check. Then `scripts/harness.py close RUN_DIR` executes the full objective plan and `validate_run.py`. Documentation alone cannot waive a required objective check.

Read [references/output-contract.md](references/output-contract.md) for required artifacts and reporting vocabulary.

## Finish

Return a concise completion summary with:

- live Jianying draft name and exact total timecode;
- completed recording-analysis range and links to the Claude handoff when that module was active;
- completed phase range and any intentionally skipped phase;
- narration, caption, visual-match, BGM, and ending QA facts;
- unresolved human-audition or rights questions;
- whether a final export was authorized and performed;
- harness lifecycle, final close result, and any consumed failure budget;
- clickable links to `run_manifest.json`, the edit ledger, acceptance report, latest picture render, BGM, SRT, and QA images.
- When superseded renders are no longer referenced after live QA, move them to a dated Trash folder instead of deleting them permanently. Keep the current render, its render segments, and the stable Jianying media hardlink until user acceptance.

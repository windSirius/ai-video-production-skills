# Module 01: Apple Vision game-recording analysis

> **历史 Harness 参考。** 本文适用于既有 `run_manifest.json` 工程；其中 workflow v2/v2.2 是旧流程编号，不等于当前 `production_contract_version=2`。新项目使用 [十三阶段总控](../SKILL.md) 和 [当前提交契约](submission-contracts-v2.md)。保留本文用于旧工程核验，迁移按 [旧项目迁移](legacy-migration.md) 执行。

Use this module before manuscript work when the user supplies a complete game mission recording. Its job is to create a chronological, evidence-backed fact base for later script writing. Do not write commentary copy in this module.

## Boundary

Input:

- one or more complete mission recordings;
- optional mission name, game version, protagonist choice, or user notes.

Output:

- media probe and source inventory;
- full-duration frame coverage;
- Apple Vision OCR and visual observations;
- deduplicated dialogue, objective, location, and UI changes;
- a start-to-finish mission-flow timeline;
- contact sheets and evidence-frame paths;
- `claude_handoff.md` and `claude_handoff.json`.

Do not generate a narration manuscript, interpret lore as fact, edit Jianying, or choose BGM. Apple Vision does not hear spoken-only dialogue. When important speech has no visible subtitle, mark it `audio_transcript_needed`; do not invent the line.

## Required artifacts

Store one analysis package under `recording_analysis/`:

```text
recording_analysis/
  source_manifest.json
  media_probe.json
  sampling_plan.json
  frames/
    coarse/
    scene/
    dense/
  frame_input.tsv
  vision_frame_index.tsv
  ocr_events.tsv
  mission_flow.tsv
  unresolved.tsv
  contact_sheets/
  claude_handoff.md
  claude_handoff.json
  qa_report.json
```

Preserve source files unchanged. Use absolute source paths and stable frame IDs.

## Step 1: Probe and define coverage

1. Run `ffprobe` for duration, dimensions, frame rate, stream count, audio presence, and start time.
2. Record whether the recording includes game subtitles, streamer overlays, watermarks, black/loading sections, menus, and multiple mission parts.
3. Define the analysis interval from the first source frame through the final source frame. Do not trim menus, travel, deaths, retries, loading, or rewards before they are classified.
4. Split recordings longer than 30 minutes into overlapping analysis chunks of 10–20 minutes. Keep at least two seconds of overlap and merge by source timecode later.

Gate: every source has a probe record and the union of planned intervals covers its complete duration.

## Step 2: Extract a two-pass frame set

Pass A, complete coverage:

- extract a coarse frame every 2 seconds by default;
- additionally extract the first and last 30 seconds at one-second intervals;
- extract ffmpeg scene-change candidates using a conservative scene score;
- retain black/loading frames because they are part of the task flow.

Pass B, event refinement:

- after the first Vision pass, find OCR changes, objective updates, dialogue changes, large feature-distance jumps, new faces, and likely interaction/combat boundaries;
- re-extract at 0.5-second intervals within at least three seconds on each side of those candidates;
- use 0.25-second sampling only for very fast dialogue, cutscene, or choice transitions.

Write `frame_input.tsv` with:

```text
frame_id  source_id  timestamp_s  sampling_pass  path
```

Gate: timestamps are ordered, frame paths exist, and the maximum unrepresented interval does not exceed the declared coarse interval outside dense regions.

## Step 3: Run Apple Vision

Compile and run `scripts/vision_mission_analyzer.swift` on the frame input. The analyzer must use Apple Vision for:

- accurate Simplified Chinese and English text recognition;
- text bounding boxes and confidence;
- face detection;
- attention-based saliency;
- image classification labels;
- image feature prints and distance from the previous frame.

Do not reduce Vision output to OCR text alone. Preserve frame path, source timecode, regions, confidences, and visual-change evidence in `vision_frame_index.tsv`.

Gate: every input frame has exactly one result row or an explicit error row.

## Step 4: Normalize persistent screen text

Game subtitles and objectives often persist across many samples. Convert raw OCR into events:

1. Normalize whitespace and obvious OCR punctuation noise without rewriting wording.
2. Group near-identical text across consecutive frames.
3. Record first seen, last seen, best-confidence text, best evidence frame, region, and event type.
4. Keep separate rows when the speaker, objective, choice, location, result, or UI function changes.
5. Preserve uncertain characters with the original OCR alternatives and confidence.

Use event types:

```text
dialogue | speaker_name | objective | location | interaction_prompt |
choice | tutorial | combat_ui | reward | system_notice | menu | unknown
```

Gate: repeated persistent text is collapsed, but no distinct dialogue or objective change is lost.

## Step 5: Build the mission-flow timeline

Create `mission_flow.tsv` with one chronological row per meaningful game-state interval:

```text
step_id
source_id
start_s
end_s
phase_type
location
characters
visible_text
player_action
game_response
objective_before
objective_after
result
evidence_frames
fact_or_inference
confidence
unresolved
```

Allowed `phase_type` values:

```text
loading | menu | cutscene | dialogue | exploration | interaction | choice |
puzzle | combat | boss | objective_update | reward | transition | retry | unknown
```

Rules:

- cover the recording from start to finish, including travel and loading;
- create a boundary when the task objective, location, participants, interaction mode, combat state, or narrative beat changes;
- distinguish player action from game response;
- write visible facts as facts and interpretation as inference;
- never infer an off-screen action or unheard line without evidence;
- link every row to at least one evidence frame;
- record deaths, retries, detours, repeated attempts, optional dialogue, and skipped sections instead of silently flattening them.

Gate: rows are ordered, nonnegative, nonoverlapping unless explicitly linked, and cover the full analysis interval without an unexplained gap larger than the coarse sampling interval.

## Step 6: Inspect the recording visually

Generate contact sheets for:

- the full recording at coarse intervals;
- every mission-flow chapter;
- every low-confidence or unresolved interval;
- opening, final objective resolution, rewards, and ending state.

Look at the images. OCR and classifications are retrieval evidence, not a substitute for visual inspection. Correct false boundaries, OCR contamination from overlays, and labels that contradict the frame.

Gate: every mission-flow row has been visually confirmed or explicitly marked low confidence.

## Step 7: Produce the Claude handoff

`claude_handoff.md` must contain:

1. source and version context;
2. a concise mission overview;
3. a complete chronological walkthrough with source timecodes;
4. all visible dialogue and objective changes in order;
5. characters, locations, objects, choices, fights, outcomes, and rewards;
6. repeated attempts, optional paths, and recording-specific noise;
7. facts suitable for script writing;
8. interpretations that require lore research;
9. unresolved OCR, missing audio-only dialogue, and other evidence gaps;
10. direct paths to `mission_flow.tsv`, `ocr_events.tsv`, and contact sheets.

`claude_handoff.json` must expose the same material as structured arrays so another model can filter it without reparsing prose.

Do not instruct Claude to treat inference as canon. Label each statement `visual_fact`, `visible_text`, `recording_action`, `inference`, or `unresolved`.

## Acceptance checks

Require objective checks for:

- source manifest and media probe are nonempty;
- frame input and Vision output row counts agree;
- `mission_flow.tsv` contains the first and final source timecodes;
- every mission-flow row has evidence frames;
- no unexplained coverage gap exceeds the declared limit;
- the Claude Markdown and JSON handoffs exist and are nonempty;
- unresolved speech or OCR is reported rather than silently guessed.

Use `tsv_row_count_match` for `frame_input.tsv` versus `vision_frame_index.tsv`. Use `mission_flow_coverage` with the probed `duration_s`, the coarse sampling interval as `max_gap_s`, and required fields including `evidence_frames`, `fact_or_inference`, and `confidence`.

Only after this module passes may manuscript generation begin. The user may also stop here and send the handoff package to Claude.

---
name: voxcpm-batch-dubbing
description: "Automate long-form voice cloning and repaired narration masters in a local VoxCPM or VoxCPM2 Gradio app: preserve canonical text separately from pronunciation proxies, split and generate sequentially, save every candidate, enforce signal/ASR/similarity gates (0.90 by default for Alan's workflow), rerun weak segments, repair clicks/silence/loudness, assemble the final WAV, and emit hash-bound manifests. Use for VoxCPM batch dubbing, voice cloning, long-script narration, similarity QA, targeted re-generation, or audio repair."
---

# VoxCPM Batch Dubbing

Turn a prepared reference voice and a long script into numbered, checked WAV clips without losing browser state or overwriting earlier results.

## Non-negotiable rules

- Treat `参考音频内容文本 / Transcript of Reference Audio` as the exact transcript of the reference audio.
- Treat `Target Text` as the new text to synthesize in the current iteration.
- Never put the narration script into the reference-transcript field unless the user says the reference audio itself contains that script.
- In Ultimate Cloning mode, Control Instruction is disabled. Do not describe the transcript field as Control Instruction in reports.
- Save the generated WAV before replacing Target Text. A new result replaces the previous result in the Gradio page.
- Do not claim to have subjectively listened when no audio-perception tool is available. Use transcription and signal checks, then state the limitation. Ask the user to audition uncertain pronunciation, emotion, or timbre.
- Preserve a user-prepared browser session. Do not open a blank page when the prepared tab can be controlled.
- Keep `canonical_text` and `generation_text` separate. Pronunciation proxies such as `胡寄生` may be submitted to VoxCPM, but the canonical manuscript, subtitle, and manifest must retain `槲寄生`.
- For Alan's production workflow, require normalized ASR similarity `>= 0.90` for every accepted segment unless the user explicitly sets a stricter threshold. A strong average never excuses one failed segment.
- Never overwrite an accepted segment with a new attempt. Keep attempts separately, promote exactly one file to the canonical numbered path, and record both hashes.
- A stitched raw generation is not the final master. Run targeted repair, stable-loudness normalization, full decode, and secondary ASR before handoff.

## 1. Establish the control surface

1. Read and follow the Browser skill before browser automation.
2. Prefer a controllable existing tab. If the user prepared the page in Chrome and Browser cannot see it, read and use the Computer Use skill to operate that Chrome window.
3. Re-query UI state after every meaningful action. If the user interacts with the app, discard stale element indexes and fetch a fresh state before continuing.
4. Keep the service running after completion unless the user asks to stop it.

Read [references/voxcpm-gradio.md](references/voxcpm-gradio.md) for current labels, launch patterns, and recovery notes.

## 2. Resolve inputs and output scope

Identify:

- VoxCPM project and launch command, or the already-running URL;
- reference audio path;
- exact reference-audio transcript when Ultimate Cloning is requested;
- source narration document;
- output directory and naming scheme;
- whether Target Text already contains the first prepared segment.
- the canonical-text path, pronunciation map, minimum similarity, loudness target, and whether an earlier repaired master already exists.

Use the applicable artifact skill to read the source document. For PDF, render and inspect pages as required by the PDF skill; for DOCX, use the Documents skill. Strip titles, page numbers, headers, and layout artifacts from narration text.

## 3. Configure Ultimate Cloning correctly

1. Upload the reference audio when it is not already loaded.
2. Enable `Ultimate Cloning Mode`.
3. Wait until the reference-transcript field appears.
4. Fill the exact reference transcript and verify the visible value.
5. Fill only the current narration segment into Target Text.
6. Leave advanced settings unchanged unless the user specifies them or a retry requires a documented adjustment.

Auto-ASR may run after Ultimate mode is enabled. If the user supplied an exact transcript, refill and verify it before clicking Generate so the submitted job captures the correct value.

## 4. Segment the narration

Split at semantic boundaries, not arbitrary character positions:

- Keep complete sentences and closely related paragraphs together.
- Prefer roughly 100-350 Chinese characters per segment; shorten dense or failure-prone passages.
- Preserve punctuation, names, quoted dialogue, Latin acronyms, and numerals.
- Treat the existing Target Text as segment 01 when the user already prepared it.
- Verify that ordered segments cover the source exactly once, excluding document-only titles and page furniture.

Write a compact `segments.md` or equivalent manifest in the output directory when the job has multiple segments.

Prefer `segments.json` as the machine authority. Each row should include `segment_id`, `canonical_text`, `generation_text`, source span and eventual accepted WAV hash. Read [references/repair-and-authority.md](references/repair-and-authority.md) before using pronunciation substitutions or choosing between old and new repaired masters.

## 5. Generate, save, and validate each segment

For each segment, in order:

1. Fetch fresh UI state.
2. Replace Target Text and verify the exact visible value.
3. Click Generate once.
4. Poll at intervals shorter than 60 seconds and keep the user informed during long MPS inference.
5. Wait until processing disappears and the generated-audio download URL changes.
6. Immediately save that URL as `01.wav`, `02.wav`, and so on. Direct local download with `curl -fsS <gradio-url> -o <file>` is valid; files do not need to appear in Chrome Downloads.
7. Run `scripts/qa_audio.py` on the saved file.
8. When SenseVoice is available, run `scripts/transcribe_sensevoice.py`, then run `scripts/audit_similarity.py` against `canonical_text`. Do not compare ASR to the pronunciation proxy.
9. Require per-segment similarity to meet the frozen threshold; for this workflow the default is `0.90`.
10. Proceed only after the file exists and validation passes.

Retry or split the segment when any of these occur:

- the download URL did not change;
- the file is empty, invalid, or has no audio stream;
- transcription shows a missing tail, repeated passage, or reordered sentences;
- there is an unexplained long silence or sustained clipping;
- the browser reports an error or the service disconnects.

Treat isolated ASR substitutions of proper nouns or homophones as uncertainty, not proof of a synthesis error. Confirm omissions and repetitions from surrounding coverage and the audio duration.

When a segment fails, retry only that segment. Prefer changing split boundaries or a documented pronunciation proxy before changing model settings. Preserve failed attempts under `attempts/<segment_id>/`, then promote the best verified candidate to `audio/<segment_id>.wav`.

## 6. Repair and assemble the master

1. Remove only verified clicks, excessive head/tail silence, clipped joins or abnormal loudness; do not denoise away breaths or consonants by default.
2. Assemble accepted numbered clips in order without time-stretching them.
3. Normalize to a stable spoken-loudness target and true-peak ceiling recorded in the run manifest. Preserve a pre-normalization master for recovery.
4. Run full decode, duration and clipping checks on the assembled WAV.
5. Run secondary ASR over the repaired master or every repaired segment and repeat the canonical-text similarity audit.
6. Record repair operations, input/output hashes and the exact promoted master in `repair_qa.json` and `audio_manifest.json`.

Do not select a file merely because its name contains `final` or `repaired`. The current master is the one whose SHA is bound by the latest passing manifest.

## 7. Finish and report

Verify:

- the expected number of numbered WAV files exists;
- every file is readable and has a nonzero duration;
- sample rate, channel count, and encoding are consistent;
- summed duration and total size are plausible;
- the last segment ends with the last words of the source;
- every segment reaches the frozen similarity threshold and the repaired master passes secondary ASR;
- `audio_manifest.json` identifies one canonical master SHA and does not point at an older repair run;
- the output directory and segment manifest are linked in the final response.

Report subjective-audio limitations separately from objective checks.

Treat the canonical numbered WAV files, `segments.json`, pronunciation map, ASR outputs, `repair_qa.json`, final master and `audio_manifest.json` as the handoff package for `jianying-dubbing-postproduction`.

## Cancellation

When the user asks to stop, cancel the active generation and stop only the exact VoxCPM `app.py` processes in scope. Resolve PIDs with a read-only process check first, terminate them, and verify that no matching process remains. Do not delete generated clips.

## Resources

- `references/voxcpm-gradio.md`: launch command, UI mapping, and recovery guidance.
- `references/repair-and-authority.md`: canonical/generation text separation, similarity, repair, loudness, and version-selection rules.
- `scripts/qa_audio.py`: format, duration, silence, and clipping-oriented checks.
- `scripts/transcribe_sensevoice.py`: load SenseVoice once and transcribe multiple generated clips.
- `scripts/audit_similarity.py`: deterministic normalized similarity gate for canonical text versus ASR.

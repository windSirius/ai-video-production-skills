---
name: voxcpm-batch-dubbing
description: "Automate long-form voice cloning and batch narration in a local VoxCPM or VoxCPM2 Gradio app: start or attach to the app, use Ultimate Cloning with a reference WAV and its transcript, read scripts from PDF/DOCX/TXT/Markdown, split them into natural segments, generate each Target Text sequentially, save every WAV before it is replaced, run signal and ASR quality checks, and produce a final manifest. Use for VoxCPM batch dubbing, reference-voice cloning, long-script voiceover, repeated Target Text generation, or continuation of a user-prepared VoxCPM browser session."
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

## 5. Generate, save, and validate each segment

For each segment, in order:

1. Fetch fresh UI state.
2. Replace Target Text and verify the exact visible value.
3. Click Generate once.
4. Poll at intervals shorter than 60 seconds and keep the user informed during long MPS inference.
5. Wait until processing disappears and the generated-audio download URL changes.
6. Immediately save that URL as `01.wav`, `02.wav`, and so on. Direct local download with `curl -fsS <gradio-url> -o <file>` is valid; files do not need to appear in Chrome Downloads.
7. Run `scripts/qa_audio.py` on the saved file.
8. When SenseVoice is available, run `scripts/transcribe_sensevoice.py` and compare coverage, order, and the final words against the source segment.
9. Proceed only after the file exists and validation passes.

Retry or split the segment when any of these occur:

- the download URL did not change;
- the file is empty, invalid, or has no audio stream;
- transcription shows a missing tail, repeated passage, or reordered sentences;
- there is an unexplained long silence or sustained clipping;
- the browser reports an error or the service disconnects.

Treat isolated ASR substitutions of proper nouns or homophones as uncertainty, not proof of a synthesis error. Confirm omissions and repetitions from surrounding coverage and the audio duration.

## 6. Finish and report

Verify:

- the expected number of numbered WAV files exists;
- every file is readable and has a nonzero duration;
- sample rate, channel count, and encoding are consistent;
- summed duration and total size are plausible;
- the last segment ends with the last words of the source;
- the output directory and segment manifest are linked in the final response.

Report subjective-audio limitations separately from objective checks.

Treat the numbered WAV files, `segments.md`, QA results, and final manifest as the handoff package for `jianying-dubbing-postproduction`.

## Cancellation

When the user asks to stop, cancel the active generation and stop only the exact VoxCPM `app.py` processes in scope. Resolve PIDs with a read-only process check first, terminate them, and verify that no matching process remains. Do not delete generated clips.

## Resources

- `references/voxcpm-gradio.md`: launch command, UI mapping, and recovery guidance.
- `scripts/qa_audio.py`: format, duration, silence, and clipping-oriented checks.
- `scripts/transcribe_sensevoice.py`: load SenseVoice once and transcribe multiple generated clips.

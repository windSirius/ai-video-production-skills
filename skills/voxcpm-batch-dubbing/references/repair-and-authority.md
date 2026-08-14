# Text authority, similarity, and repair

## Canonical text versus generation text

`canonical_text` is what the audience should hear and what subtitles must display. `generation_text` is a disposable input shim used only when the synthesizer mispronounces a term. Store both in `segments.json`; never overwrite one with the other.

ASR is diagnostic evidence. Compare normalized ASR with `canonical_text`, while allowing an explicit alias map for known homophones. Never copy an ASR spelling into the manuscript without human evidence.

## Similarity gate

Use Unicode normalization, remove punctuation and whitespace, apply only the approved alias map, then compute sequence similarity. For Alan's workflow:

- every accepted segment must score at least `0.90`;
- omissions, repetitions, reordering and a missing tail are automatic retry reasons even when a coarse score appears high;
- report the minimum, median and mean, but release is controlled by the minimum;
- a user-specified stricter threshold wins.

## Attempt and promotion model

Keep every attempt immutable. A segment directory may contain several candidates, but exactly one is copied or linked into the canonical `audio/NN.wav` path. The manifest records candidate SHA, promoted SHA, ASR SHA, score, model settings and reason for selection.

## Audio repair

Repair only observed defects: click at a join, clipped transient, pathological silence, DC offset, unstable loudness or a failed segment. Preserve source consonants and breaths. After repair, re-run full decode, peak/RMS or LUFS statistics, duration checks and ASR.

The final master needs a stable loudness target and true-peak ceiling. Record the actual target rather than assuming a platform default. Keep both pre-normalization and normalized hashes so the edit remains reversible.

## Version authority

The latest passing `audio_manifest.json` decides which master is current. File names and modification times are not authority. A manifest must bind the canonical manuscript, segments, promoted clips, repair report and final master by SHA-256.

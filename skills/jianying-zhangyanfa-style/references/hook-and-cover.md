# High-density hook and one-frame cover

Use this profile only when the brief asks for a high-retention opening, a 0–10 second PV/CG montage, or an embedded platform cover. It is a conditional module, not the cadence for the full video.

## One-frame platform cover

The 2026-07-22 finished Himeko reference and its open Jianying project establish this implementation:

- Put the approved cover still on the main picture lane at `00:00:00:00` for exactly one timeline frame.
- At 60 fps, its duration is `00:00:00:01` or about `16.667 ms`.
- Move the narrative picture master, captions, narration, and BGM right by the same one frame. Do not overwrite or trim the first narrative frame.
- Keep the cover static and full-frame. It is an embedded discovery/platform frame, not a title sequence that viewers should consciously watch.
- Verify the export frame by frame: frame 0 is the cover, frame 1 is the first narrative image, there is no black frame between them, and all narrative tracks remain synchronized.
- For first-time insertion, expect the cover-inclusive picture duration to equal the body master plus one frame. When replacing an assembly that already includes a cover frame, preserve the existing cover-inclusive duration. Container/audio tails may make the exported duration slightly longer; validate picture frame count separately from container duration.

Do not hold the cover longer than one frame unless the user explicitly requests a visible title card.

## 0–10 second hook storyboard

Build the opening as roughly 8–10 semantic beats before touching the live timeline. Each beat must serve the spoken clause rather than merely supply motion.

Measure these ten narrative seconds from frame 1, after the cover. In the cover-inclusive project, every narrative boundary therefore appears one frame later than its narrative-relative time.

1. Begin with the story consequence, central symbol, or emotionally loaded subject.
2. Use clean PV, CG, or cinematic story footage. Reject menus, dialogue UI, logos, unrelated combat, and low-information establishing shots.
3. Aim for a meaningful visual refresh roughly every second. In the measured Himeko reference, the first narrative image breathes for about two seconds, then detectable changes land at approximately seconds 2, 3, 4, 5, 6, 7, 8, 9, and 10. A two-second first beat is acceptable when it makes the question legible.
4. Make the sequence progress: premise → danger/history → character consequence → group/relationship → answer or reversal. Interchangeable glamour shots do not count as a narrative hook.
5. Prefer hard cuts and source-native motion. Use a flash or transition only when it belongs to the source scene or marks the move into the body.
6. After roughly ten seconds, return to the normal sentence-level rhythm. Never extrapolate the one-second cadence across the full video.

## Hook text hierarchy

The open Himeko project confirms two distinct text systems:

| Function | Font and size | Styling | Placement |
|---|---|---|---|
| Ordinary narration | 新青年体, size `5` | saved cyan/white outline preset | fixed bottom-center position from the profile |
| Opening question | 新青年体, size `9` | manual red fill, ordinary preset cleared | upper-middle, composition-aware |
| Body proof or reversal | 新青年体, usually size `5` | manual red fill, ordinary preset cleared | follow the ordinary caption zone unless the proof card needs another composition |
| Closing thesis | same font; size follows composition | one full red clause, not keyword coloring | over the decisive character image |

The opening red line may use a short fade-in, but it must become readable immediately. Keep it to one semantic clause per caption block. Red is a structural signal for question, proof, reversal, or thesis; it is not decorative palette matching.

## Stable implementation pattern

For automated or fragile projects, prefer this recoverable lane structure:

1. one-frame cover still;
2. one continuous, video-only `picture_only` master containing the narrative cuts;
3. dense semantic caption blocks;
4. sequential narration WAV clips at `0.0 dB` with loudness normalization;
5. a chapter-length or full-length BGM master at about `-20.0 dB` with loudness normalization;
6. only genuinely necessary evidence or graphic overlays above the master.

This is a stability architecture, not a ban on live segmented footage. Keep the editable match plan, source ledger, and previous picture master recoverable so a baked visual decision can still be revised.

## Hook acceptance checks

- Frame 0 is the intended cover; frame 1 is narrative footage.
- Inspect the first 12 decoded frames; a 1 fps contact sheet cannot prove the cover is only one frame.
- The narrative starts with no black, UI, watermark, or accidental source subtitle.
- Inspect one frame near each narrative-relative whole second from 0 through 10, measured after the cover; every visual change must match the current spoken beat.
- The red hook text is size `9`, manually styled, readable against every opening shot, and is not using the ordinary preset.
- By about 10 seconds, caption size and visual cadence have returned to the body profile.
- Adding the cover changed every narrative lane by the same one-frame offset and did not create drift.
- The final export retains an intentional image at the end and contains no unintended black tail.

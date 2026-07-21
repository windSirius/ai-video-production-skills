# Jianying execution checklist

## Before editing

- Confirm the correct draft title and total duration.
- Save a recoverable copy of the current picture track or keep its rendered file.
- Record narration clip count, caption count, BGM tracks, and current ending frame.
- Do not delete the main track if linked/ripple deletion would remove captions or audio. Prefer Jianying's “替换片段” command for an equal-duration picture-only render.

## Build order

1. Place numbered narration WAVs sequentially.
2. Run Manuscript Match and repair semantic caption breaks.
3. Apply the user's normal caption preset in bulk.
4. Build the main picture track from the match plan with source audio muted.
5. Add sparse evidence cards and blur effects on upper tracks.
6. Add chapter-length BGM cues.
7. Perform audio and visual QA.

## Exact observed settings

### Normal captions

- Font: 新青年体.
- Font size: `5` in the observed desktop project.
- Character spacing: `0`.
- Line spacing: `0`.
- Alignment: center.
- Preset: third cyan/white outline preset in the displayed preset row.
- Scale: `100%`.
- Position: `X=0`, `Y=-888`.

Apply to all ordinary narration captions, then repair deliberate red-emphasis captions separately.

### Narration

- Volume: `0.0 dB`.
- Fade in/out: `0.0 s` unless a particular clip audibly clicks.
- Loudness normalization: enabled, target approximately `-23 LUFS`.
- Voice enhancement/effects: off unless the user requests them.

### BGM

- Volume: `-20.0 dB` baseline.
- Loudness normalization: enabled, target approximately `-23 LUFS`.
- Place cue changes at chapter boundaries.
- Preview consonant-heavy sentences; lower BGM further if it masks narration.

### Main footage

- Source audio: `-∞ dB` by default.
- Scale: normally `100%`; preserve aspect ratio.
- Prefer hard cuts.
- Keep 60 fps when the target draft is already 60 fps.

### Evidence insert

- Place the screenshot/image on an upper video track.
- Use a dark card, gold/white heading, white quote, and red proof box where feasible.
- Add a blur effect aligned to the evidence insert when bands or background extensions need treatment.
- Reference blur intensity: `50`.

## Visible QA points

- `00:00`: intentional opening frame, no accidental black.
- First 10 seconds: emotional hook and central question are clear.
- First evidence card: text is readable at normal preview scale.
- Midpoint: caption position remains fixed and BGM remains subordinate.
- Emotional slowdown: shot durations visibly lengthen.
- Final thesis: red emphasis is legible and not overused elsewhere.
- Project end: exact duration preserved and final frame is visible.

## Replacement safety

When replacing a rendered picture-only track:

1. Match the old track's frame rate, resolution, frame count, and duration.
2. Select the existing picture clip.
3. Use the context-menu command “替换片段”.
4. Keep “复用原视频效果” enabled only when the new render should inherit the same transform/effect settings.
5. Reopen the draft if necessary and visibly verify the new filename on the main track.
6. Check captions, narration, BGM, the total duration, and the end frame before reporting completion.

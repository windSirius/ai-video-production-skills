# Jianying execution checklist

## Before editing

- Confirm the correct draft title and total duration.
- Save a recoverable copy of the current picture track or keep its rendered file.
- Record narration clip count, caption count, BGM tracks, and current ending frame.
- Do not delete the main track if linked/ripple deletion would remove captions or audio. Prefer Jianying's “替换片段” command for an equal-duration picture-only render.

### pyJianYingDraft 11.1 media staging

- Before creating a macOS Jianying 11.1 draft, copy all referenced video and audio into a stable directory under `${AI_VIDEO_MEDIA_ROOT:-$HOME/Movies/JianyingMedia}`.
- Do not point a generated draft directly at media inside iCloud Drive. In the verified 2026-07-28 A/B test, Jianying opened the timeline and captions but marked the iCloud media as `无法访问权限`.
- Verify hashes after staging, then write the staged absolute paths into the draft.
- Treat the first Jianying open/save as a migration boundary. Once a draft has been opened or saved by Jianying 11.1, do not overwrite it with pyJianYingDraft; create a new named draft for repairs.
- A valid live check must show the picture, narration waveform, editable captions, total duration, and at least one critical evidence/payoff frame.

### H2 function-density preflight

- Set `ZHANGYANFA_LEARNING_ROOT` to the local 剪辑学习系统 directory. After freezing the narration-unit map and visual selections, but before generating a new pyJianYingDraft draft, express the planned artificial refreshes in the `visual-density-plan` schema and run `$ZHANGYANFA_LEARNING_ROOT/tools/density_policy_check.py`.
- Use `$ZHANGYANFA_LEARNING_ROOT/policies/pyjianying-visual-strategy-v0.2.json` as the policy source and preserve the JSON report with the production run.
- The checker is advisory while `function-dependent-density` remains H2. Do not automatically retime, replace, or reject footage only because the checker warns.
- Review every artificial refresh inside identity attribution, evidence reading, consequence explanation, and emotional interpretation. Each should add a new identity, relationship, evidence item, causal step, emotional state, orientation cue, or contrast, or have an observable meaning/action/gaze/sound/function-boundary motivation.
- Source-shot movement is not an artificial refresh. Preserve useful performance, gaze, and action instead of creating one-second cadence by alternating the same evidence with stills or crops.
- A plan schema error blocks generation; an H2 editorial warning requests review but does not block by default.

## Build order

1. Place numbered narration WAVs sequentially.
2. Run Manuscript Match and repair semantic caption breaks.
3. Apply the user's normal caption preset in bulk.
4. Repair red structural-emphasis captions separately; never include them in the ordinary bulk preset pass.
5. Build the main picture track from the match plan with source audio muted or structurally absent.
6. If the brief requires an embedded cover, insert the approved still for exactly one frame before every narrative lane. Follow [hook-and-cover.md](hook-and-cover.md).
7. Add sparse evidence cards and blur effects as live overlays, or bake them into the recoverable picture master when using the stability-first route.
8. Add chapter-length BGM cues or a verified pre-mixed chapter/full-length BGM master.
9. Perform audio and visual QA.

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

### Red structural emphasis

- Opening high-density hook: 新青年体, size `9`, manual red color, ordinary preset cleared, upper-middle placement.
- Body proof/reversal: normally keep size `5`, use manual red color, and clear the ordinary preset.
- Closing thesis: emphasize one complete clause; size and placement may follow the final composition.
- Do not turn scattered keywords red. The whole selected clause carries the structural emphasis.

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
- A video-only picture master is preferred for automated assembly because source audio is then structurally absent rather than merely hidden.
- Scale: normally `100%`; preserve aspect ratio.
- Prefer hard cuts.
- Keep 60 fps when the target draft is already 60 fps.

### One-frame cover

- Put the cover still on the main picture lane at frame 0 for exactly one frame.
- Move the picture master, every caption, all narration clips, and BGM right by exactly one frame.
- At 60 fps, verify `frame 0 = cover` and `frame 1 = first narrative image`.
- On first insertion, cover-inclusive picture duration equals body-master duration plus one frame. When replacing an already cover-inclusive assembly, preserve the existing cover-inclusive duration.
- Treat picture-frame duration separately from container duration. The Himeko timeline ends at `00:10:16:20`, while its AAC export container reports about `00:10:16.341`.
- Do not stretch the cover into a visible title card without explicit approval.

### Stability-first picture architecture

- Use a single continuous, video-only picture master when live segmented footage would make the draft fragile or slow to rebuild.
- Keep narration WAVs as separate sequential clips so individual delivery repairs remain local.
- A verified full-length BGM master is acceptable; keep its source manifest and chapter decisions outside the baked file.
- Keep the previous picture master, match plan, and source ledger recoverable. A continuous master is an execution boundary, not permission to discard edit provenance.

### Evidence insert

- For a live insert, place the screenshot/image on an upper video track. It may instead be baked into a stability-first picture master only when the editable source card and match plan remain recoverable.
- Preserve a readable original document page when its provenance matters; otherwise rebuild it as a dark card with a gold/white heading, white quote, and red proof box.
- Add a blur effect aligned to the evidence insert when bands or background extensions need treatment.
- Reference blur intensity: `50`.
- Preview at normal viewing size and read the highlighted passage aloud before accepting the hold duration.

## Visible QA points

- `00:00`: intentional opening frame, no accidental black.
- Frame `00:00:00:01`: first narrative frame begins immediately after a one-frame cover when that module is used.
- First 10 seconds: emotional hook and central question are clear; for a high-density hook, inspect each whole-second beat for semantic fit, UI, logos, source subtitles, and repetition.
- First evidence card: text is readable at normal preview scale.
- Midpoint: caption position remains fixed and BGM remains subordinate.
- Emotional slowdown: shot durations visibly lengthen.
- Final thesis: red emphasis is legible and not overused elsewhere.
- Project end: exact duration preserved and final frame is visible.
- Export: verify picture frame count separately from AAC/container tail duration.
- Export audio: measure the final mix; target approximately `-23 LUFS` integrated and true peak near `-3.8 dBFS`, then listen for consonant masking.

## Replacement safety

When replacing a rendered picture-only track:

1. Match the exact slot being replaced: an already cover-inclusive slot keeps its frame count and duration; a first-time cover insertion intentionally adds one frame to the body master.
2. Select the existing picture clip.
3. Use the context-menu command “替换片段”.
4. Keep “复用原视频效果” enabled only when the new render should inherit the same transform/effect settings.
5. Reopen the draft if necessary and visibly verify the new filename on the main track.
6. Check captions, narration, BGM, the total duration, and the end frame before reporting completion.

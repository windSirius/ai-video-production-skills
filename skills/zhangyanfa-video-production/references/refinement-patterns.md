# Learned acceptance-refinement patterns

Apply these patterns only when the named risk exists. They are defaults, not mandatory decoration.

## Duplicate ordinary captions over baked cards

- Identify every ordinary caption whose visible time overlaps a baked thesis or evidence card and repeats its meaning.
- Use Jianying `停用片段` rather than deleting it.
- Preserve caption text, timing, and style in the project for rollback.
- Visually check the middle of every card: the card remains, the ordinary bottom caption does not.
- Count and report disabled captions.

## Static-card or slide-deck feeling

- Use a restrained 100%→103% scale push across the card.
- Use approximately 6 frames for entry and exit fades.
- On evidence cards, delay the red proof rectangle by about 5 frames so the quotation lands before the annotation.
- Keep header, body, and proof text inside safe margins and inspect at normal preview scale.
- Return to character or story footage immediately after evidence.

## BGM lacks rhetorical breathing

- Start only from already verified sources in the configured BGM root; do not replace a weak section with footage audio, a download, or generated music.
- Start near the house baseline of `-20 dB` in Jianying with loudness normalization enabled.
- Dip the music under a reversal or decisive thesis rather than changing tracks for one sentence.
- Permit a restrained 1–1.5 dB lift for a recovered signal, reply, reunion, or hopeful turn.
- Fade toward silence before the final image when the ending needs aftertaste.
- Keep automation in a reproducible offline BGM master when many precise changes are required.
- Verify gain and normalization in the live project; report LUFS only from a measured export.

## Ending breath is too short

- Add about 1 second of an intentional non-black final frame after narration ends.
- Extend the BGM master with matching silence or a completed fade.
- Confirm exact total timecode and inspect the final frame at the project endpoint.
- Do not add a generic channel bumper unless the project already uses one.

## Captions are correct but pictures drift semantically

- Freeze the user-adjusted SRT and do not rerun caption postproduction.
- Re-index source footage at coarse and dense intervals, then OCR visible dialogue, names, objects, and evidence text.
- Retrieve three candidates per short semantic unit and reject menus, logos, transitions, and character-only filler.
- Rebuild one equal-duration, picture-only master and use `替换片段` so captions, narration, and BGM remain untouched.
- Verify the new filename, unchanged timecode and lanes, plus live opening/middle/ending screenshots before marking the project updated.

## Opening or ending lacks editorial intent

- Study only the first and last 20–30 seconds of the reference video at one-second intervals.
- Transfer hook density, evidence timing, emotional release, and final-frame function rather than copying its shot sequence.
- Require a non-black active opening, recognizable stakes within three seconds, and an intentional non-black final image that completes the farewell.

## Evidence and reporting

For each refinement, record:

```text
priority category feedback timeline_range planned_edit assets acceptance_test status
```

Use `done` only after the live timeline or measured asset passes the acceptance test. Record inherited source issues, such as a pre-existing brief black transition, separately from newly introduced defects.

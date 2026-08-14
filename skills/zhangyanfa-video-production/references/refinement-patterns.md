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

- Keep the project's frozen source mode. For `local_library`, start only from verified configured-root sources. For `generated_score`, revise the chapter prompt or regenerate only the weak chapter; do not silently switch provenance modes.
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

## Evidence page looks like a one-frame flash

- Inspect the exact cut at native fps before extending the page.
- Check whether outgoing and incoming opacity both reach zero at the cut. If so, replace the page-to-page fade with a hard cut or overlap; do not lengthen an already readable page to hide the defect.
- Re-render only affected chunks, invalidate cache by HTML/asset hash, and inspect cut `-6…+6` frames.

## Highlight rectangle is too large or misplaced

- Locate the exact target words in source-image pixel coordinates.
- Add contain/pad offsets and any scale to convert source coordinates into canvas coordinates.
- Scope the CSS override to the exact card ID. Never change a shared class when only one page is wrong.
- Render one midpoint frame and confirm the box isolates only the intended phrase before rerendering the chunk.

## Cover character or official model is distorted

- Stop using the generated character layer. Return to the frozen official/user source.
- Generate only a background or light treatment if needed, then composite the unchanged character deterministically.
- Recheck face, eyes, hands, clothing structure and signature prop against the source at full size and thumbnail size.

## Client deadline requires a fast patch

- Translate feedback into the smallest exact range and asset IDs.
- Patch only those IDs and affected chunks. Reuse unchanged hashes; preserve the old accepted master.
- Follow “宁少做，不多做”: remove a questionable label, box, insert or effect when removal solves the note more safely than redesign.
- Re-run local point QA plus the global frame/decode contract before delivery.

## Evidence and reporting

For each refinement, record:

```text
priority category feedback timeline_range planned_edit assets acceptance_test status
```

Use `done` only after the live timeline or measured asset passes the acceptance test. Record inherited source issues, such as a pre-existing brief black transition, separately from newly introduced defects.

# Caption-locked OCR visual workflow

Use this procedure for picture rematching after captions are stable, especially when the user has manually corrected Jianying subtitles.

## 1. Freeze caption authority

1. Read the live Jianying caption track and export or copy a fresh SRT snapshot.
2. Record caption count, first start, final end, project timecode, narration count, BGM lanes, and current picture filename.
3. Treat this snapshot as immutable. Do not run Manuscript Match, semantic caption repair, typography changes, or duplicate removal during picture work.
4. Require the rebuilt picture to equal the caption spine duration. Never fix a picture mismatch by moving captions.

## 2. Analyze supplied reference videos

Probe duration, dimensions, frame rate, and audio presence. Build separate contact sheets for:

- the first 30 seconds at roughly one-second intervals;
- the last 20–30 seconds at roughly one-second intervals;
- the full video at coarse intervals for pacing context.

Extract structural rules, not a literal edit decision list. Record how quickly a face, motion, danger, or central question appears; when direct text/evidence replaces atmospheric footage; how the ending returns to character, motif, or thesis; and the visual function of the final frame.

## 3. Build visual and OCR indexes

1. Probe every source and assign a stable source ID.
2. Extract coarse frames across the whole source, normally every 8–15 seconds.
3. Extract dense frames at roughly 1–3 second intervals around likely character, dialogue, evidence, opening, and ending windows.
4. Compile `scripts/vision_ocr.swift` with `xcrun swiftc`, then run `vision_ocr OUTPUT.tsv FRAME_ROOT...`. It recognizes Simplified Chinese and English with macOS Vision.
5. Merge coarse and dense rows into one index containing source, timestamp, image path, and OCR text.
6. Preserve contact sheets for visual inspection. OCR is evidence retrieval, not a substitute for looking at the frame.
7. Bind the source manifest, index rows, OCR rows, evidence paths, and counts in a current-generation index manifest. Do not trust a separate audit file's self-reported row count without rereading the source artifacts.

## 4. Build semantic visual units

- Cover every caption exactly once and in order.
- Keep one caption per unit by default.
- Merge adjacent captions only when they form one indivisible thought or continuous dialogue beat.
- Normally keep ordinary units under six seconds; split longer units at semantic or rhetorical boundaries.
- Allow larger purpose-built opening and ending groups only when their internal source cuts remain mapped to individual caption times.

For each unit, record subject, action, object/location, emotion, narrative function, and exact quoted terms.

## 5. Retrieve and rank candidates

For a long-form rebuild, retrieve every unit against the complete normalized index in one `build_match_plan` stage. Keep the unit's semantics independent even though execution is bulk. Retain a configurable full pool, normally 32–64 viable candidates where the source permits, and expose at least three temporally or source-distinct A/B/C candidates. Score:

1. Exact visible dialogue, name, object, or evidence matching the caption.
2. Correct subject and action.
3. Correct place, chronology, emotional temperature, and narrative function.
4. Motion and transition safety across the requested duration.
5. Novelty relative to shots already used nearby.

Penalize or reject menus, task lists, maps, settings, rewards, long UI screens, logos, title slates, loading states, source heads/tails, black/near-black/overexposed transitions, unrelated baked text, character-only filler, and repeated high-emotion close-ups that exhaust later peaks.

An OCR hit is strong only when the visible frame and the sentence agree. If text matches but the action or chronology conflicts, lower the score and continue searching.

Make the first selection globally, not by taking every local top-one independently. Enforce exact-range reuse budgets, adjacency and reverse-order rules, chronology, source diversity, and reservation of the strongest climax/resolution shots.

Record the complete pool, candidate A/B/C, component scores, exact source in/out, selected candidate ID, selected reason, original machine confidence, concrete retry evidence, and reuse group. Mark this result `machine_proposed`; it is not ready to render.

## 6. Review, repair, and approve the plan

1. Generate a selected-shot contact review covering every cue exactly once.
2. Generate A/B/C head/middle/tail evidence for risk rows: identities, quotations, comparisons, cards or external assets, low confidence, OCR/UI/black risk, repeated/overlapping ranges, opening, ending, and reviewer-reported rows.
3. For a named character, verify the visible person or panel independently. OCR or dialogue mentioning a name is not identity evidence.
4. Bind every review manifest to the current match-sheet and candidate-pool hashes. List the exact evidence files; ignore orphan images left in the directory.
5. Apply decisions through a base-hash-bound repair manifest. An override must enter the retained pool with evidence and provenance before selection.
6. Preserve the prior generation and append a delta chain listing the exact changed cues. Re-review every changed row and any affected hook, ending, identity, overlap, or reuse gate.
7. Do not overwrite machine confidence or retry history with the human outcome.
8. Render only when selected review covers all cues, risk review covers all derived risk rows, identity/opening/ending gates pass, global audits pass, and unresolved rows equal zero.

## 7. Design opening and ending

Opening gate:

- first frame is non-black and visually active;
- recognizable character, motion, danger, or contradiction appears within three seconds;
- early evidence or direct dialogue quickly converts spectacle into a concrete question;
- no logo, menu, slow fade, or generic establishing shot leads the video.

Ending gate:

- the last 10–20 seconds slow down without becoming static;
- character and motif return in a way that resolves the argument;
- the final spoken line and final image support each other;
- the final frame is intentional, readable, and non-black.

Treat both intervals as sequence-level gates, not isolated thumbnails. A later patch touching either interval invalidates that gate.

## 8. Render the deterministic picture master

1. Render one versioned MP4 from the current reviewed match generation with the target project's dimensions and frame rate.
2. Match the caption spine duration within one frame where practical.
3. Include exactly one video stream and no audio stream.
4. Bind the render manifest to the canonical SRT, timing contract, source manifest, candidate pool, current match sheet, and passing review manifest hashes.
5. Run `ffprobe`, full decode, the match-sheet audit, source-range/overlap audit, and strict black detection. Start with `blackdetect=d=0.05:pix_th=0.02`; inspect any hit rather than trusting a looser threshold that can misclassify dark source transitions.
6. Generate opening, ending, and coarse contact sheets before touching Jianying.
7. For feedback, use one declared `patch_picture_master` generation. Prove the base SHA, exact changed cues/frame ranges, unchanged segment hashes, renewed review gates, and the full output frame contract.

## 9. Replace safely in Jianying

1. Create a stable regular-file path for the approved render. Prefer a hardlink under `AI_VIDEO_MEDIA_ROOT`, defaulting to `$HOME/Movies/JianyingMedia`; never rely on a symlink or `/tmp` for the saved draft.
2. Import and preview the exact video. Confirm it is recognized as MPEG-4 video with the expected duration.
3. Right-click the existing main picture clip and choose `替换片段`.
4. Confirm the replacement preview is video-to-video, then apply it.
5. Wait for processing. Verify the timeline label shows the new filename.
6. Confirm total timecode, caption lane, narration clips, and BGM lanes are unchanged.
7. Capture live QA screenshots at the opening hook, a representative middle sentence, and the final spoken line.
8. Save the draft. Reopen and repeat the checks if persistence is uncertain.

## 10. Close the phase

Write an acceptance report containing caption count, narration count, OCR frame count, semantic-unit count, picture metadata, black-gap result, live filename, timecode, track-preservation result, opening/ending findings, save state, and export state.

Only after live replacement passes, move superseded renders and segment folders to a dated Trash directory. Keep the accepted render, its current render segments, match sheet, OCR index, QA images, and stable Jianying hardlink.

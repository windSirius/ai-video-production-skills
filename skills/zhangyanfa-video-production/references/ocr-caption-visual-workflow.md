# Caption-locked OCR visual workflow

Use this procedure for picture rematching after captions are stable, especially when the user has manually corrected Jianying subtitles.

## 1. Freeze caption authority

1. Read the live Jianying caption track and export or copy a fresh SRT snapshot.
2. Record caption count, first start, final end, project timecode, narration count, BGM lanes, and current picture filename.
3. Treat this snapshot as immutable. Do not run Manuscript Match, semantic caption repair, typography changes, or duplicate removal during picture work.
4. Require the rebuilt picture to equal the live-derived narration timing contract. When captions end earlier, map the remaining frames to an intentional final-picture hold; never shorten the picture or move captions to hide the difference.

## 2. Analyze supplied reference videos

Probe duration, dimensions, frame rate, and audio presence. Build separate contact sheets for:

- the first 30 seconds at roughly one-second intervals;
- the last 20–30 seconds at roughly one-second intervals;
- the full video at coarse intervals for pacing context.

Extract structural rules, not a literal edit decision list. Record how quickly a face, motion, danger, or central question appears; when direct text/evidence replaces atmospheric footage; how the ending returns to character, motif, or thesis; and the visual function of the final frame.

## 3. Normalize source proxies and build reusable indexes

1. Probe every original source, assign a stable source ID, and record its SHA-256.
2. Create or reuse a seek-safe proxy keyed by the original-source hash and normalization-profile hash. Default to 1080p H.264, CFR 30, `yuv420p`, BT.709 metadata, and a GOP no longer than 30 frames. The artifact contract may preauthorize a provisional frame-rate or resolution override; it becomes a passing production profile only after the later stress gate proves it.
3. Decode-test and probe the proxy. Preserve original-source provenance and exact time mapping; never treat the proxy as a new source identity.
4. Extract coarse frames across the whole proxy, normally every 8–15 seconds.
5. Extract dense frames at roughly 1–3 second intervals around likely character, dialogue, evidence, opening, and ending windows.
6. Compile `scripts/vision_ocr.swift` with `xcrun swiftc`, then run `vision_ocr OUTPUT.tsv FRAME_ROOT...`. It recognizes Simplified Chinese and English with macOS Vision.
7. Merge coarse and dense rows into one index containing original source, proxy identity, timestamp, image path, and OCR text.
8. Preserve contact sheets for visual inspection. OCR is evidence retrieval, not a substitute for looking at the frame.
9. Bind the original-source manifest, proxy hashes/profile, index rows, OCR rows, evidence paths, and counts in a current-generation index manifest. Reuse the proxy and index while their bound hashes remain current; do not rebuild them merely because a run resumed. Do not trust a separate audit file's self-reported row count without rereading the source artifacts.
10. Keep proxies, indexes, browser caches, and render work in a declared local non-iCloud scratch/cache. Stop before generation if that path cannot be resolved. Sync only current manifests, accepted evidence, and deliverables.

## 4. Build semantic visual units

- Cover every caption exactly once and in order.
- Group adjacent captions into the smallest complete narrative, evidence, action, or dialogue beat. Prefer a stable 4–8 second visual unit when meaning and source continuity allow it; do not force a new visual unit merely because a caption ended.
- Keep cue IDs and integer cue start/end frames as clock mappings inside the unit. A cue boundary must not by itself create a new source seek, asset activation, cut, or HyperFrames segment.
- Split when the subject, action, location, narrative function, evidence requirement, or intended shot genuinely changes. Avoid sub-two-second units unless the opening hook or an intentional montage requires them.
- Allow larger purpose-built opening and ending groups only when every internal source cut has its own visual reason; record each approved cut on the integer frame clock and list the nearby cue IDs only as timing/evidence mappings.

For each unit, record covered cue IDs and frame range, subject, action, object/location, emotion, narrative function, and exact quoted terms. Audit both exact cue coverage and exact frame coverage independently from the shot count.

## 5. Retrieve and rank candidates

For a long-form rebuild, retrieve every semantic unit against the complete normalized index in one `build_match_plan` stage. Keep each unit's semantics independent even though execution is bulk. Retain 8–12 viable candidates for an ordinary unit. Expand progressively up to 32 and expose at least three temporally or source-distinct A/B/C candidates only for a derived risk class: named identity, quotation/comparison/evidence, card/external asset, low confidence, OCR/UI/black hazard, repeated/overlapping range, opening/ending, or a specific reviewer-reported correction. A free-form risk label cannot bypass the ordinary pool, and an insufficient pool remains unresolved with search evidence. Score:

1. Exact visible dialogue, name, object, or evidence matching the caption.
2. Correct subject and action.
3. Correct place, chronology, emotional temperature, and narrative function.
4. Motion and transition safety across the requested duration.
5. Novelty relative to shots already used nearby.

Penalize or reject menus, task lists, maps, settings, rewards, long UI screens, logos, title slates, loading states, source heads/tails, black/near-black/overexposed transitions, unrelated baked text, character-only filler, and repeated high-emotion close-ups that exhaust later peaks.

An OCR hit is strong only when the visible frame and the sentence agree. If text matches but the action or chronology conflicts, lower the score and continue searching.

Make the first selection globally, not by taking every local top-one independently. Enforce exact-range reuse budgets, adjacency and reverse-order rules, chronology, source diversity, and reservation of the strongest climax/resolution shots.

Record the retained pool, any required candidate A/B/C, component scores, exact original-source and proxy in/out, selected candidate ID, selected reason, original machine confidence, concrete retry evidence, and reuse group. Mark this result `machine_proposed`; it is not ready to render.

## 6. Review, repair, and approve the plan

1. Generate a selected-shot contact review covering every semantic visual unit exactly once. Run a separate mapping audit proving every cue and frame belongs to exactly one unit; do not generate one visual review card per cue when several cues share one visual beat.
2. Generate A/B/C head/middle/tail evidence for risk units: identities, quotations, comparisons, cards or external assets, low confidence, OCR/UI/black risk, repeated/overlapping ranges, opening, ending, and reviewer-reported units.
3. For a named character, verify the visible person or panel independently. OCR or dialogue mentioning a name is not identity evidence.
4. Bind every review manifest to the current match-sheet and candidate-pool hashes. List the exact evidence files; ignore orphan images left in the directory.
5. Apply decisions through a base-hash-bound repair manifest. An override must enter the retained pool with evidence and provenance before selection.
6. Preserve the prior generation and append a delta chain listing the exact changed semantic units, covered cues, and frame ranges. Re-review every changed unit and any affected hook, ending, identity, overlap, or reuse gate.
7. Do not overwrite machine confidence or retry history with the human outcome.
8. Render only when selected review covers all semantic units, cue/frame mapping covers the timing spine exactly once, risk review covers all derived risk units, identity/opening/ending gates pass, global audits pass, and unresolved units equal zero.

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

## 8. Pass HyperFrames render gates and produce the master

1. Bind the HyperFrames composition and integer-frame render plan to the canonical SRT, timing contract, original-source/proxy manifest, candidate pool, current semantic-unit match sheet, and passing review hashes. Render segments follow intentional semantic-unit/shot cuts, not caption boundaries.
2. Render a real 30–60 second HyperFrames stress sample through the production composition path. Include representative asset activations, hard cuts, short and long holds, and any card/still treatment. Inspect the sample first/last frames, every seam, and the first frames after every asset activation; fail on black, stale, duplicated, missing, or decoder-lag frames.
3. After the stress gate passes, render 720p opening, ending, and representative-middle proxies with production timing and motion. Obtain explicit aesthetic approval for hook, evidence timing, continuity, cadence, emotional release, and final-image function. Repair and rerender only affected proxy intervals.
4. Only after both gates pass, perform one planned full-length HyperFrames production render at the contract target resolution, normally 1080p, from the current reviewed match generation. Match the live-derived narration timing contract within one frame and include exactly one video stream with no audio stream. Do not use a full-resolution render as the aesthetic-review proxy.
5. Run one complete final QA on the candidate master: `ffprobe`, full decode, match-sheet and cue/frame-mapping audit, source-range/overlap audit, exact frame count, first/last and transition checks, plus strict black detection. Start with `blackdetect=d=0.05:pix_th=0.02`; inspect any hit rather than trusting a looser threshold that can misclassify dark source transitions.
6. Generate opening, ending, and coarse contact sheets before touching Jianying. Reuse the hash-bound final-QA evidence rather than repeating the full decode during unchanged Harness or reporting steps.
7. For later feedback, use one declared `patch_picture_master` generation. Bind the accepted base SHA and prove exact changed semantic units/cues/frame ranges, changed chunk QA, unchanged chunk hashes, neighboring seams, renewed affected review gates, and the full output frame contract. Do not fully decode or frame-hash the accepted base again, and do not compare every frame of base and output; fully decode the assembled patched output once only if it becomes the new accepted master.

## 9. Replace safely in Jianying

1. Create a stable regular-file path for the approved render. Prefer a hardlink under `${AI_VIDEO_MEDIA_ROOT:-$HOME/Movies/JianyingMedia}/`; never rely on a symlink or `/tmp` for the saved draft.
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

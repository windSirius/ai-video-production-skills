# HyperFrames render workflow

Use this workflow whenever the pipeline creates a moving-image video asset. HyperFrames must own the composition, frame clock, validation, capture, and output render. FFmpeg may normalize source proxies, probe outputs, and run QA; it may not author or replace the picture master.

Before source normalization or any formal render, load `authority_bundle.json`. Planning and low-resolution proxies may use an explicitly provisional bundle; a target-resolution A/B/C master requires `scripts/audit_authority_chain.py RUN_DIR` to pass without provisional mode. Bind its revision and SHA into every render lineage.

## 1. Normalize and cache render sources

1. Assign every original source a stable source ID and SHA-256 before deriving media.
2. Create or reuse one seek-safe proxy keyed by the original-source hash and the normalization-profile hash. Default to 1080p H.264, CFR 30, `yuv420p`, BT.709 metadata, and a GOP no longer than 30 frames. The artifact contract may preauthorize a provisional frame-rate or resolution override; it becomes a passing production profile only after the later stress gate proves it.
3. Probe and fully decode-test each proxy before indexing or authoring. Store checker-versioned evidence bound to the proxy SHA/profile; downstream prerequisite checks reuse that result after confirming fingerprints and must not repeatedly decode an unchanged full proxy. Preserve the exact original source path and range in the lineage; never relabel a proxy as the original source.
4. Reuse a passing proxy and its visual/OCR index while the original-source and profile hashes remain unchanged. Do not rebuild a cache merely because a run resumed.
5. If a normalized full-source proxy still seeks unreliably, derive only the selected source ranges as short seek-safe proxies whose first requested frame is decodable. Bind those derivatives to the parent proxy/source hashes and exact source ranges.
6. Keep proxies, indexes, browser caches, and render work in a declared local non-iCloud scratch/cache. Stop before generation if that path cannot be resolved. Sync only the current manifests, accepted evidence, and deliverables; do not make cloud synchronization part of the render critical path.

This source gate prevents sparse-keyframe, mixed-frame-rate, and decoder-activation defects from being discovered only after a full render.

## 2. Preflight and bind the profile

1. Confirm `hyperframes`, `node`, `ffmpeg`, `ffprobe`, and a Chromium-compatible browser are available.
2. Capture `hyperframes doctor --json`, tool versions, `ffmpeg -encoders`, free bytes, cache location, and SHA-256 of the current timing contract, source/proxy manifest, and visual-review inputs in `hyperframes/environment.json`.
3. Calculate `estimated_peak_bytes` and preserve at least `render_policy.minimum_free_gib_after_render` after the render.
4. Select exactly one profile and record the reason before mutation:
   - `hyperframes_chunked_videotoolbox_v1`: normal macOS path.
   - `hyperframes_low_disk_stream_v1`: HyperFrames capture/encode with persistent frame cache disabled.
5. Stop if HyperFrames is missing or cannot validate the composition. Do not silently render through an unrelated path.
6. Read target width, height and fps from the locked delivery spec. Alan's current default is 2560×1440/60fps, not an inferred 1080p fallback; changing these values invalidates target-resolution proxies and masters.

## 3. Author by semantic visual unit

- Keep the project under `RUN_DIR/hyperframes/project/` and the entry composition at `index.html` unless the manifest declares another file.
- Write the normalized, hashable composition declaration used by the v2 gates to `RUN_DIR/hyperframes/composition.json`; bind it to the project entry/assets and keep its SHA aligned with the stress, aesthetic-approval, and master manifests.
- Derive width, height, fps, duration, and every segment boundary from `timing_contract.json` and the reviewed semantic-unit match sheet.
- Treat caption cues only as immutable clock mappings within semantic visual units. A cue boundary must not by itself restart source decoding, reactivate an asset, or create a render segment.
- Write `hyperframes/render_plan.json` with ordered integer `start_frame`, `frame_count`, semantic-unit ID, covered cue IDs, source/proxy identity and range, motion treatment, and transition fields. Require complete cue and frame coverage with no overlap or gap unless the transition explicitly owns the overlap.
- Before composition freeze, require a chapter source-coverage matrix and a whole-plan audit of exact-range reuse, significant overlap, adjacent same-source runs, source concentration, black hazards and opening/ending shot budgets. Per-row candidate quality cannot substitute for this global pass.
- Prefer visual holds or source continuity across adjacent cues in the same semantic beat. Create a new source activation only for an intentional visual cut.
- Use the HyperFrames virtual frame clock for animation. Do not drive render-visible motion from wall time, random values, network state, or an unpinned browser session.
- Distinguish `jianying_picture_master`, `standalone_preview`, and `authorized_final_export` before authoring caption or audio layers.

### One boundary authority

- Derive every start and end from integer frames. Quantize each shared boundary once, then compute `duration = quantized_end - quantized_start`.
- Never serialize `start_frame / fps` and `frame_count / fps` independently with decimal rounding. At 60 fps, a one-nanosecond gap can place a real sampled frame on the empty composition background.
- Run `scripts/audit_hyperframes_boundaries.py PROJECT/index.html --fps FPS` after building the canonical project and every derived chunk. Require zero positive gaps on a continuous track; declare intentional overlaps explicitly.
- When clips share a boundary, prefer the incoming clip on the boundary frame. Do not extend the outgoing clip by one frame merely to hide the empty sample.

## 4. Validate before rendering

1. Run `hyperframes lint PROJECT --json`.
2. Run `hyperframes check PROJECT --json --at-transitions --frame-check` and add the known caption zone for previews or final exports containing captions.
3. Save structured results in `hyperframes/check_result.json` and bind them to the current composition/render-plan hashes.
4. Treat errors, missing assets, black output, frame-zone violations, and unreviewed transition warnings as failures. Do not accept a zero exit code without retained evidence.

## 5. Pass the real HyperFrames stress gate

1. Render a 30–60 second sample through the same HyperFrames composition, browser, profile class, source proxies, frame clock, and transition logic intended for production.
2. Include several source activations, a hard cut, the shortest expected visual hold, at least one longer moving shot, and any card/still/overlay treatment that appears in the master. Include opening or ending boundaries when either has unusual treatment.
3. Decode and inspect the sample's first and last frames, every transition seam, and the first frames after every asset activation. Fail on black/near-black activation frames, stale frames from the prior asset, duplicated activation frames, missing frames, decoder lag, or a duration/frame-count mismatch.
4. Bind the sample, checks, and current composition/source hashes in the render lineage. If the composition, proxy profile, browser path, or transition implementation changes, invalidate and rerun the stress gate.

Do not start aesthetic proxies or the full-length production render until this gate passes. A lint/check pass alone does not prove browser video activation.

## 6. Approve 720p aesthetic proxies

1. Under workflow v3, render the complete `[0,target_frame_count)` timeline at 720p through HyperFrames after the stress gate passes and include frozen narration. Opening, ending and representative-middle captures are navigation evidence, not substitutes. A legacy v2 run may retain its already-frozen excerpt contract.
2. Preserve the production timing, semantic-unit boundaries, motion, transitions, and crop decisions. Lower only the spatial resolution or review bitrate.
3. Review the full continuous proxy at 1×. Use the opening to inspect hook/evidence timing, the middle to inspect continuity and sustainable cadence, and the ending to inspect emotional release and final-image function.
4. Record objective proxy checks and the user's explicit creative verdict as separate fields. A machine, producer agent or the existence of a review manifest cannot set the user verdict. Repair and rerender only the affected 720p intervals until both statuses pass.

Use these proxies for aesthetic iteration. Do not create a full-length target-resolution render to solicit ordinary creative feedback.

## 7. Perform one planned target-resolution production render

Start one full-length render at the frozen contract target resolution only after the authority-chain, stress, global reuse/black and user aesthetic gates pass. Align chunks to semantic-unit boundaries and normally group enough adjacent units for roughly 30–60 seconds per chunk; do not create one chunk per caption cue. A retry is allowed only after an objective technical failure and recorded repair, never as the default aesthetic-review loop or a way to discover hook/reuse problems.

### Normal macOS path

- Render locally with an explicit output, fps, quality, `--gpu`, `--strict`, and a bounded worker count.
- Prefer H.264 VideoToolbox for SDR Jianying masters and record the encoder reported by the run. Use HEVC only when the artifact contract requires it and compatibility is verified.
- Do not promise byte-identical rerenders from hardware encoding. Hash the completed artifact and verify decoded frames.

### Low-disk streaming path

- Use `--frames-cache-dir off --low-memory-mode --workers 1 --gpu --strict` and never select `png-sequence`.
- Keep source extraction and render work inside the declared run/cache locations. Monitor free space and stop before crossing the reserve.
- Prefer the HyperFrames streaming encoder. Do not preserve decoded full-frame sequences after the process exits.

## 8. Artifact-role branch

- For `jianying_picture_master`, emit video only: no audio stream and no burned captions. Import it through Jianying replacement so existing caption, narration, and BGM lanes remain protected.
- For `standalone_preview`, permit caption and audio composition only when the review request requires them.
- For `authorized_final_export`, require explicit export authority, include verified captions/audio, and measure the exported mix before any LUFS claim.

## 9. Run one complete final QA

- Probe stream count, codec, width, height, fps, timebase, pixel format, color metadata, frame count, duration, and audio policy.
- Decode through the full output; test first/last frames, every transition seam, black gaps, repeated/dropped frames, and exact equality with `target_frame_count`.
- Write `hyperframes/render_manifest.json` with environment, profile, commands, hashes, timing, disk, encoder, cache, segment lineage, probe, and QA results.
- Run this complete probe/decode/black/seam pass once on the candidate production master. Store checker-versioned evidence and reuse it after fingerprint revalidation instead of repeating full-output checks during unchanged administrative, prerequisite, or Harness steps.
- Register the output as `generated` only after all checks pass. A successful file write alone is not acceptance.
- Keep the current composition, plan, manifest, output, and required repair segments recoverable until user acceptance. Move superseded caches and renders to a dated Trash folder only after they are no longer referenced.
- Generate a boundary contact sheet containing `-1/0/+1` around every semantic-unit and chunk boundary. Review every page at original detail, then continuously play the actual first 10 seconds, last 10 seconds, and any user-reported range. A compressed ten-second overview is not a substitute for those intervals.

### Auxiliary B/C-track branch

- Derive fps and exact target frame count from the same authority bundle as A-track. A longer old-clock green/alpha master that will merely be clipped in Jianying is not a passing formal B/C deliverable.
- Bind B/C HTML, every still/silhouette/icon, CSS and build script to the chunk input fingerprint.
- Keep evidence pages fully visible long enough to read. Adjacent pages normally hard-cut; a transition may fade only when their opacity curves overlap or a persistent non-empty background remains.
- Produce `alpha_master` only when downstream alpha handling is verified. If transparency becomes black in the editor, retain the alpha source project and render a separate `green_screen_master` with a uniform pure-green composition background.
- Validate green background continuity and sample every page transition. Never replace only one silhouette with a green-backed rectangle.

## 10. Patch and verify incrementally

When later feedback changes a limited range:

1. Bind the accepted base-master SHA, base render-plan/chunk manifest, current input hashes, changed semantic-unit IDs, exact changed frame ranges, and affected chunk IDs before rendering.
2. Regenerate only changed chunks. Fully decode those chunks and check their first/last and activation frames; inspect both neighboring seams.
3. Prove unchanged content by matching existing chunk hashes and ordered lineage. Do not fully decode or frame-hash the entire accepted base again, and do not compare every base/output frame.
4. Assemble one new master from the verified unchanged and changed chunks, then prove ordered frame coverage, target frame count, media metadata, and audio policy. Fully decode the new master once if it becomes the new accepted production master; do not also repeat a full decode of the already accepted base.
5. Preserve the prior master and delta manifest until the patched master passes and the user accepts it.

Cache validity must bind the canonical HTML, referenced assets, generator/build scripts, render plan and tool version. A cache check that compares only codec, dimensions, fps, frame count or alpha mode is insufficient; force the affected chunks stale before rerendering.

Assemble chunks in render-plan order and write a concat receipt binding the plan SHA, each chunk receipt/output SHA, stream signature, final output SHA, exact frame count and full-decode result. Recheck all bound files immediately before atomic promotion so a concurrent change cannot produce a false receipt.

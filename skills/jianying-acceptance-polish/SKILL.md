---
name: jianying-acceptance-polish
description: "Turn client, producer, or platform-review feedback into the smallest verified Jianying or HyperFrames patch: resolve comments to exact timecodes/frames, diagnose one-frame flashes and bad transitions, fix evidence-card holds/highlight boxes, replace weak footage, repair official-source cover fidelity, normalize narration/BGM, preserve approved tracks, rerender only affected hash-bound chunks, and issue an evidence-backed acceptance report. Use for 甲方验收修改, 驳回待修改, 一闪而过, 红框错位, 封面人物崩坏, 黑帧, 响度, 节奏, or final QA."
---

# Jianying Acceptance Polish

Convert broad review language into precise, reversible timeline edits while preserving already-approved narration and captions.

## Non-negotiable rules

- Read and follow the Computer Use skill before operating Jianying or CapCut.
- Treat every control labeled 「试试剪映助手」 or 「剪映助手」 as permanently forbidden. Never click, open, dismiss, focus, test, or use it. If it obscures a required control, use a verified non-assistant route or stop the live action; when called by `zhangyanfa-video-production`, obey its route-preflight, per-step pre-click authorization, and harness-managed trace gates.
- Treat the review text as requirements, not as permission to alter unrelated creative choices.
- Resolve each comment to an exact timeline range, track, asset, and acceptance test before editing.
- Preserve caption text, styling, and timing unless the feedback explicitly includes subtitles.
- Inspect replacement assets before insertion; filenames alone do not prove content.
- Export or retain recoverable intermediate files for picture-track replacement and cover art.
- Do not claim final integrated loudness unless it was measured from an exported mix.
- Do not claim a cover is applied when it is only generated or imported into the media bin.
- Prefer the smallest patch that satisfies the feedback. “宁少做不多做” means remove an uncertain overlay, reduce a highlight, or hard-cut two approved pages before adding new motion.
- For renderer bugs, diagnose source → proxy → composition → chunk → assembled master. A valid source frame does not prove the composed boundary is valid.
- Never trust a render cache that ignores HTML, asset, plan, proxy or generator hashes. Force only affected chunks when the unchanged-chunk receipts remain valid.

## Inputs and handoff

Resolve:

- reviewer feedback and any quoted requirements;
- current Jianying project and timeline duration;
- replacement footage, logos, cover assets, or newly uploaded clips;
- narration and BGM track structure;
- delivery platform, target aspect ratio, and whether final export is authorized.

Use `jianying-sentence-visual-matching` first when most lines still need shot retrieval. Use this skill for focused acceptance risk and final polish.

## 1. Convert feedback into an edit ledger

Classify every item:

- `compliance`: required title, franchise, product, logo, or cover element;
- `audio`: narration loudness, clipping risk, BGM masking, or silence;
- `pacing`: long no-cut range, weak hook, or missing emphasis;
- `reuse`: an emotional shot has lost impact through repetition;
- `caption`: text, style, position, duplication, or semantic breaks;
- `delivery`: duration, resolution, frame rate, black gaps, or export state.
- `renderer`: one-frame black/green/transparent flash, boundary gap, stale-cache reuse or chunk/concat mismatch;
- `overlay`: misplaced/oversized highlight, short evidence hold, internal-production label or wrong chroma/alpha treatment;
- `identity`: malformed or incorrect official face, silhouette, costume or model on a cover/card.

Read [references/review-to-edit-map.md](references/review-to-edit-map.md) for concrete edit patterns.

Write one ledger row per requirement with:

```text
priority category feedback timeline_range planned_edit assets acceptance_test status
```

## 2. Audit the current cut before changing it

1. Record timeline duration, resolution, frame rate, track count, and caption count.
2. Run `scripts/audit_acceptance.py` on the latest rendered picture or exported draft.
3. Inspect the exact reviewer-named ranges.
   Use `scripts/extract_feedback_frames.py VIDEO --time 228 --time 232 --radius-frames 6 --output-dir qa/feedback_frames` to freeze frame-accurate evidence before editing.
4. Count occurrences of any overused shot.
5. Capture the current audio settings for narration and BGM.
6. Save or link a subtitle backup when caption lanes could be affected.
7. For HyperFrames output, compare the source/proxy edge frames with the rendered chunk and assembled master; audit integer-frame boundaries before changing assets.

The audit script provides evidence about black frames, loudness, and long no-cut intervals. Treat scene detection as a review aid, not a substitute for watching the range.

## 3. Fix compliance and opening risks

When the opening or cover must reference another work:

1. Inspect the supplied source and build a contact sheet.
2. Pick visually unmistakable shots, title cards, characters, or iconography.
3. Replace the matching 3-4 second spoken reference with 2-3 motivated shots when fast comparison is appropriate.
4. Avoid spending the main video's emotional climax in the first seconds.
5. Create a cover that shows both works clearly at thumbnail size.
6. Import the cover into Jianying and state separately whether it was applied in the export-cover UI.

For an official character/model cover, compose from frozen official sources by crop, mask, color grade and typography. Do not use AI regeneration to “fix” a named face or costume. Compare the result with its source at full size and thumbnail size.

Verify the spoken reference and inserted visuals overlap in time.

## 4. Correct audio balance

1. Identify whether narration is one clip or many clips.
2. Enable Jianying's loudness normalization or equivalent on all narration clips when requested.
3. Apply the same gain to every narration clip; verify at least the first and last clip numerically.
4. Set BGM relative to narration, not by an isolated absolute number. A 10-14 dB gap is a useful starting range for roughly 20-30% amplitude.
5. Check for clipping risk and masked words.
6. Export a test mix and measure integrated loudness only when the user authorizes export or supplies a rendered mix.

For phone-first information video, prioritize intelligible speech over musical fullness.

## 5. Repair pacing collapse

For a reviewer-named long static range, combine only motivated treatments:

- alternate wide and close shots every 4-6 seconds;
- use slow scale movement such as 100% to 112-115%;
- crop toward the speaking character or emotional reaction;
- insert an intentional black or designed quote card for the central line;
- leave short silence only when it strengthens the beat and does not desynchronize narration.

After inserting a card, verify black detection reports only the intentional interval.

## 6. Reduce overused footage

1. Count exact occurrences and record their timeline positions.
2. Label the narrative purpose of each occurrence.
3. Keep the strongest shot at the climax and optionally one closing callback.
4. Replace hook or exposition occurrences with props, documents, environmental clues, alternate angles, or newly indexed footage.
5. Recount after editing.

Do not solve reuse by applying different crops to the same recognizable emotional moment unless the crops reveal genuinely different information.

## 7. Implement safely in Jianying

- For many picture changes, render a verified picture-only replacement with the exact project duration and use `Replace Clip` on the main video lane.
- Preserve audio and caption lanes during replacement.
- For a few changes, split and replace directly.
- Re-query the UI after every selection or panel change.
- Verify all multi-clip audio edits numerically; do not infer bulk success from one selected clip.

When the defect is in a HyperFrames B-track or picture master:

1. patch the canonical composition or generator, not a derived chunk copy;
2. derive adjacent timing from shared integer frame boundaries;
3. force-render only affected chunks, while requiring valid receipts for every reused chunk;
4. assemble with a receipt bound to the current plan and chunk hashes;
5. regenerate the exact delivery mode (alpha or chroma) and do not verify an old master;
6. re-extract the reported frames plus `-1/0/+1` and continuously play the repaired range.

## 8. Acceptance verification

Require evidence for each ledger row:

- compliance footage appears during the referenced words;
- cover visibly contains every required element;
- narration gain and BGM gain are confirmed across the intended tracks;
- reviewer-named static ranges contain visible changes at the planned cadence;
- intentional black cards are the only unexplained black intervals;
- overused shot count meets the new budget;
- captions remain present, styled, and aligned;
- duration, resolution, frame rate, and frame count are plausible;
- the report distinguishes project changes, generated assets, imported assets, and final exports.
- every reviewer timecode has before/after frame evidence; one-frame flash reports include the exact center frame and neighbors;
- highlight rectangles enclose only the intended source pixels after scaling/padding;
- official faces/models pass direct source comparison; no regenerated likeness is accepted as a repair;
- only intended chunks/ranges changed, or the report explains why a full rebuild was necessary.

Do not perform final export unless the request includes it. Leave the playhead at a useful review point and report what remains for the user.

## Resources

- `scripts/audit_acceptance.py`: probe metadata, measure loudness, detect black intervals, and list long gaps between scene cuts.
- `scripts/extract_feedback_frames.py`: convert reviewer timecodes to exact frame numbers and extract a hash-bound `-N…+N` evidence set.
- [references/review-to-edit-map.md](references/review-to-edit-map.md): translate common reviewer language into concrete edits and acceptance tests.

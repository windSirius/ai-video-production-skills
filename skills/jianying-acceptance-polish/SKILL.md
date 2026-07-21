---
name: jianying-acceptance-polish
description: "Turn client, producer, or platform-review feedback into verified Jianying Pro or CapCut Desktop revisions: translate comments into exact timeline ranges, add missing franchise or reference footage, repair hooks and cover art, normalize narration and BGM balance, break long static sections, add quote cards or slow pushes, reduce overused emotional shots, preserve captions, and produce an evidence-backed acceptance report. Use for 甲方验收修改, 宏观反馈, 技术硬伤, 响度偏低, 节奏塌陷, 素材复用过度, opening/cover requirements, or final pre-export QA."
---

# Jianying Acceptance Polish

Convert broad review language into precise, reversible timeline edits while preserving already-approved narration and captions.

## Non-negotiable rules

- Read and follow the Computer Use skill before operating Jianying or CapCut.
- Treat the review text as requirements, not as permission to alter unrelated creative choices.
- Resolve each comment to an exact timeline range, track, asset, and acceptance test before editing.
- Preserve caption text, styling, and timing unless the feedback explicitly includes subtitles.
- Inspect replacement assets before insertion; filenames alone do not prove content.
- Export or retain recoverable intermediate files for picture-track replacement and cover art.
- Do not claim final integrated loudness unless it was measured from an exported mix.
- Do not claim a cover is applied when it is only generated or imported into the media bin.

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

Read [references/review-to-edit-map.md](references/review-to-edit-map.md) for concrete edit patterns.

Write one ledger row per requirement with:

```text
priority category feedback timeline_range planned_edit assets acceptance_test status
```

## 2. Audit the current cut before changing it

1. Record timeline duration, resolution, frame rate, track count, and caption count.
2. Run `scripts/audit_acceptance.py` on the latest rendered picture or exported draft.
3. Inspect the exact reviewer-named ranges.
4. Count occurrences of any overused shot.
5. Capture the current audio settings for narration and BGM.
6. Save or link a subtitle backup when caption lanes could be affected.

The audit script provides evidence about black frames, loudness, and long no-cut intervals. Treat scene detection as a review aid, not a substitute for watching the range.

## 3. Fix compliance and opening risks

When the opening or cover must reference another work:

1. Inspect the supplied source and build a contact sheet.
2. Pick visually unmistakable shots, title cards, characters, or iconography.
3. Replace the matching 3-4 second spoken reference with 2-3 motivated shots when fast comparison is appropriate.
4. Avoid spending the main video's emotional climax in the first seconds.
5. Create a cover that shows both works clearly at thumbnail size.
6. Import the cover into Jianying and state separately whether it was applied in the export-cover UI.

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

Do not perform final export unless the request includes it. Leave the playhead at a useful review point and report what remains for the user.

## Resources

- `scripts/audit_acceptance.py`: probe metadata, measure loudness, detect black intervals, and list long gaps between scene cuts.
- [references/review-to-edit-map.md](references/review-to-edit-map.md): translate common reviewer language into concrete edits and acceptance tests.

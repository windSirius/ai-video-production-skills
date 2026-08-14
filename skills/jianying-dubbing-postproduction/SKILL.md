---
name: jianying-dubbing-postproduction
description: "Build and repair the canonical narration/subtitle timeline in Jianying Pro or CapCut Desktop: choose the current hash-bound audio master, run Manuscript Match, resegment against the canonical manuscript, preserve project typography, eliminate punctuation-only and duplicate rows, verify lexical coverage and audio-tail tolerance, export versioned SRT backups, and prove the live timeline matches the audited file. Use for VoxCPM narration import, 文稿匹配, 修字幕, 最终版字幕, semantic resegmentation, duplicate cleanup, or subtitle authority/version conflicts."
---

# Jianying Dubbing Postproduction

Turn numbered narration WAV files and a clean script into one sequential audio track with matched, styled, semantically clean captions.

## Non-negotiable rules

- Read and follow the Computer Use skill before operating Jianying or CapCut.
- Treat every control labeled 「试试剪映助手」 or 「剪映助手」 as permanently forbidden. Never click, open, dismiss, focus, test, or use it. If it obscures a required control, use a verified non-assistant route or stop the live action; when called by `zhangyanfa-video-production`, obey its route-preflight, per-step pre-click authorization, and harness-managed trace gates.
- Preserve the user's open project and prepared UI state. Re-query the app after every meaningful action and whenever the user interacts.
- Never append audio while the playhead is still at zero. Focus the timeline, jump to the project end, then add the next clip.
- Never simulate a caption merge by assigning the same complete sentence to adjacent time segments. This creates duplicate rows even if the rendered pixels look continuous.
- Never delete the old caption track until a replacement track is imported, recognized as captions, and verified on the timeline. Export a recoverable subtitle backup first.
- Do not assume `File > Import` imports SRT as captions. Some Jianying builds treat that command as media import or ignore SRT. Verify the result before changing the project.
- Use the verified macOS SRT route: export captions first; edit and audit the SRT offline; return through `文本 > 新建文本 > 导入本地字幕`; verify the imported file appears as a `本地字幕` material card; then drag that card into the timeline. Import completion alone does not create a caption track.
- Caption-list edits rebuild accessibility elements. Fetch fresh UI state after each text edit; never reuse stale element indexes.
- Preserve the requested font, preset, size, and position while editing caption text.
- Treat the clean narration manuscript as the semantic authority and Manuscript Match timing as an initial alignment, not as an approved caption segmentation.
- Authority order is: user-designated final SRT, canonical narration manuscript bound by the current audio manifest, `segments.json` canonical text, raw Manuscript Match, then ASR. `generation_text` and ASR spellings are never subtitle authority.
- Select the narration master by the latest passing `audio_manifest.json` SHA, not by filename, modification time, or an older `audio_repaired` directory.
- Prove that the final caption sequence covers the manuscript-matched text exactly once in order. Never accept a visually plausible result with omitted, repeated, or reordered words.
- When a user-adjusted SRT exists, treat it as the strongest evidence of project-specific segmentation and punctuation preferences. Compare it with the prior semantic version before applying generic length rules.
- Apply this user's default terminal-punctuation rule to every final caption: remove `，。；：,.;:` at the effective end, including immediately before trailing `」』”’）》〉）】`; preserve `？！?!` unless the user explicitly overrides the style.

## Choose the scope

Use `voxcpm-batch-dubbing` first when narration still needs to be generated. Start this skill when numbered WAV files already exist or the user has prepared a Jianying project.

Resolve:

- ordered WAV files and their durations;
- the exact clean narration manuscript used for Manuscript Match;
- the open Jianying project;
- caption style settings;
- whether the request stops after matching, includes semantic editing, or includes export.

Read [references/version-authority.md](references/version-authority.md) whenever multiple scripts, SRTs, repair runs or similarly named masters exist. Record the chosen manuscript, audio and SRT hashes before editing.

## 1. Attach to Jianying safely

1. Prefer the running Jianying window. Use the full app path when the display name or bundle identifier is ambiguous.
2. Capture a fresh accessibility tree and screenshot before acting.
3. Treat screenshots as the source of truth when the accessibility tree omits unlabeled controls.
4. If the user changes the app, discard the current plan's coordinates and element indexes, then re-query.

Read [references/jianying-ui.md](references/jianying-ui.md) for UI-specific recovery notes.

## 2. Build one sequential narration track

1. Import all numbered WAV files and confirm the expected count.
2. Add them in filename order.
3. Before each add, focus the timeline and jump to the current project end.
4. Confirm each new clip lands after the prior clip on the same audio track, without overlap or stacking.
5. Compare the timeline end time with the summed WAV durations. Investigate discrepancies larger than normal frame rounding.

Do not rely on multi-select drag when the editor's insertion behavior is unclear. Sequential add-at-end is slower but deterministic.

## 3. Run Manuscript Match

1. Open `Text > Smart Text > Manuscript Match` (`文本 > 智能文本 > 文稿匹配`).
2. Click `Start Using` (`开始使用`).
3. Inspect the dialog before choosing an input method. In builds that expose only a text area, paste the manuscript; do not claim a file was dragged in.
4. Paste narration only. Remove titles, page numbers, headers, and document furniture.
5. Click `Start Match` (`开始匹配`) and wait until caption clips appear across the timeline.
6. Verify the first and last captions and confirm coverage reaches the narration end.

## 4. Apply caption style in bulk

Select only the caption track with a marquee or caption-specific multi-select. Exclude audio clips and verify the selected-caption count before changing style.

Apply the user-specified style. For this user's established house style, use unless overridden:

- font: `新青年体`;
- preset: second preset, white outline with black fill;
- position: `X = 0`, `Y = -888`.

After applying, inspect a caption near the beginning, middle, and end. Confirm that bulk edits did not reset font, preset, scale, or position.

## 5. Freeze the raw match and plan semantic captions

Read [references/caption-editing.md](references/caption-editing.md) before large caption edits.

1. Open the top-right `导出` dialog, disable video and audio export, enable `字幕导出`, choose `SRT` with `Unicode / UTF-8`, and export the untouched Manuscript Match result as `captions_matched_raw.srt` before editing.
2. Open the right-side `Captions` (`字幕`) list and extract the complete indexed sequence.
3. Align every raw caption with its exact span in the clean manuscript.
4. Build `caption_semantic_plan.tsv` before live edits. Record old rows, source manuscript span, planned caption text, planned one/two-line layout, timing strategy, and reason.
5. Require the plan to cover the matched narration text exactly once, in order.

## 6. Rebuild semantic segmentation and line layout

1. Decide semantic caption boundaries from the manuscript, audible phrasing, and rhetorical intent. Do not preserve a bad machine boundary merely because Jianying created it.
2. Keep grammatical and rhetorical units intact. Avoid isolated conjunctions, particles, subjects without predicates, unmatched quotation marks, and sentence tails that depend on the previous caption.
3. Separate semantic segmentation from visual line wrapping:
   - one caption clip represents one spoken thought or intentional short beat;
   - keep one logical SRT text line by default for this user's current house style and let Jianying wrap it naturally;
   - use an explicit newline only when the project already uses manual line breaks or live preview proves that a phrase-safe two-line layout is necessary;
   - when manually breaking two lines, place the break at a phrase boundary and balance visual width;
   - never split a name, title, fixed term, number-unit pair, or quoted phrase only to equalize width.
4. Prefer one complete logical caption over several machine-cut fragments. Let long direct quotations remain intact when their display duration is sufficient; do not split a quotation solely to satisfy a character target.
5. Separate a narrator lead-in from the direct quotation when the lead-in has its own spoken beat: for example, use `开拓者转述的时候说得很硬` followed by the complete quotation, rather than attaching half of the quotation to the lead-in.
6. Treat 7–18 visible Chinese characters as a diagnostic range, not a target. Allow shorter deliberate beats and longer complete quotations when timing and readability support them. Review captions over 24 visible characters without automatically splitting them.
7. Restore internal commas where they express audible breathing, contrast, or clause structure. At every effective caption ending, remove `，。；：,.;:`; first ignore any trailing `」』”’）》〉）】` so forms such as `；」` and `。」` are also repaired. Preserve `？！?!`.
8. Use the verified caption-SRT replacement path when true clip merging or splitting is required. If caption import is unavailable, redistribute meaning across existing timing segments without duplicates, empty rows, or punctuation-only rows.
9. During live caption-list editing, change one row, fetch fresh UI state, and locate the next row by current text and order.
10. Re-scan the full caption list after every bounded group of edits.

If two existing time segments must remain separate, distribute meaning across them instead of duplicating the combined sentence. Example:

```text
Bad
35 最后一行是「你离开后连精灵都失去期待」
36 最后一行是「你离开后连精灵都失去期待」

Good
35 最后一行是
36 「你离开后连精灵都失去期待」
```

## 7. Clean adjacent duplicates

1. Audit every adjacent caption pair after semantic resegmentation.
2. Merge truly identical adjacent entries by extending the earlier range only when the caption import/replacement workflow is verified.
3. Otherwise redistribute the sentence across the existing segments. Never place the same complete sentence in both rows.
4. Require adjacent exact duplicates to equal zero before exporting the final backup.

## 8. Use SRT replacement only when verified

When the installed build supports caption-file import:

1. Preserve `captions_matched_raw.srt`, then create the planned semantic SRT as a separate version.
2. Run `scripts/merge_adjacent_srt.py` to merge adjacent identical captions and extend the earlier time range.
3. Run `scripts/audit_semantic_srt.py raw.srt final.srt --canonical-source 口播纯文本.md --audio-duration-seconds <seconds>` and require it to pass before touching the live timeline.
4. In Jianying, open `文本 > 新建文本 > 导入本地字幕`; do not use `文件 > 导入`.
5. Select the audited SRT and confirm the system file dialog.
6. Verify that Jianying created a `本地字幕` material card whose displayed filename matches the audited SRT. This proves only that the file entered the material panel.
7. Drag that exact local-subtitle card into the timeline. Do not claim success merely because the card exists.
8. Prove the caption-track count changes `1 → 2`, and verify the new track's caption count, first text, last text, and timing against the audited SRT.
9. Only after the new track is verified, remove the old raw-caption track and prove the count changes `2 → 1`.
10. Reapply style if import resets it, then export and audit the surviving caption track.

When caption-file import is absent or unverified, keep the original timing segments and perform semantic redistribution in the caption list. Keep the cleaned SRT as a backup, not as proof that the live project changed.

## 9. Export the final SRT backup

1. Save the live project after semantic edits and duplicate cleanup.
2. Open the top-right `导出` dialog, disable video and audio export, enable `字幕导出`, choose `SRT` with `Unicode / UTF-8`, and export the edited caption track as `captions_semantic_final.srt`.
3. Parse the exported file and report its entry count and final end time.
4. Run `scripts/audit_semantic_srt.py captions_matched_raw.srt captions_semantic_final.srt --canonical-source 口播纯文本.md --audio-duration-seconds <seconds>`.
5. If the exported final SRT does not match the live caption list, do not report the backup as final; repair the export or label it accurately.

## 10. Final verification

Verify all of the following before reporting completion:

- audio clips are ordered, non-overlapping, and total duration is plausible;
- captions cover the narration from start to finish;
- the requested style appears at the beginning, middle, and end;
- adjacent exact duplicate captions equal zero;
- no caption ends in `，。；：,.;:`, including before trailing `」』”’）》〉）】`; `？！?!` remain permitted;
- normalized final text covers the raw Manuscript Match text exactly once and in order, apart from approved terminal style punctuation;
- normalized final text also covers the frozen canonical narration text exactly once; when the user directly supplied a final SRT, record that this SRT supersedes the earlier segmentation while preserving lexical coverage;
- no row consists only of punctuation or an unmatched closing quote;
- semantic boundaries follow the manuscript rather than arbitrary ASR fragments;
- one/two-line wrapping is readable and does not split names, fixed terms, number-unit pairs, or quotations improperly;
- quoted passages are balanced across their visible units;
- the user's example problem is visibly corrected in the live project;
- both the untouched raw-match SRT and edited final SRT paths exist, and their entry counts are reported separately from the live project count.
- final SRT end time differs from the current audio master only within the frozen tolerance (100 ms by default; ordinary frame rounding such as 43 ms is acceptable).

State clearly whether work is saved only in the project, backed up as SRT, or exported as video.

When the narration and captions are stable but picture selection remains weak, hand the project, SRT backup, and source footage to `jianying-sentence-visual-matching`. Use `jianying-acceptance-polish` after picture matching for focused reviewer feedback and final pre-export risk checks.

## Resources

- [references/jianying-ui.md](references/jianying-ui.md): Jianying UI mapping, accessibility behavior, and recovery rules.
- [references/caption-editing.md](references/caption-editing.md): semantic segmentation and duplicate-prevention heuristics.
- [references/version-authority.md](references/version-authority.md): canonical text/audio/SRT priority, proxy spellings, and stale-version avoidance.
- `scripts/merge_adjacent_srt.py`: audit or merge adjacent identical SRT entries without losing their combined time span.
- `scripts/audit_semantic_srt.py`: verify raw and canonical text coverage, ordering, duplicates, punctuation-only rows, forbidden terminal punctuation, quote balance, audio-tail tolerance, length, and reading-speed warnings.

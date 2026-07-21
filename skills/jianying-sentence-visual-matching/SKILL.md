---
name: jianying-sentence-visual-matching
description: "Match narration or captions to source footage sentence by sentence, exhaustively retrieve and rank multiple candidates for every spoken unit, build searchable shot indexes and contact sheets, control clip reuse, generate an auditable match plan, rebuild the picture track, and verify synchronization in Jianying Pro or CapCut Desktop. Use for 剪映画面匹配, 每句话独立找画面, 逐句找素材, 口播与游戏画面对齐, subtitle-to-shot matching, replacing generic or repeated footage, adding newly uploaded scenes, or rebuilding a timeline whose dialogue does not match the picture."
---

# Jianying Sentence Visual Matching

Build a picture track from narration meaning, one spoken unit at a time, without losing the user's captions, audio, or prepared Jianying project.

## Non-negotiable rules

- Read and follow the Computer Use skill before operating Jianying or CapCut.
- Preserve the narration, caption timing, caption style, and audio tracks unless the user explicitly asks to change them.
- Treat every sentence or caption unit as an independent retrieval problem. Do not select one long source passage merely because it roughly covers a paragraph.
- Produce at least three candidates for every ordinary sentence before selecting one. For a uniquely constrained line, document why fewer exist and run the expansion ladder.
- Inspect enough source frames before concluding that no suitable shot exists. One coarse contact sheet is never sufficient evidence.
- Prefer semantic relevance first, then emotional fit, then motion continuity and visual quality.
- Track reuse explicitly. Do not spend the strongest emotional shot in the hook if it is needed for the climax.
- Never claim the live project changed until the replacement is visible on the Jianying timeline.
- Keep a recoverable match plan outside the editor.
- Do not bulk-apply an incomplete match plan. Finish retrieval, ranking, and reuse review first.

## Definition of done

The task is complete only when:

- every spoken unit has a selected shot or an intentional text/card treatment;
- every selection has candidate evidence and a concrete match reason;
- all weak or low-confidence rows have completed a second retrieval pass;
- exact source in/out points cover the caption duration;
- reuse and continuity audits pass;
- the rebuilt picture track is visible in Jianying and its duration still matches the stable narration timeline.

## Inputs and handoff

Resolve:

- clean narration text or the current SRT/caption list;
- ordered source videos, including newly uploaded footage;
- the open Jianying project or a target output video;
- any must-use or forbidden shots;
- the intended platform and pacing tolerance.

Use `jianying-dubbing-postproduction` first when audio order, manuscript matching, or caption cleanup is unfinished. This skill should receive stable narration timing.

## 1. Freeze the narration timeline

1. Export or locate an SRT backup when possible.
2. Convert the caption sequence to a match sheet with `scripts/srt_to_match_sheet.py`.
3. Preserve start time, end time, text, and line order.
4. Merge only captions that form one inseparable spoken idea. Keep deliberate short beats separate.
5. Do not change timing while searching for footage.

## 2. Build a searchable shot inventory

1. Probe every source clip for duration, resolution, and frame rate.
2. Run `scripts/build_shot_index.py` with a coarse interval such as 5-10 seconds across every source, including the beginning, ending, title cards, and newly uploaded footage.
3. Inspect the contact sheets and annotate useful characters, locations, props, actions, emotional states, and title cards.
4. Re-index promising ranges at 1-2 second intervals. Use sub-second inspection for brief expressions, documents, transitions, or name cards.
5. Record exact source in/out points, not only thumbnail timestamps.

Read [references/matching-heuristics.md](references/matching-heuristics.md) before choosing shots for a long script.

## 3. Match each sentence independently

For every row in the match sheet, complete this closed loop before moving on:

1. Extract the sentence's concrete nouns, named characters, actions, location, emotional direction, and narrative function.
2. Search the full inventory for literal matches and record candidate A.
3. Search alternate characters, angles, actions, or objects and record candidates B and C.
4. Score each candidate for semantic match, emotional match, continuity, visual quality, and reuse cost. Select the highest justified total, not merely the prettiest frame.
5. If every candidate is weak, run the expansion ladder in [references/matching-heuristics.md](references/matching-heuristics.md), then search again. Do not silently accept a generic filler shot.
6. Choose an exact source range long enough to cover the narration without looping visibly.
7. Record source clip, source in/out, treatment, candidate scores, selection reason, confidence, retry round, and reuse group.
8. Compare the selection with the previous and next rows. Change it if it repeats a subject, location, or emotional beat without purpose.
9. Mark the row `planned` only after the selected shot passes duration, reuse, and adjacency checks.

Use 2-3 shots inside a 3-4 second slot only for intentional hooks, comparisons, or named references. Do not turn the whole video into arbitrary fast cuts.

After all rows are planned, run `scripts/audit_match_sheet.py`. Resolve every reported error before touching the live timeline.

## 4. Budget strong shots

Classify standout footage before editing:

- `hook`: immediately legible but not the final emotional payoff;
- `exposition`: readable locations, props, documents, and character context;
- `escalation`: reactions and closer framing;
- `climax`: the strongest reveal, reunion, embrace, or collapse;
- `resolution`: calm aftermath or thematic closing image.

Reserve climax footage for the climax and at most one closing callback. Replace excessive reuse with alternate angles, object details, wider shots, or newly indexed footage.

## 5. Rebuild the picture track

Choose the safest implementation:

- For a fragile existing project, replace picture segments while leaving caption and audio lanes untouched.
- For many deterministic replacements, build an intermediate picture-only video from the match sheet, verify its exact duration and frame count, then use Jianying's `Replace Clip` on the main video track.
- For a few corrections, split and replace directly in Jianying.

Apply replacements in timeline order. After each major section, verify the project duration did not change and subtitles remain aligned. Use crop variants, slow pushes, or alternate angles only when they support the current sentence. Keep the previous picture track disabled or backed up until final QA passes.

## 6. Verify the result

Inspect at minimum:

- the first and last frame of every major section;
- every newly inserted source;
- every repeated shot occurrence;
- each emotionally important line;
- transitions around black cards or title cards;
- the first, middle, and last caption alignment.

Require:

- every match-sheet row has a source or a documented intentional card;
- every low-confidence row shows a completed expansion/retry pass;
- no unexplained black gap exists;
- no clip ends before its caption;
- source reuse counts stay within the chosen budget;
- the final picture duration equals the narration timeline within frame rounding.

Hand the verified timeline to `jianying-acceptance-polish` when reviewer feedback, loudness, pacing, cover, or delivery-risk fixes remain.

## Resources

- `scripts/build_shot_index.py`: sample source videos, make contact sheets, and write a timestamped shot index.
- `scripts/srt_to_match_sheet.py`: convert stable SRT timing into a traceable TSV matching template.
- `scripts/audit_match_sheet.py`: reject incomplete candidates, invalid source ranges, weak unchecked rows, and unexplained reuse before editing.
- [references/matching-heuristics.md](references/matching-heuristics.md): retrieval, shot selection, continuity, and reuse heuristics.

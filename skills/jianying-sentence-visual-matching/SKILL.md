---
name: jianying-sentence-visual-matching
description: "Build reusable narration-to-picture edits with an indexed bulk workflow: freeze the final SRT, search a full Vision/OCR shot corpus, retain a full candidate pool and expose at least three ranked choices per cue, optimize selections globally, review every selected shot plus risk-row candidates and identities, render an equal-duration picture-only master, and apply hash-bound incremental repairs before Jianying replacement. Use for 剪映画面匹配, 批量逐句配画, 每句话找多个候选, 口播与游戏画面对齐, subtitle-to-shot matching, rebuilding a long picture track, or repairing generic, repeated, or semantically wrong footage."
---

# Jianying Sentence Visual Matching

Build a picture track from narration meaning without losing the user's captions, audio, or prepared Jianying project. For long-form rebuilds, use one complete indexed match plan as the scalable work unit; keep cue-level review and repair traceable inside that plan.

## Non-negotiable rules

- Read and follow the Computer Use skill before operating Jianying or CapCut.
- Treat every control labeled 「试试剪映助手」 or 「剪映助手」 as permanently forbidden. Never click, open, dismiss, focus, test, or use it. If it obscures a required control, use a verified non-assistant route or stop the live action; when called by `zhangyanfa-video-production`, obey its route-preflight, per-step pre-click authorization, and harness-managed trace gates.
- Preserve the narration, caption timing, caption style, and audio tracks unless the user explicitly asks to change them.
- Treat every sentence or caption unit as an independent retrieval query even when retrieval runs in one bulk job. Do not select one long source passage merely because it roughly covers a paragraph.
- Produce at least three distinct candidates for every ordinary unit before machine selection. For a uniquely constrained line, document why fewer exist and run the expansion ladder.
- Inspect enough source frames before concluding that no suitable shot exists. One coarse contact sheet is never sufficient evidence.
- Prefer semantic relevance first, then identity correctness, emotional fit, motion continuity, and visual quality.
- Track reuse explicitly. Do not spend the strongest emotional shot in the hook if it is needed for the climax.
- Never claim the live project changed until the replacement is visible on the Jianying timeline.
- Keep a recoverable match plan outside the editor.
- Do not equate three populated candidate fields with three visually reviewed candidates. Record machine proposal, selected-shot review, candidate review, and identity review as separate states.
- Do not bulk-apply an incomplete plan. Finish global retrieval, selected-contact review, risk-row A/B/C review, reuse/overlap audit, and opening/ending review first.

## Definition of done

The task is complete only when:

- every spoken unit has a selected shot or an intentional text/card treatment;
- every selection has candidate evidence, a concrete match reason, and a selected-shot review;
- every identity-sensitive, hook, ending, quotation, external-asset, low-confidence, or high-OCR-collision row has an A/B/C review;
- every named-character row has an explicit identity verdict independent of lexical/OCR similarity;
- all weak or low-confidence rows have completed a second retrieval pass;
- exact source in/out points cover the caption duration;
- reuse and continuity audits pass;
- the review bundle binds to the current match-sheet SHA-256 and contains no unresolved repair row;
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
5. Normalize Vision/OCR, annotations, evidence-frame paths, source identity, rights status, and exact source in/out points into one searchable corpus.

Read [references/matching-heuristics.md](references/matching-heuristics.md) before choosing shots for a long script.
Read [references/indexed-bulk-workflow.md](references/indexed-bulk-workflow.md) for the reusable plan, review, repair, and Harness schemas.

## 3. Choose the execution route

- Use the indexed bulk route by default for a full rebuild or roughly 30 or more units. One complete plan is one bounded unit under `match_plans_per_batch=1`; the bundle check must prove coverage of every cue.
- Use the focused row route for a few corrections or when no normalized index exists. Keep `match_rows_per_batch=1` for this route.
- Never disguise a bulk plan as one generic `offline_artifact`. When the parent production Harness is active, use its registered visual-index, bulk-plan, review, repair, render, and patch actions.

## 4. Build the indexed bulk proposal

1. Parse every unit into subject, named entities, action/state, object/location, emotion, narrative job, and required screen time.
2. Build a project identity dictionary before retrieval. Keep visually distinct characters separate even when OCR or dialogue places their names in the same frame.
3. Search the full corpus in one job. Combine text/OCR similarity, aliases, chapter source priors, exact-quote bonuses, source phase, and negative penalties for menus, loading, black transitions, UI clutter, unresolved OCR, and source edges.
4. Retain the complete viable candidate pool, normally 32–64 results when available, then record at least A/B/C with distinct source ranges. Give every candidate a stable ID and head/middle/tail evidence. Run the expansion ladder when the pool remains weak.
5. Make a provisional selection against the full pool using global reuse, overlap, reverse-order, adjacency, and strong-shot-budget costs, not independent top-one ranking alone.
6. Record the complete machine proposal in `match_sheet.tsv` with `qa_status=machine_proposed`; do not mark it reviewed or render-ready.
7. Generate selected-shot evidence for every unit and A/B/C evidence for every risk row.

Use 2-3 shots inside a 3-4 second slot only for intentional hooks, comparisons, or named references. Do not turn the whole video into arbitrary fast cuts.

## 5. Review and approve the plan

1. Inspect the complete selected-shot contact sheets for semantic flow, black/flash events, framing, and repetition.
2. Inspect A/B/C head/middle/tail contact sheets for all risk rows defined in the indexed workflow reference.
3. Verify named-character identity from the image itself or trusted character evidence; dialogue text that mentions a name is not identity proof.
4. Audit the first hook interval and ending interval as independent sequences rather than isolated thumbnails.
5. Write a review manifest bound to the exact match-sheet hash. Record reviewed cue IDs, evidence paths, identity verdicts, unresolved rows, and reviewer notes.
6. Apply review decisions through a repair manifest. A manual override must enter the retained pool with evidence before selection. Rerun global reuse/overlap checks and repeat until no unresolved row remains.
7. Run `scripts/audit_match_sheet.py --stage render-ready` with the canonical SRT, current source manifest, candidate pool, review manifest, and selected-evidence TSV. The script delegates the final review gate to the production checker so the standalone skill cannot pass a weaker audit. Do not render on the proposed-stage audit alone.

## 6. Budget strong shots

Classify standout footage before editing:

- `hook`: immediately legible but not the final emotional payoff;
- `exposition`: readable locations, props, documents, and character context;
- `escalation`: reactions and closer framing;
- `climax`: the strongest reveal, reunion, embrace, or collapse;
- `resolution`: calm aftermath or thematic closing image.

Reserve climax footage for the climax and at most one closing callback. Replace excessive reuse with alternate angles, object details, wider shots, or newly indexed footage.

## 7. Render and repair the picture master

Choose the safest implementation:

- For a fragile existing project, replace picture segments while leaving caption and audio lanes untouched.
- For many deterministic replacements, build an intermediate picture-only video from the reviewed plan, verify exact duration and frame count, then use Jianying's `Replace Clip` on the main video track.
- For a few corrections, split and replace directly in Jianying.

For feedback after a master exists, patch only declared cue/range IDs through a hash-bound repair manifest. Re-audit the whole plan and source overlap after every patch. Incrementally rerender only when the unchanged ranges and exact frame boundaries are proven; otherwise rerender the full master. Keep prior masters recoverable until acceptance.

## 8. Apply and verify the result

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
- every risk row has the required A/B/C or identity review;
- no unexplained black gap exists;
- no clip ends before its caption;
- source reuse counts stay within the chosen budget;
- the final picture duration equals the narration timeline within frame rounding.

Hand the verified timeline to `jianying-acceptance-polish` when reviewer feedback, loudness, pacing, cover, or delivery-risk fixes remain.

## Resources

- `scripts/build_shot_index.py`: sample source videos, make contact sheets, and write a timestamped shot index.
- `scripts/srt_to_match_sheet.py`: convert stable SRT timing into a traceable TSV matching template.
- `scripts/build_candidate_review_sheets.py`: render selected and A/B/C evidence, require the current candidate pool, and bind the manifest to both match-sheet and pool hashes.
- `scripts/audit_match_sheet.py`: audit proposed, reviewed, or render-ready stages without conflating them.
- `scripts/apply_match_repairs.py`: require base match-sheet, review, and candidate-pool hashes; apply only covered decisions; add reviewed overrides as `manual_expansion`; and keep recoverable prior snapshots.
- [references/matching-heuristics.md](references/matching-heuristics.md): retrieval, shot selection, continuity, and reuse heuristics.
- [references/indexed-bulk-workflow.md](references/indexed-bulk-workflow.md): canonical artifact bundle, risk gates, repair loop, and Harness mapping.

When the system Python lacks Pillow, load the Codex workspace dependencies and run the review-sheet builder with the bundled Python executable; do not weaken or skip the evidence stage.

---
name: top-tier-narrative-editing
description: Research, model, test, and iteratively improve top-tier narrative editing for game lore, character studies, documentary explainers, and video essays. Use when Codex must learn from excellent references and real client outcomes, distinguish transferable editorial grammar from surface imitation, benchmark scripts/cuts/covers, design A/B experiments, evaluate hooks, A/B/C track reasoning, evidence readability, source/identity fidelity, pacing, emotion, sound and production reliability, or promote verified findings into reusable workflows.
---

# Top-tier narrative editing

## Objective

Learn the mechanisms that make excellent narrative edits clear, compelling, and emotionally controlled. Apply those mechanisms to the target format without treating the user's current editing habits as the quality ceiling.

Treat the user's existing work as evidence of subject, voice, constraints, and available production methods. Treat recognized reference works, repeated cross-creator patterns, controlled comparisons, and real audience behavior as quality evidence.

## Required references

- Read [benchmark-framework.md](references/benchmark-framework.md) before choosing reference works.
- Read [quality-rubric.md](references/quality-rubric.md) before evaluating or revising an edit.
- Read [learning-protocol.md](references/learning-protocol.md) before recording, promoting, or retiring a rule.
- Read [data-contract.md](references/data-contract.md) before creating or changing corpus, hypothesis, or experiment data.

Use `jianying-zhangyanfa-style` only as the application layer for Alan's current project conventions. Do not let that personal profile override stronger benchmark evidence unless the user explicitly prefers the personal behavior.

## Core model

Separate every decision into four layers:

1. **Narrative function**: hook, setup, claim, evidence, counterpoint, turn, payoff, or resolution.
2. **Viewer state**: curiosity, orientation, comprehension, tension, doubt, empathy, release, or reflection.
3. **Editorial mechanism**: shot choice, cut timing, juxtaposition, motif, typography, silence, music, sound effect, or evidence card.
4. **Implementation**: exact media, duration, track, animation, volume, and Jianying operation.

Never learn an implementation detail as a universal rule when only the narrative mechanism repeats.

## Iteration workflow

1. Define the target format, audience promise, delivery platform, duration, and production constraints.
2. Divide the script into narrative units and state the intended viewer-state change for each unit.
3. Select a small reference cluster for the relevant problem. For user-designated Bilibili seasons, fetch complete episode metadata with `scripts/fetch_bilibili_season.py`, then use `scripts/select_bilibili_samples.py` to create a coverage-oriented review queue. Treat its output as sampling priority, never a quality ranking. Do not use one creator as the entire benchmark.
4. For local reference files, measure cadence, first frames, audio, and representative frames. Run `scripts/analyze_visual_refresh.py` when the edit uses persistent anchors, picture-in-picture, overlays, or subtle graphic refreshes that a conventional hard-cut detector may miss. When timed narration transcripts are available, run `scripts/summarize_av_alignment.py` to compare speech cadence, visual refresh, and rough boundary alignment across samples. Treat both outputs as measurement proxies and combine them with manual semantic review; neither cut detection nor ASR segmentation can identify editorial intent.
5. Record observations as hypotheses, not rules.
6. Create at least two materially different treatments for the highest-impact uncertain section, usually the opening, first proof sequence, emotional turn, or ending.
7. Score both treatments with [quality-rubric.md](references/quality-rubric.md). Run `scripts/evaluate_edit.py` for consistent aggregation and hard-gate checks.
8. Prefer blind or minimally primed comparison when practical. Hold the script, narration, and source pool constant when testing an editorial mechanism.
9. Record the outcome using [learning-protocol.md](references/learning-protocol.md).
10. Run `scripts/validate_learning_data.py` against the corpus and hypothesis registries before promoting, narrowing, or retiring a hypothesis.
11. Recheck previously passed quality gates after every change. Improvement in pace must not silently damage clarity, identity accuracy, evidence readability, audio, or emotional continuity.
12. Treat production failures as data too. A one-frame renderer gap, unreviewed silhouette, malformed official face, stale cache or unreadable card is not an artistic preference; fix the hard gate before comparing aesthetics.

## Evidence levels

- **H0 — Idea**: plausible editorial hypothesis with no direct comparison.
- **H1 — Observed**: present in one strong reference or one successful project.
- **H2 — Repeated**: found across at least three relevant works from at least two independent creators, with the same underlying function.
- **H3 — Tested**: wins a controlled comparison or resolves a clearly diagnosed failure without causing regressions.
- **H4 — Operational**: succeeds across at least three target projects and has measurable audience or acceptance evidence.

Only H3 and H4 findings may become defaults. H1 and H2 findings remain conditional guidance.

## What to learn

- How the opening converts title/thumbnail expectation into a precise viewing promise.
- How every visual either advances action, explains a claim, proves a claim, reveals character, creates contrast, or controls emotion.
- How cuts follow changes in meaning, attention, action, gaze, or sound instead of arbitrary sentence boundaries.
- How factual evidence remains attributable and readable while the emotional thread stays alive.
- How music, silence, ambience, and effects shape chapters and emphasis without competing with narration.
- How motifs, callbacks, withheld information, and payoff create continuity across long-form work.
- How the edit varies density: compression for argument and discovery, expansion for consequence and reflection.
- How review-first B/C asset approval and official-source cover fidelity prevent expensive downstream rework.
- How chunked rendering, shared integer-frame boundaries and hash-bound receipts preserve the intended edit without invisible technical regressions.

## What not to learn

- View count as proof of editing quality.
- A creator's font, LUT, transition pack, color palette, or music library as transferable grammar.
- Fast cutting as a universal retention solution.
- One video's exact shot-duration median as a target.
- Accidental compression, low resolution, watermarks, or platform artifacts.
- Copyrighted sequences as reusable templates.
- The user's current implementation merely because it is familiar.

## Quality claim policy

Do not describe an output as “top-tier” merely because it is polished or scores well on an internal rubric. State the evidence level and unresolved uncertainties. Internal scoring is a revision proxy; published audience retention and repeated project outcomes are stronger evidence.

When YouTube analytics are available, compare the video's first 30 seconds, dips, spikes, and top moments with its own similar-length baseline. Do not invent universal retention thresholds.

## Deliverables

For each learning cycle, preserve:

- reference cluster and selection rationale;
- narrative-unit map;
- hypotheses and evidence levels;
- A/B treatments or before/after artifacts;
- rubric results and hard-gate failures;
- audience or acceptance evidence when available;
- promoted, narrowed, and retired rules;
- the next highest-value uncertainty.
- client/platform review rows, exact repair evidence, and whether the failure was editorial, asset-fidelity, UI, renderer, cache, or delivery related.

Keep artifacts versioned and recoverable. Never overwrite the only good draft or picture master.

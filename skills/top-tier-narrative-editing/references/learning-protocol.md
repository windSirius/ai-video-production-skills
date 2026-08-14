# Learning and iteration protocol

## Experiment record

Create one record per meaningful editorial hypothesis:

```json
{
  "experiment_id": "YYYYMMDD-project-section-hypothesis",
  "target": "project and exact timeline range",
  "narrative_function": "hook|setup|claim|evidence|counterpoint|turn|payoff|resolution",
  "hypothesis": "If X changes, Y viewer state should improve because Z",
  "evidence_level_before": "H0|H1|H2|H3|H4",
  "reference_evidence": [],
  "control": "what remains unchanged",
  "variant_a": "current treatment",
  "variant_b": "test treatment",
  "rubric_a": {},
  "rubric_b": {},
  "external_result": null,
  "regressions": [],
  "production_gate_results": {},
  "client_feedback_rows": [],
  "decision": "promote|narrow|retain|retire",
  "evidence_level_after": "H0|H1|H2|H3|H4",
  "next_test": ""
}
```

## Promotion rules

- Promote H0 to H1 after a clear observation in one relevant, strong reference.
- Promote H1 to H2 only after the same mechanism appears across at least three relevant works from at least two creators.
- Promote H2 to H3 only after a controlled project comparison supports it and hard gates remain passed.
- Promote H3 to H4 only after success across at least three target projects plus audience, acceptance, or equivalent outcome evidence.
- Narrow a rule when it works only for a specific narrative function, duration, audience, or source type.
- Retire a rule when it repeatedly loses comparisons or creates regressions.

## Contrastive learning

Prefer comparisons that isolate one editorial mechanism:

- consequence-first versus context-first opening;
- literal B-roll versus character-reaction evidence;
- rapid montage versus held proof;
- continuous BGM versus chapter change;
- narration-only transition versus sound bridge;
- chronological explanation versus question-driven reveal.

Do not compare two variants that change script, narration, footage pool, music, typography, and pacing simultaneously.

## Regression ledger

After every apparent improvement, recheck:

- identity and factual accuracy;
- narration intelligibility;
- evidence reading time;
- emotional continuity;
- source reuse;
- caption timing and safe area;
- first and final frames;
- recoverability of the previous draft.
- official-source identity fidelity in cover/silhouette assets;
- B/C asset review status and audience-card cleanliness;
- full-frame/UID consistency;
- semantic and chunk boundary frames, first/last 10 seconds, and user-named ranges;
- cache and receipt freshness.

An experiment that improves one rubric category but fails a hard gate is not a win.

## Client acceptance as evidence

Store client/platform feedback as timestamped, literal requirements with before/after evidence. A rejection is strong evidence of a project failure, but classify its cause before generalizing:

- `editorial`: meaning, pacing, emphasis or emotional architecture;
- `asset_fidelity`: wrong/malformed face, silhouette, model, crop or evidence card;
- `workflow`: unreviewed B/C asset, stale version, missing source ledger;
- `renderer`: one-frame gap, bad alpha/chroma, cache or concat fault;
- `delivery`: cover application, aspect ratio, loudness, export state.

Only repeated editorial causes should change a creative default. Workflow and renderer failures should harden the production gate immediately without being mistaken for taste.

## Versioning

Record:

- corpus version;
- rubric version;
- rule-set version;
- project and draft identifiers;
- analysis tool version;
- date and operator.

Keep hypotheses and retired rules; do not rewrite history to make later decisions look inevitable.

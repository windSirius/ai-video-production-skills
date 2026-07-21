# Sentence-to-shot matching heuristics

## Retrieval order

Search in this order:

1. exact named character, location, prop, document, or action;
2. a reaction shot that expresses the sentence's emotion;
3. an establishing shot that supplies missing context;
4. a symbolic detail whose meaning is obvious in context;
5. a designed text or black card for a uniquely important quotation.

Do not use a generic pretty shot when a literal match exists elsewhere in the source.

## Expansion ladder

Run these steps in order whenever all initial candidates are generic, repeated, or below medium confidence:

1. search every source clip again by the exact named character, place, prop, action, or written phrase;
2. inspect the promising clip at 1-2 second intervals rather than relying on the coarse index;
3. inspect the 10 seconds before and after each promising frame, including reaction shots and reverse angles;
4. search newly added footage and the first/last seconds of every clip;
5. relax from literal action to emotional reaction, then to motivated symbolic detail;
6. use a designed card only when the line is a hook, quotation, reveal, or thematic statement.

Record the completed level in `retry_round`. A low-confidence choice with `retry_round=0` is unfinished.

## Parse each spoken unit

Record:

- subject and named entity;
- action or state change;
- object or location;
- emotional polarity and intensity;
- narrative job: hook, evidence, explanation, twist, climax, or conclusion;
- required screen time.

Use these fields as the search query for the shot inventory.

## Candidate scoring

Score every candidate from 0-3 in each category:

- `semantic`: named entity, action, prop, place, or causal idea is visible;
- `emotion`: expression and intensity match the spoken line;
- `continuity`: angle, screen direction, and location work with adjacent rows;
- `quality`: readable subject, useful motion, framing, and technical quality;
- `reuse_cost`: `3` for unused, `2` for a motivated callback, `1` for noticeable reuse, `0` for harmful repetition.

Use the total to compare candidates, but allow a lower total only with a written narrative reason. Prefer a literal `semantic=3` shot over a generic beautiful shot with high visual quality.

## Source coverage

- Build a coarse index first, then a dense index around promising ranges.
- Sample title sequences and transitions separately; an evenly spaced index can miss a one-second name card.
- Include the final seconds of each clip.
- Re-index newly uploaded footage rather than assuming the old inventory is complete.

## Duration and pacing

- Let an ordinary explanatory shot breathe for roughly 3-6 seconds.
- Use faster cuts for hooks, lists, comparisons, or explicit references to another work.
- Break a long static dialogue section every 4-6 seconds with a motivated angle, crop, reaction, or card.
- A crop variant counts as visual change only when the subject or emotional emphasis changes visibly.

## Continuity

- Avoid consecutive shots that jump between unrelated locations without a narrative reason.
- Preserve screen direction when alternating two characters.
- Enter a close-up after context has been established unless surprise is intentional.
- Return from a black card to a stable image; avoid another hard visual shock immediately afterward.

## Reuse budget

- Mark standout shots before editing.
- Keep the strongest embrace, reunion, reveal, or collapse for the climax.
- Use a second occurrence only as a deliberate ending callback.
- Count exact source ranges, not only filenames; two different angles from one clip are not identical reuse.
- If a shot appears three or more times, require an explicit reason for every occurrence.

## Match-sheet fields

Use at least:

```text
line_id start end duration text subject action object_location emotion narrative_job candidate_a candidate_a_score candidate_b candidate_b_score candidate_c candidate_c_score source_file source_in source_out treatment match_reason confidence retry_round reuse_group qa_status
```

Keep `match_reason` short but concrete, such as `letter close-up matches remembered details`, not `looks good`.

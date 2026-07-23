# Manuscript-led Caption Editing

## Goals

Treat Jianying Manuscript Match as a timing draft. Rebuild its caption boundaries and visual line layout from the clean narration manuscript so the viewer receives complete, readable thoughts without omitted, repeated, or reordered words.

## Two different boundaries

Do not confuse these operations:

- **Caption boundary:** when one caption clip ends and the next spoken thought begins.
- **Visual line break:** where one caption clip wraps from line one to line two.

Choose the caption boundary from meaning and speech. Choose the visual line break from phrase structure and balanced screen width. Never use duplicate neighboring clips to imitate either operation.

For this user's current house style, keep each SRT entry as one logical text line by default and allow Jianying to wrap it visually. Both the earlier semantic SRT and the user-adjusted reference SRT used zero manual newline characters. Add explicit newlines only after live-preview evidence shows a consistent need.

## Planning from the manuscript

1. Export and preserve the untouched Manuscript Match SRT.
2. Align its full text to the exact clean manuscript used for matching.
3. Mark clauses, quotations, contrast, cause/effect, enumeration, rhetorical questions, deliberate pauses, and emphasis beats.
4. Map old caption rows to new semantic units before editing Jianying.
5. Confirm that the planned units concatenate to the full matched text exactly once in order.

Use a plan with:

```text
plan_id old_rows source_span planned_text visual_lines timing_strategy reason status
```

## Segment boundaries

- Keep a subject with its predicate when the combined line remains readable.
- Keep verbs with required objects and complements.
- Keep `因为/所以`, `虽然/但是`, and other paired logical structures intelligible across adjacent units.
- Do not leave `但/而/所以/因为/以及/甚至/也/的/了/着` as an accidental isolated row.
- Keep quoted content balanced; avoid opening a quote in one row and leaving an isolated tail in the next.
- When a narrator lead-in introduces a direct quotation, prefer one lead-in caption followed by the complete quotation. Do not attach the first half of the quote to the lead-in merely because Manuscript Match did so.
- Merge consecutive machine fragments when they form one quotation, contrast, causal statement, list item, definition, or uninterrupted conclusion.
- Keep character names, place names, book titles, fixed lore terms, dates, numbers with units, and short quoted phrases intact.
- Preserve deliberate short beats such as `发现了吗` or `更狠的是` when they support pacing.
- Avoid rows that contain only a conjunction, punctuation mark, or closing quote.
- Prefer one or two visual lines. Re-segment an overloaded thought before considering smaller global text.
- Use 7–18 visible Chinese characters only as a diagnostic range. A complete quotation of 25–39 characters may be preferable to several semantically broken fragments when it has sufficient screen time.

## Visual line layout

- Keep one logical SRT line by default and inspect Jianying's natural wrap at the established font size.
- Add a manual newline only when natural wrapping damages a phrase or produces visibly unbalanced lines.
- For two lines, break at a phrase, clause, or quotation boundary and keep the two lines visually balanced.
- Keep the subject with its predicate when possible.
- Do not split a personal name, fixed term, number-unit pair, title mark, or short quotation between visual lines.
- Do not create a second line containing only one particle, punctuation mark, or closing quotation mark.
- Preserve the established font, preset, scale, X/Y position, outline, and safe margins while changing text.

## Punctuation

- For this user's default house style, remove terminal `，。；：,.;:` from every caption.
- Treat trailing `」』”’）》〉）】` as closing marks rather than the effective ending: remove the forbidden punctuation immediately before them while preserving the closing mark. For example, change `「一句话；」` to `「一句话」`.
- Preserve terminal `？！?!` unless the user explicitly overrides the style.
- Add internal commas when they represent a real spoken pause, contrast, apposition, or clause boundary.
- Preserve internal punctuation that carries rhythm or meaning, including em dashes, ellipses, and question marks in dialogue.
- Do not remove Chinese book-title or quote marks.

## Duplicate prevention

- Never copy the same complete sentence into adjacent timing segments as a substitute for merging.
- When true time-range merging is unavailable, assign a meaningful lead-in to the first segment and the complete quote or conclusion to the second.
- After editing, audit every adjacent pair for exact equality.

## Examples

```text
Bad split
最后一行是「你离开后
连精灵都失去期待」；

Preferred with two existing time segments
最后一行是
「你离开后连精灵都失去期待」
```

```text
Machine split
开拓者转述的时候说得很硬——「你想用她的过去动摇我们
但这些对于我们来说一点也不重要！」

Preferred
开拓者转述的时候说得很硬
「你想用她的过去动摇我们，但这些对于我们来说一点也不重要！」
```

```text
Machine fragments
「呃，是我弄错了？
十五年前，活下来的不是『素子』
而是『姬子』？」

Preferred when timing permits
「呃，是我弄错了？十五年前，活下来的不是『素子』而是『姬子』？」
```

```text
Bad duplicate
皮埃尔的歌本里每段副歌都写着未婚妻的名字
皮埃尔的歌本里每段副歌都写着未婚妻的名字

Preferred
皮埃尔的歌本里
每段副歌都写着未婚妻的名字
```

## Final audit

- Compare normalized concatenated text from raw and final SRT; require complete ordered coverage.
- Compare lexical content separately from punctuation. Punctuation changes may express house style; missing or altered words require review.
- Count adjacent exact duplicates; require zero.
- Require zero empty or punctuation-only entries.
- Check unmatched `「」`, `“”`, and `《》` across the sequence.
- Require zero captions ending in `，。；：,.;:`, including immediately before trailing `」』”’）》〉）】`.
- Inspect the first, middle, and last captions plus every caption longer than 24 visible characters.
- Confirm content still covers the narration exactly once in order.

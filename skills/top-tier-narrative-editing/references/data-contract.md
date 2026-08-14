# Learning data contract

## Corpus registry

Store the corpus as one UTF-8 JSON object:

```json
{
  "schema_version": "1.0",
  "corpus_version": "0.1",
  "updated": "YYYY-MM-DD",
  "entries": []
}
```

Each entry requires:

- `id`: stable lowercase kebab-case identifier;
- `title`, `creator`, `language`, `platform`;
- `source`: public URL or absolute local path;
- `role`: `benchmark`, `core-corpus`, `discovery`, `negative`, or `user-baseline`;
- `status`: `discovered`, `selected`, `analyzing`, `sampled`, or `fully-annotated`;
- `strata`: one or more corpus strata from the benchmark framework;
- `selection_reasons`: observable reasons for inclusion;
- `recognition_sources`: independent sources supporting benchmark status;
- `rights_mode`: `public-metadata`, `temporary-analysis-copy`, `user-owned`, or `user-provided`;
- `analysis_artifacts`: durable metric or annotation paths; never the temporary copyrighted media copy;
- `limitations`: why the entry does not by itself prove a transferable rule.

Rules:

- Require at least one independent `recognition_source` for `benchmark`.
- Use `core-corpus` for a collection explicitly selected by the user. This gives the collection sampling priority, not an automatic top-tier label for every item.
- Never use views, likes, subscribers, or platform awards alone as sufficient benchmark evidence.
- Keep non-user-owned analysis media temporary. Persist measurements, contact sheets used for analysis, timestamps, notes, and source URLs only.
- Use `user-baseline` for Alan's existing exports. Never relabel them as benchmark without independent evidence.
- Use `discovery` for promising Chinese-language or platform-specific candidates until they pass manual craft review.

## Hypothesis registry

Store hypotheses as one UTF-8 JSON object:

```json
{
  "schema_version": "1.0",
  "rule_set_version": "0.1",
  "updated": "YYYY-MM-DD",
  "hypotheses": []
}
```

Each hypothesis requires:

- `id`: stable kebab-case identifier;
- `statement`: conditional mechanism, not a surface recipe;
- `applies_to`: exact narrative functions and constraints;
- `evidence_level`: `H0`, `H1`, `H2`, `H3`, or `H4`;
- `supporting_entries`: corpus entry IDs;
- `contradicting_entries`: corpus entry IDs;
- `tests`: experiment IDs;
- `status`: `active`, `narrowed`, or `retired`;
- `limitations` and `next_test`.

Validation cannot prove that evidence is semantically sufficient, but it must reject impossible promotions:

- H1 requires at least one supporting entry.
- H2 requires at least three supporting entries from at least two creators.
- H3 requires at least one experiment.
- H4 requires at least three experiments.

## Experiment records

Use the fields in `learning-protocol.md`. Keep experiment IDs stable and preserve losing variants. An absent external result is valid; describe the internal result without pretending it is audience evidence.

# External footage and image sourcing

> **历史 Harness 参考。** 本文适用于既有 `run_manifest.json` 工程；其中 workflow v2/v2.2 是旧流程编号，不等于当前 `production_contract_version=2`。新项目使用 [十三阶段总控](../SKILL.md) 和 [当前提交契约](submission-contracts-v2.md)。保留本文用于旧工程核验，迁移按 [旧项目迁移](legacy-migration.md) 执行。

Use external retrieval only when local footage remains weak after a complete coarse and dense search, or when the user explicitly requests online material.

## Retrieval order

1. Official publisher, developer, character, event, or product media pages.
2. User-owned cloud or public source links supplied for the project.
3. Reputable archives or libraries with an explicit reuse license.
4. Commentary-compatible stills or brief reference excerpts whose provenance and purpose are documented.

## Rules

- Browse the web for current source availability and cite the direct source page in the source ledger.
- Prefer official downloadable assets. Do not bypass DRM, paywalls, authentication, rate limits, or platform download restrictions.
- Do not treat discoverability as reuse permission. Record `rights_status` as `official`, `licensed`, `user-owned`, `permission-needed`, or `unknown`.
- Do not apply `permission-needed` or `unknown` material to the live timeline without the user's authorization.
- Preserve the original filename or URL, creator/publisher, retrieval date, intended sentence, local path, and exact used range.
- Inspect the downloaded file, not only its filename or thumbnail.
- Add every new source to the shot inventory and run the same three-candidate and reuse audit used for local footage.

Use a `sources.tsv` with at least:

```text
source_id publisher title source_url retrieved_at rights_status local_path intended_line source_in source_out applied notes
```

If no sufficiently matched, authorized source exists, use a designed card, in-project symbolic detail, or report the gap rather than hiding it with generic footage.

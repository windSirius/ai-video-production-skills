# Indexed bulk visual matching

Use this route for a long commentary video, a complete picture-track rebuild, or a stable SRT with roughly 30 or more visual units. It preserves sentence-level evidence while making one complete match plan the scalable batch unit.

## Canonical stages

1. **Frozen authority** — snapshot the final SRT and narration frame clock.
2. **Visual corpus** — normalize source identity, probe metadata, Vision/OCR rows, coarse and dense frames, rights state, and evidence paths.
3. **Machine proposal** — retrieve a diverse pool for every cue, record A/B/C, and make a globally reuse-aware provisional selection.
4. **Review bundle** — inspect every selected shot and all three candidates for risk rows.
5. **Repair loop** — apply hash-bound decisions, expand weak rows, and rerun global audits.
6. **Picture master** — render one exact-duration video-only master.
7. **Incremental feedback repair** — patch declared cue/range IDs, prove unchanged ranges, rerun audits, and refresh the master.
8. **Live application** — replace the stable picture clip and verify protected tracks and duration.

Do not skip from machine proposal to picture master.

## Canonical artifact bundle

```text
captions/canonical.srt
timing_contract.json
visuals/source_identity_manifest.json
visuals/shot_index.tsv
visuals/shot_index_audit.json
visuals/cue_profiles.json
visuals/match_sheet.tsv
visuals/candidate_pool.jsonl
visuals/generation_manifest.json
visuals/candidate_review/selected_evidence_manifest.tsv
visuals/candidate_review/evidence/
visuals/candidate_review/selected/
visuals/candidate_review/risk/
visuals/review_manifest.json
visuals/repair_manifest.json
visuals/repair_result.json
visuals/repair_history.jsonl
visuals/match_sheet_audit.json
visuals/source_overlap_audit.json
visuals/render_manifest.json
visuals/render_segment_manifest.tsv
visuals/picture_master.mp4
visuals/picture_master_qa.json
visuals/boundary_contact_sheets/
visuals/continuous_range_review.json
```

Bind review, repair, render, and QA files to their input SHA-256 values. A stale review manifest cannot approve a changed match sheet.

Keep one candidate-pool JSONL row per cue. Preserve the viable retrieval pool instead of discarding every result except A/B/C: target 8–12 diverse items for an ordinary cue and expand up to 32 when identity, chronology, UI or semantic ambiguity makes the row high risk. Give each candidate a stable ID derived from source SHA, exact frame range and treatment; record origin, head/middle/tail evidence, score components, identity claims, UID/full-frame geometry, UI/rights risk and retry round. When fewer than three viable items remain, record a nonempty `candidate_shortfall_reason` and `candidate_expansion_attempts`; three candidates are the hard floor. The final `selected_candidate_id` must exist in the current pool and its source ID, file and exact range must equal the selected match-sheet row. Add an analyst-discovered override to the pool as `origin=manual_expansion` before selecting it.

Use a generation manifest such as:

```json
{
  "generation_id": "visual-g0003",
  "parent_generation_id": "visual-g0002",
  "canonical_srt_sha256": "<sha256>",
  "timing_contract_sha256": "<sha256>",
  "source_manifest_sha256": "<sha256>",
  "candidate_pool_sha256": "<sha256>",
  "match_sheet_sha256": "<sha256>",
  "decision_manifest_sha256": "<sha256>",
  "changed_cue_ids": [42]
}
```

Every audit must name the same current generation and hashes. A match-sheet or pool change invalidates the old audit unless a declared delta chain proves the inherited unmodified rows and newly reviewed changed rows cover the complete cue set.

## Retrieval model

Use a configurable combination of:

- character n-gram or embedding similarity over caption text and indexed OCR/annotations;
- exact quotation and visible-dialogue matches;
- named-character aliases;
- chapter-to-source priors;
- subject, action, location, emotion, and narrative-job compatibility;
- source chronology and phase;
- penalties for menus, loading, UI clutter, unresolved OCR, black/white transitions, source heads/tails, and prior reuse.

Keep the full viable pool under the 8–12 ordinary / up-to-32 risk budget. Enforce time/source diversity before selecting A/B/C. Optimize against the full pool rather than only the three review choices. If the global optimizer is infeasible, emit `NEEDS_EXPANSION` with affected cue IDs; do not silently fall back to repeated or unreviewed ranges. Treat the highest machine score as a proposal, not proof.

## Global selection

Optimize the provisional plan across the full timeline:

- cap exact-range reuse;
- reserve hook, climax, and resolution shots before ordinary exposition;
- penalize adjacent subject/location repetition;
- prefer an alternate angle before reusing an emotional close-up;
- preserve intentional callbacks with an explicit reuse reason;
- require every source range to cover the visual interval without a visible loop.

Use the next caption start as the default visual end when filling intentional caption gaps. Never change caption timing to simplify rendering.

## Risk rows

Require an A/B/C head/middle/tail contact review for:

- named characters or identity comparisons;
- the opening hook and final resolution interval;
- direct quotations and evidence claims;
- external footage, auxiliary assets, stills, or editorial cards;
- low-confidence proposals or completed expansion retries;
- high OCR-collision or UI-contamination risk;
- black/white transitions and source heads/tails;
- repeated emotional shots;
- user-reported or reviewer-reported cues.
- any cue with missing UID, non-full-frame crop, menu/archive/reasoning UI, task HUD, unlock notice or capture overlay.

Require explicit `identity_review=verified:<canonical character>` for a named-character selection. OCR or dialogue that merely mentions the character is insufficient.

Every ordinary row still requires selected-shot review. The scalable route reduces three-way review for low-risk rows; it does not remove review.

`build_candidate_review_sheets.py` must emit both the trusted-file JSON manifest and `selected_evidence_manifest.tsv`. The JSON starts at `READY_FOR_REVIEW`; each selected-sheet range and each TSV `visual_review` cell stays pending until a reviewer has inspected the listed hash-bound evidence. Review completion updates the TSV hash, covers every cue exactly once through `range_reviews`, and cannot inherit approval from an older match-sheet hash.

## Review manifest illustration

The JSON below is abridged to show the required top-level bindings and one evidence-frame record. It is not a copy-ready passing manifest: a real file must list every selected cue and the complete A/B/C × head/mid/tail evidence matrix for every risk cue.

```json
{
  "schema_version": 2,
  "status": "PASS",
  "match_sheet_sha256": "<sha256>",
  "candidate_pool_sha256": "<sha256>",
  "source_manifest_sha256": "<sha256>",
  "selected_evidence_manifest_sha256": "<sha256>",
  "row_count": 120,
  "selected_reviewed_ids": [1, 2, 3],
  "risk_row_ids": [1, 2, 42, 120],
  "candidate_reviewed_ids": [1, 2, 42, 120],
  "identity_required_ids": [42],
  "identity_verified": {
    "42": "角色甲"
  },
  "opening_review": {
    "status": "PASS",
    "cue_ids": [1, 2, 3],
    "range_seconds": [0, 10.0],
    "continuous_playback": true,
    "cg_pv_hook_review": "PASS"
  },
  "ending_review": {
    "status": "PASS",
    "cue_ids": [118, 119, 120],
    "range_seconds": [420.0, 432.0]
  },
  "full_frame_review": {"status": "PASS"},
  "uid_review": {"status": "PASS"},
  "range_reviews": [
    {"range": "1-4", "status": "PASS"}
  ],
  "unresolved_ids": [],
  "files": [
    {
      "kind": "evidence_frame",
      "path": "visuals/candidate_review/evidence/cue_0042_b_mid.jpg",
      "sha256": "<sha256>",
      "cue_ids": [42],
      "view": "B",
      "sample": "mid",
      "candidate_id": "<stable-id>",
      "source_id": "<stable-source-id>",
      "source_file": "<absolute-path>",
      "source_in": 61.2,
      "source_out": 64.8,
      "timestamp": 63.0
    }
  ]
}
```

`selected_reviewed_ids` must cover every row. `candidate_reviewed_ids` must cover every risk row. Every risk row needs nine trusted evidence-frame records: A/B/C × head/mid/tail, each bound to the current pool's stable candidate ID, source, and range. `identity_verified` must cover every identity-required row.

## Repair manifest minimum

```json
{
  "schema_version": 2,
  "base_match_sheet_sha256": "<sha256>",
  "before_candidate_pool_sha256": "<sha256>",
  "review_manifest_sha256": "<sha256>",
  "source_manifest_sha256": "<sha256>",
  "reason": "review or user feedback",
  "repairs": [
    {
      "line_id": 42,
      "selected_choice": "B",
      "identity_label": "角色甲",
      "identity_check": {
        "status": "PASS",
        "visible": ["角色甲"]
      },
      "evidence": "visuals/candidate_review/evidence/cue_0042_b_mid.jpg",
      "match_reason": "selected shot visibly verifies 角色甲",
      "review_status": "approved"
    }
  ]
}
```

Reject a repair when the base hash no longer matches. Preserve the old sheet, append the decision to `repair_history.jsonl`, regenerate affected evidence, and issue a new review manifest for the new hash.

The repair manifest must also bind the base/result candidate-pool hashes and list any added candidate IDs. The actual match-sheet diff must equal `changed_cue_ids`; any hidden row change fails the repair gate.

## Harness mapping

Use these registered offline actions when the parent production Harness is active:

| Action | Recipe | Required unit |
|---|---|---|
| `build_visual_index` | `offline.indexed-vision-ocr-corpus.v1` | `visual_indexes_per_batch=1` |
| `build_match_plan` | `offline.indexed-three-candidate-plan.v1` | `match_plans_per_batch=1` |
| `review_match_plan` | `offline.selected-and-risk-contact-review.v1` | `match_review_bundles_per_batch=1` |
| `repair_match_plan` | `offline.match-plan-incremental-repair.v1` | `match_repair_sets_per_batch=1` |
| `render_picture_master` | `offline.equal-duration-picture-master.v1` | `picture_masters_per_batch=1` |
| `patch_picture_master` | `offline.picture-master-incremental-patch.v1` | `picture_patches_per_batch=1` |

Keep `match_rows_per_batch=1` only for the focused correction route. A full indexed plan must not be registered as a generic `offline_artifact`.

For an incremental repair, snapshot both the match sheet and candidate pool. The repaired row's `selected_candidate_id`, source ID, source file, and source range must bind to the after-pool; a repair manifest cannot approve an arbitrary source that was never added to and reviewed in that pool.

For a rendered patch, segment hashes are derived from decoded frames in the actual base and output videos over each cue's declared output-frame span. Self-reported TSV hashes alone are not proof. Unlisted decoded changes, unchanged declared changes, stale segment-manifest hashes, or shifted cue spans fail the patch.

## Render and patch gate

Before a full render require:

- proposal audit passes for every canonical SRT row;
- review manifest is bound to the current sheet and passes all coverage checks;
- unresolved IDs equal zero;
- source overlap and reuse audits pass;
- every selected range covers its visual interval;
- opening and ending reviews pass.

After a patch, verify the exact changed frame ranges and prove unchanged ranges still derive from the previous accepted manifest. Always rerun full-duration, frame-count, no-audio, decode, black-event, opening, and ending checks.

The picture renderer must derive timing from integer output frames. Adjacent clips share the same serialized boundary; never compute one clip's end as rounded `start + duration` and the next start independently. Generate `-1/0/+1` boundary sheets for every semantic and chunk boundary, and continuously play the true first 10 seconds, final 10 seconds and any user-reported ranges.

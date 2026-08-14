# Workflow v2 compatibility contract — 2026-08-14

## Scope

This release updates eight cooperating personal skills:

1. `game-lore-script`
2. `voxcpm-batch-dubbing`
3. `jianying-dubbing-postproduction`
4. `jianying-sentence-visual-matching`
5. `jianying-zhangyanfa-style`
6. `jianying-acceptance-polish`
7. `top-tier-narrative-editing`
8. `zhangyanfa-video-production`

Unrelated system, plugin, document and football skills are intentionally outside this workflow release.

## Required behavior

- Introduces one authority chain for user-approved final files, canonical manuscripts, manifests, ASR and pronunciation proxies.
- Adds evidence ledgers and hash-bound script/audio/subtitle handoffs.
- Makes per-segment VoxCPM similarity, targeted regeneration, repair and stable-loudness masters explicit.
- Adds canonical-text and audio-tail checks to subtitle auditing.
- Standardizes ordinary visual candidate pools at 8–12, with expansion up to 32 for risk rows.
- Makes full-frame/UID review, actual opening/ending playback and boundary contact sheets release gates.
- Defines A/B/C track responsibilities, pre-render B/C review packs, hard evidence-page cuts and alpha/chroma delivery.
- Forbids generative redrawing of official named faces/models when source fidelity matters.
- Supports both frozen local-library BGM and explicitly authorized generated-score provenance.
- Requires shared integer-frame HyperFrames boundaries, input-hash cache validation, chunk receipts, concat receipts and localized rerendering.
- Converts client feedback into exact-frame minimum patches, including one-frame flashes and source-coordinate highlight repairs.
- Separates creative learning from production hard-gate failures in top-tier benchmarking.
- Adds safe storage lifecycle guidance for iCloud projects, caches, proxies and old renders.

## New executable checks

- `game-lore-script/scripts/audit_lore_script.py`
- `voxcpm-batch-dubbing/scripts/audit_similarity.py`
- canonical-source/audio-tail options in `jianying-dubbing-postproduction/scripts/audit_semantic_srt.py`
- house-profile full-frame/UID gates in `jianying-sentence-visual-matching/scripts/audit_match_sheet.py`
- `jianying-acceptance-polish/scripts/extract_feedback_frames.py`
- `zhangyanfa-video-production/scripts/audit_hyperframes_boundaries.py`
- generated-score provenance in `zhangyanfa-video-production/scripts/run_objective_checks.py`

## Compatibility and recovery

- Existing accepted artifacts remain usable when their recorded hashes and current inputs still agree.
- New gates do not authorize silent rewrites of older user-approved files.
- Local-library BGM remains the default; generated-score mode must be frozen at run initialization.
- The pre-upgrade snapshot is stored outside the Skill packages at `${CODEX_HOME:-$HOME/.codex}/skill-backups/2026-08-14-workflow-v2-before/`, with a SHA-256 manifest next to it.

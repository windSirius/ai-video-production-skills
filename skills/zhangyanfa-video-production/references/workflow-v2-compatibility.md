# Workflow compatibility contract — v2 through v3, 2026-08-21

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

## v2.1 additions — 2026-08-15

- Make zero insertion, zero substitution and zero deletion the primary narration gate, including a fresh audit of the actual repaired master and every join.
- Separate pronunciation-hotspot audition from ASR spelling, and invalidate lexical receipts after any audio mutation.
- Replace generic cover fidelity with ordered identity, narrative-shot and same-space gates; permit generated full scenes only after explicit user authorization.

## v2.2 additions — 2026-08-17

- Add one `authority_bundle.json` for the frozen delivery spec, canonical script, independent actual-final narration, sole final SRT and every downstream dependency binding.
- Add executable `authority_chain_integrity`; target-resolution renders fail closed when hashes, human release states, fps/frame count or downstream bindings diverge.
- Treat any audio edit as an invalidation of lexical receipt, subtitle, timing contract, A/B/C and BGM. Equal duration, tail trimming and final-video embedded audio are not substitutes for the edited source file.
- Separate objective and user approval states. Machine QA, review-file existence and producer self-approval cannot release pronunciation, A-track proxies, B/C assets, BGM audition or covers.
- Freeze target delivery at intake; Alan's default is 2560×1440/60fps unless the user overrides it.
- Require chapter source coverage and whole-timeline reuse/overlap/adjacency/source-concentration/black audits before the 720p A-track proxy gate.
- Require B/C to share A-track fps and target frame count instead of relying on downstream clipping.
- Require one episode-specific cover promise and a passing 16:9 no-text identity/thesis/same-space test before typography or other aspect ratios.

Existing accepted v2/v2.1 artifacts remain usable only after a recovery audit identifies their exact script, audio and SRT authorities. If the actual edited narration file is unavailable, mark the run provisional rather than reconstructing authority from matching end times.

## v3 additions — 2026-08-21

Workflow v3 is based on four completed 至冬考据 episodes and changes production control from `single_authority_bundle_v2_2` to `artifact_bound_release_v3` for new runs. It adds:

- an append-only approval ledger that distinguishes permission to work, script/audio freeze, static-asset review and full-proxy render authorization; target render requires all three artifact approvals, not merely the last one;
- timestamp/hash checks that prohibit unseen artifacts from being retrospectively approved by a broad task instruction;
- a core-claim evidence matrix with game text, real prototype, narrative function, internal cross-validation, counterevidence and confidence;
- whole-document structure/Chinese/persona/pronoun/read-aloud QA instead of line-by-line replacement;
- separate lexical, P1-pronunciation, prosody and full-length-audition voice gates, with P2 minor pronunciation warnings allowed;
- A direct+strong≥80%, A+B≥90%, CG/PV-like 0–10 second hook, visual-family reuse and cross-episode cooldown checks;
- one full-length 720p continuous A/A+B proxy with frozen narration and artifact-bound user approval before 2K60 render;
- BGM four-checkpoint human audition and deterministic official-foreground routing for exact cover subjects such as weapons/UI;
- one root `CURRENT.json` that supersedes stale PASS reports and identifies the sole current delivery set;
- executable `audit_workflow_v3.py` and `workflow_v3_release_integrity` checks.

Migration is explicit. Do not rewrite an accepted v2/v2.2 manifest in place merely to satisfy v3. First preserve existing hashes and approvals, identify actual current script/audio/SRT, then create v3 research/script/audio/visual/proxy artifacts. A legacy approval lacking artifact SHA, display time and exact user quote remains historical context, not a v3 release gate.

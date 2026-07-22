---
name: jianying-zhangyanfa-style
description: Rebuild Jianying Pro or CapCut Desktop commentary, lore-analysis, and character-study videos in Alan's “障眼法考据” editing style. Use for 复刻个人剪辑习惯, 障眼法考据风格, learning from a finished video and open Jianying project, applying the user's subtitle/audio/picture-master conventions, making a one-frame platform cover, building a high-density 0–10 second PV/CG hook, or auditing whether a draft matches this personal style.
---

# 障眼法考据剪辑风格

## Goal

Reproduce the user's editing grammar, not the topic-specific footage of one reference video. Treat narration as the spine, gameplay as emotional evidence, research cards as factual evidence, and music as chapter punctuation.

Read [style-profile.md](references/style-profile.md) before making editorial decisions. Read [hook-and-cover.md](references/hook-and-cover.md) when the brief calls for a high-retention opening or a platform cover. Read [jianying-execution.md](references/jianying-execution.md) before changing a live Jianying draft.

## Permanent UI exclusion

Treat every control labeled 「试试剪映助手」 or 「剪映助手」 as permanently forbidden. Never click, open, dismiss, focus, test, or use it. If it obscures a required control, use a verified non-assistant route or stop the live action; when called by `zhangyanfa-video-production`, obey its route-preflight, per-step pre-click authorization, and harness-managed trace gates.

## Workflow

1. Inspect the target narration, subtitle timing, available footage, draft duration, and existing track structure.
2. Preserve the current narration, captions, caption styling, and audio. Keep the previous picture track recoverable before rebuilding.
3. If a new reference video is supplied, run `scripts/analyze_reference.py VIDEO --out OUTPUT_DIR`; compare its metrics with the profile instead of overwriting the profile from one sample.
   Promote a trait only when it repeats across references, is explicitly requested by the user, or is corroborated by both a finished export and its live project. Keep single-sample implementation choices conditional.
4. Divide the narration into narrative units: hook, setup, claim, evidence, counterpoint, emotional turn, thesis, and outro.
5. Build or revise the main picture track sentence by sentence. Prefer semantic and emotional continuity over literal keyword matching.
6. Add research screenshots or quote cards only where they prove a claim. Use an upper-track live overlay, or bake them into a stability-first picture master only when the editable card and match plan remain recoverable.
7. Apply the observed subtitle and audio defaults from the profile as starting settings, then verify the finished export. Deviate when the target project visibly requires it.
8. Change BGM at chapter boundaries, not at every visual cut.
9. Perform visible QA at the hook, first thesis card, one evidence card, emotional slowdown, climax, and final frame.
10. Deliver a brief acceptance report with exact parameters, intentional deviations, unresolved low-confidence judgments, and links to any generated match plan.

## Editorial Grammar

### Hook

- Open on an emotionally loaded character image or story consequence.
- Establish the central question within roughly 4–10 seconds.
- Use one high-contrast red thesis/question treatment; do not stack multiple title cards.
- When the brief explicitly calls for a high-density opening, use the conditional 0–10 second profile in [hook-and-cover.md](references/hook-and-cover.md). Do not apply one-second cutting to the whole video.

### Exposition and argument

- Alternate gameplay/story footage with close character reactions.
- Let a claim land before inserting evidence.
- Use full-screen article, archive, painting, or quotation cards for proof; highlight the exact sentence being cited.
- Return from evidence to character footage so the video never becomes a slide deck.

### Emotional turn

- Slow the visual cadence after the factual middle section.
- Favor faces, hands, departures, solitary figures, and environmental aftermath.
- Reuse an earlier emotional motif only when it creates a callback.

### Ending

- Resolve on a character action or image, not an abstract recap screen.
- Allow the final thesis line to use red emphasis.
- When the last claim needs proof, hold the source long enough to read, return to faces or group imagery, then place the red thesis over the emotional resolution.
- Avoid a generic channel bumper unless the target draft already contains one.

## Quantitative Guardrails

- Use mostly hard cuts. Treat 2–4 seconds as the normal expository shot range. The two measured references had detector medians of about 2.68 seconds and 1.50 seconds, so no single median is a style law.
- Let reflective sections breathe for about 5–7 seconds per shot.
- Permit 1.5–3 second cuts during argumentative montage acceleration. This does not apply to a readable evidence page.
- In a deliberately high-pressure 0–10 second hook, aim for a meaningful PV/CG visual refresh about once per second, then return to ordinary semantic pacing.
- Do not force every sentence to a new shot. Cut on meaning, gaze, action, or argumentative turn.
- Let evidence-page duration follow reading time, not montage speed. A dense source page may need roughly 5–10 seconds.
- Evidence may cluster inside a proof chapter, but should remain restrained outside it. One strong proof card is preferable to several weak screenshots.
- Keep repeated source ranges rare. Reuse only for deliberate callbacks.

## Jianying Starting Defaults

Apply the observed values in [style-profile.md](references/style-profile.md) as the starting mix/style state, then verify the finished export. The core defaults are:

- Main/source footage audio: `-∞ dB`.
- Narration clips: `0.0 dB`, loudness normalization enabled to about `-23 LUFS`.
- BGM: about `-20.0 dB`, loudness normalization enabled; change music by chapter. A full-length BGM master is valid only when its internal chapter transitions, provenance, and boundaries are recorded.
- Captions: centered, scale `100%`, `X=0`, `Y=-888`, zero character and line spacing, established cyan-outline preset.
- Project cadence: retain 60 fps when the draft is already 60 fps.

The current high-density hook exception uses the same font at size `9`, manual red styling, and no ordinary caption preset. Ordinary body captions remain size `5`. Keep this hierarchy explicit rather than bulk-styling every caption red.

Across the two measured finished exports, the final-master target is approximately `-23 LUFS` integrated with true peak near `-3.8 dBFS`. Per-track settings are starting points; measure the finished mix.

Do not imitate the reference export's `854×480` delivery resolution. That is an output artifact, not a style rule; preserve the target project's higher resolution.

## Evidence Cards

- Choose between a source-faithful full-page screenshot and a rebuilt dark evidence card. Preserve the original page when its provenance or document texture matters; rebuild only when the source is unreadable at video scale.
- For rebuilt cards, use a short gold/white header and white body text on a black or dark field.
- Draw a red rectangle or use red type to isolate the exact proof sentence in either mode.
- When the source aspect ratio leaves unused bands, use a blurred extension or background layer rather than stretching the evidence.
- The reference project used a Jianying blur effect around intensity `50` for this treatment. Verify legibility after applying it.
- Keep normal subtitles visible unless they duplicate the evidence card text.

## Coordination With Other Skills

- Use `jianying-dubbing-postproduction` for numbered narration WAVs, Manuscript Match, subtitle cleanup, and SRT backup.
- Use `jianying-sentence-visual-matching` for exhaustive sentence-to-shot matching and reuse auditing.
- Use `jianying-acceptance-polish` when the request is driven by client or platform review notes.
- Use Computer Use for live Jianying UI inspection and edits; verify the visible timeline before claiming the draft changed.

## Do Not Learn These as Permanent Style

- A specific character, color palette, article, music title, or franchise scene from one reference.
- The low-resolution reference export.
- Accidental black bars, compression artifacts, or source watermarks.
- Exact narration-segment counts or exact music durations.
- Red as the ordinary caption style. A short contiguous red passage is allowed at the hook, decisive proof/reversal, climax, or closing thesis, but red remains sparse by chapter.
- One-second cutting outside a deliberately scoped opening montage.
- A held cover/title card. The observed platform cover is exactly one timeline frame and is not a visible intro sequence.

## Acceptance Criteria

- Narration remains intelligible and dominant throughout.
- Source/game audio is muted unless the user explicitly requests a story-dialogue excerpt.
- BGM does not compete with consonants and changes at meaningful chapter boundaries.
- Standard captions match the saved preset and remain semantically segmented.
- Research claims have visible proof; emotional claims have character-centered footage.
- The visual rhythm accelerates in argument-heavy sections and relaxes in reflective sections.
- The first and final frame are intentional, and there is no unintended tail black.
- The previous picture track or draft remains recoverable.

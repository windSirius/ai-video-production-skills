---
name: jianying-zhangyanfa-style
description: Rebuild Jianying Pro or CapCut Desktop commentary, lore-analysis, and character-study videos in Alan's “障眼法考据” editing style. Use for 复刻个人剪辑习惯, 障眼法考据风格, rebuilding the 7月19日 draft, learning from an older Jianying project, applying the user's established subtitle/audio/picture-track conventions, or auditing whether a draft matches this personal style.
---

# 障眼法考据剪辑风格

## Goal

Reproduce the user's editing grammar, not the topic-specific footage of one reference video. Treat narration as the spine, gameplay as emotional evidence, research cards as factual evidence, and music as chapter punctuation.

Read [style-profile.md](references/style-profile.md) before making editorial decisions. Read [jianying-execution.md](references/jianying-execution.md) before changing a live Jianying draft.

## Workflow

1. Inspect the target narration, subtitle timing, available footage, draft duration, and existing track structure.
2. Preserve the current narration, captions, caption styling, and audio. Keep the previous picture track recoverable before rebuilding.
3. If a new reference video is supplied, run `scripts/analyze_reference.py VIDEO --out OUTPUT_DIR`; compare its metrics with the profile instead of overwriting the profile from one sample.
4. Divide the narration into narrative units: hook, setup, claim, evidence, counterpoint, emotional turn, thesis, and outro.
5. Build or revise the main picture track sentence by sentence. Prefer semantic and emotional continuity over literal keyword matching.
6. Add research screenshots or quote cards only where they prove a claim. Put them on upper video tracks and keep the underlying timeline intact.
7. Apply the fixed subtitle and audio defaults from the profile. Deviate only when the source project visibly proves a different setting.
8. Change BGM at chapter boundaries, not at every visual cut.
9. Perform visible QA at the hook, first thesis card, one evidence card, emotional slowdown, climax, and final frame.
10. Deliver a brief acceptance report with exact parameters, intentional deviations, unresolved low-confidence judgments, and links to any generated match plan.

## Editorial Grammar

### Hook

- Open on an emotionally loaded character image or story consequence.
- Establish the central question within roughly 4–10 seconds.
- Use one high-contrast red thesis/question treatment; do not stack multiple title cards.

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
- Avoid a generic channel bumper unless the target draft already contains one.

## Quantitative Guardrails

- Use mostly hard cuts. Treat 2–4 seconds as the normal expository shot range; the reference median was about 2.7 seconds after clustering rapid transition detections.
- Let reflective sections breathe for about 5–7 seconds per shot.
- Permit 1.5–3 second cuts during dense evidence or argumentative acceleration.
- Do not force every sentence to a new shot. Cut on meaning, gaze, action, or argumentative turn.
- Keep evidence inserts sparse and legible. One strong proof card is preferable to several weak screenshots.
- Keep repeated source ranges rare. Reuse only for deliberate callbacks.

## Fixed Jianying Defaults

Apply the exact values in [style-profile.md](references/style-profile.md). The core defaults are:

- Main/source footage audio: `-∞ dB`.
- Narration clips: `0.0 dB`, loudness normalization enabled to about `-23 LUFS`.
- BGM: about `-20.0 dB`, loudness normalization enabled; change music by chapter.
- Captions: centered, scale `100%`, `X=0`, `Y=-888`, zero character and line spacing, established cyan-outline preset.
- Project cadence: retain 60 fps when the draft is already 60 fps.

Do not imitate the reference export's `854×480` delivery resolution. That is an output artifact, not a style rule; preserve the target project's higher resolution.

## Evidence Cards

- Use a black or dark card with a short gold/white header and white body text when quoting research.
- Draw a red rectangle or use red type to isolate the exact proof sentence.
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
- Dense red captions. Red is reserved for a question, proof, reversal, or final thesis.

## Acceptance Criteria

- Narration remains intelligible and dominant throughout.
- Source/game audio is muted unless the user explicitly requests a story-dialogue excerpt.
- BGM does not compete with consonants and changes at meaningful chapter boundaries.
- Standard captions match the saved preset and remain semantically segmented.
- Research claims have visible proof; emotional claims have character-centered footage.
- The visual rhythm accelerates in argument-heavy sections and relaxes in reflective sections.
- The first and final frame are intentional, and there is no unintended tail black.
- The previous picture track or draft remains recoverable.

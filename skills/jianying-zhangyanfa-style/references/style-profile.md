# Style profile: 障眼法考据

## Basis and confidence

This profile was derived on 2026-07-19 from the finished video “桑多涅：我究竟是为了什么，才降生到这个世上？【障眼法考据】” and its open Jianying project “6月27日”. Treat settings observed in the project as hard evidence and aesthetic inferences as adjustable guardrails.

| Trait | Observed value | Confidence |
|---|---:|---|
| Project/export cadence | 60 fps | High |
| Finished duration | 507.733 s | High |
| Reference delivery size | 854×480 | High, but not a style target |
| Source/game audio | `-∞ dB` | High |
| Narration volume | `0.0 dB` | High |
| Narration normalization | enabled, about `-23 LUFS` | High |
| BGM volume | `-20.0 dB` | High; checked on multiple music clips |
| BGM normalization | enabled, about `-23 LUFS` | High |
| Finished integrated loudness | `-22.9 LUFS`, true peak `-3.8 dBFS` | High |
| Caption scale/position | `100%`, `X=0`, `Y=-888` | High |
| Caption spacing | character `0`, line `0`, centered | High |
| Caption font | 新青年体 | Medium-high; visible in project UI |
| Caption preset | third cyan/white outline preset in the observed preset row | High visually |
| Evidence-card blur | blur effect, intensity `50` | High |
| Clustered visual transitions | 145 across 507.7 s | Medium; automated detector |
| Median detected shot interval | about `2.68 s` | Medium; transitions and motion can overcount |

## Timeline architecture

Use this lane order conceptually; exact track numbers may vary:

1. Caption track: dense, sentence-level orange caption blocks.
2. Evidence image/overlay track: sparse screenshots, artwork, or full-screen proof cards.
3. Effect track: short blur treatments aligned with selected evidence inserts.
4. Main picture track: continuous gameplay/story footage cut into semantic sections.
5. Narration track: sequential WAV clips with no decorative gaps.
6. BGM track: a few long chapter-length cues.

The reference used several narration WAVs and several long BGM cues. Preserve the pattern, not the exact counts.

## Subtitle grammar

- Normal narration: white/cyan-outline preset, bottom-centered, compact one-line captions where possible.
- Break captions by semantic clause, not by fixed character count.
- Keep punctuation readable but avoid orphaned one- or two-character fragments.
- Use red emphasis for the opening question, decisive evidence, reversal, or closing thesis.
- Do not color every keyword; emphasis is sentence-level and sparse.
- Keep evidence-card body text separate from ordinary captions.

## Picture grammar

- Start with a consequence or wounded/solitary character image before explaining context.
- Introduce the title question early with bold red text.
- Use story footage as the default visual layer.
- Prefer reaction close-ups during interpretation and wider environment/action shots during setup.
- Insert research material at the point of proof, not as ornamental B-roll.
- After a proof card, cut back to the character so the emotional thread resumes.
- Keep long reflective shots late in the video; automated cadence averaged roughly 6.5 s per detected interval from 6:00–8:00, versus roughly 2.5–3.7 s in earlier argument-heavy minutes.
- Use natural scene motion and hard cuts more often than decorative transitions.

## Evidence-card grammar

- Full-screen or nearly full-screen dark card.
- Short gold/white header naming the source or proposition.
- White body quotation.
- Red rectangle around the decisive lines.
- Blurred extension or background bands when aspect ratios differ.
- Hold long enough to read; split a long quotation into more than one card if necessary.

## Audio grammar

- Narration is the absolute foreground.
- Mute all source/game audio by default.
- Normalize narration clips uniformly instead of hand-boosting individual lines.
- Keep BGM near `-20 dB` and use mood changes to mark chapters.
- Prefer a dark/curious cue for setup, a restrained cue for evidence, and a warmer or more lyrical cue for the emotional resolution.
- Do not change music merely because the picture changes.

## Reference cadence measurements

- Automated scene threshold: `0.18`.
- Raw detections: `211`; clustered at least `0.6 s` apart: `145`.
- Clustered mean interval: `3.48 s`; median `2.68 s`; 25th percentile `1.48 s`; 75th percentile `4.27 s`.
- Approximate average intervals by minute: `2.86`, `3.70`, `3.51`, `2.83`, `3.24`, `2.51`, `6.53`, `6.65`, `2.89` seconds.

Use these as rhythm bounds, never as an automatic cut schedule.

## Signature narrative shape

1. Emotional cold open.
2. Central question in red.
3. Character/story setup.
4. Interpretive claim.
5. External or in-world evidence card.
6. Return to character reaction.
7. Slower emotional reinterpretation.
8. Closing thesis in red over a decisive character image.

## Known unknowns

- One reference cannot prove a universal BGM genre or color palette.
- The exact caption font reading should be rechecked if Jianying reports a missing font.
- The reference contained no long retained dialogue passage, so source-audio rules for intentional dialogue remain project-dependent.
- Transition detection includes some internal flashes and motion changes; visual judgment overrides the metric.

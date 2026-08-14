# Style profile: 障眼法考据

## Basis and confidence

This profile now uses two finished videos and their open Jianying projects:

- 2026-07-19: “桑多涅：我究竟是为了什么，才降生到这个世上？【障眼法考据】”, project “6月27日”.
- 2026-07-22: the user's self-revised “姬子：我的命运，就是将薪火传承！【障眼法考据】”, project “7月20日”, active timeline “时间线02”.

Treat settings visible in a live project as hard implementation evidence, finished-video measurements as delivery evidence, and aesthetic interpretation as an adjustable guardrail. A trait repeated in both projects has more weight than a topic-specific choice from either video.

This profile is an application and historical-baseline record, not a top-tier quality standard. When a stronger benchmarked method conflicts with a habit recorded here, test the stronger method through `top-tier-narrative-editing`; retain the personal habit only when it wins the comparison, is required by the production environment, or the user explicitly prefers it.

The first-reference parameter table is retained for traceability; second-reference confirmations follow it.

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
| Ordinary caption size | `5` | High; repeated in both projects |
| High-density opening caption | 新青年体, size `9`, manual red, ordinary preset cleared | High for the conditional hook profile |
| Body red-emphasis caption | same font, usually size `5`, manual red, ordinary preset cleared | High in the Himeko project |
| Embedded platform cover | exactly one frame before all narrative lanes | High in the Himeko project and export |
| Evidence-card blur | blur effect, intensity `50` | High |
| Clustered visual transitions | 145 across 507.7 s | Medium; automated detector |
| Median detected shot interval | about `2.68 s` | Medium; transitions and motion can overcount |

### Second-reference measurements

The self-revised Himeko export is H.264 `2560×1440`, 60 fps, 616.341 seconds with 48 kHz stereo AAC. Its mixed audio measures `-23.0 LUFS` integrated, LRA `4.1 LU`, and true peak `-3.8 dBFS`. The open project independently confirms narration at `0.0 dB`, BGM at `-20.0 dB`, and loudness normalization enabled for both.

At scene threshold `0.18` with a `0.6 s` cluster gap, the Himeko export has 206 clustered visual-change candidates, median interval `1.50 s`. This is materially faster than the earlier reference's `2.68 s`, largely because the new video contains a deliberately dense opening and several accelerated proof/montage passages. Use the contrast as evidence for variable pacing, not as a new universal cut rate.

The Himeko opening has a one-frame cover at export frame 0. Export frame 1 begins the narrative. The open timeline confirms a separate one-frame still placed immediately before the continuous `picture_only_v2.mp4` master, with captions, narration, and BGM starting after the same offset. See [hook-and-cover.md](hook-and-cover.md) for the conditional implementation.

## Timeline architecture

Use this lane order conceptually; exact track numbers may vary:

1. Caption track: dense, sentence-level blocks that appear orange in Jianying's timeline UI; the on-screen style remains white/cyan.
2. Evidence image/overlay track: sparse screenshots, artwork, or full-screen proof cards.
3. Effect track: short blur treatments aligned with selected evidence inserts.
4. Main picture track: continuous gameplay/story footage cut into semantic sections.
5. Narration track: sequential WAV clips with no decorative gaps.
6. BGM track: a few long chapter-length cues.

Two valid implementations have now been observed:

- Live-edit architecture: segmented story footage plus several long BGM cues.
- Stability-first architecture: one continuous video-only picture master, sequential narration WAVs, dense captions, one pre-mixed chapter/full-length BGM master, and sparse overlays. The Himeko project uses this form and places a one-frame cover before the synchronized start of every narrative lane.

Use the stability-first form for automated assembly and equal-duration replacement, but retain the source match plan and previous picture master. Preserve the pattern, not exact file counts or filenames.

## Subtitle grammar

- Normal narration: white/cyan-outline preset, bottom-centered, compact one-line captions where possible.
- Break captions by semantic clause, not by fixed character count.
- Keep punctuation readable but avoid orphaned one- or two-character fragments.
- Use red emphasis for the opening question, decisive evidence, reversal, or closing thesis.
- Do not color every keyword; emphasis is sentence-level and sparse.
- Keep evidence-card body text separate from ordinary captions.
- The high-density opening is a deliberate exception: size `9`, manual red, no ordinary preset, upper-middle placement. Body red-emphasis blocks normally keep size `5` and clear the ordinary preset before applying red.

## Picture grammar

- Start with a consequence or wounded/solitary character image before explaining context.
- Introduce the title question early with bold red text.
- When the brief asks for a high-pressure hook, use PV/CG material and refresh the visual about once per second for the first ten seconds. The first consequence shot may breathe for up to two seconds if the question needs it.
- Use story footage as the default visual layer.
- Prefer reaction close-ups during interpretation and wider environment/action shots during setup.
- Insert research material at the point of proof, not as ornamental B-roll.
- After a proof card, cut back to the character so the emotional thread resumes.
- Keep long reflective shots late in the video; automated cadence averaged roughly 6.5 s per detected interval from 6:00–8:00, versus roughly 2.5–3.7 s in earlier argument-heavy minutes.
- Use natural scene motion and hard cuts more often than decorative transitions.
- Never propagate the opening's one-second cadence across the body. The Himeko reference alternates very fast 30-second windows around `1.4–1.6 s` per detected interval with proof/reflective windows containing `5–11 s` holds.

## Evidence-card grammar

- Two accepted modes: a full-page source screenshot that preserves provenance and document texture, or a rebuilt full-screen/nearly full-screen dark card.
- A rebuilt card uses a short gold/white header naming the source or proposition and a white body quotation.
- A red rectangle or red type isolates the decisive lines in either mode.
- Blurred extension or background bands when aspect ratios differ.
- Hold long enough to read; split a long quotation into more than one card if necessary. The Himeko reference holds a dense late source page for about 8.5 seconds before returning to character footage.
- Keep provenance and review warnings in sidecar ledgers. Do not burn internal source IDs, `依据`, or `审核通过前禁止上片` into audience-facing cards unless the user explicitly asks for them.
- Adjacent page replacements use hard cuts or a continuous hold; never fade both clips to the empty background at the same instant.

## Audio grammar

- Narration is the absolute foreground.
- Mute all source/game audio by default.
- Normalize narration clips uniformly instead of hand-boosting individual lines.
- Keep BGM near `-20 dB` and use mood changes to mark chapters.
- Prefer a dark/curious cue for setup, a restrained cue for evidence, and a warmer or more lyrical cue for the emotional resolution.
- Do not change music merely because the picture changes.

## Reference cadence measurements

- Both measurements use scene threshold `0.18` and cluster detections at least `0.6 s` apart.
- Sandrone: 145 clustered candidates across 507.7 seconds; mean `3.48 s`, median `2.68 s`, P25 `1.48 s`, P75 `4.27 s`.
- Himeko: 206 clustered candidates across 616.3 seconds; mean `2.99 s`, median `1.50 s`, P25 `0.817 s`, P75 `3.717 s`.
- In Himeko, the opening 0:00–0:30 is among the fastest windows (18 candidates; median `1.00 s`). A late evidence page remains readable for roughly nine seconds before the edit returns to character footage.

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

For high-retention uploads, an invisible one-frame platform cover may precede step 1. It does not replace the emotional cold open.

## Known unknowns

- Two references still cannot prove a universal BGM genre, palette, resolution, or transition package.
- The exact caption font reading should be rechecked if Jianying reports a missing font.
- The preset's ordinal position and `Y=-888` are observations from the existing desktop canvas. If Jianying version, canvas, or resolution differs, copy the visible style from a known-good caption and verify safe-area placement rather than trusting the row number or coordinate alone.
- The reference contained no long retained dialogue passage, so source-audio rules for intentional dialogue remain project-dependent.
- Transition detection includes some internal flashes and motion changes; visual judgment overrides the metric.
- The Himeko picture master is a video-only `1920×1080/60` render inside a `2560×1440/60` delivery. Preserve the target project's chosen delivery resolution; do not hard-code either size as the universal style.

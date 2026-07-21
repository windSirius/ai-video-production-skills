# Review-to-edit map

| Reviewer language | Likely risk | Concrete edit | Acceptance test |
|---|---|---|---|
| 开头没有指定作品素材 | compliance failure | Insert an unmistakable 3-4 second montage during the named line | Required work is visible while its name is spoken |
| 封面要带一下某元素 | cover failure | Build a readable split or layered cover using supplied assets | Every required element remains identifiable at thumbnail size |
| 整体响度偏低 | technical audio | Normalize narration, add consistent gain, lower BGM relatively | Speech is clear; measured export has no clipping |
| BGM 太抢 | masking | Reduce BGM or use ducking under speech | Quiet words remain intelligible on phone speakers |
| 某段几十秒零切换 | retention risk | Alternate angles/crops, slow push, or insert a motivated card | Visible change occurs roughly every 4-6 seconds |
| 关键台词没有强调 | emotional under-delivery | Isolate the line with close-up, silence, or black/text card | The line has a unique visual and clean entry/exit |
| 同一镜头用了很多次 | desensitization | Keep the best use at climax and one optional callback | Recount meets the agreed reuse budget |
| 字幕没有问题，别动 | regression risk | Lock caption lane during picture/audio work | Caption count, text, style, and timing are unchanged |

## Cover checklist

- Use a frame that contains a recognizable character, title, symbol, or environment from each required work.
- Avoid a dark transition frame that becomes unreadable at thumbnail size.
- Keep headline text inside safe margins and test at small scale.
- Distinguish `generated`, `imported`, and `applied as export cover` in the final report.

## Audio checklist

- Confirm whether normalization is enabled.
- Confirm gain on every narration clip when the track is segmented.
- Keep BGM roughly 10-14 dB below narration as a starting point, then audition.
- Treat amplitude percentages and dB as approximate perceptual guidance, not the same as LUFS.
- Measure integrated loudness from an exported mix before reporting a final LUFS value.

## Pacing checklist

- Check the reviewer-specified interval frame by frame or at 1-2 second samples.
- Prefer motivated changes over random cuts.
- A black quote card must be intentional, readable, and bounded by clean transitions.
- Use scene detection only to find candidate long gaps; inspect the visual result manually.

## Reporting vocabulary

- `project updated`: the live Jianying timeline changed and was verified.
- `asset generated`: a local file exists outside the editor.
- `asset imported`: it appears in the Jianying media bin.
- `applied`: it is used on the timeline or in the export-cover setting.
- `exported`: a final rendered file exists and was probed.

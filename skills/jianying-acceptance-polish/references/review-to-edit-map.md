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
| 看起来像闪过一帧 | renderer boundary or simultaneous fade | Inspect exact frame and neighbors; replace simultaneous fade with hard cut or shared-frame boundary | Center frame contains intended outgoing/incoming image, not empty green/alpha/black |
| 红框太大/错位 | source-to-canvas transform error | Recompute from source pixel bounds plus actual contain/pad offset; scope to one card | Box encloses only the target phrase at head/mid/tail |
| 封面人物崩了 | identity/source-fidelity failure | Rebuild from frozen official art; remove AI-redrawn likeness | Named face/model matches source at full and thumbnail scale |
| 左下出处/右下注释删掉 | production metadata leaked on-screen | Remove burned-in footer; keep provenance in sidecar ledger | Audience frame has no internal labels; ledger still binds source |

## Cover checklist

- Use a frame that contains a recognizable character, title, symbol, or environment from each required work.
- Avoid a dark transition frame that becomes unreadable at thumbnail size.
- Keep headline text inside safe margins and test at small scale.
- Distinguish `generated`, `imported`, and `applied as export cover` in the final report.
- Freeze official source assets and compare every named face/model directly; do not repair identity with generative redraw.

## Frame-accurate patch checklist

- Convert each reviewer time to the exact output frame using the master FPS; retain the nearest frame plus at least one neighbor on each side.
- Determine whether the fault exists in source, proxy, composition, chunk, assembled master or final chroma/alpha conversion.
- Patch the canonical generator. A direct edit to a derived chunk will disappear on rebuild.
- In HyperFrames, derive both sides of a cut from one integer-frame boundary; independent decimal rounding can create a 1 ns gap that samples as a full black frame.
- Bind cache reuse to all material inputs. If the cache only checks dimensions/frame count, force the affected chunk.
- Re-run exact-range and continuous playback QA after assembly.

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

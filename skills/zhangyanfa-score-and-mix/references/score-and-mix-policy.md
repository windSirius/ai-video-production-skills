# 配乐选择与混音政策

## 章节字段

```text
chapter start_frame end_frame rhetorical_job mood energy instrumentation
candidate_id source_mode vocal_content duck_ranges transition_reason
```

章节边界来自论证与情绪变化，不来自视觉切点数量。

## 可比较候选

默认四套 A–D 候选。使用同一旁白 SHA、同一试听范围、同一基准响度与相同淡入淡出，避免把音量差误判成情绪优劣。候选应体现真正不同的情绪或配器方向，而不是只换同一首曲子的起点。

四个 audition mix 的文件 SHA 必须互不相同；还要按[曲库与去重规则](library-and-diversity.md)核验原曲作品身份和近几期复用，改变混音 SHA 不等于新曲。章节区间必须首段从 0 开始、相邻首尾相接、末段等于目标帧数，并逐段写所选 `candidate_id`。

## 来源

- `local_library`：源文件必须存在于用户批准的曲库根目录并记录 SHA。
- `generated_score`：记录服务/模型、提示词或其 SHA、生成时间、原始文件和 SHA。

不得把生成来源伪装成本地曲库，也不得把临时 URL 当长期源文件。

## 歌词

有歌词不自动淘汰，但要记录语言、含义摘要、叙事职责、与旁白重叠范围和混音策略。歌词与结论冲突、暗示未经证实关系、像角色台词或遮蔽关键论证时淘汰。

## 混音与试听

先保证旁白清楚，再判断音乐丰满度。house style 的 `0 dB` 旁白和 `-20 dB` BGM只是剪映起点；按实际母带做 duck。至少试听钩子、最密集证据、情绪转折与结尾。最终导出前不声称最终 LUFS/TP。

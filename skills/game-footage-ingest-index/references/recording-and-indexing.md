# 完整录屏与镜头索引

## 1. 探测与来源登记

对每个原始文件记录 SHA-256、时长、分辨率、帧率、音视频流、开始时间、UID、水印、字幕、菜单与覆盖层。原始文件不转写、不改名覆盖；派生代理始终保留父源身份。

## 2. 两级覆盖

- 粗层：覆盖从第一帧到最后一帧，默认每 2–5 秒采样并补充场景变化帧。
- 密层：仅对人物出现、对白变化、短暂卡面、动作转折、选项、证物、片头片尾和粗层低置信区间做 0.25–1 秒采样。

每个未覆盖间隔都要可解释。加载、菜单、战斗失败、重试与 UI 先分类，再决定能否用于成片。

每个 source 另写一条 `coverage_receipts.jsonl`：绑定 `source_id`、`source_sha256`、`reviewer`、`review_status`，并以 `intervals[{start_s,end_s,classification}]` 从 0 无缝覆盖到 probe 的 `duration_s`。不能用一行 `complete=true` 代替区间收据。

## 3. OCR、ASR 与镜头字段

OCR 与 ASR 是检索线索，不是正典。索引至少保存：

```text
shot_id source_id start_s end_s characters location action emotion
visible_text dialogue_hint ui_risk black_flash_risk uid_visible
visual_family_id evidence_frames confidence
```

有画面字幕而无声音转写时保留可见文本；有声音而无可靠 ASR 时写 `audio_transcript_needed`，不能补写台词。

## 4. 人物库

每个重要人物登记：规范名、别名、官方/用户来源证明帧、发型服装与标志物、常见同框对象、易混淆人物、可用镜头范围。人物库只提供识别依据；具体 cue 的身份通过由 track-design 对所选范围重新判断。

## 5. P0 覆盖

P0 包括开头钩子、点名人物、直接引文、核心事件、关键证物和结尾回扣。逐项记录：

```text
p0_id chapter claim_or_cue required_visual available_source
status available|acquire|card|remove evidence notes
```

只有 `available` 可以直接进入配画；其余状态必须在素材冻结前由用户或稿件决策解决。

## 6. 缓存

代理、OCR原始结果和全量帧使用 `source_sha + profile_sha + tool_version` 作为缓存键，放在本地非 iCloud scratch。项目中只保留索引、联系表、proof与缓存收据。

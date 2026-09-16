# 720 审片、正式母版与最终成片 QA

## 全长 720 整合代理

必须覆盖完整 `[0,target_frame_count)`，并包含最终 A/B/C、配音、字幕和已选 BGM。只允许降低空间分辨率或码率；切点、字幕、转场、卡片时长、绿幕/alpha处理和音频自动化保持正式方案。

机器检查分辨率、fps、帧数、解码、黑场和音频流；用户以 1× 完整观看判断语义、节奏、遮挡、B/C可读性和音乐情绪。两者分别记录。

`audit_final_master.py` 的 `--manual-review` 为必传项；没有绑定当前 video SHA 且各人工检查项为 PASS 的收据，脚本不得返回 PASS。

## 分轨母版

- A：视频流，无源游戏音；帧数和时钟准确。
- B/C：与 A 相同 fps 与目标帧数，使用已批准的 alpha 或绿幕模式。
- 每轨完整解码；检查首尾、所有素材激活帧、编辑边界和 chunk seam。

## 最终观众成片

先读冻结交付模式。独立模式检查各轨、独立配音/BGM和 SRT/时钟并生成 `independent_delivery_v2` 与 QA，不生成一个只为让检查器满意的合并文件。A 的 `subtitle_baked` 按冻结政策，默认 false；B/C 和音频不烧进 A。整片代理中的辅助字幕不改变这个交付政策。

最终 QA 绑定实际上传候选文件，至少输出：

```text
path sha256 width height fps frame_count duration codec pix_fmt color
audio_streams audio_codec sample_rate integrated_lufs true_peak
full_decode first_frame last_frame seam_review black_review
green_residue_review subtitle_review narration_tail_review status
```

检查所有 B/C active range 在观众成片中正确出现，并确认 key 后无残余整屏绿色。抽查开头十秒、每章转折、每张证据卡、用户点名范围与结尾十秒；一帧闪烁必须查看中心帧及相邻帧。

最终文件生成后更新 `CURRENT.json`，但只有人机检查均通过时才把它标成当前交付成片。

## 视觉对比的固定抽取路径

1. 冻结解码器/版本、帧定位、像素格式、输入色域/范围到 RGB 的变换及缩放算法。
2. 从同一已知视频的同一帧分别走基准和待测路径，输出无损 PNG 或原始 RGB；确认相同内容不会因 JPEG 量化或范围转换误报，再检查实际母版。
3. 保留全部首尾、编辑边界与分块 seam 的 `-1/0/+1` 点和必要 active-range 点；按源合并抽帧可减少进程启动，但必须证明点集未减少。
4. 黑场报警查看源片头/中/尾和上下文。原片合理淡出与生产黑闪分别裁决，记录具体帧与理由；不能全局关闭黑场检查。
5. QA 收据绑定被测文件 SHA、所有输入 SHA、工具版本、抽取/颜色配置和点集 SHA。任一变化使对应检查失效；未变的已通过完整解码可复用。报告实际采样数量、进程数量与耗时，不把采样称为逐帧视觉审看。

先修比较管线再重测，禁止通过放宽阈值消除大量误报。该流程规定正确性与复用条件，不预先承诺某个提速倍数。

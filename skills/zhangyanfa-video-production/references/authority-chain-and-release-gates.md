# 唯一权威链与阶段释放门禁

## 目录

1. 核心原则
2. 交付规格预检
3. `authority_bundle.json`
4. 冻结顺序
5. 失效传播
6. 客观通过与人工通过
7. 正式长渲染前检查
8. 恢复旧项目

## 1. 核心原则

每期只能有一份当前脚本文本、一份实际最终口播文件和一份最终 SRT。工程字幕、ASR 对齐字幕、交付字幕或用户改时字幕可以保留为历史，但只有 `authority_bundle.json` 指向的文件能够驱动 A/B/C、BGM 和最终导出。

“结束时间相同”不能证明“时间轴相同”。把旧860秒口播裁到855秒，不等于使用了用户修改后的855秒口播；把按旧字幕选出的画面截到新帧数，也不等于重新绑定新字幕。

## 2. 交付规格预检

创建长画面资产前先冻结：

- 主画面宽高和帧率；本系列默认 `2560×1440/60fps`，除非用户另有要求；
- 主时间轴 `target_frame_count`；
- picture-only、UID、contain/pad 和色彩策略；
- B/C 轨输出模式及其目标帧数；
- 封面所需 `16:9`、`4:3`、`3:4` 比例；
- 哪些结果是代理、哪些是正式母带。

未冻结规格时只允许素材盘点、接触表和低清概念代理；不得渲染正式长母带。

## 3. `authority_bundle.json`

在项目根目录维护一个包，至少包含：

```json
{
  "schema_version": 1,
  "revision": 1,
  "status": "frozen",
  "delivery_spec": {
    "width": 2560,
    "height": 1440,
    "fps": 60,
    "target_frame_count": 1
  },
  "authorities": {
    "script": {"path": "script.md", "sha256": "...", "status": "frozen"},
    "narration": {
      "path": "narration/final.wav",
      "sha256": "...",
      "status": "frozen",
      "duration_frame_count": 1,
      "lexical_status": "pass",
      "human_audition_status": "pass"
    },
    "subtitle": {
      "path": "captions/final.srt",
      "sha256": "...",
      "status": "frozen",
      "cue_count": 1,
      "final_end_frame": 1,
      "caption_tail_hold_frames": 0,
      "human_approval_status": "pass"
    }
  },
  "downstream": []
}
```

最终口播必须是独立、稳定、可哈希的实际文件，不能只存在于最终视频音轨或剪映缓存里。`duration_frame_count` 由该实际文件通过 ffprobe 按冻结 fps 量化所得，必须与 `target_frame_count` 相等。每个正式下游资产追加一条 `downstream`，记录 `id`、`kind`、文件 SHA、`objective_status`、`human_status`，以及它绑定的脚本、口播、字幕、帧率和目标帧数。

## 4. 冻结顺序

1. 冻结交付规格和脚本。
2. 生成并修复配音，对实际最终母带重做词级审计。
3. 用户试听专名热点和完整母带；未试听只能标记 `provisional`。
4. 从这份实际最终口播产生并确认唯一最终 SRT。
5. 运行权威链检查，冻结 revision。
6. 冻结素材覆盖矩阵、A轨候选和 B/C 审核包。
7. 只做压力样片和开头/正文/结尾代理。
8. 用户通过创意代理后，才做正式长渲染。

如果用户明确要求在试听前继续，可继续做素材研究、证据卡和低清代理，但必须标记为 `provisional`，不得宣称正式母带或让临时结果进入最终整合。

## 5. 失效传播

| 变化 | 必须失效 |
|---|---|
| 脚本文字变化 | 配音词级收据、SRT、A/B/C、BGM、封面承诺 |
| 任何口播剪切、替换、拼接、修音或重新导出 | 最终母带收据、SRT、timing contract、A/B/C、BGM |
| SRT 文字或时间变化 | A/B/C 匹配、HyperFrames composition、BGM 章节与自动化 |
| 宽高、帧率或目标帧数变化 | 对应代理、正式母带、B/C 输出和集成收据 |
| A轨 match sheet 或来源范围变化 | composition、分块、复用审计、正式母带 |
| 封面承诺或人物身份参考变化 | 所有未重新审核的封面底图与多画幅版本 |

不要用“只改了最后几秒”推测影响范围。只有绑定新 SHA 的 delta manifest 能证明未受影响部分可以复用。

## 6. 客观通过与人工通过

始终分开记录：

- `objective_status`：哈希、词级差异、帧数、黑场、复用、解码、尺寸等机器可证事实；
- `human_status`：发音、钩子、语义配画、节奏、证据卡可读性、封面人物身份与题眼等判断。

机器不得给自己签发创意通过。代理文件存在、接触表存在或自动脚本返回 PASS，都不能替代用户对指定代理的明确接受。

## 7. 正式长渲染前检查

运行：

```bash
python3 scripts/audit_authority_chain.py RUN_DIR \
  --output qa/authority_chain_pre_render.json
```

只有无 `--allow-provisional` 的结果为 `ok=true`，才能开始目标分辨率长渲染。代理规划可显式使用 `--allow-provisional`，但该结果必须带警告，不能用于正式母带授权。

正式 A/B/C 或 BGM 生成后，将其加入 `downstream`，再次运行并使用 `--require-descendant a_track` 等参数。`authority_chain_integrity` 也可作为 `verification_plan.json` 的客观检查类型。

## 8. 恢复旧项目

旧项目没有权威包时，不根据文件名猜最新版本。先盘点所有脚本、音频和 SRT，向用户确认实际使用版本，再建立 revision 1。若无法取得用户修改后的独立口播，只能标记 `provisional`；不能用旧母带裁尾冒充当前权威。

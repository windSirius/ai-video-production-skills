---
name: subtitle-timeline
description: "离线建立、修复并冻结旁白字幕与整数帧时钟：区分正典词面、用户断句时间和音频总时钟，管理 provisional → candidate_final → final_frozen 状态，审计SRT并输出帧契约。用于初版字幕、最终版字幕、语义断句、时间轴修复和字幕权威冲突；不操作剪映、不设置字体、不合成视频。"
---

# 字幕与整数帧时间轴

本技能只处理离线文件。它不打开剪映、不导入媒体、不设置字幕样式，也不把字幕放上视频轨道。

## 工作路径

先读取本期 `workspace_paths.json`，遵守[统一目录与素材规范](../zhangyanfa-video-production/references/workspace-layout.md)。用户原始SRT先保存在 `input`，候选/最终SRT、剪辑决定、有效时钟和发布依据放 `subtitle/vNNN`；不在项目根目录新增多个“最终版”。保留用户原件，注册的是精确匹配的实际版本。 所有新版本先分配目录，再写文件；不自行发明另一套阶段路径。旧期 `legacy_indexed` 工作台用于导航，不视作新生产目录或新的审批权威。

## 前置条件

读取当前 `script_manifest.json`、`audio_manifest.json`、`voice_release.json`、正典纯文本、旁白母带、项目 FPS、项目 style JSON，以及初版/文稿匹配/用户调整 SRT。`script_manifest` 必须处于 approved 并绑定正典路径/SHA；style 是正式审计与冻结的必需输入，不得省略。发生版本冲突时读取 [references/authority.md](references/authority.md)；进行语义断句时读取 [references/semantic-segmentation.md](references/semantic-segmentation.md)。

配音未进入 `released` 或 release SHA 与实际母带不一致时，只能生成 `provisional`。文件名即使叫“最终版字幕.srt”，也不能绕过这个门。

## 三维权威

1. **词面权威**：冻结的 `口播纯文本.md`。字幕若改变词语，应先建立稿件修订并重新判断配音是否有效。
2. **断句与时间权威**：用户明确指定的 SRT。没有硬错误时保留用户的切分、标点和时间。
3. **总时钟权威**：已释放母带、项目 FPS 和明确出点形成的整数帧契约。

ASR 和 Manuscript Match 只是候选，不属于上述任何最高权威。

## 状态

```text
blocked_audio_unreleased → provisional
released → candidate_final → final_frozen
```

- `provisional`：可供用户调整，`downstream_allowed=false`；
- `candidate_final`：稿件 manifest 已批准，音频/人审收据完整释放，style 与离线审计全部绑定通过，等待用户批准；
- `final_frozen`：用户批准当前 SRT，manifest、SRT、音频和帧契约的 SHA 全部一致。

正式 A/B/C 设计和 2K 渲染只能读取 `final_frozen`。

## 工作流

### 1. 建候选

保存用户或工具提供的原始 SRT，不原地覆盖。初版断句可以来自 Manuscript Match 或 ASR，但词面必须向正典纯文本校正。

### 2. 修硬错误

修复漏字、多字、错序、空条目、标点独占、相邻重复、零时长、逆序和未批准重叠。使用 `scripts/repair_srt.py` 时只输出新文件和收据；重复字幕只有在重叠/间隔落入明确容差内时才允许合并，不能用无下界的负间隔判断。

### 3. 语义断句

字幕条目表达一个完整意群或刻意短拍。不要拆开人名、固定术语、数字单位和短引文；不要让连词、助词、主语或引号尾巴单独成条。字符数和 CPS 只作提醒，不得为了指标破坏用户时间轴或中文语义。

字幕末尾标点按项目的 style JSON 执行，不在技能里写死。用户调整版优先于通用长度和换行建议。

### 4. 离线审计

运行 `scripts/audit_srt.py`，要求正典词面恰好覆盖一次并保持顺序，同时检查时间、重复、标点独占、引号、CPS 警告、approved `script_manifest`、完整 machine QA/实际音频 probe/全篇 1× 人审发布链、项目 style 和全部 SHA。只写 `released/approved` 布尔字段的浅层 JSON 不能通过。原始匹配 SRT 只用于可选对照，不是必需输入。

### 5. 冻结整数帧

音频已完整释放、候选审计通过且用户批准当前 SRT 后，运行 `scripts/freeze_timing.py`。冻结时再次核验并绑定 `script_manifest`、audio/voice 发布链和 style SHA。它把毫秒时间按明确的 `frame_rounding_policy` 转成整数帧区间，生成统一 `total_frames` 和半开区间 `[start_frame,end_frame)`；禁止各轨自行计算结尾。

任何 SRT、母带、FPS、舍入策略或出点变化都会使旧时钟和用户批准失效。

### 6. 用户删段后的统一时钟

用户明确要求整段剪掉并同步收紧时，先保存原字幕、原母带与批准范围，再生成唯一 `edit_decisions.json`：每项含稳定原 cue ID、原整数帧半开区间、保留/删除决定及原话。按原时钟一次计算保留区间和新时钟，输出 `effective_timeline.json`、原 cue 到新 cue/帧的映射及实际新母带/SRT/帧契约的 path/SHA。没有删段时该入口指向冻结原件，不复制第二套时钟。

A/B/C/BGM、审核页与 renderer 必须通过同一有效时钟入口取文件，禁止各模块硬编码原母带路径、重复执行收紧或单独四舍五入。交付前检查删除区间不存在、保留区间顺序与帧数准确、全部轨道同长、尾音完整；声称保留音频未变时必须比较实际 PCM 区间。

修改后按真实变化重新审计和登记审批。技术剪接、旧完整试听和用户同意删段分别记录，不能写成用户又以 1× 完整听过新母带；若现行发布链要求新母带完整试听，仍须获得真实试听记录。用户仅调整 SRT 时间时，不顺带改音频或删除口播。此流程不自动改变 `per_caption_refresh` 剪镜规则。

## 交付

- `provisional.srt` 与 `provisional_srt_manifest.json`
- `final_candidate.srt` 与 `subtitle_qa.json`
- `final.srt` 与 `final_srt_manifest.json`
- `timing_contract.json`
- `cues_frames.json`

剪映导入、字体预设、轨道替换和成片字幕检查属于最终整合模块，不得写进这里。

---
name: zhangyanfa-track-design
description: 在最终 SRT 和整数帧时钟冻结后，为每条字幕设计并审核 A/B/C 轨画面，执行逐字幕换镜、语义匹配、人物身份核验、复用控制和分轨审批。用于 A轨逐句配画、B轨证据卡、C轨象征层或画面返修；不负责下载素材、选BGM或正式渲染。
---

# 障眼法 A/B/C 轨设计

本模块只做编辑决定和可见审核，不把候选数量当成质量，也不在字幕、素材与配音尚未冻结时提前制作正式轨道。

## 工作路径

先读取本期 `workspace_paths.json`，遵守[统一目录与素材规范](../zhangyanfa-video-production/references/workspace-layout.md)。计划、A/B/C决定、BGM引用和固定WebUI的数据放 `tracks/vNNN`，其内按 A/B/C/BGM 分区；不要在顶层创建 `08_逐字幕配画_v3`。大代理走本期缓存，通过的审片文件放 `review/vNNN`。 所有新版本先分配目录，再写文件；不自行发明另一套阶段路径。旧期 `legacy_indexed` 工作台用于导航，不视作新生产目录或新的审批权威。

## 前提

- `authority_bundle.json` 指向唯一最终配音和最终 SRT；
- `timing_contract.json` 已冻结整数帧时钟；
- source manifest、镜头索引、人物库、权限表与 P0 覆盖有效；
- 总控已把 house style 快照写入本期 request contract。

缺少上述任一项时，只能继续素材侦察，不能标记轨道完成。

## 轨道职责

- **A轨**：全屏游戏画面、官方 PV/CG 或剧情过场，承担人物、行动、地点与情绪；禁止用制作方文字卡代替画面。默认不烧口播字幕，保留原生游戏/PV/UI 文字；水印、黑场和遮挡先实际检查，优先换成干净来源，不用裁切破坏叙事主体。
- **B轨**：原文证据、关系解释、概念具象与可阅读的比较卡。
- **C轨**：少量跨段落象征或空间提示；没有明确收益就不建。

读取 [matching-and-cut-policy.md](references/matching-and-cut-policy.md) 设计 A 轨；需要 B/C、证据卡、绿幕或 alpha 时读取 [auxiliary-track-grammar.md](references/auxiliary-track-grammar.md)。

## 逐字幕换镜

默认 `cut_policy=per_caption_refresh`：

- 每个 cue 起点必须开始新的 `shot_id`，切点等于该 cue 的 `start_frame`；
- 可以继续使用同一 source，但必须是不同且不重叠的真实镜头、反应、动作或景别；
- 仅缩放、裁切、调色或回放同一画面不算换镜；
- 连续表演确实不能切时，写 `continuity_override`，列出边界、理由、连续 source range 与用户审批 ID。未经审批的 override 为阻断项。

计划统一为 TSV；唯一键是 `(track, cue_id)`，因此同一 cue 可以同时有 A/B/C 行。每轨独立检查输出时序，跨轨重叠合法；A 轨必须覆盖最终 SRT 的每个 cue，并在每个字幕边界刷新。A 行的 `shot_id`、`source_id`、`source_in/out` 与 `visual_family_id` 必须和冻结 shot index 一致；同一 `visual_family_id` 换 ID、裁切或缩放仍视为复用。

## 人物身份硬门

字幕点名人物、人物组合、武器或关键证物时，所选范围必须有独立 proof：

```text
cue_id track canonical_identity candidate_id source_id source_in source_out
head_frame head_sha256 head_source_time mid_frame mid_sha256 mid_source_time
tail_frame tail_sha256 tail_source_time identity_basis visible_features
confusables_checked identity_verdict reviewer review_status
```

头/中/尾证明帧都要绑定 SHA 与所选 source range 内的时间；`candidate_id`、source 与范围必须和计划精确一致，`identity_basis=visible_character_features`，且 reviewer/status 通过。画面中的字幕、OCR、对白或名字文字不能证明镜头里的人是谁。象征替代必须写 `symbolic_not_identity`，不能计入人物命中。

## 候选策略

- 普通且身份明确的 cue 保留已选镜头和必要 fallback，不再固定建立 8–12 个候选。
- 人物、P0、直接引文、高风险、低置信或用户点名行才要求 A/B/C 比较与头/中/尾证明。
- 找不到合格 A 轨镜头时回到素材模块补源；经许可的转录证据卡放 B 轨。不得用 `support` 掩盖人物错误或 P0 缺口。

## 分轨审核

首次送审前必须完成两轮内部检查，返修后对实际新版重跑：

1. 逐句检查人物/地点/事件/动作、画面与口播因果、头中尾黑场、水印遮挡、证明帧和字幕边界。B/C 需在实际 A 画面上检查可读性和遮挡，不能只看孤立卡片。
2. 在全部选镜完成后检查全片：按物理镜头、原片区间和近似构图归组；裁切、缩放、调色、改 ID、另存文件不产生新镜头。运行 `audit_global_reuse.py --max-groups 4 --max-occurrences 2`，通常最多 4 组有叙事理由的回扣，每组首次使用加一次回扣。相邻不重复不能代替整片合格；真实近似画面仍须联系表和片段审看，不能只靠不同 source ID。

开头前 10 秒全用 CG/PV/剧情过场，以冻结旁白联播审看。安排多个有新信息的不同镜头，每次切换写清“推进哪条信息、为何在此时切”；不得用单张站桩、连续无关炫技镜头或机械固定镜头数量交差。第三期的 13 镜头不是以后固定配额。

通过后生成 `a_submission_v2`，绑定实际选中镜头表、时钟、冻结旁白、全片近似画面检查、开头叙事审看、B/C 叠加审看及固定 WebUI 文件。按 [v2 契约](../zhangyanfa-video-production/references/submission-contracts-v2.md) 登记；缺收据、复用超标或新版仍沿用旧审核命名空间均不能首次提交为通过。

狐久项目沿用 [固定 WebUI 与整片复用约定](references/foxjiu-review-contract.md)。所有选镜完成后必须审计实际画面的整片复用，最多保留 4 组有意义回扣；审核页沿用 `assets/review-ui-v1` 的布局和交互，只替换项目数据。

分别生成 A、B、C 审核包，并分别写入：

```text
a_track_review
b_track_review
c_track_review
```

每条审批绑定实际展示文件、SHA、时间和用户原话。一轨资产变化只使该轨审批失效。机器检查不能代替用户对人物、语义、节奏或证据可读性的判断。

## 输出与完成条件

```text
tracks/track_plan.tsv
tracks/A/match_sheet.tsv
tracks/B/plan.tsv
tracks/C/plan.tsv
tracks/identity_proof.jsonl
tracks/reuse_qa.json
tracks/review/A/
tracks/review/B/
tracks/review/C/
```

完成时每个 cue 均有画面决定、刷新决定与匹配理由；所有 P0/人物 proof 通过；无未授权素材、未解释重叠或未批准 continuity override；A/B/C 所需审核均已绑定当前 SHA。

## 脚本

- `scripts/srt_to_track_plan.py`：从最终 SRT 建立逐 cue 模板。
- `scripts/audit_track_plan.py`：以 `(track,cue_id)` 审核 TSV；reviewed 阶段同时读取 shot index、rights ledger、逐轨审核清单/审批账和最终 cue 数。

- `scripts/audit_global_reuse.py`：在全部选镜完成后统计整片物理镜头复用，合并跨文件原片区间与已核验别名；近似画面仍须视觉复核。

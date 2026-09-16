---
name: game-footage-ingest-index
description: 获取、校验并索引游戏视频素材，建立可检索的镜头、OCR/ASR、人物身份、来源权限和P0素材覆盖。用于剧情录屏梳理、素材下载、镜头库、人物库或素材缺口判断；不负责写稿、逐字幕选镜或正式渲染。
---

# 游戏素材摄入与索引

把用户给出的原始素材整理成可追溯、可检索、可复用的素材库。原文件保持只读；全量抽帧、OCR缓存和代理放在项目声明的本地非 iCloud 缓存中，项目目录只保留清单、索引、联系表与最终证明帧。

## 工作路径

先读取本期 `workspace_paths.json`，遵守[统一目录与素材规范](../zhangyanfa-video-production/references/workspace-layout.md)。原片按来源 ID 登记到共用原始素材库，当前项目在 `sources/vNNN` 保存索引与冻结清单；代理、全量抽帧、OCR/ASR放 `cache:ingest`。已有用户指定原片位置优先，登记引用，不强行搬迁。新下载前先查已有 source ID、URL 与 SHA。 所有新版本先分配目录，再写文件；不自行发明另一套阶段路径。旧期 `legacy_indexed` 工作台用于导航，不视作新生产目录或新的审批权威。

## 模式

- `reconnaissance`：写稿前梳理完整剧情、可见台词、人物、事件、证据与素材缺口。
- `final_source_freeze`：最终 SRT 冻结后，逐章核验 P0 画面是否齐全，并冻结供配画使用的素材清单。

## 必要输入

- 原始录屏、官方素材、用户链接或图片；
- 来源与授权信息；
- 可选的章节表、证据矩阵或最终 SRT；
- 项目 `request_contract.json` 中冻结的素材与画幅要求。

## 标准输出

```text
sources/source_manifest.jsonl
sources/rights_ledger.tsv
sources/identity_registry.json
sources/shot_index.tsv
sources/ocr_asr_index.tsv
sources/coverage_receipts.jsonl
sources/p0_coverage.tsv
sources/contact_sheets/
sources/proof_frames/
sources/ingest_qa.json
```

允许以 SQLite 或 Parquet 代替大型 TSV，但必须在 manifest 中登记格式、路径与 SHA。完整录屏分析时读取 [recording-and-indexing.md](references/recording-and-indexing.md)；外部下载或权限判断时读取 [source-and-rights.md](references/source-and-rights.md)。

## 硬门

- 每个源都有稳定 `source_id`、绝对路径、SHA-256、含正数 `duration_s` 的 probe、来源和权限状态。
- 完整录屏的索引覆盖首帧至尾帧；加载、菜单、失败重试和 UI 先分类，不能静默删除。
- `ocr_asr_index.tsv` 必须覆盖每个 `shot_id`；`coverage_receipts.jsonl` 逐源绑定 source SHA，并用分类区间无缝覆盖 `[0,duration_s]`。
- 人物库保存 canonical 证明帧、可见特征和易混淆对象；OCR 或对白出现名字不能证明画面人物身份。
- `p0_coverage.tsv` 必须逐项写 `available | acquire | card | remove`，同时写目标轨道；`card` 只可用于经允许的 B 轨证据转录，不能解决 A 轨缺画面。删句需走稿件/时间轴变更，不能在素材模块偷偷删。
- 新素材加入后重新探测并增量索引；文件名和缩略图不能代替实际检查。
- `permission_needed` 或 `unknown` 的素材不得进入正式轨道；只有权利已经查明，或用户确认自己拥有该素材并有权用于成片时，才能改写权限状态后使用。

## 成本与存储

第七步还必须做素材容量检查：按人物、地点、事件/行动与章节统计预计镜头槽位、可用的不同物理镜头、计划回扣和缺口。同一素材文件可有多个镜头，同一镜头的裁切或跨文件摘录不能充数。总时长够、候选多、P0 项目存在，都不代表整片能避免复用。开头 CG 和高频主角优先补足。容量不足先补源或调整经批准的方案，不能留到第八步用重复镜头或 A 轨文字卡补齐。

保存 `source_capacity_v2`，绑定当前 SRT、冻结素材清单、独立镜头组与实际审看证据；缺口必须为零，计划回扣不得超过本期冻结上限。字段见 [v2 提交契约](../zhangyanfa-video-production/references/submission-contracts-v2.md)。这是 `final_source_freeze` 的提交前门禁，不新增用户确认次数。

- 粗索引覆盖全片，密索引只围绕人物、台词、短暂卡面、动作与场景变化展开。
- 不把数万张中间帧同步到 iCloud；缓存键至少包含源 SHA、抽帧/OCR配置和工具版本。
- 保留精选联系表与身份/P0证明帧；可再生的全量帧只保留缓存收据。

## 交接

向 `game-lore-script` 提供事实、原文、未决项和画面可行性；向 `zhangyanfa-track-design` 提供冻结的 source manifest、镜头索引、人物库、权限表与 P0 覆盖。此模块不决定 A/B/C，不移动字幕时间，也不生成母版。

## 脚本

- `scripts/build_shot_index.py`：对素材做粗采样与联系表。
- `scripts/audit_ingest.py`：核对来源、probe、OCR/ASR、逐源全时长 coverage receipt、索引和 P0 覆盖；五个索引/账本输入都不可省略。
- `scripts/vision_mission_analyzer.swift`、`scripts/vision_ocr.swift`：在 macOS 使用 Apple Vision 提取 OCR 与视觉线索。

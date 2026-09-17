---
name: zhangyanfa-video-production
description: Manage an end-to-end 障眼法视频 project through its 13-stage state machine, current script/narration/subtitle authority, artifact-bound user approvals, downstream invalidation, final assembly, and delivery seal. Use when starting, resuming, approving, auditing, or sealing a complete video project. Route implementation work to the dedicated script, footage, dubbing, subtitle, track, score, render, and cover skills.
---

# 障眼法视频生产总控

本 Skill 只管理阶段、权威、审批、失效和封存。它不重复定义稿件、配音、字幕、素材索引、选片、BGM、渲染或封面的内部算法。

## 第一步

先读取项目状态：

```bash
python3 scripts/workflow.py status --root PROJECT_ROOT
```

- 已有 `CURRENT.json`：从它指向的当前阶段继续。
- 没有状态文件：从用户要求和既定偏好确定标题、主题、交付规格、剪镜规则、启用轨道、B/C 输出方式和整合工具后运行 `init`；已有答案不重复询问。目标时长只冻结用户给出的范围。默认完整复制 [house_style.v2.json](assets/house_style.v2.json) 到 `request_contract.json`，后续只读这份冻结副本。狐久默认交付独立 A/B/C、独立配音与 BGM，A 不烧口播字幕；只有实际要求整合片时使用 `--delivery-mode integrated` 或 `both`。
- 旧项目：读取 [legacy-migration.md](references/legacy-migration.md)。不得根据文件名猜测当前版本，不得把旧聊天补写成哈希审批。

状态文件、阶段收据和命令参数见 [state-schema.md](references/state-schema.md)。

## 工作路径硬流程

新一期必须通过 `workflow.py init` 建目录，并传稳定的 `--episode-key`（例如 `GI71_EP004`）；默认 v2 模板自动冻结 `workspace_paths.json`。每个模块写文件前读取[统一目录与素材规范](references/workspace-layout.md)，通过 `workspace_layout.py resolve/new-version` 取得阶段与版本路径。禁止在顶层临时创建带日期或 `_v3` 的阶段目录，禁止把模型 attempts、转码块和全量抽帧放进 iCloud 项目或永久原片库。

共用原片在 `~/Documents/视频工作区/02_素材库/00_原始素材库` 登记，临时处理按项目编号进入 `~/Documents/视频工作区/03_制作缓存/<episode_key>`；固定参考仍按原规则使用原件或同 SHA 副本。用户明确指定原片存放位置时登记实际路径，不擅自搬迁。

本地大文件统一归属 `~/Documents/视频工作区`。已配置 `00_管理/storage_roots.json` 时，初始化、路径解析与检查会核验兼容链接及散落目录；失败先修路径，不另建一个 Scratch 绕过。每期写入前运行 `workspace_layout.py doctor`，大范围整理另运行 `audit_storage_layout.py`。迁移后旧绝对路径只作兼容入口，新配置写实际统一路径。已有冻结路径契约保持原字节，不能为了改目录伪造审批或批量重写 SHA。

总控对新项目产物的所属目录与 `vNNN` 层做登记检查，路径契约被修改时阻断继续；状态保存后自动刷新 `00_开始这里.md` 与交付索引。接续时先看这一入口，再核对唯一权威，不能按“最终版”或时间戳猜测。旧期可用 `adopt` 补统一工作台，原状态、审批与文件保持原位；导航不授予迁移、覆盖或清理权限。

新项目必须执行 [v2 提交、审批与交付硬流程](references/submission-contracts-v2.md)。`production_contract_version=2` 的稿件、配音、素材容量和 A 轨提交均须绑定真实审校收据；总控会复算全片复用并核验嵌套证据。旧项目的冻结 v1 规则保持有效；不能为通过新门禁而篡改旧项目，也不能给新项目选择 v1 来规避检查。迁移必须是独立、有明确范围的工作。

## 十三阶段

1. 项目初始化
2. 研究与素材侦察
3. 稿件制作
4. 稿件审批
5. 配音制作
6. 最终字幕
7. 素材冻结
8. A/B/C 逐字幕配画与 BGM
9. 720p 整合终审
10. 2K60 正式渲染
11. 按交付模式整合或打包独立分轨
12. 六稿封面与多尺寸
13. 交付封存

完整依赖、阶段门禁和失效图见 [workflow-contract.md](references/workflow-contract.md)。

## 工作规则

每个模块开始前读取当前 `authority_bundle.json`。模块完成后生成实际文件和一份可注册产物；总控重新计算文件 SHA-256，不接受模块自报哈希。

只可向当前阶段注册产物：

```bash
python3 scripts/workflow.py register --root PROJECT_ROOT \
  --stage 08_track_design --role a_review --path PATH \
  --meta-json '{"cue_count":260,"identity_error_count":0,"semantic_coverage_pass":true,"unexplained_boundary_reuse_count":0,"selected_segments_sha256":"ACTUAL_SHA","submission_review":{"path":"08_配画与BGM/v001/A/submission_review.json","sha256":"ACTUAL_REPORT_SHA"}}'
```

需要人工判断的产物必须在真实展示后按角色记录决定；同一回复可以批准多个已经展示的产物，使用 `approve-batch` 一次登记，不拆成多轮问答。v2 单项登记示例：

```bash
python3 scripts/workflow.py approve --root PROJECT_ROOT \
  --role a_review --shown-at ISO_TIME --presentation approvals/presentations/a_v001.json \
  --quote 'A通过' --scope '当前A轨'
```

A、B、C、BGM 分别绑定审批对象；任何一项通过都不能替代其他项。v2 第八步批准 `bgm_review` 试听，第九步登记由该选择派生的 `bgm_master` 并放入全长整合代理，不额外要求一次同内容选曲审批。全长代理、实际交付、六稿选择与各画幅同样绑定已展示文件；字节完全相同的交付副本可沿用真实展示证据，新画幅不能预批准。

720p 整合代理通过后，将正式渲染授权绑定同一 proxy SHA、当前权威和交付规格。若展示时已明确下一步是按冻结规格正式渲染，用户回复“审核通过，进入下一步”可以同时作为该上下文的授权；使用原展示收据登记，不能逼用户重复说“2K60”。明确授权也可直接登记：

```bash
python3 scripts/workflow.py authorize-render --root PROJECT_ROOT \
  --shown-at ISO_TIME --presentation approvals/presentations/proxy_v001.json \
  --quote '现在可以进入2K60正式渲染' \
  --scope '当前720整合代理对应的正式分轨渲染'
```

没有明确审批对象和已展示下一步的“继续”或“开始”，不能生成审批记录。

当前阶段满足门禁后才能推进：

```bash
python3 scripts/workflow.py advance --root PROJECT_ROOT
```

没有 `--force`。`开始制作`、`继续`、`开始渲染`等工作授权，以及`不通过`、`未批准`、`还没确认`等否定决定，都不能登记为审批；审批原话必须明确表示通过、批准、确认最终版、选定候选或给出明确的 BGM 选择。warning 可在用户看片后接受；hard blocker 不可豁免。仍绑定相同输入的旧母版可以复用，但仍要经过阶段检查，不能直接跳过阶段。

## 唯一权威

每期只有一份当前脚本、一份独立口播母带和一份最终 SRT。它们只记录在 `authority_bundle.json`。

`CURRENT.json` 只指出当前阶段及请求契约、权威、审批账和交付清单的位置，不保存第二套产物详情。当前下游文件只记录在 `deliverables.json`。人工决定只追加到 `approvals/approval_ledger.jsonl`。

脚本、口播、字幕或其他上游文件发生变化时，先运行 `invalidate`，再注册新版。不得直接覆盖已批准文件后继续生产：

```bash
python3 scripts/workflow.py invalidate --root PROJECT_ROOT \
  --role bgm_master --reason '用户改选BGM'
```

总控按照真实依赖传播失效。例如仅更换 BGM 时，A/B/C 正式母版仍可复用，但整合代理和最终成片必须重做。

用户批准剪掉整段时，先由字幕模块保存剪辑决定表和唯一有效时钟，再让所有下游读取同一结果。不得让配音、BGM、A/B/C 各自计算删段。完成一次修改后先列实际受影响对象与范围；保留未变产物的既有批准，不扩大重审。每次用户回复可连续推进所有已满足门禁的步骤，遇到新的、尚未展示且必须由用户判断的产物才停止。

流程可按研究/稿件、配音、最终字幕、A/B/C与选曲、整片审看、封面与交付组织展示，十三阶段仍保留。不能承诺固定六次回复，也不能把后续尚未生成的文件预先记成通过。监控、低内存与增量检查按 [v2 硬流程](references/submission-contracts-v2.md) 执行。

## 模块路由

- 研究、论证、传统中文和口播稿：`game-lore-script`
- 素材获取、OCR/ASR 和镜头库：`game-footage-ingest-index`
- 配音生成与母带：`voxcpm-batch-dubbing`；狐久声线必须遵守该模块的「固定声线参考」及启动校验，不得自行从往期母带挑选参考。
- 最终字幕与整数帧时钟：`subtitle-timeline`
- A/B/C 设计、逐字幕选片和身份核验：`zhangyanfa-track-design`
- BGM 候选、避让和混音：`zhangyanfa-score-and-mix`
- 720p、2K60、安全渲染和最终整合：`zhangyanfa-track-renderer`
- 六稿封面、选稿和多尺寸：`zhangyanfa-cover-production`

只有进入对应阶段时才加载对应模块。

## 封存

第十三阶段运行：

```bash
python3 scripts/workflow.py seal --root PROJECT_ROOT
```

只有前十二阶段仍有效、要求的实际文件和审批仍匹配 SHA，才能变为 `sealed`。`integrated` 要求 `final_video`；`independent_tracks` 要求 `split_delivery` 与其 QA，不强求不存在的整合成片；`both` 要求两者。独立分轨打包后可先制作封面，封存前将已展示的交付包确认与各封面决定一起登记。用户说“这期结束了”时核对实际展示范围后执行合法封存，不再靠项目私有 adapter 跳过门禁。

封存不自动删除任何文件。需要整理缓存或旧代理时再读取 [storage-lifecycle.md](references/storage-lifecycle.md)。

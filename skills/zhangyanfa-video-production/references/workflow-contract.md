# 十三阶段生产契约

## 核心原则

阶段顺序固定，失效按照实际依赖传播。任何模块只能向当前阶段提交产物；完成的旧阶段只有在其输入与输出 SHA 仍有效时才可复用。

本表是新项目 v2 契约。v1 项目继续用原冻结规则：第八步 `bgm_master` 审批、第十一阶段整合片。新提交报告、真实展示、批量审批和独立交付格式见 [submission-contracts-v2.md](submission-contracts-v2.md)，不得选择旧版本跳过新检查。

`objective_status=pass_with_warnings` 不是 hard blocker，但需要人工判断的产物仍须用户批准。`hard_blockers` 非空时不得推进。

## 阶段门禁

| 阶段 | 模块 | 必需产物与门禁 |
|---|---|---|
| `01_init` | 总控 | 非占位标题与主题、宽高、fps、可选目标时长范围、剪镜规则、启用轨道、B/C输出方式、整合工具与完整 house style 已冻结在`request_contract.json`；`init`自动完成 |
| `02_research_scout` | `game-lore-script`、`game-footage-ingest-index` | 非空`evidence_ledger`和`source_scout`存在且客观通过；最小 QA 元数据带版本、证据/反证/现有素材/缺口计数、已审阅标志及`qa_pass` |
| `03_script_build` | `game-lore-script` | 非空`script`和`script_qa`；原有中文/作者/画面 QA 加 `editorial_submission_v2`，完成命题证据、动机、反证、全稿指称朗读、钩子与结尾检查 |
| `04_script_approval` | 总控 | 用户批准当前`script` SHA；脚本写入唯一权威 |
| `05_narration` | `voxcpm-batch-dubbing` | 固定参考预检、开头试配后批量生成；`narration`、`voice_release`与 `voice_submission_v2`通过；用户真实完整1×试听批准母带后冻结 |
| `06_subtitle` | `subtitle-timeline` | `subtitle`、`timing_contract`通过；用户指定最终SRT；cue count与正整数`target_frame_count`冻结 |
| `07_source_freeze` | `game-footage-ingest-index` | `source_freeze`、`source_capacity_v2`通过，P0与容量缺口均0；A补游戏画面，允许的原文转录卡限B |
| `08_track_design` | `zhangyanfa-track-design`、`zhangyanfa-score-and-mix` | `track_plan`、启用的A/B/C与`bgm_review`实际试听分别绑定审批；A提交前核验全片复用、开头叙事、身份、B/C叠加及固定UI |
| `09_integrated_720_review` | `zhangyanfa-track-renderer` | `bgm_master`与派生报告绑定已选试听；全长`integrated_proxy_720`含全部审核层、冻结旁白/SRT与实际全长BGM，并由用户批准 |
| `10_formal_render` | `zhangyanfa-track-renderer` | 已批准的全长720代理另有绑定同一SHA与当前权威revision的`formal_render_authorization`；A及启用的B/C正式母版存在；`render_qa`证明串行渲染、完整解码、规格、fps和帧数通过 |
| `11_final_assembly` | `zhangyanfa-track-renderer` | `integrated`：成片与QA按冻结字幕政策通过及实际验收；`independent_tracks`：`split_delivery`与QA技术通过可先做封面，封存前完成交付确认；`both`两者都要求 |
| `12_cover` | `zhangyanfa-cover-production` | `cover_candidates`恰有六稿并完成选择；16:9、4:3、3:4各自通过布局检查和用户审批 |
| `13_seal` | 总控 | 前十二阶段仍有效；最终交付角色齐全、哈希当前、审批当前；`seal`完成 |

## 默认剪镜规则

`cut_policy=per_caption_refresh` 时，A轨在每个字幕边界必须开始新的镜头或新的、不重叠的有效源范围。B/C 的出现不能替代 A 轨刷新。确需延续同一动作时，由轨道模块在逐字幕表中登记例外理由和审批ID；未解释的复用数量必须为零。

只有用户在初始化或明确变更时选择`semantic_hold`，才允许按完整动作或场景跨字幕延续。规则变更从第八阶段重新开始。

## 审批范围

以下角色分别绑定决定，可以在一条用户回复中批量登记，不等于逐项重复询问：

- `script`
- `narration`
- `subtitle`
- 启用的`a_review`、`b_review`、`c_review`
- `bgm_review`（v1 为 `bgm_master`）
- `integrated_proxy_720`
- 按模式要求的 `final_video` / `split_delivery`
- `cover_candidates`
- `cover_16_9`、`cover_4_3`、`cover_3_4`

用户提供并明确称为最终版的文件，可以把提供时间记为展示时间。广义的“继续”“开始做”只算工作授权，不能写成产物批准。
否定原话如“不通过”“未批准”“还没确认”“不选择”也不能登记成审批，即使句中包含“通过”“批准”“确认”或“选择”等字样。

正式渲染授权必须绑定当前已批准的720整合代理；代理或权威 revision 变化后旧授权自动失效。v1 按原冻结规则要求原话明确提到正式渲染、2K、2K60、母版输出或等价对象。

v2 也接受有真实上下文的“审核通过，进入下一步”：展示收据必须已经写明 `next_action=formal_render` 和未变的交付规格 SHA。不能事后补称已展示，不能把单独“继续”记成产物批准。展示、决定和补录时间如实区分；同字节封面交付副本可绑定原展示，新画幅先生成再展示。

## 失效图

- 脚本变化：脚本批准、口播、字幕、素材冻结、轨道、BGM、代理、母版、成片和封面全部失效。
- 口播变化：口播批准、字幕及全部时间相关轨道、BGM、代理、母版和成片失效；封面可保留。
- 字幕或时间时钟变化：字幕批准、素材冻结确认、A/B/C、BGM、代理、母版和成片失效。
- 素材冻结变化：轨道、代理、相应母版和成片失效；使用该素材的封面也须失效。
- A/B/C变化：对应审核、整合代理、对应正式母版、统一渲染QA和成片失效。
- 仅BGM候选变化：第八步选择、全长BGM、代理与交付失效；全长BGM内容变化从第九步重做；A/B/C正式母版保留。
- 整合代理变化：代理审批和最终成片失效；未变的正式画面母版可以保留。
- 正式母版变化：统一渲染QA、最终成片和封存失效。
- 最终成片变化：成片审批和封存失效。
- 封面变化：对应画幅审批和封存失效。
- 宽高或fps变化：从第六阶段重新量化时钟；已批准脚本和内容未变的口播可以保留。

阶段线性不等于全部重算。推进时若中间阶段已有仍有效的完成收据，总控跳到下一项真正未完成阶段；这属于哈希复用，不是越级。

## 模块收据边界

总控不遍历完整候选池、OCR明细或渲染分块。模块交付实际产物与版本化提交报告；总控核验当前文件、嵌套证据和实际选镜表并复算整片复用，正式渲染前与封存时再次检查必要链条。文笔、自然度、叙事性与可读性仍须实际审看，不能靠布尔字段伪造完成。

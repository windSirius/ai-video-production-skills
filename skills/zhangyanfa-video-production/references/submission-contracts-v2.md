# v2 提交、审批与交付硬流程

适用于冻结了 `delivery_spec.production_contract_version=2` 的项目。默认模板是 `assets/house_style.v2.json`；初始化后读项目的冻结副本，不能读取可变模板来改动正在制作的项目。v1 不被追溯加门，也不得给新项目选择 v1 逃避检查。

## 提交顺序

1. 模块完成实际产物和规定检查。
2. 保存实际审读/试听/审看证据，生成下列 SHA 绑定报告。
3. `workflow.py register` 重新计算产物 SHA，并执行对应提交检查；失败先修，不展示为“待通过成品”。
4. 用固定审核页或真实文件展示，保存实际展示收据。
5. 根据用户真实决定登记已展示的对象，满足门禁后继续。机器 PASS、制作者审看和用户批准是三种记录。

硬流程不等于全自动判断。程序可查哈希、文件、帧时钟、镜头复用和收据完整性，不能证明文笔好、音乐动人或某人真的听过；审查者必须实际完成对应检查，禁止空模板批量填 PASS。

## 通用报告结构

文件引用均为 `{"path":"相对项目根目录的路径或绝对路径","sha256":"实际文件的64位SHA"}`。下列 `REF` 是文档占位符，不能直接提交。注册元数据 `submission_review: REF` 指向对应报告。报告不能把自身哈希写进自身；引用的是实际产物，注册元数据保存在总控交付清单中。

人工/制作方审查项结构统一：

```json
{"status":"pass","reviewer":"实际审查者","notes":"发现、处理和剩余边界","evidence":[{"path":"review/notes.md","sha256":"ACTUAL_SHA"}]}
```

`evidence` 至少一份实际文件：例如逐句批注、带时间码试听记录、原文定位、证明帧、全片联系表或真实代理。标记工具实际做的检查范围，不把几帧抽查看成完整观看。

## 第三步：稿件首次送审

`script_qa.meta.submission_review` 指向 `editorial_submission_v2`：

- `schema: editorial_submission_v2`，`status: PASS`。
- `bindings.script` 绑定当前 `script`，`bindings.canonical_text` 绑定当前正典纯文本。
- 六项通用审查对象：`thesis_and_evidence`、`character_motivation`、`counterexplanation_and_falsifier`、`full_referent_and_readaloud_review`、`opening_promise`、`ending_payoff`。
- `counterexplanation_and_falsifier` 检查研究是否处理反证，不要求把反证念进口播。狐久推断类按 [game-lore-script 连续叙事规则](../../game-lore-script/SKILL.md#狐久推断类口播连续叙事硬规则) 逐段检查：记录反证的非口播保存位置、中途打断的清理结果，以及结尾限定段的位置或无需保留的理由。原文必要条件和推测语气仍需准确。
- 各项证据必须对应本稿；不涉及人物行动时写明不适用的理由，不为了表格虚构动机。
- 狐久纯文本末尾必须是冻结的固定收束语。原有传统中文、作者语言、逐句/段间/全稿朗读检查继续执行；此报告不能替代它们。

先核实命题与证据层级，再审开头和整稿；A+ 表示值得深挖，不提升证据置信度。禁止用听起来肯定的句式填补没有直接证据的环节。

## 第五步：开头试配先于整批生成

模型加载前执行固定声线预检。不可变输入 `source_manifest` 至少保留参考音频、参考文字、`generation_config`、原有规则 SHA 和 `canonical_text_sha256`；生成进度另存 attempts 日志。

开头样段用正式生成块和正式配置，检查断句、停顿、语气、尾字和专名。由制作方实际试听并保存 `voice_opening_smoke_v2`：

```json
{
  "schema":"voice_opening_smoke_v2", "status":"PASS",
  "source_manifest":{"path":"ABSOLUTE_IMMUTABLE_INPUT","sha256":"ACTUAL_SHA"},
  "sample_audio":{"path":"ABSOLUTE_SAMPLE_WAV","sha256":"ACTUAL_SHA"},
  "canonical_text":{"path":"ABSOLUTE_CANONICAL_TEXT","sha256":"ACTUAL_SHA"},
  "reviewer":"实际试听者", "notes":"具体断句与停顿判断",
  "checks":{"opening_prosody":true,"pause_naturalness":true,
            "pronunciation_hotspots":true,"listened_to_actual_sample":true}
}
```

声线 verifier 独立运行，因此该收据使用绝对路径。样段不必增加用户审批，但不通过就不能批量生产。

```bash
python3 ../voxcpm-batch-dubbing/scripts/verify_voice_reference.py \
  --source-manifest INPUT --phase reference --output-json REFERENCE_CHECK
# 实际生成并听样段后
python3 ../voxcpm-batch-dubbing/scripts/verify_voice_reference.py \
  --source-manifest INPUT --phase bulk --smoke-review SMOKE_REVIEW --output-json BULK_PREFLIGHT
```

批次前、续作前均重新运行；输入/配置/参考变更会使试音绑定失效。`--phase repair` 只做返修参考检查，不能代替 bulk 的试音门禁。默认 `reference` 保持旧调用兼容。

`voice_release.meta.submission_review` 指向 `voice_submission_v2`：

- `bindings.script`、`bindings.narration`；`reference_preflight: REF` 指向通过的 bulk 检查。
- 通用审查对象：`fixed_reference_preflight`、`opening_prosody`、`pronunciation_hotspots`、`joins_and_tail`。
- 总控重新检查输入、固定音频、参考文字、实际试音和对应 SHA，不只相信预检里的 PASS。
- 最终母带仍必须经过完整 machine QA 和真实用户 1× 完整试听发布链。开头样段审听不冒充最终母带批准。

## 第六、七步：唯一时钟与素材容量

用户最终 SRT 原件保持不变；后续若批准删段，由字幕模块一次生成剪辑决定表、保留区间、新母带/SRT/帧契约与 `effective_timeline.json`。其他模块只解析这一入口；不得各自裁一次，或一轨读旧母带另一轨读新时钟。变更后绑定实际有效文件并走相应失效。技术剪接记录不能被写成新增完整 1× 试听。

`source_freeze.meta.submission_review` 指向 `source_capacity_v2`：

- `bindings.subtitle` 和 `bindings.source_freeze` 绑定当前实际文件。
- `capacities` 每行含 `subject`、正整数 `required_slots`、不重复的 `eligible_physical_groups`、`planned_callbacks` 非负整数；可用独立镜头加计划回扣须足够需求。
- 每个物理镜头组必须来自冻结索引；跨章节共用的库存不能在多行重复当新增储备。用全片分配表作为 `capacity_review.evidence` 验证全局可用性。
- `unresolved_capacity_gaps:0`；通用审查对象 `capacity_review`。
- 回扣总预算不得大于冻结上限。正式选镜仍要再做全片审计，容量判断不能替代最终结果。

`P0=0` 与容量充足必须同时满足。A 轨只能选有效游戏/CG 画面；转录卡限 B 轨且注明来源与证据性质。狐久已授权确实找不到的剧情画面按[缺画面转 B 规则](../../game-footage-ingest-index/references/foxjiu-missing-footage-fallback.md)改由 B 承接直接证据；冻结表应保留已查来源、原文、用户授权及实际呈现材料，不能把原生视频未取得继续作为同一条证据的阻断项，也不能仅改状态就宣称卡片完成。A 的相关上下文镜头仍需独立满足容量、时间覆盖与复用要求，B 卡不计入 A 物理镜头数量。

## 第八步：实际 A 轨提交门禁

`a_review.meta.submission_review` 指向 `a_submission_v2`，`meta.selected_segments_sha256` 同时绑定实际选镜 JSON。

- `bindings`: `track_plan`、`narration`、`subtitle`、`timing_contract`、`selected_segments`。
- `selected_segments` 是 JSON 数组或含 `segments` 数组的对象。每行至少有 `segment_id`、`cue_id`、`source_id`、`source_sha256`、`source_in/out`（秒）、`start_frame/end_frame`（整数）、`visual_family_id`、`visual_type`、`production_caption_baked:false`、`production_card_baked:false`。
- `visual_type` 为 `gameplay|official_cg|official_pv|story_cutscene`。不是制作方卡片，不擅自删游戏自带文字。
- 可选 `source_origins:REF` 为 source ID 到 `{parent_sha256,offset_s}` 的映射；`family_aliases:REF` 为已视觉核验的同一物理镜头别名。跨文件摘录需提供原片映射。
- 运行全片物理复用审计，默认最多 4 组、每组最多 2 次；连续区间从 0 覆盖到冻结总帧数。原有逐字幕切点和身份 proof 检查继续执行。
- 通用审查对象：`near_visual_review`、`whole_episode_review`、`opening_review`、`auxiliary_overlay_review`。近似构图须实际查看，不能随意改 family ID 消除重复。
- `opening_review.watched_with_frozen_narration:true`；`shot_purposes` 每行 `{segment_id,purpose,new_information}` 必须恰好覆盖实际前 10 秒镜头。全段 CG/PV/过场，多个物理镜头；具体快慢服从叙事，不定 13 镜头配额。
- `review_ui` 为 `{framework_id:"foxjiu-review-ui-v1",version_namespace,previous_version_namespace,framework_manifest:REF,framework_files:{"index.html":REF,"review.css":REF,"review.js":REF}}`。框架文件保持冻结 SHA，项目数据另接；新计划命名空间不得等于上一版，旧草稿保留但不继承批准。

总控在登记 A 审核包时重新计算复用；正式渲染前和封存时再次核对嵌套证据。不能只上传一份与实际选择无关的 `reuse_qa=PASS`。

## 第八至九步：BGM 试听到全长

第八步 `bgm_review` 实体是用户选中的真实试听混音，meta 写 `candidate_id`。A–D 四个方向使用相同冻结旁白和可比范围/电平。角色分别获批，可一次回复登记。

第九步 `bgm_master.meta.derivation:REF` 指向 `bgm_derivation_v2`：

- `schema:bgm_derivation_v2`，`status:PASS`；
- `bindings`: `bgm_review`、`bgm_master`、`narration`、`subtitle`、`timing_contract`；
- 与已选试听相同的 `candidate_id`、冻结 `target_frame_count`；
- `chapter_coverage_pass:true`、`narration_intelligibility_pass:true`，实际章节和混音 QA 另存；
- 全长 `integrated_proxy_720.meta.bgm_master_sha256` 必须等于该母带 SHA。

用户在全长代理中审听最终 BGM；不再为同一选曲额外设置一次审批。替换全长 BGM 使第九步、交付和封存失效，A/B/C 母版保留；换候选从第八步失效。

## 真实展示与一次回复的多项决定

展示后保存 `artifact_presentation_v2`，不是登记时伪造“刚刚展示”：

```json
{
  "schema":"artifact_presentation_v2",
  "shown_at":"真实展示的ISO时间",
  "display_evidence":{"type":"webui","locator":"真实页面地址及版本，或聊天消息标识"},
  "items":[{"role":"a_review","artifact":{"path":"实际展示文件","sha256":"ACTUAL_SHA"}}],
  "next_action":{"action":"formal_render","delivery_spec_sha256":"FROZEN_SPEC_JSON_SHA_IF_APPLICABLE"}
}
```

`type` 仅 `chat|webui|user_supplied_file`。`next_action` 仅在展示时确实说明下一步正式渲染时写入。spec SHA 按 `production_contracts.json_digest` 的规范 JSON 计算，不能事后补称已展示。

展示、产物登记、用户决定、补录决定可以发生在不同时间；必须如实记录。已展示原文件与后来交付副本 SHA 相同即可；不同字节、改稿或新画幅必须重新展示。封面展示收据应包含候选单张，不能只拿 contact sheet SHA 证明所选单张。

批量文件：

```json
{
  "schema":"approval_batch_v2",
  "user_quote":"A审核通过、B审核通过、C审核通过，BGM选择A",
  "decided_at":"真实用户决定的ISO时间",
  "decisions":[
    {"role":"a_review","shown_at":"真实展示时间","presentation":"reviews/presentation.json","scope":"当前A轨"},
    {"role":"b_review","shown_at":"真实展示时间","presentation":"reviews/presentation.json","scope":"当前B轨"},
    {"role":"c_review","shown_at":"真实展示时间","presentation":"reviews/presentation.json","scope":"当前C轨"},
    {"role":"bgm_review","shown_at":"真实展示时间","presentation":"reviews/presentation.json","scope":"候选A实际试听"}
  ]
}
```

```bash
python3 scripts/workflow.py approve-batch --root PROJECT_ROOT --decisions DECISIONS_JSON
```

先验证整个批次再写账，任何一项无真实展示、错 SHA 或未来决定均拒绝。多范围回复中有否定/修改时，可以提供 `decision_clause`，它必须是原话中完整、逐字相同的正面分句，原始全文仍保留。只批准该分句指向的已展示范围，不能把“但不要字幕”解释成已批准后来新导出的不同文件。未变的旧对象不重复追加审批。

用户“审核通过，进入下一步”且原展示明确正式渲染及同一规格时，先批准代理、advance 到 10，再以同一展示收据和原话执行 `authorize-render`。模糊“继续”、缺展示的推测以及预批未来文件均不接受。该事件只授予制作动作，不冒充已经验收正式输出。

## 第十一至十三步：按模式交付

`delivery_mode=integrated|independent_tracks|both`。独立分轨提交：

- `split_delivery` 文件 `schema:independent_delivery_v2,status:ready`；
- `assets` 按角色绑定 `narration,subtitle,timing_contract,bgm_master,render_qa` 与全部启用的 `a_master/b_master/c_master`；
- `width,height,fps,target_frame_count` 等于冻结规格；`a_subtitle_baked` 按冻结选择，`a_audio_baked:false,a_auxiliary_overlays_baked:false`；
- `split_delivery_qa` 文件 `status:PASS,delivery:REF,audio_tail_pass:true,asset_clock_pass:true`，并保存实际 probe、解码和视觉检查收据。

第十一阶段技术检查通过后可制作封面；已展示交付包的确认可在 11/12/13 阶段登记，封存时必须齐全。各封面比例仍分别绑定实际文件，但用户一次明确回复可记录多项；不存在的未来比例不能预批。独立模式不要求 `final_video`，`both` 要求两种交付都齐全。禁止修改私有控制器让 `seal_errors=[]`。

## 低内存、监控和增量执行

- 重生成/解码/渲染任务共用稳定锁 `~/Documents/视频工作区/03_制作缓存/.foxjiu-heavy-worker.lock`，不能按项目或日期换锁而意外同时运行。配音批次和其他重任务用 `scripts/heavy_job.py -- COMMAND ...`；renderer 的 `safe_render_supervisor.py` 已自动持锁，不再套一层。锁描述符传递给子进程，锁占用返回75；锁持有时可顺序做轻量文案/清单工作。禁止仅检查锁文件是否存在后继续，禁止强删另一个活跃任务的锁。
- 同时一个重 worker。正式渲染 A→B→C，非 iCloud staging；配音保持同一模型会话连续批量，压力或失败才卸载/重启，不以牺牲音质换低占用。
- 每次进展记录：当前阶段/块、已完成与剩余、最后有效产物、elapsed、实际模型加载/生成/QA耗时。内存注明是 worker RSS、整个进程树还是系统/统一内存，不互相替代。ETA 用本次已完成块统计，未足够采样时明确未估计。
- 监控关注新输出、失败、停滞、压力和完成，不反复创建监控任务或刷同一状态；对用户有意义的进展及时汇报。停止准确进程组，保留通过块，从有效输入指纹续作。
- 缓存/QA 键至少含媒体 SHA、工具版本、实际配置、采样点集和对应输入 SHA。只复用完全相同的检查；改变音频、镜头、颜色管线或边界后重跑受影响项。禁止用缓存命中跳过新的内容判断。
- 图像比较先用同源同帧固定样本验证 RGB/PNG 抽取路径，避免 JPEG 与色彩转换误报。全部必要边界点保留，可按源批量解码，不能为提速删检查点或放宽错误阈值。
- 只有记录基线与修改后同工作量耗时，才能声称提速。模板、锁约定和 batching 计划本身不等于已经实测的收益。

常规维护只改 skill 与工具；旧项目迁移、缓存删除、模型更换和固定参考变更不随本契约自动发生。

## 每期必须记录的改进指标

在项目 `workflow_metrics.json` 记录首次送审后的返修范围/原因、已知规则被再次提醒的次数、A 重选 cue 数与分母、配音块数/保存 attempts/错误类别及分项耗时、实际用户决策次数、QA 经复核的误报、最终交付与控制器状态。时间、计数须能追溯到本期事件或收据；没有观测写 null/unknown，不填0伪装成功。

审批账多行不等于多次用户回复，聊天间隔不等于模型运行时间，额外候选不一定是配音错误。封存时据此写短复盘并更新可追溯的项目研究/素材索引。若获得真实发布数据，再关联标题/封面版本、点击率和前30秒/章节留存；没有数据不声称某个CG开头或封面提高了留存。

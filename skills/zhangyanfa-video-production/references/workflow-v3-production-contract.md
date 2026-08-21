# Workflow v3：创意先冻结，机器后渲染

## 目的

Workflow v3 用来修复四期实战中反复出现的同一类问题：机器指标已经通过，观众仍能立刻听出断裂、看出错配、素材疲劳或封面失真。v3 不用更多“注意事项”代替判断，而是把批准语义、整条听审、语义覆盖、跨期复用、全长动态代理和唯一当前版本变成可审计产物。

逐期问题、根因和门禁映射见 [four-episode-retrospective-to-gates.md](four-episode-retrospective-to-gates.md)。

新项目使用 `workflow_profiles.production_control=artifact_bound_release_v3`。旧 v2/v2.2 项目不被静默改写；恢复时先建立准确权威，再显式迁移。

## 1. 四种状态不得混用

所有人工决定追加到 `approvals/approval_ledger.jsonl`。允许的 `kind` 至少包括：

1. `work_authorization`：允许开始研究或制作，不批准任何尚未生成的创意产物；
2. `script_audio_freeze`：批准当前 `authority_bundle.json` 的 SHA，也就是同一组稿件、实际最终口播和最终 SRT；
3. `static_asset_review`：批准 `visuals/static_asset_review_bundle.json` 的 SHA；该 bundle 必须继续绑定 A 审核 manifest 与 B 审核 manifest，不能只写一句“素材已看过”；
4. `full_proxy_render_authorization`：批准已完整播放的全长 720p A/B 动态代理，并授权按同一输入指纹渲染正式母版。
5. `bgm_mix_review`：批准用户实际听过的旁白+BGM试听混音 SHA；
6. `cover_review`：批准用户实际看到的16:9封面成品 SHA。

除 `work_authorization` 外，每条批准必须包含：

```json
{
  "schema_version": 1,
  "approval_id": "APR-0001",
  "kind": "full_proxy_render_authorization",
  "status": "approved",
  "artifact_path": "hyperframes/proxy/aesthetic_proxy_720p.mp4",
  "artifact_sha256": "...",
  "artifact_created_at": "ISO-8601",
  "shown_at": "ISO-8601",
  "approved_at": "ISO-8601",
  "exact_user_quote": "可以，就这一版",
  "user_verdict": "pass",
  "scope": "render the hash-bound 2K60 A+B picture master"
}
```

必须满足 `artifact_created_at <= shown_at <= approved_at`，且批准时文件 SHA 仍匹配。广义的“继续做”“睡醒前做完”“开始渲染”只能授权动作，不能追认用户从未看过的素材、代理、BGM 或封面。

正式渲染前，三种产物批准缺一不可：`script_audio_freeze`、`static_asset_review`、`full_proxy_render_authorization`。后一项不能吞并前两项，也不能用 `work_authorization` 代替。

## 2. 研究与稿件门

核心结论先写入 `research/evidence_matrix.tsv`。每条 `claim_level=core` 的行必须填写：

```text
claim_id claim_level claim_text game_evidence real_prototype narrative_function internal_cross_validation counterevidence confidence source_refs status
```

- `game_evidence`：准确游戏原文或冻结录屏位置；
- `real_prototype`：现实原典、词源或 `not_applicable`，不能留空；
- `narrative_function`：相似的不只是名字，还包括行为和结构；
- `internal_cross_validation`：游戏内另一桥段或 `none_found`；
- `counterevidence`：缺口、反例或什么会推翻判断，不能只写结论；
- `confidence`：`direct`、`strong_inference`、`speculative`；
- `status=reviewed` 后才允许进入冻结稿。

冻结稿必须有 `script/script_qa.json`，分别通过：

- `structure_pass`：全文论证递进，不是资料堆叠；
- `evidence_pass`：强弱判断和原文边界一致；
- `chinese_oral_pass`：适合中文口播；
- `anti_calque_pass`：无机械欧化和法律/行政比喻滥用；
- `persona_pass`：以 Alan 的第一人称写作，不出现“用户认为”；
- `entity_pronoun_pass`：人物性别、称谓、专名一致；
- `read_aloud_pass`：消除连续同构转折、空泛指代和只在局部成立的补丁句；
- `human_status=pass`，并绑定冻结 script SHA。

全文审校固定按“结构与证据 → 中文与人格 → 朗读与重复”三遍完成。不得把用户指出的词逐个机械替换后直接交付。

## 3. 声音双门禁

使用完整语义/呼吸单元生成，通常为 120–200 个非空白汉字；极端专名段可合理缩短。普通段至少保留两个 lexical-exact 候选，再比较连贯性。禁止通过增加、删除或移动标点骗过模型，禁止词内、定中、主谓、动宾和并列短语内微切。

`narration/voice_release.json` 至少记录：

- `lexical_status=pass`：零插入、零替换、零删除；
- `pronunciation_status=pass` 或 `pass_with_minor_warnings`；
- `prosody_status=pass`：无异常词间停顿、句调重置和拼接感；
- `punctuation_topology=preserved`；
- `micro_splice_used=false`；
- `full_length_audition_status=pass`；
- 实际最终口播路径/SHA、master lexical receipt SHA、人工批准引用。

其中 `approval_ledger_id` 必须指向以当前 `authority_bundle.json` 为 artifact 的 `script_audio_freeze`；音频或字幕权威一变，这条批准立即失效。

发音缺陷分级：

- P0：多读、漏读、改字、错序，始终阻断；
- P1：明显改变词义、专名或核心术语的读音，例如“天使长 zhǎng”读成 `cháng`，阻断；
- P2：不改变理解的轻微声调或同音含混，记录 warning，不无限重生；标题和主命题词例外，仍需听清。

机器选择不等于人工听审。`subjective_listening_performed=false`、`awaiting_human_audition` 或 `release_ready=false` 的母带不得冻结。

## 4. 唯一时钟与失效传播

只有用户实际修改后的独立最终口播文件可以生成唯一最终 SRT。任何音频内容、间隔、拼接、修音或重新导出都会使旧 SRT、A/B/C、BGM、timing contract 和动态代理失效。

不得用裁尾、补尾、相同结束时间或 picture-only 例外，把旧口播伪装成新权威。正式母版之前，`authority_bundle.json` 的稿件、口播、SRT、fps 与目标帧必须全部 frozen，并在 v3 中增加：

```text
authorities.narration.pronunciation_hotspots_status
authorities.narration.prosody_status
authorities.narration.full_length_audition_status
```

## 5. 素材覆盖、语义匹配与跨期复用

逐句选镜前先冻结章节素材覆盖矩阵。每章至少有：CG/PV、任务实录、人物身份、地点/行动、证据页、结尾回扣和缺口处理。缺口存在时先补本地索引、录屏或精确下载，不用万能氛围镜头填满。

每个 A 轨语义单元标为：

- `direct`：画面直接呈现当前人物、行动、地点或文本；
- `strong`：存在清楚的游戏内结构/功能对应；
- `support`：只提供气氛或泛化联想。

发布 `visuals/semantic_coverage_qa.json`，正式动态代理前必须满足：

- A 轨 `direct + strong >= 0.80`；
- A+B 的直接/强匹配或精确证据覆盖 `>= 0.90`；
- `unresolved_units=0`；
- 开头 0–10 秒全部为与口播相关的 `cg_like`/PV 动态镜头；
- 章节级也不得用大量 support 镜头掩盖总分。

去重不只比较文件名和 in/out。每条素材登记 `visual_family_id`，例如同一 EP、同一场景、同一镜头组或同一美术语法。`visuals/reuse_qa.json` 至少证明：

- `max_consecutive_same_visual_family <= 3`；
- `unresolved_overlap_count=0`；
- `cross_episode_cooldown_violations=0`，或每个例外都有明确叙事理由；
- 不能把同一视频不同秒点当作天然不同素材。

系列项目同时维护共享复用台账。若画面缺口只能依赖上一期高频素材，先报告缺口并补素材，不自动复用。

## 6. B/C 轨

审核版与观众版必须分离。观众版不得显示内部编号、审核说明、证据边界、URL 或制作页脚；UID 必须按用户当前项目规则处理。黄色框和遮罩使用源图坐标及 contain/pad 变换计算，并做像素级边界抽查。

B 轨每次出现必须回答“证明或解释了什么”，并按实际阅读量安排停留。C 轨默认关闭；只有同一持续象征或空间关系跨三处以上出现，且不会与字幕/B 卡竞争时才启用。

## 7. 全长 720p 动态审核门

目标分辨率渲染前，必须生成一条从第 0 帧到 `target_frame_count` 的连续 1280×720 A 或 A+B 审核代理。v3 默认加入权威口播；可附审核字幕，但不得混入未冻结 BGM。它不是开头/中段/结尾三个摘录，也不是静态联系表。

`visuals/static_asset_review_bundle.json` 先绑定 A、B 两份静态审核 manifest 的 SHA，并由 `static_asset_review` 批准。之后，`visuals/aesthetic_review/approval.json` 必须绑定：代理、权威包、权威口播 SHA、match sheet、A 审核、B 审核、static review bundle、semantic coverage、reuse QA、composition、render plan 和 stress manifest 的 SHA，并记录：

- `full_timeline_reviewed=true`；
- `review_start_frame=0`；
- `review_end_frame=target_frame_count`；
- `human_status=approved_by_user`；
- 对应 `approval_ledger.jsonl` 的 `full_proxy_render_authorization`；
- 用户看到的正是该 SHA，且批准发生在文件生成/展示之后。

只有这条 artifact-bound approval 可以产生正式 `render_authorized=true`。

## 8. BGM 与封面

BGM 技术 QA 不等于音乐成立。至少抽听钩子、最密集证据、情绪转折、结尾四处，`human_audition_performed=true` 且 `human_status=pass` 后，再用 `bgm_mix_review` 绑定用户实际听到的试听混音 SHA；否则不能进入 seal。BGM manifest 还必须绑定最终 BGM master 的路径/SHA，`CURRENT.json` 不得指向另一个文件。

封面按主体类型分流：

- 官方角色、武器、UI、图标等身份/几何敏感主体，默认使用官方或用户提供资产做确定性前景；
- ImageGen 默认只做背景、气氛、光效或用户明确批准的完整场景；
- 不让生成模型重画需要精确识别的官方武器；需要并排展示时，优先官方图标/切图平铺；
- 先通过无字 16:9 小图，再排字；再检查缩略图、主体边缘线、变形和 AI 痕迹；最后才制作其他比例。

最终16:9成品以 `cover_review` 绑定 path/SHA；`CURRENT.json` 的封面必须与该批准文件一致，不能在用户通过后无声替换或微调。

## 9. 正式渲染与唯一当前版本

正式 2K60 是执行阶段，不是创意预览。开始之前依次通过：权威链、研究/稿件、声音双门、素材覆盖、语义覆盖、跨期复用、B/C 审核、压力样片、全长动态代理和 artifact-bound 用户批准。

交付完成后维护根目录 `CURRENT.json`，它是唯一“当前版本”入口：

```json
{
  "schema_version": 1,
  "workflow_profile": "artifact_bound_release_v3",
  "revision": 1,
  "status": "current",
  "updated_at": "ISO-8601",
  "artifacts": {
    "script": {"path": "...", "sha256": "..."},
    "narration": {"path": "...", "sha256": "..."},
    "subtitle": {"path": "...", "sha256": "..."},
    "picture_master": {"path": "...", "sha256": "..."},
    "bgm_master": {"path": "...", "sha256": "..."},
    "cover_16_9": {"path": "...", "sha256": "..."}
  }
}
```

旧成品、旧报告和旧 PASS 可以保留，但必须标为 `superseded`，不得与 `CURRENT.json` 竞争“最终版”身份。项目封存时运行 `scripts/audit_workflow_v3.py RUN_DIR --stage seal`。

## 10. 迁移与停止条件

- v2/v2.2 已批准产物在哈希未漂移时可以恢复使用，但不能自动获得 v3 的全长代理或审批资格；
- 旧批准没有 artifact SHA、展示时间或准确用户原话时，只能视为历史备注；
- 任何门禁缺失都停在对应阶段，不能通过生成更多文件或写一个 PASS manifest 跨过；
- 技术 QA 只能证明技术事实，不能给研究、发音、配画、BGM 或封面签字。

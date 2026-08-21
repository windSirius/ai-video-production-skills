---
name: zhangyanfa-video-production
description: Run Alan's complete “障眼法考据” production workflow with one hash-bound script/audio/SRT authority chain, artifact-bound human approvals, research and prose gates, lexical-plus-prosody narration QA, semantic A/B coverage, full-length 720p review, 2K60 HyperFrames rendering, BGM, identity-safe covers, client-review patches, delivery sealing, and recoverable cleanup. Use for 一条龙制作, 至冬考据系列, 游戏录屏解析, 配音修音, 修字幕, A轨逐句配画, B轨解释卡或剪影, CG开头钩子, BGM生成或选曲, 封面制作, HyperFrames分块渲染, 甲方返修, 文件夹瘦身, or continuing any verified phase of the same video project.
---

# 障眼法视频生产总控

把每一期视频当成一条可暂停、可续做、可局部返修的生产链。只执行用户当前要求的阶段；复用已经验收且哈希仍有效的资产，不为“走完整流程”重做成品。

## 权威顺序

发生冲突时按下列顺序裁决：

1. 用户最新明确要求与已确认的甲方反馈；
2. 用户标记的最终字幕、最终文案、最终音频或已批准审核包；
3. `segments.json` 或干净口播正文中的 canonical 文本；
4. 当前阶段的哈希绑定清单、收据和客观 QA；
5. 机器转写、生成代理词、旧修音版本、文件名与模型推测。

不得让发音代理词污染字幕。例如合成时可临时写“胡寄生”，canonical 文本和字幕仍保留“槲寄生”。不得用机器 ASR 推翻已经核过的专名。

## 唯一权威包

完整制作或任何正式长渲染前，读取 [authority-chain-and-release-gates.md](references/authority-chain-and-release-gates.md) 和 [workflow-v3-production-contract.md](references/workflow-v3-production-contract.md)。新项目使用 `artifact_bound_release_v3`，维护项目根目录唯一的 `authority_bundle.json`、追加式 `approvals/approval_ledger.jsonl` 和唯一当前入口 `CURRENT.json`。

需要判断某条门禁为何存在、是否可以降级时，读取 [four-episode-retrospective-to-gates.md](references/four-episode-retrospective-to-gates.md)。不得用“当前这次应该没事”绕过已经由前四期实战证明会复发的问题。

任何音频剪切、替换、拼接、修音或重新导出都产生新声音权威，并使旧词级收据、SRT、timing contract、A/B/C、动态代理与 BGM 失效。不得把旧口播裁成相同长度、把旧配画截成新帧数，或用最终视频内嵌音轨替代独立最终口播文件。正式渲染前同时运行 `scripts/audit_authority_chain.py` 和 `scripts/audit_workflow_v3.py RUN_DIR --stage pre-render`；交付封存前运行 `--stage seal`。

“允许继续工作”不是“批准产物”。研究/制作授权、稿件/音频冻结、静态资产审核、全长动态代理与正式渲染授权是不同状态。除纯工作授权外，人工通过必须绑定已经存在且已经展示的产物 SHA、生成/展示/批准时间和用户准确原话；不得让广义的“继续做”“睡醒前做完”“开始渲染”批准尚未生成的创意结果。正式渲染前必须同时存在当前的 `script_audio_freeze`、`static_asset_review` 与 `full_proxy_render_authorization`，三者不得互相代替。

## 总体阶段

按需从最近的有效阶段继续：

`交付规格与审批语义 → 研究证据矩阵/反证 → 全文稿件审核 → 配音双门禁 → 唯一最终字幕 → 素材覆盖/跨期复用矩阵 → A/B静态审核 → 全长720p A/B动态审核 → BGM/封面审核 → 2K60正式母版 → 集成返修 → CURRENT封存与瘦身`

每个阶段都必须留下：输入权威、输出路径、SHA-256、状态、未决项和下一阶段接口。详细目录见 [output-contract.md](references/output-contract.md)。

## 不可妥协的规则

- 在真实剪映工程里操作前，读取并遵守 [harness.md](references/harness.md)；禁止触碰「试试剪映助手」或「剪映助手」。
- 新制作或修改的动态画面资产使用 HyperFrames；FFmpeg只做探测、技术代理、无损拼接辅助和 QA，不取代画面编排。
- 把整数帧作为唯一时钟。禁止分别四舍五入开始时间和持续时间；相邻 clip 必须共享同一个边界值。
- 开工时冻结正式交付规格；本系列默认 `2560×1440/60fps`，除非用户另有要求。不得先渲染1080p全片，再把正式分辨率当作返修意见补入。
- 默认保留完整16:9画幅与完整 UID。不得为了遮 UID 或统一构图而混用裁切版与完整画幅版。
- B轨、C轨和封面先给用户看审核包；A/B 还必须生成从第0帧覆盖目标帧的完整720p连续动态代理。只有用户对该代理 SHA 的事后明确通过，才能开始正式长渲染。
- 配音同时验收字词和连贯性。多读、漏读、改字、错序始终阻断；明显改变词义、专名或核心术语的读音阻断；不影响理解的轻微声调含混可记录 warning。禁止为通过 ASR 改动 canonical 标点拓扑或做短语内微切。
- 官方角色已有可靠形象时，默认使用官方图、用户图或原始帧做确定性合成。只有用户明确授权生成角色或完整场景时，才进入生成路线；授权不等于验收，人物身份、叙事镜头和同场景一致性仍是硬门槛。
- 官方武器、UI、图标等几何敏感主体与人物身份相同：默认只用官方/用户资产作为确定性前景；ImageGen 不得重画需要精确识别的官方武器。
- 不因“做得更多”自动提升质量。一个证据页足够时就延长停留，不再叠加第二张；返修遵循“宁少做，不多做”。
- 不删除原录屏、最终字幕、最终音频、已验收母版、工程脚本、清单、收据或 QA。任何实质删除都需用户明确授权；优先移动到可恢复备份或废纸篓。
- 明确区分 `generated`、`downloaded`、`imported`、`applied`、`project updated`、`saved`、`exported`。
- 明确区分 `objective_status` 与 `human_status`。机器只能证明哈希、帧数、黑场、复用、解码等事实；不能自行批准发音、钩子、配画、节奏或封面命题。
- 技术 PASS 不得自动写成 `render_authorized=true`。唯一合法来源是当前 SHA 的 `full_proxy_render_authorization`。

## 1. 证据、录屏与文案

完整任务录屏先按 [game-recording-vision-analysis.md](references/game-recording-vision-analysis.md) 建立任务流程和证据索引。剧情考据文案调用 `game-lore-script`，只依据已提供材料、官方页面和可追溯证据写作。每个核心命题先写 `research/evidence_matrix.tsv`，同时记录游戏原文、现实原型、叙事功能、游戏内交叉验证、反证/缺口和置信度；名字或词源相似不能单独关闭研究。

文案交付时同时固定：

- 口播正文与 spoken SHA；
- 专名表、证据等级和待核验项；
- 章节与素材锚点；
- 前10秒钩子意图；
- 标题池与封面题眼。

冻结稿前按全文完成三遍 QA：结构与证据、中文口吻与第一人称人格、朗读连贯与重复。输出 `script/script_qa.json`；禁止只对用户点名的词逐句机械替换，不看全文转折和指代。

## 2. 配音、修音与字幕

调用 `voxcpm-batch-dubbing` 生成配音。对本系列固定采用以下优先级：

1. 每个正式段对 canonical 文本达到零插入（多读）、零替换（错读）、零删除（漏读），并绑定实际 WAV、ASR 和词级收据 SHA；
2. 专名、多音字、造词和曾经读错的短语进入 `pronunciation_hotspots`，写明要求读音与禁用读音；第二 ASR 只有在能区分争议读音时才有效，同字不同音或声调问题必须抽取短音频定向试听；
3. 完整覆盖、尾字、顺序、接缝和信号检查通过；
4. 使用完整语义/呼吸单元生成，普通段至少保留两个 lexical-exact 候选，再比较连续语气、重音和相邻段衔接；不得用首个字面 PASS 自动晋升；
5. 之后才比较相似度、音调、情绪、自然度和音色。0.90 相似度是次级异常门槛，不能覆盖任何词级错误；
6. 每次重做、替词、拼接、交叉淡化、接缝修复、响度归一化或重新组装，都使受影响文件及下游母带的旧词级收据失效；
7. 实际最终母带必须再做一次全文 ASR 和零插入/零替换/零删除审计；随后完成整条1×试听并输出 `narration/voice_release.json`。若后期确认一个多字或错字，当前母带标记为 `untrusted_for_text`，重新检查全部正式段和全部接缝，不能只补已暴露的那一句。

词级门通过后仍须由用户试听 P1 专名热点和实际完整母带。用户说“稍后再听”时，只能继续素材研究、证据卡和低清代理；不得把任何下游结果标记为正式冻结。P2 轻微声调疑问可记录而不阻断，但标题、主命题和高频专名不适用该放宽。若用户在外部修改音频，先把那份实际文件复制到稳定项目路径、重新做全文词级审计并更新 SHA，再重建字幕与时间合同。

调用 `jianying-dubbing-postproduction` 或离线 SRT 流程修字幕。最终字幕必须：

- 与 canonical 文本逐字覆盖且顺序一致；
- 没有标点独占行、孤立闭引号、相邻重复或无意义碎片；
- 句末不留 `，。；：,.;:`，保留 `？！?!`；
- 只调整语义断句和展示，不改写已经录制的口播；
- 时钟与最终修音母版的差异在项目容差内。

一旦用户给出“最终版字幕”，它立即成为唯一字幕权威。工程对齐字幕、旧 canonical SRT 和 ASR 字幕只能作为历史，不能再驱动 A/B/C 或 BGM。所有下游必须绑定这一个 SRT SHA、cue count 和最终帧；禁止同时维护“工程时间字幕”和“交付字幕”两条有效时间轴。

## 3. 决定 A/B/C 轨

读取 [track-architecture.md](references/track-architecture.md)，先写一页轨道方案再搜素材。

正式选镜前按章节冻结素材覆盖矩阵：CG/PV钩子候选、任务录屏、至冬环境、人物身份镜头、关键原文证据和结尾回扣都要有来源与缺口状态。素材未覆盖时先补索引、补录或精确下载，不在逐句配画中反复消耗同一小段素材。系列项目同时维护跨期 `visual_family_id` 复用台账；同一视频不同秒点不天然等于新素材。

- **A轨**：默认连续全屏叙事画面，承担人物、行动、地点和情绪。
- **B轨**：只在需要证明、比较或解释时出现，包括原文页、圣遗物/书籍、解释卡、流程图和人物剪影。
- **C轨**：只承担少量持续象征、气氛或空间提示；没有明确增益就不建。

前10秒固定采用高密度、与口播相关的 CG/PV-like 动态钩子：通常每秒一次有意义的视觉更新，10秒后立即回到正文节奏。文字页、菜单页和任意漂亮镜头不能替代钩子叙事。

## 4. A轨逐句配画

调用 `jianying-sentence-visual-matching`：冻结最终 SRT，建立完整录屏索引与候选池，按4–8秒语义单元检索，完成 selected 审阅和风险行 A/B/C 审阅，再进入 HyperFrames。

要求：

- 每个语义单元都有真实来源、精确 in/out、候选和匹配理由；
- 专名行从画面本身确认人物，不拿 OCR 中出现的名字当身份证明；
- 画面保持完整 UID、原比例和统一 contain/pad 规则；
- 菜单、档案、任务 HUD、黑白闪、明显倒序和非叙事性重复均需单列；
- 开头、结尾和用户点名区间必须连续播放审阅，不能只看三联帧。
- 每个单元标注 `direct`、`strong` 或 `support`；A轨 `direct+strong` 不得低于80%，A+B精确证据/直接/强匹配合计不得低于90%，并做章节级检查。

在任何正式全片渲染前做全局选择审计：精确范围复用、显著重叠、相邻同源、视觉家族、跨期冷却、章节来源集中度、黑场和钩子/结尾预算。机器方案只能标记为 `machine_proposed`。v3 的720p代理必须覆盖完整时间轴，并加入冻结口播以便按观众体验连续审阅；开头/中段/结尾摘录和静态联系表只能辅助定位，不能替代全片。代理存在或制作者自己标记 PASS，不算用户验收。

## 5. B/C轨审核与渲染

正式制作前生成审核包，至少包含：每项资产原图、使用时间、画面目的、来源、人物身份、是否含文字/水印、预计停留时间和草图。A、B 两份审核 manifest 再写入 `visuals/static_asset_review_bundle.json`，由用户对该 bundle 的 SHA 作 `static_asset_review`。审核版与观众版分离；观众版不得残留内部编号、审核说明、证据边界、URL 或制作页脚。黄色框和 UID 遮挡按源图坐标及 contain/pad 变换计算，不靠目测。剪影必须基于已确认的人物原图或用户批准的象征性轮廓；官方角色不得凭空生成脸。

页面停留以读完和看懂为准。相邻证据页默认硬切或有画面重叠，不允许前一页淡出和后一页淡入同时落到透明/绿底，造成一两帧闪屏。下游透明素材显示为黑色时，输出纯绿幕版本并保留透明工程；绿幕必须是整轨背景策略，不是把单个人物资产换成绿色方块。

B/C轨必须绑定与A轨相同的最终 SRT、fps 和 `target_frame_count`。允许审核包使用临时长度；正式母版不得仍停留在旧口播帧数，再依靠最终工程裁尾掩盖差异。

## 6. HyperFrames渲染

任何 A/B/C 动态母版先读取 [hyperframes-render-workflow.md](references/hyperframes-render-workflow.md)。默认采用低内存、单 worker、短代理、分块渲染和收据绑定。

硬门槛：

1. composition、HTML、资产、脚本和代理哈希进入输入指纹；
2. clip 时钟从整数帧边界统一量化，运行 `scripts/audit_hyperframes_boundaries.py`；
3. 先检查/预览受影响分块，再正式渲染；
4. 缓存复用必须校验输入指纹，不得只看尺寸、帧率和帧数；
5. 拼接收据绑定 render plan、全部 chunk 收据和输出 SHA；
6. 完整母版全解码，核对帧数、PTS、首尾、黑白事件和每个分块边界；
7. 人工逐页审阅边界联系表，并连续播放首10秒、末10秒和用户点名区间。

目标分辨率长渲染前必须同时满足：权威链无 `--allow-provisional` 通过、workflow v3 pre-render 审计通过、交付规格已锁定、全局复用/黑场审计通过、完整720p连续代理由用户在产物生成/展示后明确通过。技术压力样片、三段摘录和机器 QA 不能替代这些门禁；正式全片不得作为创意预览。

返修只重渲受影响块；如果生成器或全局时钟改变导致所有指纹失效，诚实重建全链，不伪装成局部复用。

## 7. BGM

读取 [audio-score-and-repair.md](references/audio-score-and-repair.md)，先从最终字幕划分章节，再选择一种来源模式：

- `local_library`：只使用配置音乐根目录内的本地音乐；
- `generated_score`：仅在用户明确要求或同意生成时使用，记录模型、提示词、版本和源文件哈希。

两种模式都允许有歌词，但必须审查歌词含义与口播重叠。不要整期只铺一条毫无变化的循环；至少按论证章节改变配器、能量、空间或主题。最终 BGM 总长、章节边界、淡入淡出、响度和旁白避让都绑定最终字幕与音频母版。

BGM试听合成必须使用 `authority_bundle.json` 指向的实际最终口播 SHA；禁止裁切旧母带到目标长度后宣称已经与用户修改音频对齐。

技术混音通过后，至少人工抽听钩子、最密集证据、情绪转折和结尾。用户实际听到的旁白+BGM试听混音必须以 `bgm_mix_review` 绑定 path/SHA；`human_audition_performed=false`、`human_status!=pass` 或没有对应批准时，不得把 BGM 写进 `CURRENT.json`。

## 8. 封面

读取 [cover-production.md](references/cover-production.md)。先冻结一句本期独有的点击承诺，再把参考图明确分成三种职责：人物身份/模型参考、镜头/姿态参考、渲染/风格参考。三种参考不能混为“有这几张图就行”，上一期构图只能作风格参考，不能自动继承为本期叙事镜头。

封面按以下顺序验收：精确主体采用正确资产路线；人物/武器/UI身份与几何正确；无字小图已能表达本期命题而非泛用对峙、救援或站桩；所有主体确实处在同一空间；最后才检查标题、装饰、缩略图和异常边缘线。需要平铺官方武器时直接使用官方图标/切图，不交给生成模型重画。用户明确授权生成角色/完整场景时，先做16:9无文字场景测试，身份与命题门禁通过后再排字；16:9通过后才制作4:3和3:4，每个画幅独立构图与验收。最终16:9成品必须以 `cover_review` 绑定用户实际看到的 path/SHA；批准后任何微调都要重新展示和批准。

## 9. 甲方返修

调用 `jianying-acceptance-polish`。把每条反馈转换成精确时间码、受影响轨道、最小修改和验收方法。

先诊断根因再改：所谓“闪过一帧”可能是转场透明度在切点同时归零，不一定是素材真的太短；红框错位要回到源图像素坐标和 contain 偏移，不靠目测反复试。修复后只审受影响点及其前后帧，再做完整母版的回归门禁。

## 10. 集成、交付与瘦身

真实剪映操作遵循模块 Skill 和 Harness。替换主画面时使用等长视频母版保护字幕、旁白和 BGM；稳定路径优先用普通文件或硬链接，不把 `/tmp` 或易断的符号链接作为长期工程依赖。

完成后先写根目录 `CURRENT.json`，只指向一份当前脚本、口播、字幕、画面母版、BGM母版和16:9封面；旧 PASS 标记为 `superseded`。再读取 [storage-lifecycle.md](references/storage-lifecycle.md)：先出磁盘清单和引用关系，再清理可再生代理、旧预览、失效分块与重复缓存。不要直接清理 `CloudDocs/session` 内部目录，也不要把 `~/Library/Caches` 整体删除。

## 质量门禁

任何一项失败都不得宣称完成：

- 核心研究命题具备游戏原文、现实原型/不适用说明、叙事功能、内部交叉验证和反证；全文中文/人格/朗读 QA 通过；
- `authority_bundle.json` 只指向一份脚本、一份独立实际最终口播和一份最终 SRT，所有正式下游绑定同一 revision；
- 配音逐段与实际最终母带均为零多读、零错读、零漏读；P1读音、专名热点、接缝、标点拓扑、整条连贯性和完整试听通过；随后相似度、覆盖、信号和修音检查通过；
- 最终 SRT 逐字覆盖 canonical 文本；
- A轨语义覆盖阈值、人物身份、完整 UID、视觉家族/跨期复用、全局黑场、完整720p连续代理的 artifact-bound 用户批准和正式交付规格通过；
- B/C轨资产审核通过，页面可读，没有闪底或误导性剪影；
- HyperFrames 整数帧、分块、拼接和全片 QA 通过；
- BGM 章节、来源、歌词、旁白可懂度与四处人工抽听通过；
- 封面精确主体资产路线、人物身份、武器几何、叙事镜头、同场景一致性、文字、边缘伪影与各画幅缩略图依次通过；
- 甲方反馈逐项有验收证据；
- 删除与瘦身只处理已确认可再生或可恢复内容。

## 模块路由

- `game-lore-script`：剧情证据、口播稿、标题和文字钩子。
- `voxcpm-batch-dubbing`：零多字/错字/漏字优先的配音生成、词级收据、相似度与修音母版。
- `jianying-dubbing-postproduction`：字幕时间轴、语义断句和 SRT 权威。
- `jianying-sentence-visual-matching`：A轨索引、候选、审核和画面母版。
- `jianying-zhangyanfa-style`：钩子、B/C轨视觉语法、字幕风格与封面。
- `jianying-acceptance-polish`：甲方反馈、局部返修和交付风险。
- `top-tier-narrative-editing`：参考作品、A/B测试和可迁移规则学习。

仅在对应阶段激活时读取该模块。总控负责顺序和交接，不重复定义模块内部算法。

## 版本契约

本套八个协作技能于 2026-08-14 升级为 workflow v2；2026-08-15 根据《原初之人》新增 v2.1；2026-08-17 根据《地原胚质与还原逆回》新增 v2.2。2026-08-21 根据前四期完整复盘升级为 workflow v3：artifact-bound 审批、研究反证矩阵、全文稿件 QA、配音字词/韵律双门、A/B语义覆盖阈值、跨期视觉家族复用、全长720p动态审核、BGM人工抽听、精确主体确定性封面路线和根目录 `CURRENT.json`。新项目读 [workflow-v3-production-contract.md](references/workflow-v3-production-contract.md)；旧项目按 [workflow-v2-compatibility.md](references/workflow-v2-compatibility.md) 恢复后再显式迁移。

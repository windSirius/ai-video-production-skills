---
name: zhangyanfa-video-production
description: Run Alan's complete “障眼法考据” production workflow from lore evidence and mission recordings through script, VoxCPM narration repair, canonical subtitles, A/B/C track planning, low-memory HyperFrames rendering, chapter-based BGM, source-faithful covers, client-review patches, Jianying integration, delivery QA, and recoverable storage cleanup. Use for 一条龙制作, 至冬考据系列, 游戏录屏解析, 配音修音, 修字幕, A轨逐句配画, B轨解释卡或剪影, CG开头钩子, BGM生成或选曲, 封面制作, HyperFrames分块渲染, 甲方返修, 文件夹瘦身, or continuing any verified phase of the same video project.
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

## 总体阶段

按需从最近的有效阶段继续：

`证据与录屏 → 文案 → 配音与修音 → 最终字幕 → 轨道方案 → A轨 → B/C轨 → BGM → 封面 → 剪映整合 → 甲方返修 → 交付与瘦身`

每个阶段都必须留下：输入权威、输出路径、SHA-256、状态、未决项和下一阶段接口。详细目录见 [output-contract.md](references/output-contract.md)。

## 不可妥协的规则

- 在真实剪映工程里操作前，读取并遵守 [harness.md](references/harness.md)；禁止触碰「试试剪映助手」或「剪映助手」。
- 新制作或修改的动态画面资产使用 HyperFrames；FFmpeg只做探测、技术代理、无损拼接辅助和 QA，不取代画面编排。
- 把整数帧作为唯一时钟。禁止分别四舍五入开始时间和持续时间；相邻 clip 必须共享同一个边界值。
- 默认保留完整16:9画幅与完整 UID。不得为了遮 UID 或统一构图而混用裁切版与完整画幅版。
- B轨、C轨和封面先给用户看审核包，再开始正式长渲染。用户已经逐项批准的资产可直接复用。
- 官方角色已有可靠形象时，禁止用生成模型重新画脸、重建建模或“补全”五官。使用官方图、用户图或原始帧做确定性合成。
- 不因“做得更多”自动提升质量。一个证据页足够时就延长停留，不再叠加第二张；返修遵循“宁少做，不多做”。
- 不删除原录屏、最终字幕、最终音频、已验收母版、工程脚本、清单、收据或 QA。任何实质删除都需用户明确授权；优先移动到可恢复备份或废纸篓。
- 明确区分 `generated`、`downloaded`、`imported`、`applied`、`project updated`、`saved`、`exported`。

## 1. 证据、录屏与文案

完整任务录屏先按 [game-recording-vision-analysis.md](references/game-recording-vision-analysis.md) 建立任务流程和证据索引。剧情考据文案调用 `game-lore-script`，只依据已提供材料、官方页面和可追溯证据写作。

文案交付时同时固定：

- 口播正文与 spoken SHA；
- 专名表、证据等级和待核验项；
- 章节与素材锚点；
- 前10秒钩子意图；
- 标题池与封面题眼。

## 2. 配音、修音与字幕

调用 `voxcpm-batch-dubbing` 生成配音。对本系列默认执行：分段覆盖、信号检查、ASR检查、相似度门槛、定向重做、稳定响度修复和最终母版绑定。用户要求相似度不低于0.90时，任何低于0.90的正式段都不得交付。

调用 `jianying-dubbing-postproduction` 或离线 SRT 流程修字幕。最终字幕必须：

- 与 canonical 文本逐字覆盖且顺序一致；
- 没有标点独占行、孤立闭引号、相邻重复或无意义碎片；
- 句末不留 `，。；：,.;:`，保留 `？！?!`；
- 只调整语义断句和展示，不改写已经录制的口播；
- 时钟与最终修音母版的差异在项目容差内。

一旦用户给出“最终版字幕”，它立即成为 A/B/C 轨、BGM 和封面节奏判断的时间权威。

## 3. 决定 A/B/C 轨

读取 [track-architecture.md](references/track-architecture.md)，先写一页轨道方案再搜素材。

- **A轨**：默认连续全屏叙事画面，承担人物、行动、地点和情绪。
- **B轨**：只在需要证明、比较或解释时出现，包括原文页、圣遗物/书籍、解释卡、流程图和人物剪影。
- **C轨**：只承担少量持续象征、气氛或空间提示；没有明确增益就不建。

前10秒可单独采用高密度 CG/PV 钩子：通常每秒一次有意义的视觉更新，10秒后立即回到正文节奏。钩子不是把任意漂亮镜头切成十段；每一秒都要对应当前口播。

## 4. A轨逐句配画

调用 `jianying-sentence-visual-matching`：冻结最终 SRT，建立完整录屏索引与候选池，按4–8秒语义单元检索，完成 selected 审阅和风险行 A/B/C 审阅，再进入 HyperFrames。

要求：

- 每个语义单元都有真实来源、精确 in/out、候选和匹配理由；
- 专名行从画面本身确认人物，不拿 OCR 中出现的名字当身份证明；
- 画面保持完整 UID、原比例和统一 contain/pad 规则；
- 菜单、档案、任务 HUD、黑白闪、明显倒序和非叙事性重复均需单列；
- 开头、结尾和用户点名区间必须连续播放审阅，不能只看三联帧。

## 5. B/C轨审核与渲染

正式制作前生成审核包，至少包含：每项资产原图、使用时间、画面目的、来源、人物身份、是否含文字/水印、预计停留时间和草图。剪影必须基于已确认的人物原图或用户批准的象征性轮廓；官方角色不得凭空生成脸。

页面停留以读完和看懂为准。相邻证据页默认硬切或有画面重叠，不允许前一页淡出和后一页淡入同时落到透明/绿底，造成一两帧闪屏。下游透明素材显示为黑色时，输出纯绿幕版本并保留透明工程；绿幕必须是整轨背景策略，不是把单个人物资产换成绿色方块。

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

返修只重渲受影响块；如果生成器或全局时钟改变导致所有指纹失效，诚实重建全链，不伪装成局部复用。

## 7. BGM

读取 [audio-score-and-repair.md](references/audio-score-and-repair.md)，先从最终字幕划分章节，再选择一种来源模式：

- `local_library`：只使用配置音乐根目录内的本地音乐；
- `generated_score`：仅在用户明确要求或同意生成时使用，记录模型、提示词、版本和源文件哈希。

两种模式都允许有歌词，但必须审查歌词含义与口播重叠。不要整期只铺一条毫无变化的循环；至少按论证章节改变配器、能量、空间或主题。最终 BGM 总长、章节边界、淡入淡出、响度和旁白避让都绑定最终字幕与音频母版。

## 8. 封面

读取 [cover-production.md](references/cover-production.md)。先确定题眼和一眼能认出的主体，再分别排16:9、4:3和3:4；不得把一个画幅机械裁成另外两个。

封面硬门槛：人物/道具使用源图确定性合成；文字由本地字体排版；缩略图尺寸可读；来源与输出逐项对照；角色脸、手、标志物或官方模型出现重绘、变形、错位时直接失败，不得以“风格化”为理由放行。

## 9. 甲方返修

调用 `jianying-acceptance-polish`。把每条反馈转换成精确时间码、受影响轨道、最小修改和验收方法。

先诊断根因再改：所谓“闪过一帧”可能是转场透明度在切点同时归零，不一定是素材真的太短；红框错位要回到源图像素坐标和 contain 偏移，不靠目测反复试。修复后只审受影响点及其前后帧，再做完整母版的回归门禁。

## 10. 集成、交付与瘦身

真实剪映操作遵循模块 Skill 和 Harness。替换主画面时使用等长视频母版保护字幕、旁白和 BGM；稳定路径优先用普通文件或硬链接，不把 `/tmp` 或易断的符号链接作为长期工程依赖。

完成后读取 [storage-lifecycle.md](references/storage-lifecycle.md)：先出磁盘清单和引用关系，再清理可再生代理、旧预览、失效分块与重复缓存。不要直接清理 `CloudDocs/session` 内部目录，也不要把 `~/Library/Caches` 整体删除。

## 质量门禁

任何一项失败都不得宣称完成：

- 文案证据、专名和版本权威明确；
- 配音相似度、覆盖、信号和修音检查通过；
- 最终 SRT 逐字覆盖 canonical 文本；
- A轨语义、人物身份、完整 UID、开头和结尾通过；
- B/C轨资产审核通过，页面可读，没有闪底或误导性剪影；
- HyperFrames 整数帧、分块、拼接和全片 QA 通过；
- BGM 章节、来源、歌词与旁白可懂度通过；
- 封面源图保真和缩略图通过；
- 甲方反馈逐项有验收证据；
- 删除与瘦身只处理已确认可再生或可恢复内容。

## 模块路由

- `game-lore-script`：剧情证据、口播稿、标题和文字钩子。
- `voxcpm-batch-dubbing`：配音生成、相似度与修音母版。
- `jianying-dubbing-postproduction`：字幕时间轴、语义断句和 SRT 权威。
- `jianying-sentence-visual-matching`：A轨索引、候选、审核和画面母版。
- `jianying-zhangyanfa-style`：钩子、B/C轨视觉语法、字幕风格与封面。
- `jianying-acceptance-polish`：甲方反馈、局部返修和交付风险。
- `top-tier-narrative-editing`：参考作品、A/B测试和可迁移规则学习。

仅在对应阶段激活时读取该模块。总控负责顺序和交接，不重复定义模块内部算法。

## 版本契约

本套八个协作技能于 2026-08-14 依据四期至冬视频的完整制作、返修和验收记录升级为 workflow v2。执行新项目或接续旧项目时，先按 [workflow-v2-compatibility.md](references/workflow-v2-compatibility.md) 确认权威链、兼容策略、回归门禁与恢复边界。

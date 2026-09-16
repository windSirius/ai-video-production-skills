---
name: voxcpm-batch-dubbing
description: "用本地 VoxCPM/VoxCPM2 生成并修复长篇旁白母带：保持正典文字与发音代理分离，逐段生成和校验，重新审计任何被修改的音频，并执行 machine_verified → awaiting_human_audition → released 的发布状态机。用于批量配音、局部重配和旁白母带；不负责字幕、配画或视频渲染。"
---

# VoxCPM 批量配音

输入是已批准稿件，输出是一条经机器检查和完整人工试听共同批准的旁白母带。机器能找出许多词面和信号问题，却不能替人确认整篇听感。

## 工作路径

先读取本期 `workspace_paths.json`，遵守[统一目录与素材规范](../zhangyanfa-video-production/references/workspace-layout.md)。模型生成 attempts 和中间拼接放 `cache:voice/vNNN`；接受片段、最终母带、QA与试听发布记录放 `voice/vNNN`。不可让最终母带只留在“缓存”目录。 所有新版本先分配目录，再写文件；不自行发明另一套阶段路径。旧期 `legacy_indexed` 工作台用于导航，不视作新生产目录或新的审批权威。

## 前置条件与边界

只接受 `script_manifest.json` 当前绑定的 `口播纯文本.md`。核对稿件 SHA 后再切段；标题、画面锚点、Markdown 和制作旁注不得进入合成文本。

本技能不生成 SRT，不修改正典专名，也不处理视频轨道。操作 VoxCPM 页面时读取 [references/voxcpm-adapter.md](references/voxcpm-adapter.md)；发生发音代理、拼接、修复或版本冲突时读取 [references/authority-and-release.md](references/authority-and-release.md)。

### 狐久固定声线参考

狐久的视频配音始终使用用户指定的 `~/Desktop/无量塔.WAV`，或与该原件 SHA-256 完全相同的副本；参考文字必须逐字使用 [固定参考记录](references/foxjiu-voice-reference.json) 的 `transcript`。这是用户明确锁定的长期要求，只有用户再次明确更换参考才能修改。不得自行改用往期母带、其他声线、裁剪片段或重写参考文字。原件暂不可读时仅允许使用校验一致的副本；否则停止生成并说明缺失，不能自动替代。

每次启动生成（包括续作、返修和监控任务）先执行 `scripts/verify_voice_reference.py --source-manifest SOURCE_MANIFEST`。校验当前参考音频、prompt/reference 两个音频输入及参考文字；任何不一致都在加载模型前失败。项目记录参考来源、原件 SHA 和当前副本 SHA。

## 文本权威

- `canonical_text`：观众应当听到、字幕应当显示的文字；
- `generation_text`：只为解决合成读音而存在的临时代理；
- ASR：诊断证据，不得反向改写正典文字；
- approved alias：只能来自绑定当前 canonical/ASR SHA 的 `asr_alias_evidence_v1` 收据；每条必须记录第二识别器或定点人工试听证据、审核人和结论，不接受自由替换 map，也不等于允许音频读错。

## 发布状态机

状态只能按顺序前进：

```text
generating → machine_verified → awaiting_human_audition → released
```

失败进入 `repair_required`，修复后从机器检查重新开始。`machine_verified` 不等于可交付；`awaiting_human_audition` 时必须写 `release_ready=false`。

## 工作流

### 1. 切段与生成

批量生成前先做开头试配，使用正式生成块长度与同一模型配置，实际听开头断句、停顿、专名与语气；专名热点可增加短样段。默认不新增用户审批关卡，由制作方先完成试听并保留实际音频与备注；用户主动要求试听时按其要求处理。试配不通过先局部修复，不能把问题复制到整篇。

生成输入保存为不可变 `source_manifest`，与持续写入的 attempts 日志分开。参考预检通过才可加载模型做试配；整批启动前必须执行 `scripts/verify_voice_reference.py --source-manifest INPUT --phase bulk --smoke-review REVIEW --output-json PREFLIGHT`。`voice_opening_smoke_v2` 的字段见 [v2 契约](../zhangyanfa-video-production/references/submission-contracts-v2.md)。缺少实际试音、绑定失效或停顿审听未完成即失败。参考、正典或生成配置变化后重新试配；续作仍须重跑预检，不能沿用文件名判断。

区分正典单元与实际送入模型的生成块：正典单元保留逐句证据和定位，生成块可以按顺序打包多个相邻正典单元。VoxCPM2 默认以约 150 个可发音字符为一个生成块，优先落在 120–180；不要默认逐句或按短句生成，因为过短输入容易降低音色、韵律和连续性。专名密集、说话人切换、引用边界或定点返修可以有理由地缩短，但低于 100 个可发音字符应告警，低于 60 应视为 very-short 例外；不得为凑长度增删、重复或改写正典文字。需要规划或审核生成块时运行 `scripts/plan_generation_blocks.py`，并读取 [VoxCPM Gradio 适配](references/voxcpm-adapter.md) 中的长度和边界规则。

按合法语义边界切分或打包，并证明所有非空白正典恰好覆盖一次；source span 之间只能跳过纯空白分隔符，且必须把每个 gap 的原文、span 和 SHA 写入计划，任何非空白遗漏或重叠都应失败。每次生成先保存不可变 attempt，再替换 Target Text；不得覆盖已接受文件。

每个候选按以下顺序选择：词面与顺序、尾字和接缝、信号完整、专名读音，最后才是音色、情绪和自然度。ASR 出现同音字或专名差异时，用第二识别器或定点人工试听裁决，不得扩大 alias 强行通过。

### 2. 修复与母带

冻结参考与试配通过后，优先同一模型会话顺序生成完整批次；不为每块反复重载模型。先记录冷启动、模型加载、逐块生成、重试和 QA 各自耗时，再判断瓶颈。只有显存/内存压力或实际失败才重启会话；低内存不通过任意降低模型质量、缩短成碎句或跳过 QA 实现。返修只重做受影响块与相邻接缝，并保存不可变尝试。

只修已经证实的点击、异常静音、削波、响度或错误片段。按顺序拼接，不拉伸语速。任何再生成、拼接、淡化、标准化或修复都会产生新文件，使旧 SHA、词面收据和试听批准失效。

对实际最终母带执行：完整解码、时长与格式、响度和峰值、全文 ASR、零未解释插入/替换/删除、专名热点、每个接缝前后至少 1.5 秒的边界检查。相似度只能排序，不能覆盖词面错误。

### 3. 完整人工试听

机器 QA 必须绑定当前 canonical 与实际 master SHA；状态工具还会对实际 master 执行 ffprobe 和完整解码，不能只信收据里的 `full_decode=pass`。

机器通过后先写 `machine_verified`，再显式进入 `awaiting_human_audition`。用户或经用户授权的人必须以 1× 速度完整试听最终母带，检查漏字、多字、错字、专名读音、音色、情绪、语速、停顿、长静音和接缝。

人工批准必须先形成独立的 `human_audition_v1` 收据，绑定当前正典与母带 SHA，并明确 `complete_master_audition=true`、`full_speed_1x_audition=true`。状态工具只读取和核验该收据，不得根据命令参数自行制造“已完整试听”。任何后续变更都会使批准失效。只有机器检查全部通过、人工试听为 `approved` 且批准 SHA 与当前母带一致时，才能写 `released` 和 `release_ready=true`。

使用 `scripts/audio_release_state.py` 创建和推进状态；不要手改状态字段，也不要根据文件名里的 `final` 推断当前母带。

## 交付

向 v2 总控登记 `voice_release` 时附 `voice_submission_v2`，绑定实际母带、正典、开头试音和 bulk 预检。总控会重新核验参考与试音文件；完整用户 1× 试听仍由原发布链独立证明，不能从“开始下一步”或制作者开头试听推定。监控与共享重任务锁遵守 [总控 v2 硬流程](../zhangyanfa-video-production/references/submission-contracts-v2.md)。

- `segments.json`
- `audio/accepted/NN.wav`
- `narration_master.wav`
- `audio_qa.json`
- `audio_manifest.json`
- `voice_release.json`

下游 `subtitle-timeline` 只接受 `released` 且 SHA 匹配的母带。失败 attempts 可以保留在工作区，封存时移入历史目录，不能混入当前交付入口。

## 取消

用户要求停止时，先只读确认本次 VoxCPM 进程，再终止准确的进程并验证已经退出。保留已生成文件，不做清理。

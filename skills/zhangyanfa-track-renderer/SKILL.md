---
name: zhangyanfa-track-renderer
description: 将已批准的 A/B/C 计划和 BGM 安全地生成 720p 分轨与全长整合审核代理、2K60 分轨母版和最终成片，并在 macOS 上执行单工渲染监督、断点续作、最终音画 QA 和局部补丁。
---

# 障眼法轨道与成片渲染

这是渲染与整合模块，不替用户做选镜、选曲或封面判断。任何 HyperFrames 制作、检查或渲染先读取 `hyperframes` 入口 Skill，再按本模块冻结的权威与资源策略执行。

## 工作路径

先读取本期 `workspace_paths.json`，遵守[统一目录与素材规范](../zhangyanfa-video-production/references/workspace-layout.md)。审片文件放 `review/vNNN`，正式独立母版与QA放 `masters/vNNN`，交付清单和需要的整合片放 `delivery/vNNN`。chunk、浏览器缓存和临时转码写 `cache:render`；交付索引引用已验收母版，不额外复制一套。 所有新版本先分配目录，再写文件；不自行发明另一套阶段路径。旧期 `legacy_indexed` 工作台用于导航，不视作新生产目录或新的审批权威。

## 前提

- 本期所需 A/B/C 审批和 BGM 审批均绑定当前 SHA；
- 实际最终配音、最终 SRT、timing contract、轨道计划和资产均冻结；
- `assembly_mode=jianying|hyperframes` 已在初始化时确定；
- 本地非 iCloud scratch、磁盘保留值和恢复目录可用。

## 720p 审核

先按需生成 A 全长代理，以及包含全部 active ranges 与时间码的 B/C 分轨审核文件；用户要求全长分轨时生成完整时间轴版本。随后必须生成一条覆盖 `[0,target_frame_count)` 的全长整合代理，真实包含：

```text
A + B + C + 最终配音 + 最终字幕 + 已选BGM
```

整合代理必须使用正式时钟、边界、几何、字幕、自动化和转场，只降低空间分辨率或审片码率。用户对其 SHA 的明确通过与 `formal_render_authorization` 是两个事件；一句话同时明确二者时可以同时登记。

审核用字幕可以是可开关叠加层，不能因此默认烧入 A 母版。v2 按冻结 `delivery_mode`、`a_subtitle_baked`、`final_subtitle_baked` 和分轨音频政策生成；实际全长 BGM 必须绑定第八步所选试听。展示代理时明确下一步与输出规格；用户在这个上下文中回复“审核通过，进入下一步”可由总控记录两项事件，无须重复问同一授权。

启动任何正式 A/B/C 渲染命令前必须运行 `scripts/formal_render_preflight.py --project-root PROJECT`。它要求 `CURRENT.current_stage=10_formal_render`，当前 `integrated_proxy_720` 文件/SHA 与其 artifact-bound approval 一致，并在审批账中找到绑定同一 proxy SHA、当前 authority revision 和用户原话的 `formal_render_authorization`。preflight 非 PASS 时不得调用 supervisor。

v2 preflight 还会重新核对实际稿件/声音/素材/A 轨审查证据、整片复用、固定 WebUI、BGM 派生链和冻结交付规格；禁止用项目私有 adapter 返回空错误绕过。旧收据里的 PASS 不能证明被改过的输入仍通过。

## 2K60 安全渲染

读取 [macos-safe-rendering.md](references/macos-safe-rendering.md)。正式分轨严格按 `A → B → C` 串行，全局仅允许一个渲染进程和一个 worker。优先使用本地 staging、低内存模式、VideoToolbox 和按真实编辑边界分块；每个完成块都有输入指纹、输出 SHA、完整解码与边界收据。

监督器使用 `caffeinate` 防休眠并记录内存、swap、`memory_pressure`、磁盘余量、热状态、进程活性与帧进度。出现严重压力、磁盘越线、热状态异常或长时间无进展时，终止当前进程组，保留已通过块，冷却后缩短分块并从最后有效收据继续。禁止并行渲染另一轨来“节省时间”。

## B/C 输出

B/C 的 fps 与目标帧数必须等于 A 轨权威。使用 alpha 还是全帧纯绿在轨道计划中冻结；不得把局部绿色矩形塞进透明素材。每页可读时间、每个边界 `-1/0/+1` 和真实 key/alpha 模式都要验收。

## 最终整合与 QA

正式 A/B/C 母版通过后按交付模式执行：`integrated` 生成最终成片；`independent_tracks` 保留无旁白/BGM/B/C 叠加的独立 A、独立 B/C、旁白、BGM、SRT 和时钟，生成 `independent_delivery_v2` 清单及 QA；`both` 交付两者。禁止为了总控封存而额外强制合并独立轨。读取 [final-master-qa.md](references/final-master-qa.md)，对实际交付模式至少检查：

- 完整解码、精确帧数、分辨率、fps、色彩和音频流；
- 首帧、尾帧、每个编辑/分块边界的 `-1/0/+1`；
- 黑闪、绿闪、透明闪、丢帧、重复帧和缓存错帧；
- B/C 在正确区间出现，最终观众成片无残余绿幕；
- 字幕、旁白和 BGM 同步，尾字尾音完整；
- 只有最终导出混音才测量 LUFS/TP；
- 最终文件 SHA 与 `CURRENT.json` 一致。

视觉对比必须先用已知正确的相同帧验证抽取链，再执行全片；基准与待测都使用相同明确的 RGB、色彩变换和无损 PNG/原始像素，禁止用 JPEG 色差误报后直接放宽阈值。保留全部必需采样点，按媒体文件合并解码/抽帧进程；完整解码等已通过检查只有文件 SHA、工具版本和配置都相同时才复用。详见 QA 参考；没有实测不得报告提速倍数。

## 局部返修

以已批准母版 SHA 为 base，只修改声明范围。未改块必须匹配旧 SHA；改动块完整解码并检查相邻边界；新整合成片重新做一次最终 QA。不得直接改派生 chunk 而不修改权威 composition 或计划。

## 脚本

- `scripts/audit_hyperframes_boundaries.py`：检查共享帧边界。
- `scripts/audit_final_master.py`：probe、完整解码与基础交付检查。
- `scripts/formal_render_preflight.py`：正式渲染前核对 CURRENT、整合 720 审批与独立正式渲染授权。
- `scripts/extract_feedback_frames.py`：提取反馈时间点附近精确帧。
- `scripts/safe_render_supervisor.py`：串行运行任务、监控资源并保存收据。

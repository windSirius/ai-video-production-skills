---
name: zhangyanfa-score-and-mix
description: 建立可检索的 BGM 曲库，检查跨期复用，并根据冻结旁白、字幕和论证节点设计不同配乐方案，完成选曲、避让与混音。用于曲库扩充、BGM 候选、章节配乐和全长母带；不生成配音、不修改字幕或视频画面。
---

# 障眼法 BGM 与混音

## 工作路径

先读取本期 `workspace_paths.json`，遵守[统一目录与素材规范](../zhangyanfa-video-production/references/workspace-layout.md)。试听候选、全长BGM及其派生/混音收据统一放 `tracks/vNNN/BGM`；制作阶段可以是第九步，但BGM的物理归属不随阶段切换。中间混音写本期本地缓存，登记的母带必须持久保存。 所有新版本先分配目录，再写文件；不自行发明另一套阶段路径。旧期 `legacy_indexed` 工作台用于导航，不视作新生产目录或新的审批权威。

## 前提与边界

只读取权威包中的实际最终配音、最终 SRT、fps 和目标帧数。manifest 的 `authority_bindings.narration` 与 `.srt` 必须各自绑定真实文件 path/SHA，不能只填 64 位字符串。配音内容、字幕文字或时间发生变化时，旧 BGM 章节、自动化、试听与审批全部失效。

本模块不生成或修复旁白，不修改字幕，不替视觉轨道做情绪补救。

## 章节计划

按本期实际论证节点划分钩子、设问、证据、反转、情绪回落与结尾。每章记录目标情绪、信息密度、能量、配器、是否有歌词、旁白避让点和切换理由。音乐切换服从论证节点，不跟随每个画面切点。

选择来源、歌词或具体混音策略时读取 [score-and-mix-policy.md](references/score-and-mix-policy.md)。

## 候选审核

- 新候选先执行[曲库发现与跨期去重](references/library-and-diversity.md)：读取共享曲库与真实选曲历史，按本期叙事需求选短名单，禁止把上一期固定歌单仅换标签后提交。既有已批准项目不追溯失效。
- 先检查原有曲目的评估覆盖；文件索引不等于已评估。用户要求整库盘点时，每首都有实际音频检查、用途或待核问题及可播放试听，不把未评估写成不适合。未曾进入候选的旧收藏同样属于新选择，无需重新下载才算新曲。
- 默认先比较 12 首不同作品，再形成四套方向；四套主曲至少三首未进入最近三期候选，近三期实际选中过的主曲最多保留一首。题材需要回归主题时写明理由，可调整编辑默认值，不要求用户额外批准技术去重。
- 文件 SHA 只判断字节身份；同曲裁切、循环、转码、去旋律版仍属于同一 `composition_id`，不能充当多个不同方向。配器/节奏/叙事作用都要写清，不能只改“悬疑”“古老”等名称。
- 候选数量读取本期冻结的 house style；默认提供 A–D 四套方向。
- 所有候选使用同一段冻结旁白、同一试听范围和可比较电平。
- A–D 试听音频必须有互不相同的实际 SHA；仅换方向标签不算候选。
- 展示候选的情绪差异、章节适配与潜在遮蔽，不用文件名替代试听。
- 用户选择具体候选 ID 后，才制作全长 BGM master。

提交试听前运行 `audit_bgm_diversity.py`，用实际试听 manifest 的源曲 SHA 复核发现计划，保存输入绑定与结果。这个检查不替代真实试听、来源核对或艺术判断。固定审核 WebUI 只补充曲名、配器差异、近期使用情况和章节作用，不另换界面框架。

审批事件固定为 `bgm_review`，其 artifact path/SHA 必须和所选候选的 `approved_audition_mix` 完全一致。A/B/C 通过或整合代理通过不能代替 BGM 独立审批。

v2 总控的第八步登记并批准 `bgm_review`；第九步才登记 `bgm_master`，随附 `bgm_derivation_v2`，绑定已选试听、全长母带、旁白、SRT 和帧契约，并核验 candidate ID、章节覆盖及旁白可懂度。全长母带进入实际 720p 整合代理接受整片审看，不再额外要求一次同内容选曲确认。字段见 [v2 契约](../zhangyanfa-video-production/references/submission-contracts-v2.md)。冻结 v1 的旧项目按其既有角色继续，不改历史审批。

试听时说明各方向怎样服务本期论证：哪里让证据清楚、哪里推动反转、哪里留白。仅用“史诗/悬疑/抒情”标签或四段不相关音乐不能完成候选设计。用户一句话同时批准 A/B/C 并选择 BGM 时，原话和各实际文件一次登记，不重复询问。

## 来源与歌词

明确区分 `local_library` 与 `generated_score`，记录源文件、授权、原始 SHA 和派生文件。歌词必须审查含义、叙事冲突与旁白可懂度；来源在本地不等于拥有发布权限。

原有用户音乐原位索引，不为建库再复制。新获取曲目进入统一原始素材库，保存作者下载页、许可及署名文本；曲库标注获取来源，进入制作 manifest 后仍遵循既定 `source_mode`。先下载有明确用途的一批，不抓整站、不常驻存放全曲 WAV。来源说明推导的配器、情绪标签须标明待实际试听确认，不能写成人工通过。

## 混音

- 旁白始终居前；专名、直接引文、核心证据与结论处额外 duck。
- house style 中的旁白/BGM电平只是起点，不是验收结论。
- `sections` 从 0 开始无缝覆盖到 `target_frame_count`，每段绑定所选 candidate；全长 master 与目标帧时钟一致，检查头尾、循环、章节边界和自动化。
- 只有最终导出混音经过测量后，才能报告 integrated LUFS 和 true peak。
- 章节允许使用多首同一方向的曲目，所用曲目必须已经包含在该方案试听与来源清单中；选定单曲后不能偷偷加入新曲。完整篇幅也可保留一首合适的主曲，但需解释循环与情绪推进，不能默认整篇机械平铺。

## 输出

```text
tracks/vNNN/BGM/
  catalog_snapshot.json + history_snapshot.json
  bgm_discovery.json + bgm_diversity_audit.json
  bgm_chapters.json + bgm_candidates/
  bgm_review_manifest.json + bgm_manifest.json
  bgm_master.wav + mix_qa.json
```

这里的 `tracks` 是 resolver 的逻辑 kind，实际目录由本期路径契约给出；旧项目的 `audio/` 位置不迁移。

## 脚本

- `scripts/audit_bgm_manifest.py`：校验来源模式、权威绑定、章节覆盖、候选选择和审批。
- `scripts/index_bgm_library.py`：只索引显式目录/文件，以真实 SHA 去重，不搬迁或复制原曲。
- `scripts/audit_bgm_diversity.py`：按作品身份检查短名单、近期复用、配器差异，并核对实际试听源曲。

# AI Video Production Skills

[![Validate skills](https://github.com/windSirius/ai-video-production-skills/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/windSirius/ai-video-production-skills/actions/workflows/validate-skills.yml)

可复用的游戏剧情视频制作 Skill：从研究与口播稿，到固定声线配音、字幕、逐句 A/B/C 配画、BGM、2K60 分轨、六稿封面和交付封存。总控记录实际文件、SHA-256、展示和审批，专用模块分别实现各阶段。

这是供代理使用的工作流、检查器与模板集合。配音引擎、模型、原片、音乐、图像生成服务、HyperFrames 和剪映需按阶段另行准备；克隆仓库不会自动安装这些生产环境。

[安装与首次运行](INSTALL.md) · [依赖与平台支持](DEPENDENCIES.md) · [更新记录](CHANGELOG.md) · [开发约定](CONTRIBUTING.md)

## 当前生产模块

```text
skills/
├── zhangyanfa-video-production/  # 十三阶段总控、产物审批、失效传播、统一工作目录
├── game-lore-script/             # 证据链、反证、作者语言和冻结口播稿
├── game-footage-ingest-index/    # 下载验证、来源登记、OCR/ASR、镜头与人物索引
├── voxcpm-batch-dubbing/         # 固定声线、开头试配、分段生成与母带释放
├── subtitle-timeline/            # 用户最终时间轴、语义断句、整数帧契约
├── zhangyanfa-track-design/      # A/B/C 逐字幕配画、固定审核 UI、全片复用检查
├── zhangyanfa-score-and-mix/     # BGM 候选、选择绑定、旁白避让与全长混音
├── zhangyanfa-track-renderer/    # 720p 审片、单工 2K60 渲染、断点恢复和 QA
└── zhangyanfa-cover-production/ # 六个不同封面方案及选定后的多画幅制作
```

从 `zhangyanfa-video-production` 进入。已有项目先运行：

```bash
python3 skills/zhangyanfa-video-production/scripts/workflow.py status --root PROJECT_ROOT
```

新项目采用 v2 提交契约与固定目录。项目内保存已接受产物、来源和审批；永久原片进入素材库；下载分块、尝试音频、转码和全量抽帧进入按 `episode_key` 隔离的本地缓存。每个模块使用 `workspace_paths.json` 取得实际路径，不根据“最终版”或修改时间猜测权威。

本地工作根统一为 `~/Documents/视频工作区`，素材与按期缓存实际集中存放；iCloud 项目和交付通过同一入口访问。经授权迁移的旧绝对路径保留兼容链接，冻结契约不因搬迁重写。配置本机 `storage_roots.json` 后，路径解析会阻断断链和新增散落目录；使用 `audit_storage_layout.py` 可独立复查。

模块清单以 [skill_catalog.json](skill_catalog.json) 为准，安装器和结构检查共用这一份清单。完整流程安装九个生产模块；按阶段才加载对应模块的详细说明。

## 生产约定

- 冻结作者语言和证据审校，明确预测、反证与正典的边界。
- 狐久声线核对固定参考音频 SHA 和准确参考文字；批量配音前核验真实开头试配，母带仍需完整人工试听。
- 所有轨道读取同一份最终字幕和帧时钟；删段决定统一传播，未变化的产物保留已有批准。
- 使用固定 `review-ui-v1` 审核框架，按版本隔离候选和选择；开头用具有叙事关系的不同 CG 镜头，全片按实际镜头和源区间检查复用。
- 狐久默认交付独立 A/B/C、独立旁白和 BGM，A 不烧入口播字幕；整合片按实际交付要求生成。
- 正式渲染使用共享工作锁、非 iCloud 缓存、可验证的恢复收据和增量检查；生成不代表审批通过。
- 封面先制作六个不同方案，选定后分别完成 16:9、4:3、3:4；封存不自动删除缓存或云端文件。

准确的阶段门禁见 [总控 Skill](skills/zhangyanfa-video-production/SKILL.md)、[v2 提交契约](skills/zhangyanfa-video-production/references/submission-contracts-v2.md) 和 [统一工作目录](skills/zhangyanfa-video-production/references/workspace-layout.md)。

## 旧项目兼容

仓库继续保留 `jianying-dubbing-postproduction`、`jianying-sentence-visual-matching`、`jianying-zhangyanfa-style`、`jianying-acceptance-polish` 和 `top-tier-narrative-editing`，以及它们使用的早期 Harness 工具。前四个用于既有剪映工作流，最后一个是可选的叙事剪辑学习模块。已有 `run_manifest.json` 工程按原契约核验，迁移见 [旧项目迁移](skills/zhangyanfa-video-production/references/legacy-migration.md)。新项目由 `workflow.py` 管理，不同时启动两套状态机。旧文档中的 workflow v2/v2.2 与当前 `production_contract_version=2` 不是同一套版本编号。

## 安装与本机配置

以下命令在 macOS 或 Linux 的终端中执行。先按 [依赖说明](DEPENDENCIES.md) 准备 Python 3.11–3.14 与 FFmpeg：

```bash
git clone https://github.com/windSirius/ai-video-production-skills.git
cd ai-video-production-skills
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python tools/doctor.py

# 默认只预览；确认目标后用下一条命令执行。
python tools/install_skills.py
python tools/install_skills.py --apply
```

默认复制九个生产模块到 `~/.agents/skills`，这是当前官方文档中的用户级发现目录。安装器拒绝覆盖同名目录或链接；更新、软链接开发和已有 `~/.codex/skills` 环境的处理见 [安装指南](INSTALL.md)。路径依据：[OpenAI Build skills](https://learn.chatgpt.com/docs/build-skills#where-to-save-skills)。

`config.example.env` 仅服务于旧模块，需手动 `source`，并非当前流程的通用配置。当前工作目录通过 `init --media-root --cache-root` 冻结；默认分别为 `~/Documents/视频工作区/02_素材库/00_原始素材库` 与 `~/Documents/视频工作区/03_制作缓存`。可复制运行的初始化例子见 [安装指南](INSTALL.md)。

狐久参考记录中的 `~/` 指当前用户主目录，参考校验器会展开路径，并输出实际文件绑定。仓库只包含经授权发布的参考规则，不附带私人音频；原件或备份必须通过相同 SHA 校验。缺少参考时不能用往期母带替代。其他作者需要独立、明确授权并测试的规则配置，不能以换路径的方式绕过狐久固定声线检查。

BGM 按冻结的 `source_mode` 审查：本地音乐库模式核对配置后的音乐根目录，明确授权的生成配乐模式核对生成来源；两者都须经试听、选定和最终混音检查。

## 开发与验证

常规协作按 [CONTRIBUTING.md](CONTRIBUTING.md) 使用分支和 Pull Request。代码、引用和测试放在所属模块，仓库级说明放在根目录。

```bash
python -m pip install -r requirements-dev.txt
python tools/check.py

# macOS：额外验证四份原生 Swift/Vision 辅助脚本。
python tools/check.py --swift
```

本地与 GitHub Actions 共用同一入口：环境检查 → 包结构、JSON/YAML、全仓库本地 Markdown 文件链接与审核框架哈希 → Python 编译 → CLI `--help` → 各模块独立回归测试 → diff 检查。每个测试目录独立运行，避免不同模块的同名 helper 互相污染。普通编译缓存不会误报；被强制加入 Git 的缓存和媒体仍会拦截。

CI 覆盖 Linux Python 3.11/3.14 与 macOS Python 3.14，macOS 额外检查 Swift。契约测试使用合成文件验证审批、哈希、失效和恢复逻辑，不代替真实模型推理、媒体 QA、视觉判断或人工试听。

## 运行依赖

| 层级 | 安装入口 | 用途 |
| --- | --- | --- |
| 基础 Python 工具 | [requirements.txt](requirements.txt) | Pillow；镜头联系表、图片尺寸核验 |
| 仓库开发与 CI | [requirements-dev.txt](requirements-dev.txt) | 基础依赖与 PyYAML；结构和数据校验 |
| 旧采集辅助工具 | [requirements-legacy.txt](requirements-legacy.txt) | 基础依赖与 certifi；可选的 HTTPS 证书包 |
| 系统与生产运行时 | [DEPENDENCIES.md](DEPENDENCIES.md) | FFmpeg、Swift/Vision、VoxCPM、可选 ASR、HyperFrames/编辑器 |

依赖范围用于限定已支持的大版本，不是模型环境的锁文件。正式制作另记录实际 Python、工具、模型与服务版本。安装器只复制 skill 源文件，不负责配置推理服务或自动安装第三方插件。

不提交密钥、私人声音、原始素材、模型权重、剪映工程或渲染产物。本机专有路径也不进入公共仓库；处理规范见 [SECURITY.md](SECURITY.md)。

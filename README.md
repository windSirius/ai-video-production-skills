# AI Video Production Skills

可复用的游戏剧情视频制作 Skill：从研究与口播稿，到固定声线配音、字幕、逐句 A/B/C 配画、BGM、2K60 分轨、六稿封面和交付封存。总控记录实际文件、SHA-256、展示和审批，专用模块分别实现各阶段。

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

## 本轮流程约定

- 冻结作者语言和证据审校，明确预测、反证与正典的边界。
- 狐久声线核对固定参考音频 SHA 和准确参考文字；批量配音前核验真实开头试配，母带仍需完整人工试听。
- 所有轨道读取同一份最终字幕和帧时钟；删段决定统一传播，未变化的产物保留已有批准。
- 使用固定 `review-ui-v1` 审核框架，按版本隔离候选和选择；开头用具有叙事关系的不同 CG 镜头，全片按实际镜头和源区间检查复用。
- 狐久默认交付独立 A/B/C、独立旁白和 BGM，A 不烧入口播字幕；整合片按实际交付要求生成。
- 正式渲染使用共享工作锁、非 iCloud 缓存、可验证的恢复收据和增量检查；生成不代表审批通过。
- 封面先制作六个不同方案，选定后分别完成 16:9、4:3、3:4；封存不自动删除缓存或云端文件。

准确的阶段门禁见 [总控 Skill](skills/zhangyanfa-video-production/SKILL.md)、[v2 提交契约](skills/zhangyanfa-video-production/references/submission-contracts-v2.md) 和 [统一工作目录](skills/zhangyanfa-video-production/references/workspace-layout.md)。

## 旧项目兼容

仓库继续保留 `jianying-dubbing-postproduction`、`jianying-sentence-visual-matching`、`jianying-zhangyanfa-style`、`jianying-acceptance-polish` 和 `top-tier-narrative-editing`，以及它们使用的早期 Harness 工具。已有剪映或 `run_manifest.json` 工程按原契约核验，迁移见 [旧项目迁移](skills/zhangyanfa-video-production/references/legacy-migration.md)。新项目由 `workflow.py` 管理，不同时启动两套状态机。

## 安装与本机配置

1. 克隆仓库，确保 `${CODEX_HOME:-$HOME/.codex}/skills` 已存在。
2. 将需要的 `skills/<skill-name>` 复制或软链接到该目录；完整流程应安装上列九个模块。
3. 已有同名 Skill 时先比较和备份；正式生产固定到已验证的提交。

`config.example.env` 保留旧模块的本机配置示例。新目录模块默认使用 `~/Documents/视频素材/00_原始素材库` 和 `~/Documents/视频制作缓存`，初始化可用 `--media-root`、`--cache-root` 指定实际位置，用户指定的原片路径优先。

狐久参考记录中的 `~/` 指当前用户主目录，生成实际来源清单时需展开为本机路径。仓库只包含参考规则，不附带私人音频；原件或备份必须通过相同 SHA 校验。其他作者使用自己的明确授权配置，不能以换路径的方式绕过固定声线检查。

BGM 按冻结的 `source_mode` 审查：本地音乐库模式核对配置后的音乐根目录，明确授权的生成配乐模式核对生成来源；两者都须经试听、选定和最终混音检查。

## 开发与验证

常规协作按 [CONTRIBUTING.md](CONTRIBUTING.md) 使用分支和 Pull Request。代码、引用和测试放在所属模块，仓库级说明放在根目录。

```bash
python3 -m pip install -r requirements.txt
python3 tools/validate_skills.py
python3 -m compileall -q skills
git diff --check

# 示例：测试总控与工作目录；其他模块使用各自 scripts 或 tests 目录。
python3 -m unittest discover -s skills/zhangyanfa-video-production/scripts -p 'test_*.py'
```

GitHub Actions 检查包结构、Python 编译、脚本入口，并分别运行各模块的回归测试。契约测试使用合成文件验证审批、哈希、失效和恢复逻辑，不代替真实媒体 QA 或人工试听。

## 运行依赖

- Python 3.11+、FFmpeg/FFprobe、Pillow。
- macOS、Apple Vision 与 Swift/Xcode Command Line Tools 用于原生 OCR/画面分析；契约测试不要求 macOS。
- 本地 VoxCPM/VoxCPM2；可选 FunASR/SenseVoice，模型与运行服务单独安装。
- 按实际阶段安装 HyperFrames、浏览器或桌面操作能力；旧剪映模块需要剪映专业版或 CapCut Desktop。

不提交密钥、私人声音、原始素材、模型权重、剪映工程或渲染产物。本机专有路径也不进入公共仓库。

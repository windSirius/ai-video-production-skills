# 依赖与平台支持

依赖按脚本实际 import、外部命令和人工操作分别列出。轻量工具环境与模型推理环境分开管理，基础安装不下载任何模型。本文的工具/依赖发布信息核对日期为 2026-09-16。

## 支持范围

| 环境 | 验证范围 | 限制 |
| --- | --- | --- |
| Linux，Python 3.11/3.14 | CI 全部 Python 回归、媒体合成测试、包和数据检查 | Apple Vision、macOS 资源监督与桌面编辑器不在此环境运行 |
| macOS，Python 3.14 | CI 同一套回归与四份 Swift 脚本 typecheck | 真实屏幕、OCR、模型推理和正式渲染仍需制作机器检查 |
| Python 3.12/3.13 | 支持的中间版本 | CI 测试最低和最高版本，不逐个覆盖 |
| Windows | 未验证 | 路径、POSIX 锁和 macOS 专用脚本不能据 Python 测试结果宣称可用 |

## Python 依赖

| 文件/库 | 版本范围 | 实际用途 |
| --- | --- | --- |
| `requirements.txt`：Pillow | `>=12.3.0,<13` | `build_shot_index.py`、旧候选联系表、封面尺寸和比例检查 |
| `requirements-dev.txt`：PyYAML | `>=6.0.3,<7`，并包含基础依赖 | 解析 Skill frontmatter、agents 元数据与仓库 YAML，拒绝重复键 |
| `requirements-legacy.txt`：certifi | `>=2026.7.22`，并包含基础依赖 | 旧 `fetch_bilibili_season.py` 的可选 CA 证书；没有时使用系统信任库 |
| FunASR | 由独立 ASR 环境固定 | 仅 `transcribe_sensevoice.py` 执行真实转写时延迟导入；`--help` 不加载它 |

Pillow 与 PyYAML 的范围限制了已验证的大版本；这不是逐平台精确锁文件。正式生产保存实际 `python -m pip freeze` 和工具版本到本期工具日志，不把私人环境导出提交到仓库。更新下限或大版本时，重跑全部媒体回归与 CI。发布信息来自 [Pillow](https://pypi.org/project/Pillow/)、[PyYAML](https://pypi.org/project/PyYAML/) 与 [certifi](https://pypi.org/project/certifi/)。

```bash
python -m pip install -r requirements-dev.txt
python -m pip check
python tools/doctor.py --dev
```

## 系统工具

| 工具 | 使用阶段 | 安装与验证 |
| --- | --- | --- |
| Git | 克隆、安装版本固定、开发检查 | `git --version`；不需要 GitHub 凭据运行测试 |
| FFmpeg + FFprobe | 片段探测、音频 QA、抽帧、封面差异与合成回归 | 两个命令都必须在 PATH；使用支持脚本所需过滤器和 `-fps_mode` 的构建，完整兼容性由 `check.py` 验证 |
| Xcode Command Line Tools / Swift / Apple Vision | macOS 原生 OCR 与镜头分析 | `xcode-select --install`；`python tools/doctor.py --dev --swift`，再运行 `check.py --swift` |
| macOS 资源工具 | 正式渲染监督 | `memory_pressure`、`caffeinate` 等由系统提供；Linux CI 不能替代真实 Mac 上的资源压力验证 |

macOS 已安装 Homebrew 时可用 `brew install ffmpeg`。Ubuntu/Debian 使用 `sudo apt-get update` 后执行 `sudo apt-get install ffmpeg`。FFmpeg 的过滤器、编码器和硬件加速取决于实际构建；`doctor.py` 只检查工具可执行，正式渲染仍要通过项目级 preflight 与压力样片。封面尺寸优先使用 Pillow，macOS `sips` 仅作备用。

## 按需生产环境

| 能力 | 如何准备 | 仓库提供什么 |
| --- | --- | --- |
| VoxCPM/VoxCPM2 配音 | 按 [OpenBMB/VoxCPM](https://github.com/OpenBMB/VoxCPM) 准备独立服务与模型，记录服务/模型版本；可复用用户已有的本地 Gradio/API | 分块、固定参考检查、字面审计、音频 QA 与发布状态；不捆绑推理引擎 |
| SenseVoice 转写 | 按 [FunASR](https://github.com/modelscope/FunASR) 配置独立环境，预先准备本地模型，通过 `--model` 显式传入 | 批量转写适配器；基础安装和测试不会加载模型 |
| 原片下载 | 按来源使用现有下载器、连接器或平台允许的方式，先查素材库并记录来源 | 来源/镜头/P0 覆盖检查；没有一个随仓库安装的通用视频下载服务 |
| HyperFrames | 另行安装可用的 HyperFrames CLI/skill、浏览器与对应执行环境；进入制作/渲染前读取其入口 skill | 渲染 preflight、监督、帧边界与最终母版 QA；不捆绑 HTML 渲染器 |
| 图像/封面生成 | 使用当前宿主提供且用户授权的图像能力或官方原始资产 | 六方案与画幅验收规则；不包含图像生成模型 |
| 旧剪映/CapCut 工程 | 安装桌面编辑器与所需操作能力；`pyJianYingDraft` 和本机学习工作区只在相应旧执行路径启用 | 兼容文档和检查器；未声明跨版本编辑器自动化保证 |

这些运行时不能因为 `pip install -r requirements.txt` 成功就视为就绪。语音栈的 Python、Torch、设备和模型要求以选定版本为准，勿把工具环境的 Python 3.14 直接当作推理引擎兼容性声明。`doctor.py` 不会启动它们，也不检查账户或密钥。

## 故障定位

- `ModuleNotFoundError: PIL`：检查执行脚本的 Python 是否是安装了 `requirements.txt` 的虚拟环境。
- 提示缺少 PyYAML：开发检查需要 `requirements-dev.txt`，纯使用文档不需要开发依赖。
- 缺少 FFmpeg/FFprobe：安装两个系统命令并重新检查 PATH；跳过媒体测试不能代替通过。
- Python HTTPS 证书失败：旧采集工具可安装 `requirements-legacy.txt`，或修复当前 Python 的证书信任；不要关闭 TLS 校验。
- 找不到模型/服务：确认独立运行时及实际版本，不能为通过 QA 用合成静音或另一声线替代。
- Skill 没出现或出现两个版本：检查安装路径与同名目录，参见 [INSTALL.md](INSTALL.md)。

# 安装、更新与首次运行

所有相对命令均从仓库根目录执行。生产模块共九个，完整列表在 [skill_catalog.json](skill_catalog.json)；五个兼容/可选模块仅在对应旧工程或学习任务中安装。仓库提供工作流指令和检查工具，模型、素材和制作服务另按 [DEPENDENCIES.md](DEPENDENCIES.md) 准备。

## 准备工具环境

使用 Python 3.11–3.14，创建独立虚拟环境，避免把开发依赖混入已有 VoxCPM/ASR 环境：

```bash
git clone https://github.com/windSirius/ai-video-production-skills.git
cd ai-video-production-skills
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python tools/doctor.py
```

`doctor.py` 检查 Python/Pillow 和 FFmpeg/FFprobe 是否可用，非零退出表示必要条件未满足。它不加载模型、不下载音频、不检查私人参考文件。开发者改装 `requirements-dev.txt` 并运行 `python tools/check.py`；依赖安装只在此虚拟环境生效，代理执行脚本时也须使用它的 Python。

## 安装九个生产模块

```bash
python tools/install_skills.py
python tools/install_skills.py --apply
```

第一条只预览，不创建目录；第二条按清单复制到 `~/.agents/skills`。这是 [OpenAI 官方文档](https://learn.chatgpt.com/docs/build-skills#where-to-save-skills) 规定的用户级本地 skill 目录。仓库级安装可以显式指定某个项目的 `.agents/skills`：

```bash
python tools/install_skills.py --destination /path/to/project/.agents/skills
python tools/install_skills.py --destination /path/to/project/.agents/skills --apply
```

安装器先检查整批目标；任何同名目录、普通文件或不同目标的链接都使安装失败，避免覆盖用户修改。它不会复制 Python 缓存或 `.DS_Store`，也不会执行模型安装。只需兼容模块时使用 `--set compatibility`；需要全部十四个模块时使用 `--set all`。已有剪映模块可能调用总控中的旧 Harness 辅助工具，因此兼容工程应同时保留总控模块。

本机如果已经从 `~/.codex/skills` 或自定义位置加载这些模块，先确认实际生效路径，再显式用 `--destination` 指向该位置。不要在两个发现目录安装同名的不同版本；官方说明同名 skill 不会自动合并。本仓库的安装器不会移动或清除现有安装。

确认新 skill 出现在宿主的 skill 列表后再使用；未刷新时重启宿主。在支持 `$` 调用的 Codex CLI/IDE 中，可用：

```text
$zhangyanfa-video-production 从当前项目状态继续制作。
```

## 更新与开发软链接

正式制作固定到已经验证的 Git 提交，保留 `git rev-parse HEAD` 的结果。先比较本地已安装版本的改动，备份到 **skill 发现目录之外**，再将旧目录移出发现目录并安装新版本；安装器不提供强制覆盖开关。备份放在同一个 skills 根目录的另一名称下，仍可能被发现为重复 skill。

已经批准的项目继续遵守其冻结契约；更新 skill 不等于改写旧项目的审批和权威。需要迁移时按 [旧项目迁移](skills/zhangyanfa-video-production/references/legacy-migration.md) 单独处理。

开发环境可用软链接，Git checkout 的改动会立即影响链接后的 skill：

```bash
python tools/install_skills.py --mode symlink
python tools/install_skills.py --mode symlink --apply
```

同一目标链接可重复运行；链接到其他位置、失效链接、已有副本都会报冲突。移动或删除仓库会破坏这些链接。复制安装不会随 `git pull` 自动更新。

## 新项目初始化

以下例子创建独立的示例项目。正式制作先按用户需求确定题目和格式；稳定 `episode_key` 不能拿来复用另一集的缓存。

```bash
python skills/zhangyanfa-video-production/scripts/workflow.py init \
  --root "$HOME/Documents/视频制作示例/01_示例主题" \
  --title '示例主题' --theme '验证工作目录与状态入口' \
  --width 2560 --height 1440 --fps 60 \
  --cut-policy per_caption_refresh --tracks A,B,C,BGM \
  --b-output-mode green --c-output-mode green \
  --assembly-tool hyperframes \
  --delivery-mode independent_tracks --a-subtitles exclude \
  --episode-key DEMO_EP001 \
  --media-root "$HOME/Documents/视频素材/00_原始素材库" \
  --cache-root "$HOME/Documents/视频制作缓存"

python skills/zhangyanfa-video-production/scripts/workflow.py status \
  --root "$HOME/Documents/视频制作示例/01_示例主题"

python skills/zhangyanfa-video-production/scripts/workspace_layout.py doctor \
  --root "$HOME/Documents/视频制作示例/01_示例主题"
```

`init` 只创建项目、冻结请求与路径并建立导航，不能产生稿件、配音、审批或渲染授权。打开项目里的 `00_开始这里.md`，各阶段产物按 `v001/v002` 保存。缓存根不能位于 iCloud，也不能与项目和原始素材库重叠。已有项目使用 `status`，不要再次 `init`；命令完整参数以 `--help` 为准。

## 本机配置与参考声音

新工作流的路径来自 `init` 参数和冻结后的 `workspace_paths.json`，没有自动读取 `.env` 的通用配置层。

旧模块确实需要环境变量时才执行：

```bash
cp config.example.env .env
# 编辑 .env 后再加载；脚本不会自动读取它。
source .env
```

`AI_VIDEO_MUSIC_ROOT` 由旧 Harness 脚本读取；`AI_VIDEO_MEDIA_ROOT` 与 `ZHANGYANFA_LEARNING_ROOT` 是旧编辑执行说明的约定，后者依赖未随仓库发布的本机学习工作区。已移除无人读取的 `AI_VIDEO_EDITOR_APP`，编辑器路径应在实际执行时定位。

狐久固定参考见 [参考规则](skills/voxcpm-batch-dubbing/references/foxjiu-voice-reference.json)。需要授权的原件或 SHA 一致的备份；仓库不提供音频。参考校验器接受 `~/` 路径，仍严格核对字节、准确文字与批量生成前的真实开头试配。不能从往期母带截音替代，也不能把规则里的 SHA 改成手边文件以通过检查。

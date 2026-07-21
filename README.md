# AI Video Production Skills

用于共同开发 AI 辅助视频生产流程的私有 Codex Skill 仓库。目标是把录屏分析、文稿交接、克隆配音、字幕后期、逐句配画、个人剪辑风格和验收修订拆成可独立验证、可恢复、可协作迭代的模块。

## 仓库结构

```text
skills/
├── zhangyanfa-video-production/       # 总控流程与客观验收
├── voxcpm-batch-dubbing/              # VoxCPM 批量克隆配音
├── jianying-dubbing-postproduction/   # 配音铺轨、文稿匹配与字幕整理
├── jianying-sentence-visual-matching/ # 逐句检索、评分与重建画面轨
├── jianying-zhangyanfa-style/         # “障眼法考据”个人风格 Profile
└── jianying-acceptance-polish/        # 甲方反馈、技术审计与交付前 QA
```

`zhangyanfa-video-production` 是总入口，其余目录是按阶段调用的独立 Skill。个人风格模块可以替换或扩展，不应与通用生产安全规则混在一起。

## 本地安装

1. 克隆本仓库。
2. 确保 `${CODEX_HOME:-$HOME/.codex}/skills` 已存在。
3. 将需要的 `skills/<skill-name>` 目录复制或软链接到该目录。
4. 若目标位置已有同名 Skill，先备份并比较差异，不要直接覆盖。

开发时推荐从仓库目录软链接，以便本地测试直接反映当前分支；正式使用前应固定到已通过评审的提交。

## 本机配置

复制 `config.example.env` 为 `.env`，再按各自机器修改。`.env` 不会被 Git 跟踪。

```bash
cp config.example.env .env
source .env
```

默认音乐目录为 `$HOME/Music`，剪映稳定媒体目录为 `$HOME/Movies/JianyingMedia`。所有 BGM 仍必须来自配置后的音乐根目录，不能从素材、下载或生成内容中绕过来源检查。

## 开发与验证

从短分支提交改动，通过 Pull Request 合并；不要直接在 `main` 上共同编辑。

```bash
python3 -m pip install -r requirements.txt
python3 tools/validate_skills.py
python3 -m compileall -q skills
```

每次修改应说明：改变了哪个生产阶段、为什么需要改变、如何验证、是否影响恢复机制或现有项目。新增或修改脚本必须运行代表性测试。

## 运行依赖

- macOS、Apple Vision 与 Swift/Xcode Command Line Tools（录屏分析模块）
- Python 3、FFmpeg/FFprobe、Pillow
- 剪映专业版或 CapCut Desktop
- 本地 VoxCPM/VoxCPM2 Gradio；可选 FunASR/SenseVoice
- Codex Browser 与 Computer Use；读取 PDF/DOCX 时还需相应文档能力

依赖不是仓库的一部分。不要提交模型权重、原始录屏、声音参考、剪映工程、导出视频或运行生成物。

## 协作约定

具体要求见 [CONTRIBUTING.md](CONTRIBUTING.md)。当前代码所有者为 `@windSirius` 与 `@chenserry09-collab`；两位协作者通过短分支和 Pull Request 交叉评审改动。

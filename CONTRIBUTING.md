# 协作开发约定

## 分支与 Pull Request

1. 从最新 `main` 创建短分支，使用 `feature/<主题>`、`fix/<主题>` 或 `docs/<主题>`。
2. 一次 PR 只解决一个清晰问题；不要混入运行生成物或无关格式化。
3. 在 PR 中写明变更阶段、动机、验证证据、兼容性和恢复影响。
4. 至少由另一位协作者评审后再合并。

维护者明确要求直接更新指定分支时遵循该次授权，仍完成下列检查并保留提交和 CI 证据。不能把一次分支授权推广为后续所有发布或媒体操作的授权。

## Skill 结构

- 每个 Skill 只在自己的目录中保留 `SKILL.md`、`agents/openai.yaml` 和确有用途的 `scripts/`、`references/`、`assets/`。
- `SKILL.md` YAML frontmatter 只能包含 `name` 和 `description`；目录名必须与 `name` 相同。
- 将触发条件完整写进 `description`；正文使用命令式说明核心流程。
- 保持 `SKILL.md` 精简，接近 500 行时把细节移到一层 `references/`。
- 不要在单个 Skill 目录里增加 README、安装指南、变更日志等仓库级文档。
- 修改 `SKILL.md` 后同步检查 `agents/openai.yaml`，其中 `default_prompt` 必须显式包含 `$skill-name`。
- 增减模块时同步更新 `skill_catalog.json`、README、安装/依赖说明和 Issue 模板；安装器从清单取包，校验器要求所有包恰好出现一次。
- 当前 `workflow.py` 与旧 Harness 的版本编号和审批不能混用。给历史文档增加明确适用范围，保留旧工程实际调用的脚本。
- `review-ui-v1` 是经批准的框架快照；普通文档或依赖更新不得修改其 HTML/CSS/JS。校验器核对 manifest 中的 SHA，不以重新写 SHA 的方式掩盖视觉变更。

## 安全与可恢复性

- 不得削弱“先备份、后变更、再验证”的时间线安全规则。
- 不得把“已生成”“已导入”“已应用到项目”“已导出”混为同一状态。
- 不得提交 API 密钥、访问令牌、私人声音、原始素材、客户数据、模型权重或剪映工程。
- 本机路径必须来自环境变量或 `$HOME` 默认值，不得新增 `/Users/<name>/...` 硬编码。
- 任何会导出、发布、上传、删除或覆盖不可恢复资产的行为，都必须保留明确授权边界。

## 环境与提交前检查

先按 [INSTALL.md](INSTALL.md) 创建虚拟环境；必需系统命令与模型环境的边界见 [DEPENDENCIES.md](DEPENDENCIES.md)。

```bash
python -m pip install -r requirements-dev.txt
python -m pip check
python tools/check.py

# macOS 原生脚本改动时：
python tools/check.py --swift
```

统一检查器执行环境/结构/数据/本地 Markdown 文件链接/固定 UI 哈希检查、隔离缓存编译、真实 CLI 的 `--help`、各模块独立 unittest 与 staged/unstaged diff 检查。它不会下载模型或外部媒体。`--swift` 在 macOS 上 typecheck 四份原生辅助脚本。

定位单个模块时可运行：

```bash
python -m unittest discover -s tools/tests -p 'test_*.py'
python -m unittest discover -s skills/zhangyanfa-video-production/scripts -p 'test_*.py'
```

不要在整个 `skills` 根目录递归混跑测试；不同模块存在同名 helper。编译后的未跟踪 `__pycache__` 被忽略，强制加入 Git 的缓存或媒体仍会被拒绝。结构检查覆盖 Git 已跟踪文件和新未忽略源码，不能代替完整的敏感数据扫描或外链可用性检查。

新工具使用临时目录和合成测试数据验证实际边界，特别是文件覆盖、安装冲突、审批失效与路径解析；不得访问真实制作项目或加载私人声音作为测试夹具。纯文档修订不必添加镜像测试。

CI 使用同一入口，在 Linux Python 3.11/3.14 和 macOS Python 3.14 上运行。更新 GitHub Actions 时从官方发布确认兼容性，固定完整 commit SHA 并注释版本；更新依赖时一起核对 `requirements*.txt`、`doctor.py`、本文档与 CI。提交前检查新增未跟踪文件，记录实际命令及通过/失败，不把机器测试写成人工审批或真实推理质量证明。

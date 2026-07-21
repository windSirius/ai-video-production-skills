# 协作开发约定

## 分支与 Pull Request

1. 从最新 `main` 创建短分支，使用 `feature/<主题>`、`fix/<主题>` 或 `docs/<主题>`。
2. 一次 PR 只解决一个清晰问题；不要混入运行生成物或无关格式化。
3. 在 PR 中写明变更阶段、动机、验证证据、兼容性和恢复影响。
4. 至少由另一位协作者评审后再合并。

## Skill 结构

- 每个 Skill 只在自己的目录中保留 `SKILL.md`、`agents/openai.yaml` 和确有用途的 `scripts/`、`references/`、`assets/`。
- `SKILL.md` YAML frontmatter 只能包含 `name` 和 `description`；目录名必须与 `name` 相同。
- 将触发条件完整写进 `description`；正文使用命令式说明核心流程。
- 保持 `SKILL.md` 精简，接近 500 行时把细节移到一层 `references/`。
- 不要在单个 Skill 目录里增加 README、安装指南、变更日志等仓库级文档。
- 修改 `SKILL.md` 后同步检查 `agents/openai.yaml`，其中 `default_prompt` 必须显式包含 `$skill-name`。

## 安全与可恢复性

- 不得削弱“先备份、后变更、再验证”的时间线安全规则。
- 不得把“已生成”“已导入”“已应用到项目”“已导出”混为同一状态。
- 不得提交 API 密钥、访问令牌、私人声音、原始素材、客户数据、模型权重或剪映工程。
- 本机路径必须来自环境变量或 `$HOME` 默认值，不得新增 `/Users/<name>/...` 硬编码。
- 任何会导出、发布、上传、删除或覆盖不可恢复资产的行为，都必须保留明确授权边界。

## 提交前检查

```bash
python3 -m pip install -r requirements.txt
python3 tools/validate_skills.py
python3 -m compileall -q skills
git diff --check
```

若修改了 Python 或 Swift 脚本，还要运行其 `--help`、最小样例或对应的可重复测试，并在 PR 中记录结果。

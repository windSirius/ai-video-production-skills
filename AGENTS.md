# Repository instructions

- Treat `skills/zhangyanfa-video-production` as the orchestration entrypoint and the other directories as independently testable modules.
- Preserve production safety, recoverability, explicit authorization boundaries, and objective verification when editing workflows.
- Keep Skill packages minimal. Put contributor documentation at the repository root, not inside `skills/*`.
- Keep `SKILL.md` frontmatter limited to `name` and `description`; keep trigger guidance in `description`.
- Load detailed references only when their phase is active, and keep references one level below each Skill.
- Never add secrets, private media, model weights, generated outputs, or user-specific `/Users/<name>` paths.
- Run `python3 tools/validate_skills.py`, `python3 -m compileall -q skills`, and relevant script tests before proposing a merge.

# Repository instructions

- Treat `skills/zhangyanfa-video-production` as the orchestration entrypoint and the other directories as independently testable modules.
- Preserve production safety, recoverability, explicit authorization boundaries, and objective verification when editing workflows.
- Keep Skill packages minimal. Put contributor documentation at the repository root, not inside `skills/*`.
- Keep `SKILL.md` frontmatter limited to `name` and `description`; keep trigger guidance in `description`.
- Load detailed references only when their phase is active, and keep references one level below each Skill.
- Never add secrets, private media, model weights, generated outputs, or user-specific `/Users/<name>` paths.
- Install `requirements-dev.txt` and run `python3 tools/check.py` before proposing a merge; on macOS, also use `--swift` when native helpers change. The shared runner includes source validation, compilation, entrypoint checks, isolated module tests, and diff checks.
- Keep `skill_catalog.json`, README module descriptions, dependency documentation, and issue templates consistent when adding or retiring a module.
- Distinguish current `workflow.py` contracts from the retained `run_manifest.json` Harness. Never reinterpret old approvals using the new state machine.

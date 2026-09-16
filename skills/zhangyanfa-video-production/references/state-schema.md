# 最小状态文件与命令

新项目默认 `zhangyanfa_video_v5` 与 `house_style.v2`。详细字段与有效例子见 [submission-contracts-v2.md](submission-contracts-v2.md)。以下旧基础字段继续存在；v1 项目保持冻结语义。

## 根目录

默认新项目同时生成 `workspace_paths.json`，其 path/SHA 写入冻结的 `request_contract.workspace_layout`。目录和模块路径见 [workspace-layout.md](workspace-layout.md)；`init --episode-key GI71_EP004` 可另外指定媒体库和本地缓存根。总控登记时检查角色所属目录及 vNNN 层，保存状态后更新自动导航。旧项目新增的 legacy 导航清单不改变原审批权威。

```text
CURRENT.json
request_contract.json
authority_bundle.json
deliverables.json
approvals/approval_ledger.jsonl
state/stages/
state/stages/history/
```

所有写入由`scripts/workflow.py`完成。不要手工修改状态文件；状态命令会检查`CURRENT.json`保存的请求契约、权威和交付清单 SHA，发现漂移后拒绝变更命令。

## `request_contract.json`

初始化时冻结项目ID、已确认的非占位标题与主题、交付规格、可选目标时长范围和完整 house style。它保留所用模板的 profile、schema 与 SHA，但项目运行期间绝不回读可变模板。需要改变剪镜、轨道或样式契约时，应明确失效相应阶段或另建项目，不能直接改写此文件。

## `CURRENT.json`

只保存路由信息：项目ID、标题、当前阶段、当前状态、下一步、阻塞项，以及`request_contract.json`、`authority_bundle.json`、审批账、`deliverables.json`和当前阶段收据的指针。

项目状态只有`active`、`blocked`、`sealed`。阶段状态只有`pending`、`in_progress`、`awaiting_user`、`complete`、`stale`。

## `authority_bundle.json`

只保存交付规格与当前`script`、`narration`、`subtitle`。三项状态只有`unbound`和`frozen`。任何一项冻结都必须指向当前文件SHA及审批ID。

`target_frame_count`在最终字幕阶段以前允许为空；第六阶段完成后必须为正整数。

v2 还冻结 `production_contract_version`、`delivery_mode`、A/成片字幕政策、`bgm_flow`、复用组/次数上限、开头秒数、A允许画面类型、固定声线SHA、固定收束语及审核UI manifest SHA。初始化可显式传 `--delivery-mode integrated|independent_tracks|both`、`--a-subtitles exclude|burn`、`--final-subtitles exclude|burn`；默认独立轨与无口播字幕。

## `deliverables.json`

`items`只保留每个角色的唯一当前文件；被替换或失效的条目进入`history`，不能继续参与门禁。每个当前条目记录path、SHA、阶段、客观状态、注册时间、注册时的权威绑定、最小元数据和可选审批ID。

## `approval_ledger.jsonl`

追加式记录人工批准。每条记录包含审批ID、阶段、角色、文件path/SHA、权威revision、产物注册时间、展示时间、决定时间、用户准确原话和批准范围。

`formal_render_authorization` 也追加到同一账本，但它不是第二次审批产物：它绑定已经批准的 `integrated_proxy_720` path/SHA、当前 authority revision 和用户明确的 2K/2K60/正式渲染授权原话。总控只通过 `authorize-render` 写入该事件。

v2 增加真实 `presentation` 文件绑定、`recorded_at`、可选逐字 `decision_clause`。用户决定时间可用 `--decided-at` 如实补录，不能反推或伪造。正式渲染授权还绑定 `delivery_spec_sha256`，接受原展示中已明确下一步的上下文批准。`new_full_1x_audition_claimed:false` 表示本账不制造试听事实；音频试听仍以独立实际人审收据为准。

旧记录永不改写。当前产物是否获批，由`deliverables.json`中的`approval_id`反向核对审批账。

## 阶段收据

每次`advance`生成`state/stages/STAGE.json`，记录当时的权威revision、输入绑定、输出角色与SHA、warnings和审批ID。失效时收据标为`stale`；再次完成前，旧收据移到`state/stages/history/`。

## 命令

初始化：

```bash
python3 scripts/workflow.py init --root PROJECT_ROOT --episode-key GI71_EP004 \
  --title TITLE --theme THEME --width 2560 --height 1440 --fps 60 \
  --target-duration-min-seconds 540 --target-duration-max-seconds 660 \
  --cut-policy per_caption_refresh --tracks A,B,C,BGM \
  --b-output-mode green --c-output-mode green --assembly-tool jianying
```

目标时长参数可省略；如提供，最短与最长秒数必须同时提供。精确十分钟应显式写成`600/600`，总控不会自行发明容差。

查询：

```bash
python3 scripts/workflow.py status --root PROJECT_ROOT
```

注册当前阶段产物：

```bash
python3 scripts/workflow.py register --root PROJECT_ROOT \
  --stage 03_script_build --role script --path PATH
```

`--meta-json`用于阶段门禁的少量结构化事实。它不能替代实际文件或人工审批。

第二阶段的两份产物必须非空，并分别提交带版本、计数、已审阅标志与`qa_pass`的最小 QA 元数据。第三阶段的`script`与`script_qa`必须非空；`script_qa.meta.script_sha256`必须等于总控登记的当前稿件 SHA，并带`qa_schema_version`、`qa_pass`及三项稿件检查结果。

审批：

```bash
python3 scripts/workflow.py approve --root PROJECT_ROOT \
  --role script --shown-at 2026-08-30T08:00:00+12:00 \
  --presentation approvals/presentations/script_v001.json \
  --quote '审批通过' --scope '当前稿件'
```

正式渲染授权：

```bash
python3 scripts/workflow.py authorize-render --root PROJECT_ROOT \
  --shown-at 2026-08-30T08:00:00+12:00 \
  --presentation approvals/presentations/proxy_v001.json \
  --quote '现在可以进入2K60正式渲染' \
  --scope '当前720整合代理对应的正式分轨渲染'
```

推进：

```bash
python3 scripts/workflow.py advance --root PROJECT_ROOT
```

失效：

```bash
python3 scripts/workflow.py invalidate --root PROJECT_ROOT \
  --role bgm_master --reason '用户改选BGM'

python3 scripts/workflow.py invalidate --root PROJECT_ROOT \
  --from-stage 06_subtitle --reason '最终字幕时间轴发生变化'
```

封存：

```bash
python3 scripts/workflow.py seal --root PROJECT_ROOT
```

所有命令都没有`--force`。

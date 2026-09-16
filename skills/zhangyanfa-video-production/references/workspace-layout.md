# 每期工作目录与素材位置

新项目必须通过总控 `init` 创建；不要凭上一期目录名临时仿制。初始化冻结 `workspace_paths.json`，各模块通过 resolver 获取路径。路径规范与内容审批是两件事：导航不会把旧稿、试听、文件存在或技术 PASS 改成已批准。

## 三个位置

| 位置 | 默认根目录 | 保存内容 |
| --- | --- | --- |
| 每期项目 | iCloud `视频/<系列>/<两位期号>_<主题短名>/` | 输入、研究、稿件、通过的配音、字幕、素材引用、轨道决定、审片、正式输出、封面、审批与重建依据 |
| 永久原始素材库 | `~/Documents/视频素材/00_原始素材库/` | 按 `游戏/source_id/原文件名` 保存的新原片；固定参考和旧素材通过索引引用原位置 |
| 本期处理缓存 | `~/Documents/视频制作缓存/<episode_key>/` | ingest、voice、review、render、qa、logs 下的可再生中间数据；vNNN 子目录隔离处理版本 |

`episode_key` 采用 `GI71_EP004`、`HSR45_EP010` 等稳定 ASCII 编号；项目显示题目可改变，编号和已引用根目录不能随标题反复改名。已有用户指定路径优先，先登记实际位置，不擅自搬走原文件。共用素材库在本机，不等于已备份；已在 iCloud 的旧原片保持原位置，不把符号链接当跨设备备份。

原片不是缓存。往期名叫“素材缓存”“配音缓存”的目录可能混有原始下载、接受音频和交付依赖；一律先保留并登记真实用途，不能按名称整体清理。这个规范不授权删除或 iCloud 移除下载。

## 固定项目结构

```text
04_主题短名/
├── 00_开始这里.md           # 自动入口：各阶段、实际文件、素材和缓存
├── 00_用户输入/            # 原样接收截图、说明、用户调整文件
├── 02_研究/v001/           # 选题、证据、反证、素材侦察
├── 03_脚本/v001/           # 稿件、纯文本、审校、冻结manifest
├── 05_配音/v001/           # 已接受片段、最终母带、发布与试听收据
├── 06_字幕/v001/           # SRT、统一时钟、cue映射、剪辑决定
├── 07_素材/v001/           # 引用/来源/镜头索引、P0及容量冻结
├── 08_配画与BGM/v001/      # A、B、C、BGM、计划、固定审核页数据
├── 09_审片/v001/           # 全长720审片与实际反馈
├── 10_正式输出/v001/       # A/B/C母版与正式技术QA
├── 11_交付/                # 自动文件索引；vNNN存交付清单/QA、需要的整合片
├── 12_封面/v001/           # 六稿、选择、16:9/4:3/3:4与QA
├── 98_工具与日志/          # 本期脚本、配置及轻量日志
├── 99_历史/                # 未绑定旧草稿、历史导入和变更说明
├── CURRENT.json / request_contract.json / authority_bundle.json
├── deliverables.json / workspace_paths.json / workflow_metrics.json
└── approvals/ + state/     # 唯一审批账和阶段收据
```

01 是初始化、04 是批准稿件，13 是封存事件，所以不额外建立内容目录；这些操作仍完整保留在十三阶段总控。以上编号对应原流程，不能为了连续编号再换一套阶段含义。

顶层目录名固定，不出现 `03_脚本_v1`、`10_正式分轨_v3` 或日期后缀。版本放进阶段下的 `v001/v002`。阶段可独立升级；例如新 A 为 v002、未改 B 仍指 v001，当前对象由总控决定，不以最大版本号或修改时间猜测。

文件名使用用途；离开目录后仍需辨认的母版可用 `GI71_EP004_A_2560x1440_60fps_v001.mp4`。禁止用“最终最终”“新新版本”替代版本与审批。用户原文件名不改，用接收清单解释角色。

已被批准、源清单、剪辑工程或收据绑定的文件保持原位置。不能为了整齐把它们挪到 99_历史；旧版本可以留在各阶段版本目录，入口只列当前指针。真正的无引用草稿才可按明确范围归档。

## 操作入口

新一期 `workflow.py init` 使用默认 v2 profile 时自动建目录、冻结路径、分配缓存；显式提供 `--episode-key GI71_EP004`。必要时可传 `--media-root` 与 `--cache-root`，缓存不能位于 iCloud，也不能与项目或原片库重叠。

```bash
python3 scripts/workspace_layout.py resolve --root PROJECT_ROOT --kind script --version v001
python3 scripts/workspace_layout.py new-version --root PROJECT_ROOT --kind voice
python3 scripts/workspace_layout.py resolve --root PROJECT_ROOT --kind cache:render --version v001
python3 scripts/workspace_layout.py doctor --root PROJECT_ROOT
python3 scripts/workspace_layout.py refresh --root PROJECT_ROOT
```

模块在 resolver 返回的位置写文件；不要把另一项目的绝对路径复制进脚本。配置只记录来源、当前 project root、media root 与 cache root，不在每段代码里各写一套。已定义 kind：input、research、script、voice、subtitle、sources、tracks、review、masters、delivery、covers、tools、history，以及 media 和 cache:ingest/voice/review/render/qa/logs。

`new-version` 原子创建下一个版本目录，不覆盖前版；跨模块共用一个剪辑修订时，在计划里明确引用各模块实际版本，不独立计算时钟。总控登记时验证角色所属阶段目录及 vNNN 层；路径契约被改动会触发冻结指针错误。总控保存状态后自动更新入口和文件索引。

`00_开始这里.md` 和 `11_交付/00_文件索引.md` 是生成文件，不手填“最新版”或审批。个人备注放用户输入/需求补充。交付索引引用现有母版和封面，不为方便另复制一套大文件；需要可离线转交的打包副本时另按明确交付请求生成并校验。

在已建 `00_制作管理/项目索引.json` 的视频根目录下新建一期，初始化会登记这个导航目录；后续状态保存同步更新总入口中的项目、题目和文件索引。其他位置不会被自动扫描或导入。该索引只管导航，不能替代项目权威或审批。

## 原始素材登记与查找

新下载前先查库内 `registry.json` 以及旧素材位置索引；以游戏、source ID/URL、实际 SHA 判重，不只按文件名。新下载暂存在本期 `cache:ingest`，校验后把本次新下载的原件一次落在 `media_root/游戏/source_id/`；若用户要求原片放本期 folder，则保存在该指定位置并登记，不能违背用户要求。

```bash
python3 scripts/media_registry.py --library MEDIA_ROOT --path ORIGINAL \
  --game 原神 --source-id BVxxxx_p01 --title '可读标题' --origin '原始来源URL'
```

登记器流式计算实际 SHA、合并同字节身份和别名，不搬、复制或删除文件。相同 source ID 对应不同字节会失败，须先说明确有不同剪辑/质量/版本并分配新 ID。同一原片只保留一个工作主源；合法备份作为副本记录，不能为了判重自动删除。素材登记不提供版权批准，原来源/权利审查继续执行。

代理、裁切段、OCR/ASR、联系表记录 `derived_from`、原片 SHA、原区间和工具配置，写本期缓存；精选证明帧与重建配置留项目。已验收的旁白、BGM、母版不能只存在于缓存。

## 旧期接入

已交付旧期用 `adopt --mapping MAPPING_JSON`，新增 `workspace_paths.json`、`00_开始这里.md` 和 `00_工作台/`。工作台按同一套阶段分类，用相对链接直达原目录；mapping 保存每个 kind 对应的真实文件/目录列表。未找到的类别保持空入口并说明，不能凭目录名推定批准。

原 `CURRENT`、权威、审批、原片、母带、母版及工程引用均不改；导航是只读视图，不能经旧期工作台链接写新生产产物。`resolve` 会拒绝给 legacy 模式分配新的正式工作路径；需要旧期返修时先明确迁移方案，旧源和批准关系要保留。

完成接入后验证所有链接、控制文件前后 SHA、缓存所有权与登记输出位置。第二期等有删段的旧工程，交付索引必须同时链接实际独立交付清单中的音频/SRT，不把原始旁白条目冒充剪辑后的交付文件。

跨电脑：Markdown索引及 JSON 保存真实来源路径；本机符号链接不是素材副本。迁移需重新定位 storage roots、核验实际 SHA，再重建链接，不能直接宣称工程已可跨机器复现。

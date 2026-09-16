# macOS 安全串行渲染

## 本地化与预检

- 将 composition、选中素材代理、chunk、浏览器缓存和临时输出放到声明的本地非 iCloud scratch。
- 记录 `sysctl hw.memsize`、`vm_stat`、`memory_pressure`、可用磁盘、工具版本、硬件编码器与当前 SHA。
- 预留空间必须覆盖预计输出、临时块与安全余量；不满足时停止，不边渲边赌磁盘。
- 对所有选择范围使用可 seek 的 CFR 代理；原始源与代理身份分开记录。

## 单工执行

`safe_render_supervisor.py` 启动时持有总控共享的 `~/Documents/视频制作缓存/.foxjiu-heavy-worker.lock`，并向渲染子进程传递锁描述符；其他重任务（包括配音模型批次）用 `zhangyanfa-video-production/scripts/heavy_job.py -- COMMAND ...` 包裹。不要再把已自带锁的 supervisor 放进第二层 guard。锁占用返回 75，不杀其他项目、不删除锁文件；待现有任务释放后恢复。

正式轨道顺序固定为 A、B、C。一次只运行一个 HyperFrames/浏览器渲染和一个 worker；使用 `caffeinate` 保持系统唤醒。优先 VideoToolbox、GPU与低内存模式，实际编码器必须写入收据。

chunk 按真实编辑边界分割。初始块长依据机器预检和720压力样片决定；资源压力升高或崩溃后缩短，不把固定秒数写成永久规则。

## 监控与停止

监督器周期记录：进程状态、最近进度时间、RSS、系统 memory pressure、swap、磁盘余量与可获得的热状态。以下任一情况触发可恢复停止：

- memory pressure 为 critical 或系统持续换页；
- swap 在连续样本中快速增长；
- 磁盘低于冻结保留值；
- thermal state 为 serious/critical；
- 渲染进程长时间无任何进度；
- 输出块未通过基本解码。

停止时终止整个渲染进程组，不能留下孤儿 Chromium。已通过块与收据保留；当前 partial 标记失败。冷却后降低块长或源代理压力，从最后有效块继续。

## 收据

每个块绑定 composition、计划、素材/代理、工具版本、帧范围、命令、开始结束时间、退出码、输出 SHA、probe和完整解码。复用块前重新核对全部输入指纹；只比尺寸和帧数的缓存无效。

v2 supervisor 计划写 `production_contract_version:2`；每个 task 写 `input_bindings:[{path,sha256}]` 和非空 `tool_versions`，并把真实帧范围、输出配置及命令保存在 task 中。输入清单必须完整包含实际 composition、计划、素材/代理和时钟，不能只列一份无关文件。supervisor 复算输入 SHA 与整个 task 指纹后才复用收据；旧的仅输出 SHA 收据不能命中。任务退出0且有非空文件仅代表生成成功，probe、完整解码和最终视觉 QA 仍是另外的门禁。

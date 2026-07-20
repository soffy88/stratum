# AII 进料→抽取全链路 — 固化记录

最后确认: 2026-07-06 10:25, 有🚨(ocr-vllm exited, GPU硬件故障未恢复——详见下方"GPU硬件故障"章节的后续更新)

## 拓扑(源文件 → MD → KU)

```
① 源文件进料(人工/外部渠道, 无自动"发现新书"能力, 靠人往下面几个目录扔文件)
   /mnt/d/books/{数学,Economic}         D盘(本机NTFS分区, nvme1n1p1)人工下载存放处
   /home/soffy/books/{数学,Economic}    本地人工投PDF处
   stratum 系统抓取                     → /home/soffy/shared/stratum-to-aii (已是MD, 非PDF)
        ↓
② aii-feeder.service (scripts/feeder_run.sh, 600s一轮, 三个KU飞轮各自也主动调一次不等它)
   scripts/pull_ingest.sh 一次做全:
     D盘同步 → math_convert.py/econ_convert.py(PDF→MD, 文字层书) → classify_md.py(分拣到books/MD/{经济学,中文数学,英文数学,其它})
   扫描版/烂文本层书(需OCR) → aii-ocr-daemon.service(独立慢节奏循环, 见下)自动排队走ocr-vllm
        ↓  books/MD/{经济学,中文数学,英文数学,其它}  ← 三个KU飞轮的消费队列
③ 三个常驻KU飞轮(各自discover→质量门→入库/隔离, 详见各脚本注释)
   aii-flywheel-econ-zh   → econ_flywheel_zh.sh   → 严格LLM质量门(econ_quality_gate.py)
   aii-flywheel-misc      → misc_flywheel.sh      → 同上质量门, 密度基准已按学科校正(QGATE_KU_PER_CHAPTER=8)
   aii-flywheel-math-prog → math_flywheel_prog.sh → 0-LLM程序抽取, 无LLM质量门, 靠math_route_or_skip.py结构门禁
        ↓
   aii.ku_onto (postgres, aii-postgres容器)
```

依赖的常驻服务(全部 `systemctl --user`, 都设了自动重启, linger已开机启用):

| 服务 | 作用 | Restart策略 |
|---|---|---|
| aii-embed | 共享BGE-M3嵌入(端口8102), 三个KU飞轮入库都要调 | always |
| aii-feeder | 喂书守护, 见②  | always |
| aii-flywheel-econ-zh / -misc / -math-prog | 见③ | always |
| aii-backend | epistemic backend(8101), 内含自己的"background flywheel"(evolution cycle, 跟上面3个CLI飞轮是两码事) | on-failure |
| aii-ocr-daemon | 2026-07-06新增, `scripts/ocr_daemon.sh`独立慢节奏循环(默认1800s/轮, 一次invocation本身可能跑数小时), 扫描版/烂文本层PDF自动排队走ocr-vllm。不进`pull_ingest.sh`(那条有600s超时会腰斩~80min的OCR任务), `math_convert.py`/`econ_convert.py`里的自主OCR分支由`MATH_CONVERT_AUTO_OCR=1`门禁只此daemon打开 | always |

docker: `aii-postgres`(存KU) `ocr-vllm`(OCR, 由aii-ocr-daemon按需`docker start/stop`, 空闲不占卡) — 均已设 `restart: unless-stopped`/`always`。GPU排队: `math_ocr_convert.ensure_container()`会先等`aii-embed`(BGE-M3, /health的loaded字段)空闲卸载(最多等10min)再启动ocr-vllm, 不是撞见占用就放弃。

## 体检

```bash
bash scripts/pipeline_health_check.sh   # exit 0=全绿, 1=有🚨
```

检查项: 6个systemd服务是否active / aii-embed实际调一次(不只看进程) / aii-postgres+ocr-vllm容器 / D盘挂载(`mountpoint -q`, 不要用`mount|grep`——pipefail下grep -q提前退出会让mount收到SIGPIPE误判失败) / 各阶段积压深度 / 隔离积压 / 有没有拉料进程卡住>15min。

## 已知不变量(体检看的就是这些)

- **积压不是问题, 长期为0才是问题**——现状 stratum待分类369份、books/MD各分类池均有存货(45~62不等), 说明供给远大于消耗, 不存在"断料"风险, 真出问题时看的是这些数字有没有异常归零或暴涨不降。
- **隔离(quarantine.json)不会自愈**——2026-07-06 用户决定econ_zh 31条+misc 44条不逐本review, 直接放弃, 已归档到各自quarantine.json的`archived[]`(`quarantined[]`清空), state.json本就已把这些substrate标终态, 不会被discover脚本重新捡起。math旧管道23条仍留着(退役管道遗产, 不是这次决定的范围, 不会再变)。以后新产生的隔离同理: 飞轮不会自己清, 得人工决定或明确说"放弃清除"。
- **math-prog 没有LLM质量门**——质量由`math_route_or_skip.py`(只收编号定理/定义书)+入库ok/err计数把关, 不是密度/完整率那套。

## 2026-07-05 事故记录(根因+已修)

1. **aii-embed 被手动stop, 8.5小时零产出**——`Restart=always`对主动stop不生效(只管崩溃自愈), 没人发现。恢复: 已重启, 加了这份体检脚本以后能一条命令测出来(不再靠人翻log)。
2. **feeder 单轮卡了9小时19分(14:41→00:00)**——具体卡在`pull_ingest.sh`内哪一步没能完全实锤(D盘同步/math_convert/econ_convert/classify_md四步都无unbounded调用, 排查未发现embed依赖), 但已自愈。硬化: 给所有4处`flock -c "bash scripts/pull_ingest.sh"`调用加了`timeout 600`包裹(econ_flywheel_zh.sh/misc_flywheel.sh/math_flywheel_prog.sh/feeder_run.sh), 以后再卡会在10分钟后被杀掉重试, 不会再无声阻塞数小时。
3. **misc密度阈值套错学科**——沿用econ的15KU/章基准套所有"其它"类书, 误伤哲学/通识类书。已改`QGATE_KU_PER_CHAPTER`/`QGATE_CHAPTER_FLOOR`可环境变量覆盖, misc设8/3。
4. **KU内容质量bug**(不是入库流程, 是抽取准确性): 英文字段空壳未检测(53+17条已修+检测已补)、目录块误判为正文(`_bad_anchor`已加"参考书目"窗口检测)、中文术语裸"是"句优先级高于"TERM(English Gloss)"真定义句(已加3b优先级)。
5. **ocr-vllm 容器无重启策略**、**当时体检脚本D盘挂载检测有pipefail误判bug**——发现即修(见上)。
6. **GPU只有9.65GB, ocr-vllm要75%利用率(7.23GB)**——`docker start ocr-vllm`时若aii-embed刚好把BGE-M3加载在GPU上(哪怕只占~2.4GB), 剩余显存就不够ocr-vllm启动, 会直接`Engine core initialization failed`退出(退出码137, 容易误判成"被杀"而非"启动失败")。实测复现: 体检脚本自己调一次`/embed`就会触发这个竞争。规避: 等aii-embed空闲卸载(`AII_EMBED_IDLE_SEC=300`, 看`curl :8102/health`的`loaded`字段)再`docker start ocr-vllm`, 别顶着重叠启动。这是硬件容量结构性限制, 不是能简单修掉的bug。

## 2026-07-06 math_prog(0-LLM程序化抽取)质量重抽

用户反馈一条KU"没提取到概念名"(标题就是裸标记`Example 8.11`, 内容还吞了整章的Summary/Further Reading/11道Exercises)引出的连锁排查, 改了 `scripts/math_program_ingest.py` 三处根因(全部是正则/规则改动, 仍0-LLM):
1. **无书自带括号名时不再留裸标记**——摘陈述开头一句逐字当label(仍是摘录不是编造); 书自带括号名(英文`(...)`/中文`（...）`)现在中英文类型词都认。
2. **内容边界止损**——原来只认"下一个Definition/Theorem/Example"当边界, 不认"Summary/Exercises/习题"这类章末收尾段, 也不认普通编号小节标题(如"12.3 Ridge Regression"), 导致最后一条吞掉后面一大截不相干内容(实测吞过整章)。加了STOP边界正则堵上。
3. **无节号书的假重复丢失(最隐蔽)**——扁平编号书(每章重置计数, 如"命题1"每章都有)如果没有干净的"N.N小节标题", 原代码不会冠章号, 导致不同章的"命题1"撞进同一个去重key被当成"重复"丢掉。实测一本书238处标记只survive 9条(76%被误删)。修法: 无节号但有章号时, label冠"第N章"防跨章撞名。
   剩余损耗(如两本历史文集类数学经典, 前言/传记占比极大导致大量标记落在检测到的第一个"章"之前而被`ch==0`丢弃)是书本身体裁(古典文献汇编, 非现代教材结构)和抽取范式的错配, 没有再深挖。
4. **顺手修的**: PDF抽取偶发NUL字节(`\x00`), postgres直接拒绝插入(`ok=N-2 err=2`那种)——`_clean()`里加了过滤。

全量重抽了当时已入库的全部11本书(2955→2929条KU, 裸标记title 67%→0%, 超长(>3000字符)KU 17%→9%)。过程中出过一次真实事故: 批处理删KU时连带清掉了`.done`标记, 导致常驻的`aii-flywheel-math-prog`把"正在处理中"的书当新书抢着重跑, 和批处理撞车——发现后杀掉冲突进程、确认两个已完成的book无脏数据, 之后改成先`systemctl --user stop aii-flywheel-math-prog`再批处理, 完事重新`start`。以后再做这类"删旧KU+重抽"的批量操作, 记得先停对应飞轮服务。

## 2026-07-06 OCR自动化上线(aii-ocr-daemon)

背景: 当时积压45本待OCR(数学25+经济20, econ_convert.py之前完全没接OCR)。`math_ocr_convert.py`(GPU锁/vLLM容器管理)本来就写好了, 但从未被自动调用过(`math_convert.py --do`里那段"自主OCR"代码只在手动跑才碰得到, `pull_ingest.sh`调用它时OCR书永远排在最后而且没人给够时间跑完)。新增 `aii-ocr-daemon.service` + `_wait_for_embed_idle()`GPU排队, 见上面"依赖的常驻服务"表格。

**上线即实测复现一个真问题**: 跑起来后 `ocr-vllm` 连续2次 CUDA OOM 崩溃(`torch.OutOfMemoryError`, KV cache仅0.75GiB/13168token, 8并发把它挤爆)。docker的`restart: unless-stopped`策略兜底自动重启了, 没丢数据(该本书未写入的进度下一轮重跑, 页级缓存`ocr_cache/`保留), 但白白损耗了两次崩溃重启的时间。根因: `CONCURRENCY=8`(客户端并发请求数)对`--gpu-memory-utilization 0.75`(特意压低留给aii-embed的显存)下的KV cache池太激进。改成`CONCURRENCY=4`(`scripts/math_ocr_convert.py`), 同一处理哲学与`AII_SYNTH_CONCURRENCY=4`那次"4-5低偶发超时,6+持续过载"的调参结论一致。

## 🚨 2026-07-06 06:35 GPU硬件级故障(Xid 79, "GPU has fallen off the bus")——aii-ocr-daemon已停, 待人工处理

OCR daemon上线后处理"代数拓扑基础(Munkres)"这本书途中, `journalctl -k` 记录:
```
NVRM: Xid (PCI:0000:01:00): 79, GPU has fallen off the bus.
NVRM: GPU 0000:01:00.0: GPU has fallen off the bus.
```
这之后host上 `nvidia-smi` 直接报 `Unable to determine the device handle for GPU0: Unknown Error` / `No devices were found`——**不是ocr-vllm容器的问题, 是GPU在硬件/驱动层彻底断线了, host级故障**。`docker inspect` 显示 `RestartCount=12`——docker的`restart: unless-stopped`policy在GPU断线后仍不断重启容器, 每次都立刻因`NVMLError_Unknown`崩溃, 空转了12次。

**根因链条(推测,非确证)**: 之前那两次CUDA OOM崩溃 → docker自动重启 → 短时间内多次init/teardown GPU上下文 → 可能是压垮本就不太稳的PCIe连接/驱动状态的最后一根稻草(GSP RPC队列在日志里能看到大量`GspRmFree failed`)。不代表OCR代码本身有bug干出了硬件故障, 但"OOM→自动重启"这个循环客观上是触发点之一。

**已做的安全处置(只做了这些, 没有碰任何需要root/有破坏性的操作)**:
- `docker stop ocr-vllm`(它已经是Exited状态, 这步是确认+防御性)
- `systemctl --user stop aii-ocr-daemon`——防止它在无GPU可用的情况下继续每轮重试`ensure_container()`空转
- 验证过 `aii-embed` 已自动降级到 `device:"cpu"` 且真实embed调用成功——**三个核心KU飞轮不受影响**, 只是embedding会慢一些(CPU而非GPU)
- 没有再碰GPU/驱动/docker以外的任何东西

**需要人工判断/操作(我不会未经允许就做, 这类操作影响host上全部~100+个容器/服务)**:
- Xid 79 "fallen off the bus" 通常需要 `sudo systemctl reboot` 才能真正恢复(某些情况下 `echo 1 > /sys/bus/pci/devices/0000:01:00/remove` + rescan 能免重启修复, 但不保证, 且需要root)
- 重启前建议先确认没有其它重要的、未保存状态的工作跑在这台host上(这台机器同时扛着经济学/数学飞轮以外的一大堆容器: aegis/helios/tide/quant/selene/mneme等)
- GPU恢复后, `aii-ocr-daemon` 需要手动 `systemctl --user start aii-ocr-daemon` 才会重新开始(不会自愈启动, 这是刻意的——不想在GPU状态不明时又自动开始猛跑)

## 2026-07-06 10:25 GPU故障后续: 已重启host, 但硬件仍未恢复 + aii-embed一度真实故障(已修) + aii-ocr-daemon被linger误唤醒(已再停)

距06:35 Xid 79记录约4小时后发现host已被重启(`uptime`显示仅运行5分钟), 但`nvidia-smi`重启后依然报`Unable to determine the device handle`/`No devices were found`——**说明这次GPU故障不是简单的驱动挂起, `sudo systemctl reboot`这条"通常有效"的修复手段已经试过且未生效, 硬件层面的问题比预想的更严重**。

**期间aii-embed经历了一次真实的服务故障(不只是"变慢", 是彻底不可用)**: host重启后`aii-embed`跟着重启(所有服务`ActiveEnterTimestamp`同为10:18:23), 模型加载时`_pick_device()`调用`nvidia-smi --query-gpu=memory.free`——推测是reboot过程中GPU曾短暂可被枚举到(足够让这条探测命令一次性成功返回正常空闲显存值), 于是选中了`device=cuda`; 但GPU随后又不可用, 导致此后**每一次`/embed`调用都在实际编码时抛`torch.AcceleratorError: CUDA error: unspecified launch failure`, 100%失败**, 三个KU飞轮的入库通路(入库前必须先嵌入)在此期间全部卡死。数据库确认: 最后一条KU创建于当天05:48:19(卡在Xid 79发生前后), 直到发现问题时(10:23)已经**4.5小时零产出**, 期间host重启也没能自愈这个状态(重启不会让已加载在内存里的`_device`重新探测, 服务本身没崩溃, 只是每次请求都500, 不会触发`Restart=always`)。

处置: `systemctl --user restart aii-embed`, 重启后`_pick_device()`重新探测(此时nvidia-smi已稳定报错), 正确降级到`device=cpu`, `/embed`实测调用成功恢复。**这不是永久修复, 只是让服务状态与GPU真实不可用的现状对齐**——GPU物理故障不解决, 之后任何时刻只要GPU出现哪怕一次性的短暂"看似可用"探测窗口, 同样的问题会复现(风险点已知, 未做代码层加固, 比如探测后再做一次实际tensor操作验证真实可用性)。

**另一个连带发现**: `aii-ocr-daemon`在host重启后被systemd linger自动拉起(linger服务默认开机自启, 不区分"这个服务此前是被人手动stop的"), 违背了06:35事故记录里"GPU恢复前不该自愈启动, 需要人工重新start"的刻意设计——发现时它已经在GPU仍死的情况下空转重试`ocr-vllm`容器3次(`RestartCount`)。已重新`systemctl --user stop aii-ocr-daemon`且`docker stop ocr-vllm`。**这是本次新发现的一个设计缺口**: linger自启无法区分"崩溃后自愈"和"人工干预后应保持停止", 下次GPU故障+重启的组合场景会再犯同样的问题, 除非改成显式禁用(`systemctl --user disable`)而不是仅`stop`。

三个核心KU飞轮(econ-zh/misc/math-prog)本身不受GPU故障直接影响(不用OCR, 只用embed), aii-embed修复后已确认可正常工作, 目前跑在CPU(变慢, 不影响正确性)。

## 遗留, 需要人工决策(不是我能program化判断的)

- ①源文件进料完全靠人工往D盘/本地目录扔文件, 没有主动"发现新书"机制——如果想要真正"不断料", 需要人持续投料, 或者另外接一个自动书源(如stratum的订阅/爬取)扩大到PDF/书籍范围
- math旧管道23条隔离(退役, 与当前math-prog无关)——留着还是清, 没问过, 按兵不动
- OCR降并发(8→4)是否彻底解决OOM还没跑完全部45本验证过(GPU故障中断了验证), 需要GPU恢复后继续观察; 如果4还不够稳, 下一步应该是降`--gpu-memory-utilization`或`--max-num-seqs`而不是继续降并发(并发再降会拖慢~80min/大书的处理时间)
- **GPU硬件故障: reboot已试过且未解决**(10:18已重启host, `nvidia-smi`仍不可用)——下一步不再是"要不要重启"的问题, 需要人工判断是否要开始查硬件本身(排线/PCIe插槽/电源, 甚至联系硬件支持), 这已超出软件层面能处理的范围
- **aii-ocr-daemon的linger自启会覆盖人工stop的意图**(本次已复现一次): 若GPU长期不可用, 应考虑`systemctl --user disable aii-ocr-daemon`而非仅`stop`, 否则每次host重启都会重新空转重试`ocr-vllm`

<!-- WATCHDOG:START -->
## 🚨 Needs Human (看门狗自动维护, 2026-07-20T00:31:40Z)

- ✅ 无严重项 (overall=degraded)

<!-- WATCHDOG:END -->

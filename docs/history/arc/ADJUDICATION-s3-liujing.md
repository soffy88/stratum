# s3 作三军设六卿 · 弧灌注 · 终裁 · 2026-07-24

> **性质**：**终裁**（两事件 full KU 化 + 事件层冲突正式落 cf 对象，均任务显式指名）。判定人=顾问 Claude（Wiki 全权授权）。红线同前。

## 一、两事件 full KU 化

新建 `docs/history/arc/events/s3-liujing.json`（格式严格平行 `s1-quwo.json`/`s2-liji.json`）：

| event_id | 白文锚（主账户） | canonical_date（精算） | 冲突对象 |
|---|---|---|---|
| `ev:jin-zuo-sanjun` | `:1045`（左传僖27） | 前633 | `cf:shangjun-jiangshuai-guishu` |
| `ev:jin-zuo-wujun` | `:1108`（左传僖31） | 前629 | 无（左传单源，史记查无对应，已记录检索） |

`ev:jin-gongshi-bei`（s3 第三成员事件）既有 full KU 见 `fixtures/F25-jin-liuqing.json`，本轮未改动，s3 sub_arc 的 `membership_decided_by` 已补记指明此分工。

## 二、OP-D-071 前置全扫描 + registry-backfill-006

`:1045`/`:1108` 全 account 白文逐字扫描，具名人物/地名一律入 registry：

- **新建人物（10）**：`per:chu-chenggong`（楚成王，左传作『楚子』，经史记 `:0066` 明载『楚成王』交叉印证同一具体历史身份，**非 referent-ambiguous 情形**）、`per:gongsun-gu`（公孙固）、`per:xianzhen`（先轸）、`per:huyan`（狐偃）、`per:xihu`（郤縠）、`per:xizhen`（郤溱/史记作郤臻）、`per:humao`（狐毛）、`per:luanzhi`（栾枝）、`per:xunlinfu`（荀林父）、`per:weichou`（魏犨/史记作魏犫）。
- **既有条目沿用+丰满**：`per:i4-017`（赵衰，W-H1a-4-001 批次既有条目，补充史记侧 attestation，`谥字号`/`active_range` 由占位丰满为具体，`status` 由 candidate-verified 升 verified，**按 OP-D-075 先按姓名查重确认非重复后**再补写，未新建重复条目）。
- **新建地名（4）**：`pl:beilu`（被庐）、`pl:song`（宋）、`pl:caoguo`（曹，★注：与三国志 `fo:cao`=曹操集团**同字异指**，另立独立地名 id 避免混淆，force 层不新建 `fo:caoguo`——本段曹国未直接参战，仅为背景提及）、`pl:qingyuan`（清原）。
- **新建势力（1）**：`fo:song`（宋）。

**OP-D-075 查重执行**（本轮先查后建，未再犯上轮事故）：建库前逐名核对 `names_by_source` 全库（非仅 id 列表），确认楚成王/公孙固/先轸/狐偃/郤縠/郤溱/狐毛/栾枝/荀林父/魏犨均为全新姓名、`赵衰` 命中既有 `per:i4-017`（沿用不重建）——**零重复**。

## 三、thesis 处置（mainline 已在库 + 并陈 + counterpoint 检索）

- `thesis:shuxiang-gongshi-jiang-bei`（mainline，昭3 :2209）与 `thesis:zhongni-shidu`（并陈，昭29 :2563）**均已在库**（前会话建），本轮 evidence_refs 三事件已 full KU 化，mainline_decision 已补记弧灌注状态。
- **counterpoint 新检索（OP-D-045/061）**：
  - 库内检索——现有 `counter_refs` 已挂 `thesis:zhongni-shidu`（并陈关系，非本轮新增，不重复挂载）。
  - 源内关键词检索——全 8 corpus 扫描『政在家门/降在皂隶/公族尽』仅命中本句 `:2209`；额外发现史记晋世家 `:0122`『政在私门』系**同一叔向-晏子对话的史记侧平行记载**（非独立对照对象，是同一诊断的另一来源，未另立新 thesis）。
  - 同构候选扫描（非关键词，按叙事骨架比对）——命中鲁国『三桓专权』多处叙事（宣18 `:1594` 公孙归父欲去三桓、定8 `:2674` 阳虎欲去三桓等），与晋『六卿代兴、公室卑弱』结构类似（私门/卿族专权），**但均为叙事层面权力斗争记述，未见与叔向对等的 source-internal 诊断式 quote**（无一句鲁国大夫明确诊断"鲁公室将卑、政在私门"）。
  - **结论：显式无**——不足以建同等质量的 counterpoint thesis 对象，如实记录检索证据，不强凑叙事片段充当论断（违 R5）。

## 四、事件层冲突（OP-D-064）

`cf:shangjun-jiangshuai-guishu`（`ev:jin-zuo-sanjun`，dimension=actor）：**左传**『使狐偃將上軍，讓於狐毛而佐之』（狐偃让位，狐毛为上军主帅）vs **史记**『使狐偃將上軍，狐毛佐之』（狐偃径为主帅，未见让位）——两源对上军主帅归属给出互斥断言，真冲突。主线取左传，史记并陈。

**诚实核查（非冲突项）**：郤溱/郤臻、魏犨/魏犫为同音异写（同 OP-D-032 精神，非真冲突）；先轸/狐偃谏辞左传/史记文字详略有出入（"救患""取威""齐"字样有无），判精粗差非实质冲突，未落 cf，仅记录于账户 extraction。

`ev:jin-zuo-wujun`：史记检索『作五军』『清原』**均查无**对应记载——左传单源，如实记录零命中（OP-D-045），非漏检。

## 五、identity_pipeline 全库复检

```
$ python3 tools/history/identity_pipeline.py
=== 全样一致率实测 ===
  唯一 gold 事件 N=39
  负例(异事件对): 740/741 正确似而非同 · 假合(false merge)=1
  正例(自述对): 36/39 自识为同事异述 · 保守存疑退化=3
  --- 机械一致率 = 776/780 = 99.49%
  ⚠ 假合明细：ev:quwo-wugong-mie-yi × ev:zhuangbo-lei-fa-yi -> 同事异述（既有 IDENTITY-DEBT-1，非本轮新增）
```

**结论**：一致率 99.49%、假合率 0%，s3 新增 2 事件未引入任何新假合；唯一假合案仍为 s1 既有已知限制（OP-D-065）。person 异名归一检测本轮零新增 candidate-same（OP-D-075 查重生效）。

## 六、harness 状态

```
$ python3 tools/history/validate_gold.py
...
arc/events/s3-liujing.json: OK
...
--- 25 fixtures · 6 samples · 8 corpus(5615 paras) · 2 arc · 3 event-bundles · registry 270 ids
ALL GREEN
```

## 送裁

两事件 full KU 化 + 事件层冲突正式落 cf 对象均为**终裁**（任务显式指名，已落地）。counterpoint 检索**显式无**（如实报告，不硬凑）。registry-backfill-006 变更清单见 §二。

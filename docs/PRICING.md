# Pricing and usage-unit contract

Stratum 的高算力能力按 credits 计量，避免把 token、图像、TTS 和图谱重算包装成
“无限使用”。当前基线：

| Tier | 月 credits |
| --- | ---: |
| Free | 25 |
| Plus | 250 |
| Pro | 1000 |

单位成本：deep research 10、graph rebuild 10、image generation 5、TTS 3、large
export 2。`GET /api/v1/billing/credits` 暴露当前策略及本周期已用/剩余额度，
`POST /api/v1/billing/credits/estimate` 用于前端在执行前展示消耗。服务层
`credit_meter.consume_credits()` 以 PostgreSQL `usage_credits` 为原子扣减账本，
成功扣到月度边界时仍返回成功，但剩余额度为 0。

`researcher` 已在创建运行记录前调用同一账本扣减 `deep_research` credits；其他高算力
任务接入时也必须遵循这一事务入口规则，拒绝时不得创建异步任务。支付 provider 仍由
现有 Stripe/WeChat 流程负责。
需要支持客户端重试的 researcher 入口可在 `params.idempotency_key` 传递稳定值；migration 028 的事件账本
会保证同一用户与同一 key 不重复扣 aggregate credits；如果同一 key 被复用于不同 capability、
units 或计费月份，会返回幂等冲突而不是静默 replay。真实数据库并发行为仍需部署验收。
`CreditDecision.outcome` 会区分首次扣费、`replayed`、`in_flight` 与真正 `denied`；researcher
对已完成 replay 不重复执行，对并发中的相同 key 返回 409，而额度不足仍返回 402。

平台内容访问也按 `free < plus < pro` 累积层级执行：Free 只能访问 `free`，Plus
包含 Free/Plus，Pro 包含全部三档。真实支付 provider、订阅 webhook 和内容 tier
数据仍需部署商户密钥与真实账号后验收。

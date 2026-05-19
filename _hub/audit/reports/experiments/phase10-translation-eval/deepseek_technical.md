# deepseek / technical

## 原文

PostgreSQL's MVCC (Multi-Version Concurrency Control) mechanism allows readers
to proceed without blocking writers and vice versa. Each row version carries
xmin and xmax transaction IDs, which determine its visibility to any given
snapshot. The VACUUM process reclaims storage occupied by dead row versions,
preventing table bloat caused by update-heavy workloads.

## 译文

PostgreSQL的MVCC（多版本并发控制）机制允许读取操作无需等待写入操作即可进行，反之亦然。每个行版本都携带xmin和xmax事务ID，这些ID决定了该行版本对任何给定快照的可见性。VACUUM进程回收被废弃行版本占用的存储空间，从而防止因高更新负载导致的表膨胀。

## 统计

- tokens_in: 193
- tokens_out: 78
- cost_usd: $0.00014
- elapsed: 1.89s

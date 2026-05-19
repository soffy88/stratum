# qwen3 / technical

## 原文

PostgreSQL's MVCC (Multi-Version Concurrency Control) mechanism allows readers
to proceed without blocking writers and vice versa. Each row version carries
xmin and xmax transaction IDs, which determine its visibility to any given
snapshot. The VACUUM process reclaims storage occupied by dead row versions,
preventing table bloat caused by update-heavy workloads.

## 译文

PostgreSQL 的 MVCC（多版本并发控制）机制允许读者在不阻塞写入者的情况下进行操作，反之亦然。每个行版本都包含 xmin 和 xmax 事务 ID，这些 ID 决定了它对任何给定快照的可见性。VACUUM 过程会回收由过时行版本占用的存储空间，防止因更新密集型工作负载导致表膨胀。

## 统计

- tokens_in: 212
- tokens_out: 87
- cost_usd: $0.00002
- elapsed: 1.34s

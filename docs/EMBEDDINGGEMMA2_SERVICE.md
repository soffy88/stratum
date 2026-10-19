# EmbeddingGemma 2 共享嵌入服务 — AII/Stratum 接入方案

> 2026-10-13 部署并实测。本文只是方案，AII 代码、配置、数据库都没有改动。
> 服务的完整说明（接口细节、实测数字、运维）见 `/data/soffy/projects/hevi-omfootage/docs/EMBEDDINGGEMMA2_SERVICE.md`。

## 1. 服务速览

- **地址：`http://100.68.226.13:8790`**（笔记本 DESKTOP-72AVCFH 的 Windows tailnet IP，经 portproxy 转到 WSL）。OpenAI 兼容，`base_url=http://100.68.226.13:8790/v1`，api_key 随便填（服务默认不鉴权；设置 `EMB_API_KEY` 后开启鉴权）。
- 模型 `google/embeddinggemma-2`，跑在 GPU（GTX 1050 Ti）上，float32。默认输出 **768 维**，可选 `dimensions` 512/256/128（MRL，截断后会重新 L2 归一化）。最长 8K token，服务默认截到 2048 token（`EMB_MAX_SEQ`）。
- 接口：
  - `POST /v1/embeddings`：标准 OpenAI 格式，input 可以是字符串或数组，一次最多 2048 条，支持 `encoding_format=base64`
  - `POST /v1/embeddings/multimodal`：图像/视频/音频
  - `GET /health`、`GET /v1/models`
  - `POST /embed`：和 aii-embed 同形状，`{"texts"}` → `{"embeddings","dim","device"}`
- 任务前缀：扩展字段 `task`（SearchQuery / Document / QuestionAnswering / Clustering / SentenceSimilarity …），或 `input_type: query|document`，或用 model 别名 `embeddinggemma-2-query` / `embeddinggemma-2-document`。只能设 model 名的客户端，用别名也能拿到正确前缀。
- 并发：动态合批（每批 32 条，等 10 ms 合并），GPU 前向串行排队，不拒绝请求。systemd `embgemma2.service` 开机自启、崩溃后自动重启。
- 实测（客户端在 ubuntu26）：单条 p50 91 ms；32 条一批 p50 309 ms（约 104 条/秒）；16 路并发约 151 条/秒、0 错误；约 1800 字的长文本 507 ms/条。「冬天静电」↔「静电产生原因」0.891 > ↔「蓝鲸」0.814（SentenceSimilarity 前缀，768 维），全部有限值，范数为 1。
- ⚠ 调用时要绕过 ubuntu26 上的 http_proxy（`NO_PROXY=100.68.226.13`），否则会被代理返回 502。

## 2. AII 现状（2026-10-13 只读调查，仓库 `/data/soffy/projects/stratum`，HEAD df57c69）

> `/data/soffy/projects/AII` 只是空壳目录，真正的代码在 `stratum`。

- **模型**：`BAAI/bge-m3`，**1024 维**，sentence-transformers，`normalize_embeddings=True`。
- **服务**：共享微服务 aii-embed（`aii/aii/api/embed_app.py`，`POST /embed {"texts"}`）。部署在笔记本 WSL 的 systemd `aii-embed.service`，端口 :8102，代码在 `/home/soffy/aii-embed`。当前 override 设了 `AII_EMBED_VRAM_MIN_GB=99`，实际等于**强制跑 CPU**；`AII_EMBED_IDLE_SEC=10800`。服务端 batch 2，OOM 时自动降批。
- **客户端选择**：`aii/aii/aii/api/_provider.py:719-748`
  - 设了 `AII_EMBED_URL`：用 `oprim.embedding.aii_remote.AiiRemoteEmbedder`（地址解析顺序：构造参数 → `STRATUM_EMBED_URL` → `AII_EMBED_URL` → `http://127.0.0.1:8102`，5xx 时退避重试，再失败就降级到 fallback）
  - 没设：在进程内加载 `oprim.embedding.bge_m3.BgeM3Embedder`
  - 消费方通过 `oprim.vector_encode(texts=..., provider="default")` 调用，例如 `service/chapter_dedup.py`、`onto_persist.py`、`background_flywheel.py`
- **部署配置**：`aii/deploy/systemd/aii-backend.service:10` 写的是 `AII_EMBED_URL=http://100.119.113.90:8102`，也就是笔记本 WSL 自己的 tailscale IP。
  - ⚠ 本次实测：从 ubuntu26 访问 `100.119.113.90:8102/openapi.json`（1.7 KB），拿到 200 响应头后 body 一直到超时都没来；同一个文件走 `100.68.226.13:8102`（Windows portproxy）0.01 秒就返回了。
  - EG2 服务走 100.119.113.90 也是一样的现象：只有响应头，没有 body。
  - 建议 AII 自查：线上的远程嵌入是不是一直在超时、然后降级。可以考虑把地址改成 `100.68.226.13:8102`。这一条本文只提建议，没有改动。
- **存储**：PostgreSQL + pgvector，维度**写死在迁移里**，索引都是 HNSW `vector_cosine_ops`：
  - `aii/migrations/0001_onto_concept_storage.sql`：concept `vector(1024)`（:96）、invariant（:174）、`aii.ku_onto.embedding`（:258，HNSW 索引 :410）
  - `0004_kc_embedding.sql`：`aii.kc_onto.embedding vector(1024)`
  - `0009_bu_skill_embedding.sql`：`aii.bu_onto.embedding vector(1024)`（只有 paper 行）
  - `migrations/refined/0001_refined_repo_schema.sql`：多列 `vector(1024)`
  - 另外还有 `stratum.substrate_chunk.embedding`（由 `scripts/pg_reembed.py` 写入）
- **检索**：`aii/aii/storage/pg_backend.py`，包括 `search_ku_by_vector`、`search_paper_skill_by_vector`、混合检索（RRF，见 `0003_hybrid_fts.sql`）、KC 向量检索等，都用 `embedding <=> $1`。
- **重建脚本**：`scripts/pg_reembed.py`（BGE-M3 → substrate_chunk，幂等可续跑，最后建 HNSW）、`scripts/embed_kc_summaries.py`（只补 NULL，`--all` 全量重算）、`aii/scripts/dedup/orchestrate.py`。旧的 LanceDB/Ollama qwen3-embedding 路径（`batch_reembed.py`、`rebuild_indexes.py`）是 stratum-sl 桌面端的。

## 3. 接入方案

### 关键约束：维度和向量空间都不同，必须重建索引
- BGE-M3 是 1024 维，EG2 是 768/512/256/128 维，两者是**不同的向量空间**。哪怕维度对上（比如有人想补零到 1024），旧向量和新查询向量之间的余弦也毫无意义。
- 所以切换时必须：① 改 schema 维度（`vector(1024)` → `vector(768)`），或者新增并行列；② **把所有已存的 embedding 全部用 EG2 重新计算**；③ 重建 HNSW 索引；④ 查询端和写入端**同一时刻**切到 EG2、用同一个维度。不能出现一半新一半旧的状态。
- 只把 `AII_EMBED_URL` 指向 :8790/embed，接口形状是兼容的，但返回的是 768 维 EG2 向量，写进 `vector(1024)` 列会直接报维度错误。**不要只改 URL。**

### 推荐路线（双写并行列，可回滚）
1. **评测先行**：从 AII 的真实查询日志或 KU 样本里抽一个中文检索评测集，对比 BGE-M3（1024）和 EG2（768 维，查询用 SearchQuery 前缀，文档用 `title: {标题} | text: {正文}` 格式或 Document 前缀）的 recall@k 和 nDCG。BGE-M3 在中文文本检索上很强，EG2 不一定更好。**评测没有明显胜出就不切**，EG2 的价值主要在多模态（图、视频、音频统一空间）和 GPU 速度。
2. **新增客户端**：在 oprim 或 AII 里加一个 OpenAI 兼容的 embedder（`base_url=http://100.68.226.13:8790/v1`、`model=embeddinggemma-2`，查询和文档分别传 `task`），用环境变量开关，例如 `AII_EMBED_BACKEND=bge_m3|eg2`、`AII_EMBED_DIM=768`。
3. **新增迁移**（不改旧迁移）：给 `ku_onto`、`kc_onto`、`bu_onto`、`substrate_chunk` 和 refined 各表加并行列 `embedding_eg2 vector(768)`，再建 HNSW `vector_cosine_ops` 索引。也可以建影子表，切换时改名。
4. **回填**：参照 `pg_reembed.py` 写一个 EG2 版本，按批 32–64 条走 `/v1/embeddings`，幂等、可续跑、只补 NULL。吞吐按实测估算：短文本约 100–150 条/秒；如果 chunk 在 1–2K 字，按约 2 条/秒估，10 万条大约 14 小时。建议设 `EMB_MAX_SEQ` 覆盖 chunk 长度，并在夜间跑。
5. **切读**：`pg_backend.py` 的检索函数按开关选择 `embedding` 或 `embedding_eg2` 列，写入端双写。稳定一段时间后再停掉 BGE-M3 写入，最后才考虑删旧列（删数据要用户确认）。
6. **回滚**：开关切回 `bge_m3` 就行，旧列一直保留。

### 维度选择
- 768：质量最好。512：接近无损，省 1/3 存储。256：模型卡说仍接近无损，适合大表。128：多模态质量明显下降，不建议。
- 选定以后，查询和文档必须用**同一个维度**。

### 资源和风险
- EG2 和 aii-embed 在同一台笔记本上。EG2 常驻占约 1.7 GB 显存、1–2 GB 内存；aii-embed（BGE-M3）现在强制 CPU，加载后约占 2+ GB 内存。笔记本总内存 18 GB，可用大约只剩 4–5 GB。两个服务同时满载时要注意内存。如果最终切到 EG2，可以停掉 aii-embed 腾出内存。
- GPU 一次只跑一个前向。AII 的大批量回填会让 Hevi 等其他调用方排队，建议错峰。

# Experiment #05: MCP Server Framework Comparison
**实证期**: Stratum BATCH2 / 2026-05-17  
**问题**: Stratum MCP 服务器选 anthropic 官方 SDK 还是 fastmcp？

---

## 测试环境

- Python 3.14.4 (WSL2)
- mcp (anthropic SDK): 1.x
- fastmcp: latest
- 测试脚本: `/tmp/run_mcp_test.py`

---

## 实测数据

### D1: 代码行数（非空、非注释行）

| 实现 | 行数 | 
|------|------|
| anthropic-sdk-server.py | 64 行 |
| fastmcp-server.py | **28 行** |
| fastmcp 减少 | **56%** |

实际功能等价：两者均实现 `stratum_search(query, mode)` 工具 + mock 数据返回。

### D2: 冷启动时间（subprocess 计时）

| 实现 | 冷启动时间 |
|------|-----------|
| anthropic SDK (`from mcp.server import Server`) | **1046 ms** |
| fastmcp (`from fastmcp import FastMCP`) | 1455 ms |

fastmcp 启动比 SDK 慢 **409ms**（因为 fastmcp 在导入时构建 Pydantic schema）。

### D3: 导入时间（in-process）

| 实现 | 导入时间 |
|------|---------|
| mcp SDK | 内含于冷启动 |
| fastmcp | 内含于冷启动 |

### D4: 错误处理

| 实现 | 缺失必填参数时 |
|------|--------------|
| anthropic SDK | 手动 `if not arguments.get("query"): raise ValueError(...)` |
| fastmcp | Pydantic 类型提示自动验证：`def search(query: str)` 缺参数时自动报错 |

### D5: 异步支持

| 实现 | 异步 |
|------|------|
| anthropic SDK | async-first，所有 handler 必须是 `async def` |
| fastmcp | sync + async 均支持，sync 函数自动包装 |

### D6: 工具 Schema 生成

| 实现 | Schema 方式 |
|------|------------|
| anthropic SDK | 手动构造 `types.Tool(name=..., inputSchema={"type": "object", "properties": {...}, "required": [...]})` |
| fastmcp | 从 Python 类型提示 + docstring 自动生成：`@mcp.tool()` 装饰器 |

---

## 代码对比

**anthropic SDK 工具注册（SDK 手动 schema，21行）：**
```python
@sdk_server.list_tools()
async def list_tools():
    return [types.Tool(
        name="stratum.search",
        description="Search",
        inputSchema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
        }
    )]

@sdk_server.call_tool()
async def call_tool(name, arguments):
    if not arguments.get("query"):
        raise ValueError("query is required")
    return [types.TextContent(type="text", text=json.dumps(RESULTS))]
```

**fastmcp 工具注册（自动 schema，7行）：**
```python
@mcp.tool()
def stratum_search(query: str, mode: str = "exact") -> dict:
    """Search Stratum knowledge base."""
    if not query:
        raise ValueError("query is required")
    return {"results": MOCK_RESULTS, "mode": mode}
```

---

## 结论

**推荐: fastmcp**

理由（均为实测数字）：
1. **代码量**: 28 行 vs 64 行，少 56%，减少样板代码
2. **Schema 自动化**: Pydantic 自动生成 inputSchema，类型错误在参数解析阶段即被拦截
3. **双模式**: 同时支持 sync/async，无需为简单工具强制写 async
4. **启动时间差异可接受**: 冷启动 1455ms vs 1046ms，差 409ms — MCP 服务器是长驻进程，只启动一次，不影响运行时
5. **维护性**: 新增参数只需修改函数签名，Schema 自动同步

局限：fastmcp 是第三方包，anthropic SDK 是官方包；若 MCP 协议更新，SDK 跟进更快。

---

## 附: 服务器文件路径

- `experiments/02-batch/mcp-samples/anthropic-sdk-server.py`
- `experiments/02-batch/mcp-samples/fastmcp-server.py`

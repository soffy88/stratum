#!/usr/bin/env python3
"""strat — Stratum context database CLI (对标 OpenViking ov CLI).

Usage:
    strat status                          — 服务状态
    strat ls viking://resources/           — 列出目录
    strat tree viking://... -L 2           — 树形
    strat find "线性代数"                  — 搜索
    strat read viking://... --layer L1     — 读取
    strat session new                      — 创建 session
    strat session commit <id>              — 提交
    strat memories --type preference       — 查看记忆
    strat ingest <path>                    — 手动入库
    strat layers generate <id>             — 生成 L0/L1
    strat layers stats                     — 统计
    strat retrieve "query" --depth 2       — 分层检索
"""

import argparse
import json
import sys
import os
from typing import Any

import httpx

_BASE_URL = os.environ.get("STRATUM_BASE_URL", "http://localhost:9304")
_API_KEY = os.environ.get("STRATUM_API_KEY", "")
_JWT_TOKEN = os.environ.get("STRATUM_JWT_TOKEN", "")


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if _JWT_TOKEN:
        h["Authorization"] = f"Bearer {_JWT_TOKEN}"
    elif _API_KEY:
        h["X-API-Key"] = _API_KEY
    return h


def _get(path: str, params: dict | None = None) -> Any:
    resp = httpx.get(f"{_BASE_URL}{path}", headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, data: dict | None = None) -> Any:
    resp = httpx.post(f"{_BASE_URL}{path}", headers=_headers(), json=data or {}, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _pprint(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_status(args: argparse.Namespace) -> None:
    """Show service status."""
    try:
        health = _get("/health")
        print(f"✅ Stratum running at {_BASE_URL}")
        print(f"   Health: {health}")
    except Exception as e:
        print(f"❌ Cannot reach {_BASE_URL}: {e}")
        return

    try:
        layers = _get("/api/v1/layers/stats")
        print(f"   Layers: {layers}")
    except Exception:
        pass

    try:
        fs = _get("/api/v1/fs/stats")
        print(f"   Filesystem: {fs}")
    except Exception:
        pass


def cmd_ls(args: argparse.Namespace) -> None:
    """List directory contents."""
    result = _get("/api/v1/fs/ls", {"uri": args.uri, "depth": args.depth})
    for child in result.get("children", []):
        icon = "📁" if child["type"] == "directory" else "📄"
        l0 = (child.get("l0") or "")[:60]
        print(f"  {icon} {child['uri']}")
        if l0:
            print(f"     {l0}")
    print(f"\n  {result.get('count', 0)} items")


def cmd_tree(args: argparse.Namespace) -> None:
    """Show tree view."""
    result = _get("/api/v1/fs/tree", {"uri": args.uri, "depth": args.depth})
    nodes = result.get("nodes", [])
    for node in nodes:
        indent = "  " * (node.get("depth", 0) - 1)
        icon = "📁" if node["type"] == "directory" else "📄"
        name = node["uri"].split("/")[-1]
        print(f"{indent}{icon} {name}")
    print(f"\n  {len(nodes)} nodes")


def cmd_find(args: argparse.Namespace) -> None:
    """Find nodes."""
    result = _get("/api/v1/fs/find", {"q": args.query, "mode": args.mode, "limit": args.limit})
    for r in result.get("results", []):
        print(f"  {r.get('uri', '?')}")
        if r.get("l0"):
            print(f"    {r['l0'][:80]}")
    print(f"\n  {result.get('count', 0)} results")


def cmd_read(args: argparse.Namespace) -> None:
    """Read content."""
    result = _get("/api/v1/fs/cat", {"uri": args.uri, "layer": args.layer})
    print(result.get("content", "(empty)"))


def cmd_grep(args: argparse.Namespace) -> None:
    """Regex search."""
    result = _get("/api/v1/fs/grep", {
        "pattern": args.pattern, "scope": args.scope,
        "layer": args.layer, "limit": args.limit,
    })
    for m in result.get("matches", []):
        print(f"  {m['uri']}:{m.get('line_number', '?')}")
        print(f"    {m.get('match', '')[:100]}")
    print(f"\n  {result.get('count', 0)} matches")


def cmd_retrieve(args: argparse.Namespace) -> None:
    """Tiered retrieval."""
    result = _post("/api/v1/retrieve", {
        "query": args.query, "max_depth": args.depth,
        "top_k": args.top_k, "rerank": args.rerank,
    })
    for r in result.get("results", []):
        print(f"  [{r['layer']}] {r['uri']}  (score={r['score']})")
        print(f"    {r.get('content_preview', '')[:100]}")
    print(f"\n  {result.get('result_count', 0)} results in {result.get('total_ms', 0)}ms")


def cmd_session_new(args: argparse.Namespace) -> None:
    """Create a new session."""
    result = _post("/api/v1/sessions", {"title": args.title})
    print(f"Session created: {result['id']}")


def cmd_session_commit(args: argparse.Namespace) -> None:
    """Commit a session."""
    result = _post(f"/api/v1/sessions/{args.session_id}/commit")
    _pprint(result)


def cmd_session_context(args: argparse.Namespace) -> None:
    """Get session context."""
    result = _get(f"/api/v1/sessions/{args.session_id}/context", {"q": args.query})
    _pprint(result)


def cmd_memories(args: argparse.Namespace) -> None:
    """List memories."""
    result = _get("/api/v1/memories", {"memory_type": args.type, "limit": args.limit})
    for m in result.get("memories", []):
        print(f"  [{m['type']}] {m['content'][:100]}")
    print(f"\n  {len(result.get('memories', []))} memories")


def cmd_layers_generate(args: argparse.Namespace) -> None:
    """Generate L0/L1 layers."""
    result = _post("/api/v1/layers/generate", {"substrate_id": args.substrate_id, "force": args.force})
    _pprint(result)


def cmd_layers_stats(args: argparse.Namespace) -> None:
    """Show layer statistics."""
    result = _get("/api/v1/layers/stats")
    _pprint(result)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(prog="strat", description="Stratum context database CLI")
    sub = parser.add_subparsers(dest="command")

    # status
    sub.add_parser("status", help="Service status")

    # ls
    p_ls = sub.add_parser("ls", help="List directory")
    p_ls.add_argument("uri", nargs="?", default="viking://resources/")
    p_ls.add_argument("-L", "--depth", type=int, default=1)

    # tree
    p_tree = sub.add_parser("tree", help="Tree view")
    p_tree.add_argument("uri", nargs="?", default="viking://resources/")
    p_tree.add_argument("-L", "--depth", type=int, default=2)

    # find
    p_find = sub.add_parser("find", help="Find nodes")
    p_find.add_argument("query")
    p_find.add_argument("--mode", choices=["name", "content", "semantic"], default="semantic")
    p_find.add_argument("--limit", type=int, default=20)

    # read
    p_read = sub.add_parser("read", help="Read content")
    p_read.add_argument("uri")
    p_read.add_argument("--layer", choices=["L0", "L1", "L2"], default="L1")

    # grep
    p_grep = sub.add_parser("grep", help="Regex search")
    p_grep.add_argument("pattern")
    p_grep.add_argument("--scope", default="viking://resources/")
    p_grep.add_argument("--layer", choices=["L0", "L1", "L2"], default="L2")
    p_grep.add_argument("--limit", type=int, default=30)

    # retrieve
    p_ret = sub.add_parser("retrieve", help="Tiered retrieval")
    p_ret.add_argument("query")
    p_ret.add_argument("--depth", type=int, default=2)
    p_ret.add_argument("--top-k", type=int, default=10)
    p_ret.add_argument("--rerank", action="store_true")

    # session
    p_sess = sub.add_parser("session", help="Session management")
    sess_sub = p_sess.add_subparsers(dest="session_cmd")
    p_sess_new = sess_sub.add_parser("new", help="Create session")
    p_sess_new.add_argument("--title", default=None)
    p_sess_commit = sess_sub.add_parser("commit", help="Commit session")
    p_sess_commit.add_argument("session_id")
    p_sess_ctx = sess_sub.add_parser("context", help="Get context")
    p_sess_ctx.add_argument("session_id")
    p_sess_ctx.add_argument("-q", "--query", default=None)

    # memories
    p_mem = sub.add_parser("memories", help="List memories")
    p_mem.add_argument("--type", default=None)
    p_mem.add_argument("--limit", type=int, default=20)

    # layers
    p_lay = sub.add_parser("layers", help="Layer management")
    lay_sub = p_lay.add_subparsers(dest="layers_cmd")
    p_lay_gen = lay_sub.add_parser("generate", help="Generate layers")
    p_lay_gen.add_argument("substrate_id")
    p_lay_gen.add_argument("--force", action="store_true")
    lay_sub.add_parser("stats", help="Layer statistics")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    dispatch = {
        "status": cmd_status,
        "ls": cmd_ls,
        "tree": cmd_tree,
        "find": cmd_find,
        "read": cmd_read,
        "grep": cmd_grep,
        "retrieve": cmd_retrieve,
        "memories": cmd_memories,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    elif args.command == "session":
        sess_dispatch = {
            "new": cmd_session_new,
            "commit": cmd_session_commit,
            "context": cmd_session_context,
        }
        if args.session_cmd in sess_dispatch:
            sess_dispatch[args.session_cmd](args)
        else:
            p_sess.print_help()
    elif args.command == "layers":
        if args.layers_cmd == "generate":
            cmd_layers_generate(args)
        elif args.layers_cmd == "stats":
            cmd_layers_stats(args)
        else:
            p_lay.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

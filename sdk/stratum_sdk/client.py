"""StratumClient — Python SDK for the Stratum context database.

Usage:
    from stratum_sdk import StratumClient

    client = StratumClient(base_url="http://localhost:9304", jwt_token="...")

    # Filesystem operations
    nodes = client.fs.ls("viking://resources/")
    tree = client.fs.tree("viking://resources/", depth=2)
    content = client.fs.read("viking://resources/数学/xxx", layer="L1")
    results = client.fs.find("线性代数")
    matches = client.fs.grep("特征值", scope="viking://resources/数学/")

    # Retrieval
    results = client.retrieve("什么是特征值", depth=2, top_k=5)

    # Sessions
    session = client.sessions.create(title="My session")
    session.add_message("user", "Help me understand matrix decomposition")
    context = session.get_context("matrix decomposition")
    session.commit()

    # Memories
    memories = client.memories.list(type="preference")
    relevant = client.memories.search("coding style preferences")
"""

from __future__ import annotations

import json
from typing import Any

import httpx


class StratumClient:
    """Main client for the Stratum context database."""

    def __init__(
        self,
        base_url: str = "http://localhost:9304",
        jwt_token: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._headers: dict[str, str] = {"Content-Type": "application/json"}
        if jwt_token:
            self._headers["Authorization"] = f"Bearer {jwt_token}"
        elif api_key:
            self._headers["X-API-Key"] = api_key

        self._http = httpx.Client(base_url=self.base_url, timeout=timeout)

        self.fs = FileSystemAPI(self)
        self.sessions = SessionAPI(self)
        self.memories = MemoryAPI(self)
        self.layers = LayerAPI(self)

    def _get(self, path: str, params: dict | None = None) -> Any:
        resp = self._http.get(path, headers=self._headers, params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: dict | None = None) -> Any:
        resp = self._http.post(path, headers=self._headers, json=data or {})
        resp.raise_for_status()
        return resp.json()

    def _delete(self, path: str) -> Any:
        resp = self._http.delete(path, headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    def retrieve(self, query: str, depth: int = 2, top_k: int = 10,
                 rerank: bool = False) -> dict:
        """Tiered retrieval with trajectory tracking."""
        return self._post("/api/v1/retrieve", {
            "query": query, "max_depth": depth,
            "top_k": top_k, "rerank": rerank,
        })

    def status(self) -> dict:
        """Get service status."""
        return self._get("/health")


class FileSystemAPI:
    """viking:// virtual filesystem operations."""

    def __init__(self, client: StratumClient):
        self._c = client

    def ls(self, uri: str = "viking://resources/", depth: int = 1) -> list[dict]:
        """List directory contents."""
        result = self._c._get("/api/v1/fs/ls", {"uri": uri, "depth": depth})
        return result.get("children", [])

    def tree(self, uri: str = "viking://resources/", depth: int = 2) -> list[dict]:
        """Get hierarchical tree view."""
        result = self._c._get("/api/v1/fs/tree", {"uri": uri, "depth": depth})
        return result.get("nodes", [])

    def find(self, query: str, mode: str = "semantic", limit: int = 20) -> list[dict]:
        """Find nodes by name, content, or semantic search."""
        result = self._c._get("/api/v1/fs/find", {"q": query, "mode": mode, "limit": limit})
        return result.get("results", [])

    def read(self, uri: str, layer: str = "L1") -> dict:
        """Read content from a node."""
        return self._c._get("/api/v1/fs/cat", {"uri": uri, "layer": layer})

    def stat(self, uri: str) -> dict:
        """Get node metadata."""
        return self._c._get("/api/v1/fs/stat", {"uri": uri})

    def grep(self, pattern: str, scope: str = "viking://resources/",
             layer: str = "L2", limit: int = 30) -> list[dict]:
        """Regex search within scope."""
        result = self._c._get("/api/v1/fs/grep", {
            "pattern": pattern, "scope": scope, "layer": layer, "limit": limit,
        })
        return result.get("matches", [])

    def stats(self) -> dict:
        """Get filesystem statistics."""
        return self._c._get("/api/v1/fs/stats")

    def build(self) -> dict:
        """Build/rebuild directory tree."""
        return self._c._post("/api/v1/fs/build")


class SessionAPI:
    """Agent session management."""

    def __init__(self, client: StratumClient):
        self._c = client

    def create(self, title: str | None = None) -> "SessionHandle":
        """Create a new session."""
        result = self._c._post("/api/v1/sessions", {"title": title})
        return SessionHandle(self._c, result["id"])

    def get(self, session_id: str) -> dict:
        """Get session details."""
        return self._c._get(f"/api/v1/sessions/{session_id}")

    def list(self, status: str | None = None, limit: int = 20) -> list[dict]:
        """List sessions."""
        result = self._c._get("/api/v1/sessions", {"status": status, "limit": limit})
        return result.get("sessions", [])

    def delete(self, session_id: str) -> dict:
        """Delete a session."""
        return self._c._delete(f"/api/v1/sessions/{session_id}")


class SessionHandle:
    """Handle for an active session."""

    def __init__(self, client: StratumClient, session_id: str):
        self._c = client
        self.id = session_id

    def add_message(self, role: str, content: str,
                    parts: list[dict] | None = None) -> dict:
        """Add a message to the session."""
        return self._c._post(f"/api/v1/sessions/{self.id}/messages", {
            "role": role, "content": content, "parts": parts,
        })

    def get_messages(self, limit: int = 50) -> list[dict]:
        """Get session messages."""
        result = self._c._get(f"/api/v1/sessions/{self.id}/messages", {"limit": limit})
        return result.get("messages", [])

    def commit(self) -> dict:
        """Commit: compress + extract memories + update WM."""
        return self._c._post(f"/api/v1/sessions/{self.id}/commit")

    def get_context(self, query: str | None = None,
                    max_tokens: int = 4000) -> dict:
        """Get context for next agent turn."""
        params = {"max_tokens": max_tokens}
        if query:
            params["q"] = query
        return self._c._get(f"/api/v1/sessions/{self.id}/context", params)

    def get_working_memory(self) -> dict:
        """Get Working Memory."""
        return self._c._get(f"/api/v1/sessions/{self.id}/working-memory")

    def archive(self) -> dict:
        """Archive the session."""
        return self._c._post(f"/api/v1/sessions/{self.id}/archive")


class MemoryAPI:
    """Long-term memory operations."""

    def __init__(self, client: StratumClient):
        self._c = client

    def list(self, type: str | None = None, limit: int = 50) -> list[dict]:
        """List memories."""
        result = self._c._get("/api/v1/memories", {"memory_type": type, "limit": limit})
        return result.get("memories", [])

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Semantic search across memories."""
        result = self._c._get("/api/v1/memories/search", {"q": query, "limit": limit})
        return result.get("memories", [])

    def stats(self) -> dict:
        """Memory statistics."""
        return self._c._get("/api/v1/memories/stats")


class LayerAPI:
    """Layer generation operations."""

    def __init__(self, client: StratumClient):
        self._c = client

    def generate(self, substrate_id: str | None = None,
                 ku_id: str | None = None, force: bool = False) -> dict:
        """Generate L0/L1/L2 layers."""
        return self._c._post("/api/v1/layers/generate", {
            "substrate_id": substrate_id, "ku_id": ku_id, "force": force,
        })

    def get_substrate(self, substrate_id: str, layer: str = "L0") -> dict:
        """Get a specific layer for a substrate."""
        return self._c._get(f"/api/v1/layers/substrate/{substrate_id}", {"layer": layer})

    def get_ku(self, ku_id: str, layer: str = "L0") -> dict:
        """Get a specific layer for a KU."""
        return self._c._get(f"/api/v1/layers/ku/{ku_id}", {"layer": layer})

    def stats(self) -> dict:
        """Layer statistics."""
        return self._c._get("/api/v1/layers/stats")

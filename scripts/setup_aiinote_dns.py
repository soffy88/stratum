#!/usr/bin/env python3
"""为 aiinote.com 写入 Cloudflare DNS → **aegis-prod** 隧道。

正确链路(不要改成 aii 独立 tunnel / localhost:3101):
  浏览器
    → Cloudflare (aiinote.com)
    → tunnel **aegis-prod** (3ea896f2-...)
    → **aegis-caddy:8086**   ← 与 aii.kanpan.co 同一条 Caddy 入口
    → aii-web:3101

Caddy 源文件: /data/soffy/projects/aegis/Caddyfile  (:8086 块)

本脚本只补 DNS CNAME; 隧道 ingress 已在 aegis-prod 上配好。
需要 **Zone.DNS.Edit** 的 API Token(隧道 cert token 不够写 DNS)。

  export CLOUDFLARE_API_TOKEN=...
  python3 scripts/setup_aiinote_dns.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

AEGIS_TUNNEL = "3ea896f2-5be2-448e-ad27-338cdf3da4b1"
CNAME_TARGET = f"{AEGIS_TUNNEL}.cfargotunnel.com"
HOSTS = ["aiinote.com", "www.aiinote.com"]


def api(method: str, path: str, token: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {
            "success": False,
            "status": e.code,
            "error": e.read().decode()[:1500],
        }


def main() -> int:
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not token:
        print(
            "缺少 CLOUDFLARE_API_TOKEN。\n"
            "在 Cloudflare Dashboard → My Profile → API Tokens 创建:\n"
            "  Permissions: Zone.DNS Edit + Zone.Zone Read\n"
            "  Zone Resources: Include → Specific zone → aiinote.com\n"
            "然后:\n"
            "  export CLOUDFLARE_API_TOKEN=...\n"
            "  python3 scripts/setup_aiinote_dns.py\n"
            "\n"
            "或在 DNS 面板手动添加(橙云 Proxied):\n"
            f"  CNAME  @    →  {CNAME_TARGET}\n"
            f"  CNAME  www  →  {CNAME_TARGET}\n"
        )
        return 2

    z = api("GET", f"/zones?name={urllib.parse.quote('aiinote.com')}", token)
    if not z.get("success") or not z.get("result"):
        print("找不到 zone aiinote.com:", z.get("error") or z)
        return 1
    zone_id = z["result"][0]["id"]
    print("zone", zone_id)

    for host in HOSTS:
        name = "@" if host == "aiinote.com" else "www"
        # list existing
        q = urllib.parse.quote(host)
        existing = api("GET", f"/zones/{zone_id}/dns_records?name={q}", token)
        recs = existing.get("result") or []
        payload = {
            "type": "CNAME",
            "name": name if host == "aiinote.com" else host,
            "content": CNAME_TARGET,
            "proxied": True,
            "ttl": 1,
        }
        # apex often needs name=aiinote.com
        if host == "aiinote.com":
            payload["name"] = "aiinote.com"

        if recs:
            rid = recs[0]["id"]
            res = api("PUT", f"/zones/{zone_id}/dns_records/{rid}", token, payload)
            print("update", host, res.get("success"), res.get("error", "")[:200])
        else:
            res = api("POST", f"/zones/{zone_id}/dns_records", token, payload)
            print("create", host, res.get("success"), res.get("error", "")[:200])

    print("done. wait ~30s then: curl -I https://aiinote.com")
    return 0


if __name__ == "__main__":
    sys.exit(main())

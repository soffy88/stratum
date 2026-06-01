"""WeChat Official Account (MP) ingest gateway."""

import asyncio
import hashlib
import os
import sys
import defusedxml.ElementTree as ET  # stdlib ET is vulnerable to XXE / billion-laughs
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from stratum.common import generate_ulid, now_utc, sha256_hex, ensure_dir
from stratum.db import insert

WECHAT_TOKEN = os.environ.get("STRATUM_WECHAT_TOKEN", "")
STRATUM_API = os.environ.get("STRATUM_API_URL", "http://stratum-api:9302")

app = FastAPI(title="Stratum WeChat MP Gateway")


def _verify_wechat_signature(signature: str, timestamp: str, nonce: str) -> bool:
    if not WECHAT_TOKEN:
        return False
    items = sorted([WECHAT_TOKEN, timestamp, nonce])
    digest = hashlib.sha1("".join(items).encode()).hexdigest()
    return digest == signature


@app.get("/wechat/mp/callback")
async def verify(
    signature: str = Query(""),
    timestamp: str = Query(""),
    nonce: str = Query(""),
    echostr: str = Query(""),
) -> PlainTextResponse:
    if _verify_wechat_signature(signature, timestamp, nonce):
        return PlainTextResponse(echostr)
    raise HTTPException(403, "Invalid signature")


@app.post("/wechat/mp/callback")
async def handle_message(request: Request) -> PlainTextResponse:
    body = await request.body()
    try:
        root = ET.fromstring(body.decode())
    except ET.ParseError:
        return PlainTextResponse("success")

    def get(tag: str) -> str:
        el = root.find(tag)
        return el.text or "" if el is not None else ""

    msg_type = get("MsgType")
    from_user = get("FromUserName")
    content = get("Content")

    def xml_reply(text: str) -> str:
        ts = int(__import__("time").time())
        return (
            f"<xml>"
            f"<ToUserName><![CDATA[{from_user}]]></ToUserName>"
            f"<FromUserName><![CDATA[{get('ToUserName')}]]></FromUserName>"
            f"<CreateTime>{ts}</CreateTime>"
            f"<MsgType><![CDATA[text]]></MsgType>"
            f"<Content><![CDATA[{text}]]></Content>"
            f"</xml>"
        )

    if msg_type == "text":
        reply = f"收到: {content[:50]} — 搜索和入库功能即将上线。"
        return PlainTextResponse(xml_reply(reply), media_type="text/xml")

    elif msg_type in ("image", "voice", "video"):
        # Record as inbox item
        media_id = get("MediaId")
        insert(
            "changefeed",
            {
                "event_id": generate_ulid(),
                "user_id": from_user,
                "device_id": "wechat_mp",
                "event_type": "wechat_media_received",
                "payload": {"msg_type": msg_type, "media_id": media_id},
            },
        )
        reply = f"已收到{msg_type}，正在处理入库。"
        return PlainTextResponse(xml_reply(reply), media_type="text/xml")

    return PlainTextResponse("success")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)

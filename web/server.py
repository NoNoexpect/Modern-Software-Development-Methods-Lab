"""Web 服务：用 FastAPI 把智能体包装成浏览器可访问的界面。

启动：
    python -m uvicorn web.server:app --host 127.0.0.1 --port 8000
然后浏览器打开 http://127.0.0.1:8000

后端复用与 CLI 完全相同的编排链路（MCP Client + run_turn），
只是把过程事件以 SSE 流推送给前端。
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse

from agent import llm, prompt
from agent.loop import run_turn
from agent.mcp_client import connect_server
from agent.tools_adapter import mcp_tools_to_openai

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="个人研究助理")
_client = llm.build_client()

# 单用户演示：进程内保存一份对话历史
_history: list[dict[str, Any]] = [{"role": "system", "content": prompt.SYSTEM_PROMPT}]


@app.get("/")
async def index() -> FileResponse:
    """返回单页界面。"""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/tools")
async def list_skills() -> dict[str, list[dict[str, str]]]:
    """列出 MCP Server 当前注册的技能，供界面顶部展示。"""
    async with connect_server() as session:
        items = mcp_tools_to_openai((await session.list_tools()).tools)
    return {
        "tools": [
            {
                "name": item["function"]["name"],
                "description": item["function"]["description"].splitlines()[0],
            }
            for item in items
        ]
    }


@app.post("/api/reset")
async def reset() -> dict[str, str]:
    """清空对话上下文。"""
    _history.clear()
    _history.append({"role": "system", "content": prompt.SYSTEM_PROMPT})
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(payload: dict[str, Any]) -> StreamingResponse:
    """接收提问，以 SSE 流式返回编排过程与最终答复。"""
    message = str(payload.get("message", "")).strip()
    body = _stream(message) if message else _done_only()
    return StreamingResponse(
        body,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _done_only() -> AsyncIterator[str]:
    """空提问时直接结束。"""
    yield _sse({"type": "done"})


async def _stream(message: str) -> AsyncIterator[str]:
    """把编排事件经队列转成 SSE 数据流。"""
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def worker() -> None:
        """在独立任务中跑完一轮对话，事件写入队列。"""
        try:
            async with connect_server() as session:
                tools = mcp_tools_to_openai((await session.list_tools()).tools)
                _history.append({"role": "user", "content": message})
                await run_turn(session, _client, _history, tools, on_event=queue.put_nowait)
        except Exception as exc:  # 任何异常都要让前端看到原因
            queue.put_nowait({"type": "error", "content": f"{type(exc).__name__}: {exc}"})
        finally:
            queue.put_nowait({"type": "done"})

    task = asyncio.create_task(worker())
    try:
        while True:
            event = await queue.get()
            yield _sse(event)
            if event.get("type") == "done":
                break
    finally:
        await task


def _sse(event: dict[str, Any]) -> str:
    """按 SSE 规范格式化一条事件。"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

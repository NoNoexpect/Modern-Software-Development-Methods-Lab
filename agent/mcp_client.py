"""MCP 客户端：以子进程 stdio 方式连接本地 MCP Server。

智能体（MCP Client）与技能服务（MCP Server）是两个独立进程，
通过标准化的 JSON-RPC 协议通信，因此该 Server 也可直接被 Cursor 等客户端复用。
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

import config
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def _child_env() -> dict[str, str]:
    """构造子进程环境变量，继承当前环境并同步工作区路径。"""
    env = dict(os.environ)
    env["WORKSPACE_DIR"] = str(config.WORKSPACE_DIR)
    # 确保子进程能 import 项目内的 config 与 mcp_server 包
    env["PYTHONPATH"] = str(config.BASE_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    return env


@asynccontextmanager
async def connect_server() -> AsyncIterator[ClientSession]:
    """启动 MCP Server 子进程并完成初始化握手。

    用法：
        async with connect_server() as session:
            tools = await session.list_tools()
            result = await session.call_tool("web_search", {"query": "..."})
    """
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", config.MCP_SERVER_MODULE],
        env=_child_env(),
        cwd=str(config.BASE_DIR),
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session

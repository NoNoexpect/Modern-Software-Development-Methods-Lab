"""MCP Server 入口：以标准化协议把技能工具暴露给智能体或其他 MCP 客户端。

启动方式：
    python -m mcp_server.server        # stdio 模式，供智能体 / Cursor 接入
"""

from __future__ import annotations

import logging

from mcp.server.mcpserver import MCPServer

from mcp_server.tools import data, database, files, notes, web

# 子进程的 stderr 会回显给客户端，降低 httpx 的请求日志噪音
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# 创建 MCP 服务实例；名称会出现在客户端的工具列表中
mcp = MCPServer("study-research-copilot")

# 注册全部技能工具（每个工具模块自带 register 函数，避免循环依赖）
files.register(mcp)
web.register(mcp)
data.register(mcp)
database.register(mcp)
notes.register(mcp)


def main() -> None:
    """以 stdio 传输方式运行 MCP 服务，等待客户端握手。"""
    mcp.run()


if __name__ == "__main__":
    main()

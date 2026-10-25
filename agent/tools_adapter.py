"""工具适配层：把 MCP 工具描述转换为 DeepSeek 可识别的函数调用 schema。

关键点：函数 schema 完全由 MCP 服务端的 tools/list 动态生成，
不需要为每个技能手写 JSON Schema —— 这正是使用标准化协议的价值。
"""

from __future__ import annotations

from typing import Any

# 工具无参数时的兜底 schema
EMPTY_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}}


def mcp_tools_to_openai(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    """把 MCP 工具列表转换为 OpenAI 风格的 tools 参数。

    Args:
        mcp_tools: MCP `session.list_tools()` 返回的 Tool 对象列表。

    Returns:
        可直接传给 chat.completions.create(tools=...) 的结构。
    """
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": (tool.description or tool.name).strip(),
                "parameters": tool.input_schema or EMPTY_SCHEMA,
            },
        }
        for tool in mcp_tools
    ]

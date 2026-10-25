"""智能体编排循环：模型思考 → 调用 MCP 技能 → 汇总回答。

循环逻辑是本项目的核心：
1. 把对话历史 + 动态生成的工具 schema 交给 DeepSeek；
2. 模型若返回 tool_calls，则逐个通过 MCP 协议执行；
3. 把工具结果回填到消息列表，再次请求模型，直到模型直接给出自然语言答复。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from mcp import ClientSession
from openai import AsyncOpenAI

import config

# 事件回调：把编排过程中的每一步推送给调用方（CLI 打印 / Web 推送）
EventCallback = Callable[[dict[str, Any]], None]


async def run_turn(
    session: ClientSession,
    client: AsyncOpenAI,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    on_event: EventCallback | None = None,
) -> str:
    """执行一轮完整推理，返回最终自然语言答复。

    Args:
        session: 已初始化的 MCP 客户端会话。
        client: DeepSeek 异步客户端。
        messages: 对话消息列表，函数会就地追加 assistant/tool 消息。
        tools: 由 MCP 工具动态转换得到的函数调用 schema。
        on_event: 可选事件回调，实时上报技能调用与最终答复。
    """
    for _ in range(config.MAX_ITERATIONS):
        response = await client.chat.completions.create(
            model=config.DEEPSEEK_MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.3,
        )
        message = response.choices[0].message

        # 模型没有请求工具 → 说明已经准备好最终答复
        if not message.tool_calls:
            answer = (message.content or "").strip()
            messages.append({"role": "assistant", "content": answer})
            _emit(on_event, {"type": "final", "content": answer})
            return answer

        # 记录模型的决定（含工具调用意图），供下一轮上下文使用
        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [call.model_dump() for call in message.tool_calls],
            }
        )

        # 逐个执行工具调用，并把结果回填
        for call in message.tool_calls:
            arguments = _parse_arguments(call.function.arguments)
            _trace_call(call.function.name, arguments)
            _emit(
                on_event,
                {"type": "tool_call", "name": call.function.name, "arguments": arguments},
            )
            output = await call_tool(session, call.function.name, arguments)
            _emit(
                on_event,
                {
                    "type": "tool_result",
                    "name": call.function.name,
                    "preview": _preview(output),
                },
            )
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": output}
            )

    fallback = "已达最大工具调用轮数，任务尚未完成。建议缩小问题范围后重试。"
    _emit(on_event, {"type": "final", "content": fallback})
    return fallback


async def call_tool(session: ClientSession, name: str, arguments: dict[str, Any]) -> str:
    """通过 MCP 协议调用技能，并把返回内容归一化为纯文本。"""
    try:
        result = await session.call_tool(name, arguments)
    except Exception as exc:
        return f"[技能 {name} 调用异常] {type(exc).__name__}: {exc}"
    return _content_to_text(name, result)


def _content_to_text(name: str, result: Any) -> str:
    """从 MCP 工具返回的 content 列表中提取文本。"""
    parts = [block.text for block in result.content if getattr(block, "text", None)]
    text = "\n".join(parts) if parts else "(工具无文本输出)"
    if getattr(result, "is_error", False):
        return f"[技能 {name} 执行失败] {text}"
    return text


def _parse_arguments(raw: str | None) -> dict[str, Any]:
    """解析模型给出的工具参数 JSON，异常时退化为空参数。"""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _trace_call(name: str, arguments: dict[str, Any]) -> None:
    """在终端打印工具调用轨迹，便于观察编排过程。"""
    preview = json.dumps(arguments, ensure_ascii=False)
    if len(preview) > 120:
        preview = f"{preview[:120]}..."
    print(f"  [技能调用] {name} {preview}")


def _emit(on_event: EventCallback | None, event: dict[str, Any]) -> None:
    """安全触发事件回调，回调异常不应影响编排主流程。"""
    if on_event is None:
        return
    try:
        on_event(event)
    except Exception:
        pass


def _preview(text: str, limit: int = 200) -> str:
    """截取工具输出的开头片段，用于界面上的结果预览。"""
    flat = text.strip().replace("\n", " ")
    return flat if len(flat) <= limit else f"{flat[:limit]}..."

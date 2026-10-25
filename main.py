"""命令行入口：连接本地 MCP Server，并驱动 DeepSeek 智能体对话循环。

用法：
    python main.py                 # 交互模式
    python main.py "帮我总结 workspace 里的资料"   # 单次提问
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

import config
from agent import llm, prompt
from agent.loop import run_turn
from agent.mcp_client import connect_server
from agent.tools_adapter import mcp_tools_to_openai

HELP_TEXT = """可用命令：
  /tools   查看当前加载的 MCP 技能
  /reset   清空对话上下文
  /exit    退出
"""


def _force_utf8_stdout() -> None:
    """保证 Windows 控制台能正常输出中文。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


async def _turn(
    session: Any,
    client: Any,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    user_input: str,
) -> None:
    """执行一轮用户提问。"""
    messages.append({"role": "user", "content": user_input})
    print("\n助手正在思考...")
    answer = await run_turn(session, client, messages, tools)
    print(f"\n助手 > {answer}\n")


async def run(question: str | None) -> None:
    """连接 MCP Server，按单次提问或交互模式运行。"""
    client = llm.build_client()

    async with connect_server() as session:
        tool_list = (await session.list_tools()).tools
        tools = mcp_tools_to_openai(tool_list)

        print(f"MCP Server 已连接，加载技能 {len(tools)} 个：")
        for item in tools:
            print(f"  - {item['function']['name']}")
        print(f"资料工作区：{config.WORKSPACE_DIR}\n")

        messages: list[dict[str, Any]] = [{"role": "system", "content": prompt.SYSTEM_PROMPT}]

        if question:
            await _turn(session, client, messages, tools, question)
            return

        print(HELP_TEXT)
        while True:
            try:
                user_input = input("你 > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not user_input:
                continue
            if user_input in {"/exit", "/quit"}:
                break
            if user_input == "/help":
                print(HELP_TEXT)
                continue
            if user_input == "/tools":
                for item in tools:
                    first_line = item["function"]["description"].splitlines()[0]
                    print(f"  - {item['function']['name']}: {first_line}")
                print()
                continue
            if user_input == "/reset":
                messages = [{"role": "system", "content": prompt.SYSTEM_PROMPT}]
                print("对话上下文已清空。\n")
                continue
            await _turn(session, client, messages, tools, user_input)


def main() -> None:
    _force_utf8_stdout()
    parser = argparse.ArgumentParser(description="个人研究助理：MCP + DeepSeek 智能体")
    parser.add_argument("question", nargs="*", help="直接提问，留空则进入交互模式")
    args = parser.parse_args()
    question = " ".join(args.question).strip() or None

    try:
        asyncio.run(run(question))
    except KeyboardInterrupt:
        print("\n已退出。")
    except RuntimeError as exc:
        print(f"启动失败：{exc}")


if __name__ == "__main__":
    main()

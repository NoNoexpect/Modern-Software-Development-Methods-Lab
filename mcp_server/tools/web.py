"""联网类技能：网页检索与正文抓取。

检索使用 DuckDuckGo 的免密钥 HTML 接口；抓取使用 httpx + BeautifulSoup 提取正文。
"""

from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlparse

import config
import httpx
from bs4 import BeautifulSoup
from mcp.server.mcpserver import MCPServer

from mcp_server.tools.common import truncate

# 统一 UA，避免被站点直接拒绝
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
DDG_HTML_ENDPOINT = "https://html.duckduckgo.com/html/"
REQUEST_TIMEOUT = 20.0


def web_search(query: str, max_results: int = 5) -> str:
    """联网检索网页，返回标题、链接与摘要，供进一步抓取正文。

    Args:
        query: 检索关键词，建议用自然语言描述你要查的内容。
        max_results: 返回结果条数，默认 5 条。
    """
    try:
        response = httpx.post(
            DDG_HTML_ENDPOINT,
            data={"q": query},
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
        )
        response.raise_for_status()
    except Exception as exc:  # 网络异常不应中断智能体流程
        return f"检索失败（{type(exc).__name__}）：{exc}"

    soup = BeautifulSoup(response.text, "html.parser")
    nodes = soup.select(".result")[: max(1, max_results)]
    if not nodes:
        return "未检索到结果，可尝试更换关键词。"

    lines = [f"检索词：{query}", f"共 {len(nodes)} 条结果："]
    for index, node in enumerate(nodes, start=1):
        link_node = node.select_one(".result__a")
        snippet_node = node.select_one(".result__snippet")
        if link_node is None:
            continue
        title = link_node.get_text(" ", strip=True)
        url = _normalize_ddg_url(link_node.get("href", ""))
        snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
        lines.append(f"{index}. {title}\n   链接：{url}\n   摘要：{snippet}")
    return "\n".join(lines)


def fetch_webpage(url: str, max_chars: int = config.MAX_TOOL_CHARS) -> str:
    """抓取指定网页并提取可读正文，用于读取搜索结果详情。

    Args:
        url: 目标网页地址，必须以 http:// 或 https:// 开头。
        max_chars: 返回正文的最大字符数，超出部分会被截断。
    """
    if urlparse(url).scheme not in {"http", "https"}:
        return f"无效链接（仅支持 http/https）：{url}"
    try:
        response = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
        )
        response.raise_for_status()
    except Exception as exc:
        return f"抓取失败（{type(exc).__name__}）：{exc}"

    # 根据响应头判断编码，避免中文乱码
    encoding = response.encoding or "utf-8"
    soup = BeautifulSoup(response.content.decode(encoding, errors="ignore"), "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside", "form"]):
        tag.decompose()

    title = soup.title.get_text(strip=True) if soup.title else url
    text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
    return truncate(f"标题：{title}\n链接：{url}\n\n{text}", max_chars)


def register(mcp: MCPServer) -> None:
    """把本模块的技能注册到 MCP 服务。"""
    mcp.tool()(web_search)
    mcp.tool()(fetch_webpage)


def _normalize_ddg_url(href: str) -> str:
    """还原 DuckDuckGo 跳转链接中的真实地址。"""
    if not href:
        return ""
    if href.startswith("//"):
        href = f"https:{href}"
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg")
        if target:
            return unquote(target[0])
    return href

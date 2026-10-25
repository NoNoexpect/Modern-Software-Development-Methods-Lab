"""数据库类技能：把检索到的论文结构化写入 MySQL，并支持查询与统计。

这是「论文爬取 → 分析 → 入库」链路的落点：
智能体先用 web_search / fetch_webpage 拿到论文信息，分析后调用本模块写入数据库，
再通过查询与统计技能核对入库结果。

连接信息统一从 .env 读取（见 config.py），与 MCP Server 同进程运行。
"""

from __future__ import annotations

from typing import Any

import config
import pymysql
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

# 论文信息表：标题唯一，重复入库时自动更新其余字段
PAPERS_DDL = """
CREATE TABLE IF NOT EXISTS papers (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    title       VARCHAR(512) NOT NULL                COMMENT '论文标题',
    authors     VARCHAR(512) NOT NULL DEFAULT ''     COMMENT '作者',
    venue       VARCHAR(255) NOT NULL DEFAULT ''     COMMENT '来源期刊或会议',
    year        INT          NULL                    COMMENT '发表年份',
    url         VARCHAR(768) NOT NULL DEFAULT ''     COMMENT '原文链接',
    abstract    TEXT                                 COMMENT '摘要',
    keywords    VARCHAR(512) NOT NULL DEFAULT ''     COMMENT '关键词',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_title (title(191))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '论文信息表'
"""

# 复用的连接对象：MCP 服务以单进程顺序调用技能，无需连接池
_connection: pymysql.connections.Connection | None = None


def save_paper(
    title: str,
    authors: str = "",
    venue: str = "",
    year: int = 0,
    url: str = "",
    abstract: str = "",
    keywords: str = "",
) -> str:
    """把一篇论文的结构化信息写入 MySQL 的 papers 表（按标题去重，重复则更新）。

    调用前应先用 web_search / fetch_webpage 拿到论文的真实信息，不要凭记忆编造。

    Args:
        title: 论文标题，必填，作为去重依据。
        authors: 作者，多人用逗号分隔。
        venue: 来源期刊或会议名称。
        year: 发表年份，未知填 0。
        url: 原文链接。
        abstract: 摘要正文。
        keywords: 关键词，多个用逗号分隔。
    """
    if not title.strip():
        raise ToolError("title 不能为空：入库必须提供论文标题")

    connection = _connect()
    sql = (
        "INSERT INTO papers (title, authors, venue, year, url, abstract, keywords) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE authors = VALUES(authors), venue = VALUES(venue), "
        "year = VALUES(year), url = VALUES(url), abstract = VALUES(abstract), "
        "keywords = VALUES(keywords)"
    )
    params = (
        title.strip()[:512],
        authors.strip()[:512],
        venue.strip()[:255],
        year or None,
        url.strip()[:768],
        abstract.strip(),
        keywords.strip()[:512],
    )
    with connection.cursor() as cursor:
        try:
            cursor.execute(sql, params)
        except pymysql.MySQLError as exc:
            raise ToolError(f"论文入库失败：{exc}") from exc
    total = _scalar(connection, "SELECT COUNT(*) FROM papers")
    return (
        f"论文已入库：{title.strip()}（{venue or '来源未知'}，{year or '年份未知'}）\n"
        f"当前 papers 表共 {total} 条记录。"
    )


def query_papers(
    keyword: str = "",
    year_from: int = 0,
    year_to: int = 0,
    limit: int = 20,
) -> str:
    """按关键词与年份区间查询已入库的论文，返回可读列表。

    Args:
        keyword: 关键词，会在标题、作者、关键词字段中模糊匹配，留空表示不限。
        year_from: 起始年份（含），0 表示不限。
        year_to: 结束年份（含），0 表示不限。
        limit: 最多返回条数，默认 20。
    """
    connection = _connect()
    conditions: list[str] = []
    params: list[Any] = []
    if keyword.strip():
        conditions.append("(title LIKE %s OR authors LIKE %s OR keywords LIKE %s)")
        like = f"%{keyword.strip()}%"
        params.extend([like, like, like])
    if year_from:
        conditions.append("year >= %s")
        params.append(year_from)
    if year_to:
        conditions.append("year <= %s")
        params.append(year_to)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = (
        f"SELECT id, title, authors, venue, year, url, keywords FROM papers {where} "
        f"ORDER BY year DESC, id DESC LIMIT %s"
    )
    params.append(max(1, limit))

    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall()
    if not rows:
        return "未查询到匹配的论文记录。"

    lines = [f"共 {len(rows)} 条记录："]
    for row in rows:
        lines.append(
            f"- [id={row[0]}] {row[1]}｜{row[2] or '作者未知'}｜{row[3] or '来源未知'}"
            f"｜{row[4] or '年份未知'}｜关键词：{row[6] or '无'}\n  链接：{row[5] or '无'}"
        )
    return "\n".join(lines)


def paper_statistics() -> str:
    """统计 papers 表的整体情况：总数、年份分布与来源分布。

    用于入库后核对结果，或回答"存了多少篇、都集中在哪些年份"这类问题。
    """
    connection = _connect()
    total = _scalar(connection, "SELECT COUNT(*) FROM papers")
    if not total:
        return "papers 表当前为空，尚无论文入库。"

    lines = [f"论文总数：{total} 篇"]
    lines.append("按年份分布：")
    lines.extend(_group_lines(connection, "year", "年份"))
    lines.append("按来源分布：")
    lines.extend(_group_lines(connection, "venue", "来源", limit=5))
    return "\n".join(lines)


def register(mcp: MCPServer) -> None:
    """把本模块的技能注册到 MCP 服务。"""
    mcp.tool()(save_paper)
    mcp.tool()(query_papers)
    mcp.tool()(paper_statistics)


def _connect() -> pymysql.connections.Connection:
    """获取可用的 MySQL 连接，必要时自动重连并确保库表存在。"""
    global _connection
    if _connection is not None:
        try:
            _connection.ping(reconnect=True)
            return _connection
        except Exception:  # 连接已失效，走下面的重建流程
            _connection = None

    try:
        connection = pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            charset="utf8mb4",
            autocommit=True,
            connect_timeout=config.MYSQL_TIMEOUT,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{config.MYSQL_DATABASE}` "
                f"DEFAULT CHARACTER SET utf8mb4"
            )
        connection.select_db(config.MYSQL_DATABASE)
        with connection.cursor() as cursor:
            cursor.execute(PAPERS_DDL)
    except Exception as exc:
        raise ToolError(
            f"MySQL 不可用（{type(exc).__name__}: {exc}）："
            f"请检查 .env 中的 MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_PASSWORD"
        ) from exc

    _connection = connection
    return connection


def _scalar(connection: pymysql.connections.Connection, sql: str) -> int:
    """执行只返回单个数值的统计查询。"""
    with connection.cursor() as cursor:
        cursor.execute(sql)
        row = cursor.fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def _group_lines(
    connection: pymysql.connections.Connection,
    column: str,
    unit: str,
    limit: int = 10,
) -> list[str]:
    """按指定列分组计数，返回可读的分布明细。"""
    sql = (
        f"SELECT IFNULL({column}, '未填写'), COUNT(*) FROM papers "
        f"GROUP BY {column} ORDER BY COUNT(*) DESC LIMIT %s"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, [limit])
        rows = cursor.fetchall()
    return [f"  {row[0]}（{unit}）：{row[1]} 篇" for row in rows]

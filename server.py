#!/usr/bin/env python3
"""AKShare MCP Server - 基于 akshare 的金融数据 MCP 服务器。

提供A股、指数等金融数据查询工具，数据来自公开数据源（新浪财经等）。
仅供技术研究与学习使用，不构成投资建议。
"""
from __future__ import annotations

import json
import sys
from typing import Optional

try:
    from fastmcp import FastMCP
except ImportError:
    print("错误: 未安装 fastmcp，请运行: pip install fastmcp", file=sys.stderr)
    sys.exit(1)

try:
    import akshare as ak
    import pandas as pd
except ImportError:
    print("错误: 未安装 akshare，请运行: pip install akshare pandas", file=sys.stderr)
    sys.exit(1)


def _df_to_records(df: pd.DataFrame, limit: Optional[int] = None) -> list[dict]:
    """将 DataFrame 转为字典列表，处理 NaN 值。"""
    import datetime as _dt
    if df is None or df.empty:
        return []
    if limit and len(df) > limit:
        df = df.tail(limit)
    data = []
    for _, row in df.iterrows():
        item = {}
        for col in df.columns:
            val = row[col]
            if pd.isna(val):
                item[col] = None
            elif isinstance(val, (pd.Timestamp, _dt.date, _dt.datetime)) and not pd.isna(val):
                if hasattr(val, 'date') and callable(val.date):
                    item[col] = str(val.date())
                else:
                    item[col] = str(val)
            elif hasattr(val, 'item'):
                try:
                    item[col] = val.item()
                except Exception:
                    item[col] = str(val)
            else:
                item[col] = val
        data.append(item)
    return data


mcp = FastMCP("akshare")


@mcp.tool(description="获取A股个股日线历史行情数据（前复权），数据来自新浪财经")
def stock_zh_a_daily(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 500,
) -> str:
    """获取A股个股日线历史行情。

    Args:
        symbol: 股票代码，如 sh600519、sz000001、600519、000001
        start_date: 起始日期，格式 YYYY-MM-DD 或 YYYYMMDD，可选
        end_date: 结束日期，格式 YYYY-MM-DD 或 YYYYMMDD，可选，默认今天
        limit: 返回数据条数限制（取最近N条），默认 500

    Returns:
        JSON 格式的K线数据，包含 date/open/high/low/close/volume
    """
    try:
        s = symbol.lower()
        if s.startswith("sh") or s.startswith("sz"):
            code = s
        elif s.endswith(".sh") or s.endswith(".sz"):
            code = s[-2:] + s[:-3]
        else:
            if len(s) == 6 and (s[0] in "6" or s[:2] in ("68", "90", "11", "13", "51")):
                code = "sh" + s
            else:
                code = "sz" + s
        df = ak.stock_zh_a_daily(symbol=code, adjust="qfq")
        if df is None or df.empty:
            return json.dumps({"ok": False, "error": "未获取到数据，请检查代码是否正确"}, ensure_ascii=False)

        df = df.sort_values("date").reset_index(drop=True)

        if start_date:
            sd = start_date.replace("-", "")
            df = df[df["date"].astype(str).str.replace("-", "") >= sd]
        if end_date:
            ed = end_date.replace("-", "")
            df = df[df["date"].astype(str).str.replace("-", "") <= ed]

        data = _df_to_records(df, limit)
        return json.dumps({
            "ok": True,
            "symbol": symbol,
            "source": "sina",
            "count": len(data),
            "start": data[0]["date"] if data else None,
            "end": data[-1]["date"] if data else None,
            "bars": data,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False)


@mcp.tool(description="获取A股指数日线历史行情数据，数据来自新浪财经")
def stock_zh_index_daily(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 500,
) -> str:
    """获取A股指数日线历史行情。

    Args:
        symbol: 指数代码，如 sh000001、sh000102、sz399001
        start_date: 起始日期，格式 YYYY-MM-DD 或 YYYYMMDD，可选
        end_date: 结束日期，格式 YYYY-MM-DD 或 YYYYMMDD，可选，默认今天
        limit: 返回数据条数限制（取最近N条），默认 500

    Returns:
        JSON 格式的K线数据，包含 date/open/high/low/close/volume
    """
    try:
        df = ak.stock_zh_index_daily(symbol=symbol)
        if df is None or df.empty:
            return json.dumps({"ok": False, "error": "未获取到数据，请检查代码是否正确"}, ensure_ascii=False)

        df = df.sort_values("date").reset_index(drop=True)

        if start_date:
            sd = start_date.replace("-", "")
            df = df[df["date"].astype(str).str.replace("-", "") >= sd]
        if end_date:
            ed = end_date.replace("-", "")
            df = df[df["date"].astype(str).str.replace("-", "") <= ed]

        data = _df_to_records(df, limit)
        return json.dumps({
            "ok": True,
            "symbol": symbol,
            "source": "sina",
            "count": len(data),
            "start": data[0]["date"] if data else None,
            "end": data[-1]["date"] if data else None,
            "bars": data,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False)


def _get_sina_spot(symbols: list[str]) -> list[dict]:
    """从新浪财经获取实时行情。"""
    try:
        from curl_cffi import requests
    except ImportError:
        import requests as requests

    code_list = []
    for sym in symbols:
        s = sym.lower().replace(".sh", "").replace(".sz", "")
        if s.startswith("sh") or s.startswith("sz"):
            code_list.append(s)
        elif len(s) == 6:
            if s[0] in "6" or s[:2] in ("68", "90", "51", "11", "13"):
                code_list.append("sh" + s)
            else:
                code_list.append("sz" + s)
        else:
            code_list.append(sym)

    url = "https://hq.sinajs.cn/list=" + ",".join(code_list)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Referer": "https://finance.sina.com.cn/",
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
    except Exception:
        return []

    results = []
    lines = r.text.strip().split("\n")
    for i, line in enumerate(lines):
        if "=" not in line:
            continue
        code_part, data_part = line.split("=", 1)
        code = code_part.replace("var hq_str_", "").strip()
        data_str = data_part.strip().strip('"')
        if not data_str:
            continue
        fields = data_str.split(",")
        if len(fields) < 32:
            continue

        name = fields[0]
        open_price = float(fields[1]) if fields[1] else 0
        prev_close = float(fields[2]) if fields[2] else 0
        price = float(fields[3]) if fields[3] else 0
        high = float(fields[4]) if fields[4] else 0
        low = float(fields[5]) if fields[5] else 0
        volume = float(fields[8]) if fields[8] else 0
        amount = float(fields[9]) if fields[9] else 0

        change = price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0

        results.append({
            "代码": code,
            "名称": name,
            "最新价": round(price, 2),
            "涨跌额": round(change, 2),
            "涨跌幅": round(change_pct, 2),
            "今开": round(open_price, 2),
            "最高": round(high, 2),
            "最低": round(low, 2),
            "昨收": round(prev_close, 2),
            "成交量": volume,
            "成交额": amount,
            "source": "sina",
        })

    return results


@mcp.tool(description="获取A股指数实时行情列表，支持多源 fallback（新浪/东方财富）")
def stock_zh_index_spot() -> str:
    """获取A股指数实时行情。

    Returns:
        JSON 格式的指数实时行情列表
    """
    try:
        try:
            df = ak.stock_zh_index_spot_em()
            data = _df_to_records(df)
            if data:
                return json.dumps({
                    "ok": True,
                    "source": "eastmoney",
                    "count": len(data),
                    "data": data[:100],
                }, ensure_ascii=False)
        except Exception:
            pass

        try:
            df = ak.stock_zh_index_spot_sina()
            data = _df_to_records(df)
            if data:
                return json.dumps({
                    "ok": True,
                    "source": "sina",
                    "count": len(data),
                    "data": data[:100],
                }, ensure_ascii=False)
        except Exception:
            pass

        index_codes = [
            "sh000001", "sh000002", "sh000003", "sh000300", "sh000905",
            "sz399001", "sz399006", "sz399005", "sh000688", "sh000016",
        ]
        data = _get_sina_spot(index_codes)
        if data:
            return json.dumps({
                "ok": True,
                "source": "sina",
                "count": len(data),
                "data": data,
            }, ensure_ascii=False)

        return json.dumps({"ok": False, "error": "所有数据源均失败"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False)


@mcp.tool(description="获取A股个股实时行情，支持单只或多只股票，多源 fallback")
def stock_zh_a_spot(symbols: Optional[str] = None) -> str:
    """获取A股实时行情。

    Args:
        symbols: 股票代码，多个用逗号分隔，如 sh600519,sz000001,600519

    Returns:
        JSON 格式的实时行情数据
    """
    try:
        if not symbols:
            try:
                df = ak.stock_zh_a_spot_em()
                data = _df_to_records(df)
                if data:
                    return json.dumps({"ok": True, "source": "eastmoney", "count": len(data), "data": data[:200]}, ensure_ascii=False)
            except Exception:
                pass
            try:
                df = ak.stock_zh_a_spot()
                data = _df_to_records(df)
                if data:
                    return json.dumps({"ok": True, "source": "sina", "count": len(data), "data": data[:200]}, ensure_ascii=False)
            except Exception:
                pass
            return json.dumps({"ok": False, "error": "获取全部A股行情失败，请指定具体股票代码"}, ensure_ascii=False)

        sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
        if not sym_list:
            return json.dumps({"ok": False, "error": "请提供股票代码"}, ensure_ascii=False)

        try:
            df = ak.stock_zh_a_spot_em()
            results = []
            for sym in sym_list:
                code = sym.replace("sh", "").replace("sz", "").replace(".SH", "").replace(".SZ", "")
                match = df[df["代码"].astype(str).str.contains(code, case=False)]
                results.extend(_df_to_records(match))
            if results:
                return json.dumps({"ok": True, "source": "eastmoney", "count": len(results), "data": results}, ensure_ascii=False)
        except Exception:
            pass

        data = _get_sina_spot(sym_list)
        if data:
            return json.dumps({"ok": True, "source": "sina", "count": len(data), "data": data}, ensure_ascii=False)

        return json.dumps({"ok": False, "error": "未获取到数据，请检查股票代码是否正确"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False)


@mcp.tool(description="获取财联社电报（7x24小时财经快讯），支持按时间范围、关键词、级别及标红过滤")
def cls_telegraph(
    limit: int = 20,
    keyword: Optional[str] = None,
    level: Optional[str] = None,
    red_only: bool = False,
    hours: Optional[float] = None,
) -> str:
    """获取财联社电报快讯。

    Args:
        limit: 返回条数，默认 20 条
        keyword: 关键词过滤，可选
        level: 级别过滤，如 'A', 'B', 'C'，可选
        red_only: 是否只获取标红新闻（level 为 A 或 B 的重要新闻），默认 False
        hours: 只返回最近 N 小时内的新闻，可选，如 1 表示最近1小时

    Returns:
        JSON 格式的财联社电报列表
    """
    try:
        import time
        try:
            from curl_cffi import requests
        except ImportError:
            return json.dumps({
                "ok": False,
                "error": "需要安装 curl_cffi: pip install curl_cffi"
            }, ensure_ascii=False)

        base_url = "https://www.cls.cn"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Referer": "https://www.cls.cn/telegraph",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        all_items = []
        last_time = None
        # 标红新闻较少，需要翻更多页才能凑够 limit 条
        max_pages = 10 if red_only else 5

        for page in range(max_pages):
            params = {
                "app": "CailianpressWeb",
                "os": "web",
                "sv": "8.7.9",
                "name": "telegraphList",
            }
            if last_time:
                params["lastTime"] = str(last_time)

            r = requests.get(
                f"{base_url}/api/cache",
                params=params,
                headers=headers,
                impersonate="chrome120",
                timeout=15,
            )
            result = r.json()

            if result.get("errno") != 0:
                break

            roll_data = result.get("data", {}).get("roll_data", [])
            if not roll_data:
                break

            for item in roll_data:
                ctime = item.get("ctime", 0)
                all_items.append({
                    "id": item.get("id"),
                    "title": item.get("title", ""),
                    "brief": item.get("brief", ""),
                    "content": item.get("content", ""),
                    "ctime": ctime,
                    "datetime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ctime)) if ctime else "",
                    "level": item.get("level", ""),
                    "is_red": item.get("level", "") in ("A", "B"),
                    "reading_num": item.get("reading_num", 0),
                    "comment_num": item.get("comment_num", 0),
                    "share_num": item.get("share_num", 0),
                    "subjects": item.get("subjects", []),
                    "stock_list": item.get("stock_list", []),
                })

            if len(all_items) >= limit * 3:
                break

            if roll_data:
                last_time = roll_data[-1].get("ctime")
            else:
                break

            time.sleep(0.3)

        # 标红过滤：只保留 level 为 A 或 B 的新闻
        if red_only:
            all_items = [item for item in all_items if item["is_red"]]

        # 时间范围过滤：只保留最近 N 小时内的新闻
        if hours:
            now = time.time()
            cutoff = now - hours * 3600
            all_items = [item for item in all_items if item.get("ctime", 0) >= cutoff]

        if keyword:
            kw = keyword.lower()
            all_items = [
                item for item in all_items
                if kw in item["title"].lower()
                or kw in item["brief"].lower()
                or kw in item["content"].lower()
            ]

        if level:
            all_items = [item for item in all_items if item["level"] == level.upper()]

        all_items = all_items[:limit]

        return json.dumps({
            "ok": True,
            "source": "cls",
            "count": len(all_items),
            "red_only": red_only,
            "data": all_items,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False)


@mcp.tool(description="获取新闻联播文字稿")
def news_cctv(date: Optional[str] = None, limit: int = 20) -> str:
    """获取新闻联播文字稿。

    Args:
        date: 日期，格式 YYYYMMDD 或 YYYY-MM-DD，可选，默认今天
        limit: 返回条数，默认 20 条

    Returns:
        JSON 格式的新闻联播内容
    """
    try:
        if date:
            date = date.replace("-", "")
            df = ak.news_cctv(date=date)
        else:
            df = ak.news_cctv()
        data = _df_to_records(df, limit)
        return json.dumps({
            "ok": True,
            "source": "cctv",
            "count": len(data),
            "data": data,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False)


@mcp.tool(description="获取财经日历（全球财经事件日历）")
def news_economic_calendar(limit: int = 50) -> str:
    """获取全球财经事件日历。

    Args:
        limit: 返回条数，默认 50 条

    Returns:
        JSON 格式的财经日历数据
    """
    try:
        df = ak.news_economic_baidu()
        data = _df_to_records(df, limit)
        return json.dumps({
            "ok": True,
            "source": "baidu",
            "count": len(data),
            "data": data,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False)


@mcp.tool(description="获取个股相关新闻")
def stock_news(symbol: str, limit: int = 20) -> str:
    """获取个股相关新闻。

    Args:
        symbol: 股票代码，如 600519
        limit: 返回条数，默认 20 条

    Returns:
        JSON 格式的新闻列表
    """
    try:
        code = symbol.replace("sh", "").replace("sz", "").replace(".SH", "").replace(".SZ", "")
        df = ak.stock_news_em(symbol=code)
        data = _df_to_records(df, limit)
        return json.dumps({
            "ok": True,
            "source": "eastmoney",
            "symbol": symbol,
            "count": len(data),
            "data": data,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False)


@mcp.tool(description="获取上市公司公告（巨潮信息网），支持按类型、日期、关键词筛选")
def stock_notice_cninfo(
    symbol: str,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 20,
) -> str:
    """获取上市公司公告（巨潮信息网）。

    Args:
        symbol: 股票代码，如 600519、000001
        category: 公告类型，可选：年报、半年报、一季报、三季报、业绩预告、权益分派、
                  董事会、监事会、股东大会、日常经营、公司治理、中介报告、
                  首发、增发、股权激励、配股、解禁、公司债、可转债、其他融资、
                  股权变动、补充更正、澄清致歉、风险提示、特别处理和退市
        keyword: 关键词过滤，可选
        start_date: 开始日期，格式 YYYY-MM-DD 或 YYYYMMDD，可选
        end_date: 结束日期，格式 YYYY-MM-DD 或 YYYYMMDD，可选
        limit: 返回条数，默认 20 条

    Returns:
        JSON 格式的公告列表
    """
    try:
        code = symbol.replace("sh", "").replace("sz", "").replace(".SH", "").replace(".SZ", "")

        if not start_date:
            start_date = "20200101"
        else:
            start_date = start_date.replace("-", "")
        if not end_date:
            end_date = "20991231"
        else:
            end_date = end_date.replace("-", "")

        params = {
            "symbol": code,
            "market": "沪深京",
            "start_date": start_date,
            "end_date": end_date,
        }
        if category:
            params["category"] = category
        if keyword:
            params["keyword"] = keyword

        df = ak.stock_zh_a_disclosure_report_cninfo(**params)
        data = _df_to_records(df, limit)
        return json.dumps({
            "ok": True,
            "source": "cninfo",
            "symbol": symbol,
            "count": len(data),
            "data": data,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False)


@mcp.tool(description="获取上市公司基本资料（巨潮信息网）")
def stock_profile_cninfo(symbol: str) -> str:
    """获取上市公司基本资料。

    Args:
        symbol: 股票代码，如 600519、000001

    Returns:
        JSON 格式的公司基本资料
    """
    try:
        code = symbol.replace("sh", "").replace("sz", "").replace(".SH", "").replace(".SZ", "")
        df = ak.stock_profile_cninfo(symbol=code)
        data = _df_to_records(df)
        return json.dumps({
            "ok": True,
            "source": "cninfo",
            "symbol": symbol,
            "count": len(data),
            "data": data,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False)


@mcp.tool(description="获取上市公司财务摘要（巨潮信息网）")
def stock_financial_abstract_cninfo(symbol: str, limit: int = 10) -> str:
    """获取上市公司财务摘要。

    Args:
        symbol: 股票代码，如 600519、000001
        limit: 返回报告期数，默认 10 期

    Returns:
        JSON 格式的财务摘要数据
    """
    try:
        code = symbol.replace("sh", "").replace("sz", "").replace(".SH", "").replace(".SZ", "")
        df = ak.stock_financial_abstract(symbol=code)
        data = _df_to_records(df, limit)
        return json.dumps({
            "ok": True,
            "source": "cninfo",
            "symbol": symbol,
            "count": len(data),
            "data": data,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False)


@mcp.tool(description="获取上市公司分红配送信息（巨潮信息网）")
def stock_dividend_cninfo(symbol: str, limit: int = 20) -> str:
    """获取上市公司分红配送信息。

    Args:
        symbol: 股票代码，如 600519、000001
        limit: 返回条数，默认 20 条

    Returns:
        JSON 格式的分红配送数据
    """
    try:
        code = symbol.replace("sh", "").replace("sz", "").replace(".SH", "").replace(".SZ", "")
        df = ak.stock_dividend_cninfo(symbol=code)
        data = _df_to_records(df, limit)
        return json.dumps({
            "ok": True,
            "source": "cninfo",
            "symbol": symbol,
            "count": len(data),
            "data": data,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False)


# ==================== 期货 ====================


@mcp.tool(description="获取期货实时行情（新浪财经），返回国内期货所有品种的实时报价")
def futures_realtime() -> str:
    """获取国内期货实时行情。

    Returns:
        JSON 格式的期货实时行情列表
    """
    try:
        df = ak.futures_zh_realtime()
        data = _df_to_records(df)
        return json.dumps({
            "ok": True,
            "source": "sina",
            "count": len(data),
            "data": data,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False)


@mcp.tool(description="获取期货历史日线行情（新浪财经），如 V0 为PVC主力")
def futures_daily(symbol: str, limit: int = 30) -> str:
    """获取期货历史日线数据。

    Args:
        symbol: 期货合约代码，如 V0（PVC主力）、RB0（螺纹钢主力）、AU0（黄金主力）
        limit: 返回条数，默认 30 条

    Returns:
        JSON 格式的期货日线数据
    """
    try:
        df = ak.futures_zh_daily_sina(symbol=symbol)
        data = _df_to_records(df, limit)
        if data:
            return json.dumps({
                "ok": True,
                "source": "sina",
                "symbol": symbol,
                "count": len(data),
                "start": data[0].get("date", ""),
                "end": data[-1].get("date", ""),
                "data": data,
            }, ensure_ascii=False)
        return json.dumps({"ok": False, "error": "未获取到数据"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False)


@mcp.tool(description="获取全球期货实时行情（东方财富），包含CBOT/NYMEX/COMEX/LME等")
def futures_global_spot(limit: int = 50) -> str:
    """获取全球期货实时行情。

    Args:
        limit: 返回条数，默认 50 条

    Returns:
        JSON 格式的全球期货行情列表
    """
    try:
        df = ak.futures_global_spot_em()
        data = _df_to_records(df, limit)
        return json.dumps({
            "ok": True,
            "source": "eastmoney",
            "count": len(data),
            "data": data,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False)


# ==================== 外围指数 ====================


@mcp.tool(description="获取美股指数历史日线（新浪财经），如道琼斯、纳斯达克、标普500")
def index_us_daily(symbol: str, limit: int = 30) -> str:
    """获取美股指数历史日线数据。

    Args:
        symbol: 指数代码，如 .DJI（道琼斯）、.IXIC（纳斯达克）、.INX（标普500）
        limit: 返回条数，默认 30 条

    Returns:
        JSON 格式的美股指数日线数据
    """
    try:
        df = ak.index_us_stock_sina(symbol=symbol)
        data = _df_to_records(df, limit)
        if data:
            return json.dumps({
                "ok": True,
                "source": "sina",
                "symbol": symbol,
                "count": len(data),
                "start": data[0].get("date", ""),
                "end": data[-1].get("date", ""),
                "data": data,
            }, ensure_ascii=False)
        return json.dumps({"ok": False, "error": "未获取到数据"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False)


@mcp.tool(description="获取港股指数历史日线（新浪财经），如恒生指数、国企指数")
def index_hk_daily(symbol: str, limit: int = 30) -> str:
    """获取港股指数历史日线数据。

    Args:
        symbol: 指数代码，如 HSI（恒生指数）、HSCEI（国企指数）、HSTECH（恒生科技）
        limit: 返回条数，默认 30 条

    Returns:
        JSON 格式的港股指数日线数据
    """
    try:
        df = ak.stock_hk_index_daily_sina(symbol=symbol)
        data = _df_to_records(df, limit)
        if data:
            return json.dumps({
                "ok": True,
                "source": "sina",
                "symbol": symbol,
                "count": len(data),
                "start": data[0].get("date", ""),
                "end": data[-1].get("date", ""),
                "data": data,
            }, ensure_ascii=False)
        return json.dumps({"ok": False, "error": "未获取到数据"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False)


@mcp.tool(description="获取全球指数名称代码表，用于查询外围指数的代码")
def index_global_list() -> str:
    """获取全球指数名称代码表。

    Returns:
        JSON 格式的全球指数名称与代码对照表
    """
    try:
        df = ak.index_global_name_table()
        data = _df_to_records(df)
        return json.dumps({
            "ok": True,
            "source": "sina",
            "count": len(data),
            "data": data,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False)


# ==================== ETF ====================


@mcp.tool(description="获取ETF实时行情列表（东方财富），返回全部ETF的当前报价")
def fund_etf_spot(limit: int = 50) -> str:
    """获取ETF实时行情列表。

    Args:
        limit: 返回条数，默认 50 条

    Returns:
        JSON 格式的ETF实时行情列表
    """
    try:
        df = ak.fund_etf_spot_em()
        data = _df_to_records(df, limit)
        return json.dumps({
            "ok": True,
            "source": "eastmoney",
            "count": len(data),
            "data": data,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False)


@mcp.tool(description="获取ETF历史日线行情（新浪财经），如 510300 为沪深300ETF")
def fund_etf_daily(symbol: str, limit: int = 30) -> str:
    """获取ETF历史日线数据。

    Args:
        symbol: ETF代码，如 sz510300（沪深300ETF）、sz159915（创业板ETF）、sh510050（50ETF）
        limit: 返回条数，默认 30 条

    Returns:
        JSON 格式的ETF日线数据
    """
    try:
        code = symbol.lower()
        if not (code.startswith("sh") or code.startswith("sz")):
            if len(code) == 6:
                code = "sh" + code if code[0] == "5" else "sz" + code
            else:
                code = "sh" + code
        df = ak.fund_etf_hist_sina(symbol=code)
        data = _df_to_records(df, limit)
        if data:
            return json.dumps({
                "ok": True,
                "source": "sina",
                "symbol": symbol,
                "count": len(data),
                "start": data[0].get("date", ""),
                "end": data[-1].get("date", ""),
                "data": data,
            }, ensure_ascii=False)
        return json.dumps({"ok": False, "error": "未获取到数据"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()

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
    pd.set_option("string_storage", "python")
except ImportError:
    print("错误: 未安装 akshare，请运行: pip install akshare pandas", file=sys.stderr)
    sys.exit(1)


def _df_to_records(df: pd.DataFrame, limit: Optional[int] = None) -> list[dict]:
    """将 DataFrame 转为字典列表，处理 NaN 值。"""
    import datetime as _dt
    import numpy as np
    if df is None or df.empty:
        return []
    if limit and len(df) > limit:
        df = df.tail(limit)
    data = []
    for _, row in df.iterrows():
        item = {}
        for col in df.columns:
            val = row[col]
            item[col] = _safe_json(val)
        data.append(item)
    return data


def _safe_json(val):
    """将值安全转换为 JSON 可序列化类型。"""
    import numpy as np
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    if isinstance(val, (np.ndarray, list, tuple)):
        return [_safe_json(v) for v in val]
    if isinstance(val, dict):
        return {k: _safe_json(v) for k, v in val.items()}
    if isinstance(val, (pd.Timestamp,)):
        try:
            if pd.isna(val):
                return None
            return str(val.date())
        except Exception:
            return str(val)
    import datetime as _dt
    if isinstance(val, (_dt.date, _dt.datetime)):
        try:
            return str(val.date())
        except Exception:
            return str(val)
    if hasattr(val, 'item') and not isinstance(val, (str, bytes)):
        try:
            scalar = val.item()
            if isinstance(scalar, float) and pd.isna(scalar):
                return None
            return scalar
        except Exception:
            return str(val)
    return val


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


# ==================== AxData 数据源 ====================
# 基于 electkismet/AxData 开源量化数据库框架
# 提供更多数据源接口：东方财富涨停池/板块行情、财联社情绪/风口、
# 开盘红情绪、龙虎榜、期权合约、期货主力等

_axdata_client = None


def _get_axdata_client():
    """获取或初始化 AxData 客户端。"""
    global _axdata_client
    if _axdata_client is None:
        import axdata as ax
        _axdata_client = ax.AxDataClient()
    return _axdata_client


def _axdata_call(interface: str, **params) -> tuple[bool, list[dict]]:
    """调用 AxData 源端直取接口，返回 (是否成功, 数据列表)。"""
    try:
        client = _get_axdata_client()
        df = client.call(interface, **params)
        if df is None or df.empty:
            return True, []
        data = _df_to_records(df)
        return True, data
    except Exception as e:
        return False, [{"error": f"{type(e).__name__}: {str(e)[:200]}"}]


def _axdata_result(ok: bool, data: list[dict], source: str, interface: str, **extra) -> str:
    """构造 AxData 接口的标准返回。"""
    if not ok:
        return json.dumps({
            "ok": False,
            "source": source,
            "interface": interface,
            "error": data[0].get("error", "未知错误") if data else "未知错误",
        }, ensure_ascii=False)
    result = {
        "ok": True,
        "source": source,
        "interface": interface,
        "count": len(data),
        "data": data,
    }
    result.update(extra)
    return json.dumps(result, ensure_ascii=False)


# ---------- 涨停池 / 跌停池 ----------


@mcp.tool(description="获取A股涨停池（东方财富），包含涨停原因、连板数、主力资金等")
def stock_limit_up_pool(limit: int = 50) -> str:
    """获取当日涨停股票池。

    Args:
        limit: 返回条数，默认 50 条

    Returns:
        JSON 格式的涨停股列表，包含价格、涨跌幅、涨停时间、连板数、主力资金等
    """
    ok, data = _axdata_call("eastmoney_limit_up_pool")
    if ok and limit and len(data) > limit:
        data = data[:limit]
    return _axdata_result(ok, data, "eastmoney", "eastmoney_limit_up_pool")


@mcp.tool(description="获取A股跌停池（东方财富），包含跌停原因、开板次数等")
def stock_limit_down_pool(limit: int = 50) -> str:
    """获取当日跌停股票池。

    Args:
        limit: 返回条数，默认 50 条

    Returns:
        JSON 格式的跌停股列表
    """
    ok, data = _axdata_call("eastmoney_limit_down_pool")
    if ok and limit and len(data) > limit:
        data = data[:limit]
    return _axdata_result(ok, data, "eastmoney", "eastmoney_limit_down_pool")


# ---------- 板块行情 ----------


@mcp.tool(description="获取行业/概念板块实时行情（东方财富），包含涨跌幅、主力资金、领涨股等")
def sector_realtime(limit: int = 100) -> str:
    """获取板块实时行情列表。

    Args:
        limit: 返回条数，默认 100 条

    Returns:
        JSON 格式的板块行情列表，包含涨跌幅、成交额、主力净流入、领涨股等
    """
    ok, data = _axdata_call("eastmoney_sector_realtime")
    if ok and limit and len(data) > limit:
        data = data[:limit]
    return _axdata_result(ok, data, "eastmoney", "eastmoney_sector_realtime")


# ---------- 市场情绪 ----------


@mcp.tool(description="获取市场情绪指标（财联社），包含涨跌家数、涨停数、连板率、市场温度等")
def market_emotion_cls() -> str:
    """获取财联社市场情绪数据。

    Returns:
        JSON 格式的市场情绪数据，包含市场温度、涨跌分布、涨停梯队等
    """
    ok, data = _axdata_call("cls_market_emotion")
    return _axdata_result(ok, data, "cls", "cls_market_emotion")


@mcp.tool(description="获取市场情绪指标（开盘红），包含涨跌数、真实涨停数、ST涨跌数等")
def market_emotion_kph() -> str:
    """获取开盘红市场情绪数据。

    Returns:
        JSON 格式的市场情绪数据，包含涨停/跌停/真实涨停/ST涨跌等详细分布
    """
    ok, data = _axdata_call("kph_market_emotion")
    return _axdata_result(ok, data, "kph", "kph_market_emotion")


# ---------- 财联社特色数据 ----------


@mcp.tool(description="获取财联社涨停池，包含涨停原因详解")
def cls_limit_up_pool(limit: int = 50) -> str:
    """获取财联社涨停池（带涨停原因）。

    Args:
        limit: 返回条数，默认 50 条

    Returns:
        JSON 格式的涨停股列表，含详细涨停原因
    """
    ok, data = _axdata_call("cls_limit_up_pool")
    if ok and limit and len(data) > limit:
        data = data[:limit]
    return _axdata_result(ok, data, "cls", "cls_limit_up_pool")


@mcp.tool(description="获取财联社板块热度排行，包含实时热度值、排名变化等")
def cls_sector_heat() -> str:
    """获取财联社板块热度排行。

    Returns:
        JSON 格式的板块热度列表，20个热门板块
    """
    ok, data = _axdata_call("cls_sector_heat")
    return _axdata_result(ok, data, "cls", "cls_sector_heat")


@mcp.tool(description="获取财联社今日风口板块，包含催化原因")
def cls_market_wind() -> str:
    """获取财联社今日风口板块。

    Returns:
        JSON 格式的风口板块列表，含催化原因
    """
    ok, data = _axdata_call("cls_market_wind")
    return _axdata_result(ok, data, "cls", "cls_market_wind")


@mcp.tool(description="获取财联社今日主线机会，包含龙头股和板块详情")
def cls_market_mainline() -> str:
    """获取财联社今日主线机会。

    Returns:
        JSON 格式的主线机会数据，包含板块、龙头股、逻辑等
    """
    ok, data = _axdata_call("cls_market_mainline")
    return _axdata_result(ok, data, "cls", "cls_market_mainline")


# ---------- 龙虎榜 ----------


@mcp.tool(description="获取龙虎榜每日详情（新浪财经），包含上榜原因、买卖金额等")
def stock_lhb_daily(limit: int = 50) -> str:
    """获取龙虎榜每日详情。

    Args:
        limit: 返回条数，默认 50 条

    Returns:
        JSON 格式的龙虎榜数据
    """
    ok, data = _axdata_call("stock_lhb_detail_daily_sina")
    if ok and limit and len(data) > limit:
        data = data[:limit]
    return _axdata_result(ok, data, "sina", "stock_lhb_detail_daily_sina")


@mcp.tool(description="获取龙虎榜机构席位明细（新浪财经），包含机构买卖金额")
def stock_lhb_institution(limit: int = 50) -> str:
    """获取龙虎榜机构席位明细。

    Args:
        limit: 返回条数，默认 50 条

    Returns:
        JSON 格式的机构席位买卖数据
    """
    ok, data = _axdata_call("stock_lhb_jgmx_sina", limit=limit)
    return _axdata_result(ok, data, "sina", "stock_lhb_jgmx_sina")


# ---------- 期货 ----------


@mcp.tool(description="获取期货主力合约行情展示（新浪财经），含成交量/持仓量排行")
def futures_main_display(limit: int = 20) -> str:
    """获取期货主力合约行情展示。

    Args:
        limit: 返回条数，默认 20 条

    Returns:
        JSON 格式的主力期货行情列表
    """
    ok, data = _axdata_call("futures_display_main_sina")
    if ok and limit and len(data) > limit:
        data = data[:limit]
    return _axdata_result(ok, data, "sina", "futures_display_main_sina")


# ---------- 期权 ----------


@mcp.tool(description="获取商品期权品种列表（新浪财经）")
def option_commodity_list() -> str:
    """获取商品期权品种列表。

    Returns:
        JSON 格式的商品期权品种列表
    """
    ok, data = _axdata_call("option_commodity_contract_sina")
    return _axdata_result(ok, data, "sina", "option_commodity_contract_sina")


@mcp.tool(description="获取中金所沪深300期权合约列表（新浪财经）")
def option_cffex_hs300_list() -> str:
    """获取中金所沪深300期权合约列表。

    Returns:
        JSON 格式的期权合约列表
    """
    ok, data = _axdata_call("option_cffex_hs300_list_sina")
    return _axdata_result(ok, data, "sina", "option_cffex_hs300_list_sina")


# ---------- 统一数据查询接口 ----------


def _convert_symbol_sina_to_tdx(symbol: str) -> str:
    """新浪格式(sh600519/sz000001/600519) -> TDX格式(600519.SH/000001.SZ)。"""
    s = symbol.upper().strip()
    if "." in s:
        return s
    s_lower = s.lower()
    if s_lower.startswith("sh"):
        return s[2:] + ".SH"
    if s_lower.startswith("sz"):
        return s[2:] + ".SZ"
    if len(s) == 6:
        if s[0] in "6" or s[:2] in ("68", "90", "51", "11", "13"):
            return s + ".SH"
        return s + ".SZ"
    return s


def _convert_symbol_tdx_to_sina(symbol: str) -> str:
    """TDX格式(600519.SH/000001.SZ) -> 新浪格式(sh600519/sz000001)。"""
    s = symbol.upper().strip()
    if s.endswith(".SH"):
        return "sh" + s[:-3]
    if s.endswith(".SZ"):
        return "sz" + s[:-3]
    s_lower = s.lower()
    if s_lower.startswith("sh") or s_lower.startswith("sz"):
        return s_lower
    if len(s) == 6:
        if s[0] in "6" or s[:2] in ("68", "90", "51", "11", "13"):
            return "sh" + s
        return "sz" + s
    return s


# 接口映射表：统一接口名 -> 配置字典
# 配置：axdata(接口名, 参数映射, 代码转换), akshare(函数名, 参数映射, 代码转换, 过滤字段)
_DATA_INTERFACE_MAP = {
    # ===== 个股 =====
    "stock_daily": {
        "desc": "A股日K线",
        "axdata": {"interface": "stock_zh_a_hist_tx", "param_map": {"symbol": "code"}, "symbol_fmt": "tdx"},
        "akshare": {"func": "stock_zh_a_daily", "param_map": {}, "symbol_fmt": "sina", "extra": {"adjust": "qfq"}},
    },
    "stock_realtime": {
        "desc": "A股实时行情（支持单只或多只代码过滤）",
        "axdata": None,
        "akshare": {"func": "stock_zh_a_spot_em", "param_map": {}, "symbol_fmt": None, "filter_by": "代码", "drop_params": ["symbol", "code"], "sina_fallback": True},
    },
    # ===== 指数 =====
    "index_daily": {
        "desc": "A股指数日K线",
        "axdata": None,
        "akshare": {"func": "stock_zh_index_daily", "param_map": {}, "symbol_fmt": "sina"},
    },
    "index_realtime": {
        "desc": "A股指数实时行情",
        "axdata": {"interface": "stock_zh_index_spot_sina", "param_map": {}, "symbol_fmt": None},
        "akshare": {"func": "stock_zh_index_spot_em", "param_map": {}, "symbol_fmt": None, "drop_params": ["symbol", "code"], "sina_fallback": True},
    },
    # ===== ETF =====
    "etf_daily": {
        "desc": "ETF日K线",
        "axdata": {"interface": "fund_etf_hist_sina", "param_map": {}, "symbol_fmt": "sina"},
        "akshare": {"func": "fund_etf_hist_sina", "param_map": {}, "symbol_fmt": "sina"},
    },
    "etf_realtime": {
        "desc": "ETF实时行情",
        "axdata": None,
        "akshare": {"func": "fund_etf_spot_em", "param_map": {}, "symbol_fmt": None, "filter_by": "代码", "drop_params": ["symbol", "code"], "sina_fallback": True},
    },
    # ===== 期货 =====
    "futures_daily": {
        "desc": "期货日线（主力合约）",
        "axdata": {"interface": "futures_main_sina", "param_map": {}, "symbol_fmt": None},
        "akshare": {"func": "futures_zh_daily_sina", "param_map": {}, "symbol_fmt": None},
    },
    "futures_realtime": {
        "desc": "期货实时行情（主力合约展示）",
        "axdata": {"interface": "futures_display_main_sina", "param_map": {}, "symbol_fmt": None},
        "akshare": {"func": "futures_zh_realtime", "param_map": {}, "symbol_fmt": None, "filter_by": "symbol", "drop_params": ["symbol"]},
    },
    # ===== 外围指数 =====
    "index_us_daily": {
        "desc": "美股指数日线",
        "axdata": {"interface": "index_us_stock_sina", "param_map": {}, "symbol_fmt": None},
        "akshare": None,
    },
    "index_hk_daily": {
        "desc": "港股指数日线",
        "axdata": {"interface": "stock_hk_index_daily_sina", "param_map": {}, "symbol_fmt": None},
        "akshare": None,
    },
    # ===== 涨跌停 / 板块 =====
    "limit_up_pool": {
        "desc": "涨停池（含涨停原因、连板数）",
        "axdata": {"interface": "eastmoney_limit_up_pool", "param_map": {}, "symbol_fmt": None},
        "akshare": None,
    },
    "limit_down_pool": {
        "desc": "跌停池",
        "axdata": {"interface": "eastmoney_limit_down_pool", "param_map": {}, "symbol_fmt": None},
        "akshare": None,
    },
    "sector_realtime": {
        "desc": "板块实时行情（涨跌幅、主力资金、领涨股）",
        "axdata": {"interface": "eastmoney_sector_realtime", "param_map": {}, "symbol_fmt": None},
        "akshare": None,
    },
    "market_index_realtime": {
        "desc": "大盘指数实时行情",
        "axdata": {"interface": "eastmoney_market_index_realtime", "param_map": {}, "symbol_fmt": None},
        "akshare": None,
    },
    # ===== 财联社 =====
    "cls_telegraph": {
        "desc": "财联社电报快讯",
        "axdata": {"interface": "cls_news_telegraph", "param_map": {}, "symbol_fmt": None},
        "akshare": None,
    },
    "cls_market_emotion": {
        "desc": "财联社市场情绪（温度、涨跌分布、涨停梯队）",
        "axdata": {"interface": "cls_market_emotion", "param_map": {}, "symbol_fmt": None},
        "akshare": None,
    },
    "cls_limit_up_pool": {
        "desc": "财联社涨停池（含详细涨停原因）",
        "axdata": {"interface": "cls_limit_up_pool", "param_map": {}, "symbol_fmt": None},
        "akshare": None,
    },
    "cls_sector_heat": {
        "desc": "财联社板块热度排行",
        "axdata": {"interface": "cls_sector_heat", "param_map": {}, "symbol_fmt": None},
        "akshare": None,
    },
    "cls_market_wind": {
        "desc": "财联社今日风口板块（含催化原因）",
        "axdata": {"interface": "cls_market_wind", "param_map": {}, "symbol_fmt": None},
        "akshare": None,
    },
    "cls_market_mainline": {
        "desc": "财联社今日主线机会（含龙头股、逻辑）",
        "axdata": {"interface": "cls_market_mainline", "param_map": {}, "symbol_fmt": None},
        "akshare": None,
    },
    # ===== 开盘红 =====
    "kph_market_emotion": {
        "desc": "开盘红市场情绪（真实涨停、ST涨跌、涨跌分布）",
        "axdata": {"interface": "kph_market_emotion", "param_map": {}, "symbol_fmt": None},
        "akshare": None,
    },
    # ===== 龙虎榜 =====
    "lhb_daily": {
        "desc": "龙虎榜每日详情",
        "axdata": {"interface": "stock_lhb_detail_daily_sina", "param_map": {}, "symbol_fmt": None},
        "akshare": None,
    },
    "lhb_institution": {
        "desc": "龙虎榜机构席位明细",
        "axdata": {"interface": "stock_lhb_jgmx_sina", "param_map": {}, "symbol_fmt": None},
        "akshare": None,
    },
    # ===== 期权 =====
    "option_commodity_list": {
        "desc": "商品期权品种列表",
        "axdata": {"interface": "option_commodity_contract_sina", "param_map": {}, "symbol_fmt": None},
        "akshare": None,
    },
    "option_cffex_hs300_list": {
        "desc": "中金所沪深300期权合约列表",
        "axdata": {"interface": "option_cffex_hs300_list_sina", "param_map": {}, "symbol_fmt": None},
        "akshare": None,
    },
    # ===== 巨潮 =====
    "cninfo_announcements": {
        "desc": "巨潮公告列表",
        "axdata": {"interface": "cninfo_announcements", "param_map": {"symbol": "code"}, "symbol_fmt": None},
        "akshare": None,
    },
    "stock_profile_cninfo": {
        "desc": "公司概况（巨潮）",
        "axdata": {"interface": "stock_profile_cninfo", "param_map": {"symbol": "code"}, "symbol_fmt": None},
        "akshare": None,
    },
    "stock_dividend_cninfo": {
        "desc": "分红配送（巨潮）",
        "axdata": {"interface": "stock_dividend_cninfo", "param_map": {"symbol": "code"}, "symbol_fmt": None},
        "akshare": None,
    },
    # ===== 新闻 =====
    "news_cctv": {
        "desc": "新闻联播文字稿",
        "axdata": None,
        "akshare": {"func": "news_cctv", "param_map": {}, "symbol_fmt": None, "drop_params": ["symbol", "code"]},
    },
    "economic_calendar": {
        "desc": "财经日历（百度）",
        "axdata": None,
        "akshare": {"func": "news_economic_baidu", "param_map": {}, "symbol_fmt": None, "drop_params": ["symbol", "code"]},
    },
    "stock_news": {
        "desc": "个股新闻（东方财富）",
        "axdata": None,
        "akshare": {"func": "stock_news_em", "param_map": {}, "symbol_fmt": None},
    },
}


def _adapt_params(params: dict, cfg: dict) -> dict:
    """根据配置转换参数名和代码格式。"""
    result = {}
    param_map = cfg.get("param_map", {})
    symbol_fmt = cfg.get("symbol_fmt")
    drop_params = set(cfg.get("drop_params", []))

    for key, val in params.items():
        if key in drop_params:
            continue
        new_key = param_map.get(key, key)
        result[new_key] = val

    # 代码格式转换
    sym = result.get("symbol") or result.get("code") or result.get("instrument_id")
    sym_key = "symbol" if "symbol" in result else ("code" if "code" in result else None)
    if sym and sym_key and symbol_fmt:
        if symbol_fmt == "tdx":
            result[sym_key] = _convert_symbol_sina_to_tdx(sym)
        elif symbol_fmt == "sina":
            result[sym_key] = _convert_symbol_tdx_to_sina(sym)

    # 添加额外参数
    extra = cfg.get("extra", {})
    for k, v in extra.items():
        if k not in result:
            result[k] = v

    # 移除 limit 参数（源端不一定支持）
    result.pop("limit", None)

    return result


def _filter_data(data: list[dict], cfg: dict, params: dict) -> list[dict]:
    """客户端过滤：根据 symbol 参数过滤数据。"""
    filter_by = cfg.get("filter_by")
    sym = params.get("symbol") or params.get("code")
    if not filter_by or not sym:
        return data

    sym_clean = str(sym).lower().replace("sh", "").replace("sz", "").replace(".sh", "").replace(".sz", "")
    sym_list = [s.strip().lower().replace("sh", "").replace("sz", "").replace(".sh", "").replace(".sz", "")
                for s in str(sym).split(",")]

    filtered = []
    for item in data:
        val = str(item.get(filter_by, "")).lower()
        val_clean = val.replace("sh", "").replace("sz", "").replace(".sh", "").replace(".sz", "")
        if val_clean in sym_list or any(s in val_clean for s in sym_list):
            filtered.append(item)
    return filtered


def _call_axdata(cfg: dict, **params) -> tuple[bool, list[dict], str]:
    """调用 axdata 接口。"""
    try:
        client = _get_axdata_client()
        adapted = _adapt_params(params, cfg)
        df = client.call(cfg["interface"], **adapted)
        if df is not None and not df.empty:
            data = _df_to_records(df)
            # 客户端过滤
            data = _filter_data(data, cfg, params)
            return True, data, f"axdata:{cfg['interface']}"
        return False, [], f"axdata:{cfg['interface']}"
    except Exception as e:
        return False, [{"error": f"{type(e).__name__}: {str(e)[:200]}"}], f"axdata:{cfg['interface']}"


def _call_akshare(cfg: dict, **params) -> tuple[bool, list[dict], str]:
    """调用 akshare 接口。"""
    try:
        func = getattr(ak, cfg["func"])
        adapted = _adapt_params(params, cfg)
        df = func(**adapted)
        if df is not None and not df.empty:
            data = _df_to_records(df)
            # 客户端过滤
            data = _filter_data(data, cfg, params)
            return True, data, f"akshare:{cfg['func']}"
        return False, [], f"akshare:{cfg['func']}"
    except Exception as e:
        # 新浪 fallback（针对 push2 域名不可用的情况）
        if cfg.get("sina_fallback"):
            sym = params.get("symbol") or params.get("code")
            if sym:
                sym_list = [s.strip() for s in str(sym).split(",") if s.strip()]
                data = _get_sina_spot(sym_list)
                if data:
                    return True, data, "sina:direct"
        return False, [{"error": f"{type(e).__name__}: {str(e)[:200]}"}], f"akshare:{cfg['func']}"


def _call_unified(interface: str, **params) -> tuple[bool, list[dict], str]:
    """统一数据调用：自动路由到 axdata 或 akshare。

    返回 (是否成功, 数据列表, 实际数据源)。
    路由策略：
    1. 如果在映射表中，优先用 axdata，失败 fallback akshare
    2. 如果不在映射表中，尝试直接调用 axdata
    """
    cfg = _DATA_INTERFACE_MAP.get(interface)

    if cfg:
        axdata_cfg = cfg.get("axdata")
        akshare_cfg = cfg.get("akshare")

        last_error = None
        last_source = "unknown"

        # 优先 axdata
        if axdata_cfg:
            ok, data, source = _call_axdata(axdata_cfg, **params)
            if ok and data:
                return ok, data, source
            if not ok:
                last_error = data[0].get("error", "未知错误") if data else "未知错误"
                last_source = source
            else:
                last_source = source

        # fallback akshare
        if akshare_cfg:
            ok, data, source = _call_akshare(akshare_cfg, **params)
            if ok and data:
                return ok, data, source
            if not ok:
                last_error = data[0].get("error", "未知错误") if data else "未知错误"
                last_source = source
            else:
                last_source = source

        # 都没有数据，返回最后的错误或空结果
        if last_error:
            return False, [{"error": last_error}], last_source
        return True, [], last_source

    # 不在映射表中，尝试直接调 axdata
    try:
        client = _get_axdata_client()
        df = client.call(interface, **params)
        if df is not None and not df.empty:
            return True, _df_to_records(df), f"axdata:{interface}"
        return True, [], f"axdata:{interface}"
    except Exception as e:
        return False, [{"error": f"{type(e).__name__}: {str(e)[:200]}"}], f"axdata:{interface}"


@mcp.tool(description="统一数据查询接口：整合 akshare + axdata 两个数据源，自动路由到最佳来源")
def data_query(
    interface: str,
    params_json: Optional[str] = None,
    limit: int = 0,
) -> str:
    """统一数据查询接口。

    整合 akshare 和 axdata 两个数据源，自动路由到最佳来源。
    优先使用 axdata（字段更规范），失败时自动 fallback 到 akshare。
    自动处理参数名转换、代码格式转换（新浪/TDX 格式互转）。

    支持三种调用方式：
    1. 用统一别名（推荐）：interface="limit_up_pool"
    2. 用 axdata 原始接口名：interface="eastmoney_limit_up_pool"
    3. 用 akshare 函数名：interface="stock_zh_a_daily"

    常用统一别名（完整列表用 data_interfaces 工具查看）：
    - stock_daily: A股日K线（symbol 支持 sh600519 / 600519 / 600519.SH）
    - stock_realtime: A股实时行情（支持 symbol 过滤多只）
    - index_daily: 指数日K线
    - index_realtime: 指数实时行情
    - etf_daily: ETF日K线
    - etf_realtime: ETF实时行情
    - futures_daily: 期货日线
    - futures_realtime: 期货实时行情
    - limit_up_pool: 涨停池
    - limit_down_pool: 跌停池
    - sector_realtime: 板块实时行情
    - cls_market_emotion: 财联社市场情绪
    - cls_market_wind: 财联社今日风口
    - cls_market_mainline: 财联社今日主线
    - lhb_daily: 龙虎榜每日详情
    - option_commodity_list: 商品期权品种列表
    - kph_market_emotion: 开盘红市场情绪

    Args:
        interface: 接口名称，可以是统一别名、axdata接口名或akshare函数名
        params_json: JSON 格式的参数字典，如 {"symbol": "600519", "limit": 10}，可选
        limit: 返回条数限制，0 表示不限制

    Returns:
        JSON 格式的查询结果，包含 source 字段标识实际数据源
    """
    try:
        params = {}
        if params_json:
            params = json.loads(params_json)

        ok, data, source = _call_unified(interface, **params)

        if not ok:
            err_msg = data[0].get("error", "未知错误") if data else "未知错误"
            return json.dumps({
                "ok": False,
                "interface": interface,
                "source": source,
                "error": err_msg,
            }, ensure_ascii=False)

        if limit and len(data) > limit:
            data = data[:limit]

        return json.dumps({
            "ok": True,
            "interface": interface,
            "source": source,
            "count": len(data),
            "data": data,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "ok": False,
            "interface": interface,
            "error": f"{type(e).__name__}: {str(e)[:200]}",
        }, ensure_ascii=False)


@mcp.tool(description="列出所有可用的统一数据接口及其数据源映射")
def data_interfaces() -> str:
    """列出所有可用的统一数据接口。

    返回统一别名、axdata接口名、akshare函数名和说明，
    供用户查询 data_query 工具可用的接口名。

    Returns:
        JSON 格式的接口映射表
    """
    interfaces = []
    for alias, cfg in _DATA_INTERFACE_MAP.items():
        axdata_iface = cfg.get("axdata", {}).get("interface") if cfg.get("axdata") else None
        akshare_func = cfg.get("akshare", {}).get("func") if cfg.get("akshare") else None
        interfaces.append({
            "alias": alias,
            "description": cfg.get("desc", ""),
            "axdata_interface": axdata_iface,
            "akshare_function": akshare_func,
            "priority": "axdata" if axdata_iface else ("akshare" if akshare_func else "none"),
        })
    return json.dumps({
        "ok": True,
        "count": len(interfaces),
        "note": "data_query 支持用 alias、axdata_interface 或 akshare_function 调用，自动路由+自动格式转换",
        "interfaces": interfaces,
    }, ensure_ascii=False)


def _parse_args():
    """解析命令行参数。"""
    import argparse
    parser = argparse.ArgumentParser(
        description="AKShare MCP Server - 金融数据 MCP 服务器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python server.py                          # stdio 模式（默认，供 IDE 集成）
  python server.py --transport sse          # SSE 模式，默认 0.0.0.0:8000
  python server.py --transport sse --port 9000
  python server.py --transport streamable-http --host 127.0.0.1 --port 8080
  python server.py --list                   # 列出所有可用工具
        """,
    )
    parser.add_argument(
        "--transport", "-t",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="传输协议：stdio（默认）、sse、streamable-http",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="监听地址，默认 0.0.0.0（所有网卡）",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8000,
        help="监听端口，默认 8000",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="列出所有可用工具后退出",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.list:
        import asyncio
        async def _list():
            tools = await mcp.list_tools()
            print(f"=== AKShare MCP Server 共 {len(tools)} 个工具 ===")
            print()
            for t in tools:
                print(f"  {t.name}")
                if t.description:
                    print(f"    {t.description[:80]}")
                print()
        asyncio.run(_list())
        sys.exit(0)

    if args.transport == "stdio":
        mcp.run()
    else:
        # SSE 或 streamable-http 模式
        mcp.run(
            transport=args.transport,
            host=args.host,
            port=args.port,
        )

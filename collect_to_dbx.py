#!/usr/bin/env python3
"""数据采集脚本：从 akshare/axdata 拉取金融数据，存入 SQLite，供 DBX / agent 查询。

架构：
    数据源 (akshare/axdata)
        │  复用 server.py 的 _call_unified（自动 axdata 优先 + akshare fallback）
        ▼
    SQLite (data/finance.db)
        │  每类一张表，自动建表/补字段；时序类 upsert，快照类追加
        ▼
    DBX 桌面版 / Docker 连接查看  +  @dbx-app/mcp-server 暴露给 AI 助手

用法：
    python collect_to_dbx.py                       # 交互式菜单
    python collect_to_dbx.py --list                # 列出所有采集项
    python collect_to_dbx.py -c stock_daily -s 600519
    python collect_to_dbx.py -c limit_up_pool
    python collect_to_dbx.py -c all                # 采集所有"无需参数"的项
    python collect_to_dbx.py -c stock_daily,limit_up_pool -s 600519
    python collect_to_dbx.py --db /tmp/fin.db      # 自定义数据库路径

依赖：pip install -r requirements.txt （需 akshare + fastmcp + axdata 可选）
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# 延迟导入：--list / --help 等纯展示功能不应依赖 akshare/fastmcp
# 真正采集时才 import server.py 的统一调用层
_call_unified = None


def _ensure_call_unified():
    """首次采集时加载 server._call_unified（会触发 akshare/fastmcp import 检查）。"""
    global _call_unified
    if _call_unified is not None:
        return _call_unified
    try:
        from server import _call_unified as _fn
    except SystemExit:
        print("依赖未安装，请先运行: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)
    except ImportError as e:
        print(f"无法从 server.py 导入 _call_unified: {e}", file=sys.stderr)
        sys.exit(1)
    _call_unified = _fn
    return _fn


# ==================== 采集器配置 ====================
# mode:
#   "upsert"   —— 时序类，按 primary_keys 去重（INSERT OR REPLACE）
#   "snapshot" —— 快照类，每次采集追加，靠 fetched_at 区分时间
# inject_symbol：record 里本身没有 symbol 字段时，用调用参数补上
COLLECTORS: dict[str, dict] = {
    # ---------- 时序类（按主键 upsert） ----------
    "stock_daily": {
        "desc": "A股个股日K线",
        "interface": "stock_daily",
        "need_symbol": True,
        "symbol_label": "股票代码（600519 / sh600519 / 600519.SH）",
        "default_symbol": "600519",
        "table": "ak_stock_daily",
        "mode": "upsert",
        "primary_keys": ["symbol", "date"],
        "inject_symbol": True,
    },
    "index_daily": {
        "desc": "A股指数日K线",
        "interface": "index_daily",
        "need_symbol": True,
        "symbol_label": "指数代码（sh000001 / sh000300）",
        "default_symbol": "sh000001",
        "table": "ak_index_daily",
        "mode": "upsert",
        "primary_keys": ["symbol", "date"],
        "inject_symbol": True,
    },
    "etf_daily": {
        "desc": "ETF日K线",
        "interface": "etf_daily",
        "need_symbol": True,
        "symbol_label": "ETF代码（510300 / 159915）",
        "default_symbol": "510300",
        "table": "ak_etf_daily",
        "mode": "upsert",
        "primary_keys": ["symbol", "date"],
        "inject_symbol": True,
    },
    "futures_daily": {
        "desc": "期货日线（主力）",
        "interface": "futures_daily",
        "need_symbol": True,
        "symbol_label": "期货合约（V0 / RB0 / AU0）",
        "default_symbol": "RB0",
        "table": "ak_futures_daily",
        "mode": "upsert",
        "primary_keys": ["symbol", "date"],
        "inject_symbol": True,
    },
    "index_us_daily": {
        "desc": "美股指数日线",
        "interface": "index_us_daily",
        "need_symbol": True,
        "symbol_label": "美股指数（.DJI / .IXIC / .INX）",
        "default_symbol": ".DJI",
        "table": "ak_index_us_daily",
        "mode": "upsert",
        "primary_keys": ["symbol", "date"],
        "inject_symbol": True,
    },
    "index_hk_daily": {
        "desc": "港股指数日线",
        "interface": "index_hk_daily",
        "need_symbol": True,
        "symbol_label": "港股指数（HSI / HSCEI / HSTECH）",
        "default_symbol": "HSI",
        "table": "ak_index_hk_daily",
        "mode": "upsert",
        "primary_keys": ["symbol", "date"],
        "inject_symbol": True,
    },

    # ---------- 实时/快照类（每次追加） ----------
    "stock_realtime": {
        "desc": "A股实时行情（指定代码）",
        "interface": "stock_realtime",
        "need_symbol": True,
        "symbol_label": "股票代码，多个用逗号分隔",
        "default_symbol": "600519,000001",
        "table": "ak_stock_realtime",
        "mode": "snapshot",
    },
    "index_realtime": {
        "desc": "A股指数实时行情",
        "interface": "index_realtime",
        "need_symbol": False,
        "table": "ak_index_realtime",
        "mode": "snapshot",
    },
    "etf_realtime": {
        "desc": "ETF实时行情",
        "interface": "etf_realtime",
        "need_symbol": False,
        "table": "ak_etf_realtime",
        "mode": "snapshot",
        "limit": 100,
    },
    "futures_realtime": {
        "desc": "期货实时行情",
        "interface": "futures_realtime",
        "need_symbol": False,
        "table": "ak_futures_realtime",
        "mode": "snapshot",
    },
    "limit_up_pool": {
        "desc": "涨停池（东财，含涨停原因/连板数）",
        "interface": "limit_up_pool",
        "need_symbol": False,
        "table": "ak_limit_up_pool",
        "mode": "snapshot",
    },
    "limit_down_pool": {
        "desc": "跌停池",
        "interface": "limit_down_pool",
        "need_symbol": False,
        "table": "ak_limit_down_pool",
        "mode": "snapshot",
    },
    "sector_realtime": {
        "desc": "板块实时行情（东财）",
        "interface": "sector_realtime",
        "need_symbol": False,
        "table": "ak_sector_realtime",
        "mode": "snapshot",
    },
    "market_index_realtime": {
        "desc": "大盘指数实时行情",
        "interface": "market_index_realtime",
        "need_symbol": False,
        "table": "ak_market_index_realtime",
        "mode": "snapshot",
    },
    "cls_telegraph": {
        "desc": "财联社电报快讯",
        "interface": "cls_telegraph",
        "need_symbol": False,
        "table": "ak_cls_telegraph",
        "mode": "upsert",
        "primary_keys": ["id"],
    },
    "cls_market_emotion": {
        "desc": "财联社市场情绪",
        "interface": "cls_market_emotion",
        "need_symbol": False,
        "table": "ak_cls_market_emotion",
        "mode": "snapshot",
    },
    "cls_limit_up_pool": {
        "desc": "财联社涨停池（含详细原因）",
        "interface": "cls_limit_up_pool",
        "need_symbol": False,
        "table": "ak_cls_limit_up_pool",
        "mode": "snapshot",
    },
    "cls_sector_heat": {
        "desc": "财联社板块热度",
        "interface": "cls_sector_heat",
        "need_symbol": False,
        "table": "ak_cls_sector_heat",
        "mode": "snapshot",
    },
    "cls_market_wind": {
        "desc": "财联社今日风口",
        "interface": "cls_market_wind",
        "need_symbol": False,
        "table": "ak_cls_market_wind",
        "mode": "snapshot",
    },
    "cls_market_mainline": {
        "desc": "财联社今日主线",
        "interface": "cls_market_mainline",
        "need_symbol": False,
        "table": "ak_cls_market_mainline",
        "mode": "snapshot",
    },
    "kph_market_emotion": {
        "desc": "开盘红市场情绪",
        "interface": "kph_market_emotion",
        "need_symbol": False,
        "table": "ak_kph_market_emotion",
        "mode": "snapshot",
    },
    "lhb_daily": {
        "desc": "龙虎榜每日详情",
        "interface": "lhb_daily",
        "need_symbol": False,
        "table": "ak_lhb_daily",
        "mode": "snapshot",
    },
    "lhb_institution": {
        "desc": "龙虎榜机构席位",
        "interface": "lhb_institution",
        "need_symbol": False,
        "table": "ak_lhb_institution",
        "mode": "snapshot",
    },
    "option_commodity_list": {
        "desc": "商品期权品种列表",
        "interface": "option_commodity_list",
        "need_symbol": False,
        "table": "ak_option_commodity_list",
        "mode": "snapshot",
    },
    "option_cffex_hs300_list": {
        "desc": "沪深300期权合约列表",
        "interface": "option_cffex_hs300_list",
        "need_symbol": False,
        "table": "ak_option_cffex_hs300_list",
        "mode": "snapshot",
    },
    "news_cctv": {
        "desc": "新闻联播文字稿",
        "interface": "news_cctv",
        "need_symbol": False,
        "table": "ak_news_cctv",
        "mode": "snapshot",
    },
    "economic_calendar": {
        "desc": "财经日历",
        "interface": "economic_calendar",
        "need_symbol": False,
        "table": "ak_economic_calendar",
        "mode": "snapshot",
    },
    "stock_news": {
        "desc": "个股新闻",
        "interface": "stock_news",
        "need_symbol": True,
        "symbol_label": "股票代码",
        "default_symbol": "600519",
        "table": "ak_stock_news",
        "mode": "snapshot",
        "inject_symbol": True,
    },
    "cninfo_announcements": {
        "desc": "巨潮公告",
        "interface": "cninfo_announcements",
        "need_symbol": True,
        "symbol_label": "股票代码",
        "default_symbol": "600519",
        "table": "ak_cninfo_announcements",
        "mode": "snapshot",
        "inject_symbol": True,
    },
    "stock_profile_cninfo": {
        "desc": "公司概况（巨潮）",
        "interface": "stock_profile_cninfo",
        "need_symbol": True,
        "symbol_label": "股票代码",
        "default_symbol": "600519",
        "table": "ak_stock_profile",
        "mode": "snapshot",
        "inject_symbol": True,
    },
    "stock_dividend_cninfo": {
        "desc": "分红配送（巨潮）",
        "interface": "stock_dividend_cninfo",
        "need_symbol": True,
        "symbol_label": "股票代码",
        "default_symbol": "600519",
        "table": "ak_stock_dividend",
        "mode": "snapshot",
        "inject_symbol": True,
    },
}

# 按组展示，方便菜单选择
GROUPS: list[tuple[str, list[str]]] = [
    ("时序K线（按日期 upsert）", [
        "stock_daily", "index_daily", "etf_daily", "futures_daily",
        "index_us_daily", "index_hk_daily",
    ]),
    ("实时行情快照", [
        "stock_realtime", "index_realtime", "etf_realtime", "futures_realtime",
    ]),
    ("涨跌停/板块/大盘", [
        "limit_up_pool", "limit_down_pool", "sector_realtime", "market_index_realtime",
    ]),
    ("财联社数据", [
        "cls_telegraph", "cls_market_emotion", "cls_limit_up_pool",
        "cls_sector_heat", "cls_market_wind", "cls_market_mainline",
    ]),
    ("开盘红/龙虎榜/期权", [
        "kph_market_emotion", "lhb_daily", "lhb_institution",
        "option_commodity_list", "option_cffex_hs300_list",
    ]),
    ("新闻/公告/公司资料", [
        "news_cctv", "economic_calendar", "stock_news",
        "cninfo_announcements", "stock_profile_cninfo", "stock_dividend_cninfo",
    ]),
]


# ==================== SQLite 存储层 ====================

DEFAULT_DB = Path(__file__).parent / "data" / "finance.db"


def _infer_type(val) -> str:
    """根据样本值推断 SQLite 列类型。"""
    if isinstance(val, bool):
        return "INTEGER"
    if isinstance(val, int):
        return "INTEGER"
    if isinstance(val, float):
        return "REAL"
    return "TEXT"


def _quote_ident(name: str) -> str:
    """安全引用 SQLite 标识符。"""
    return '"' + str(name).replace('"', '""') + '"'


def ensure_table(
    conn: sqlite3.Connection,
    table: str,
    records: list[dict],
    primary_keys: list[str] | None = None,
    snapshot: bool = False,
) -> None:
    """根据 records 自动建表/补字段。

    - snapshot=True: 加自增 _id 主键，每次追加
    - snapshot=False + primary_keys: 用复合主键 upsert
    """
    if not records:
        return
    field_types: dict[str, str] = {}
    for r in records:
        for k, v in r.items():
            if k not in field_types:
                field_types[k] = _infer_type(v)

    col_defs: list[str] = []
    if snapshot:
        col_defs.append(f"{_quote_ident('_id')} INTEGER PRIMARY KEY AUTOINCREMENT")
    for k, t in field_types.items():
        col_defs.append(f"{_quote_ident(k)} {t}")
    col_defs.append(
        f"{_quote_ident('fetched_at')} TEXT DEFAULT (datetime('now','localtime'))"
    )
    if not snapshot and primary_keys:
        pk = ", ".join(_quote_ident(k) for k in primary_keys)
        col_defs.append(f"PRIMARY KEY ({pk})")
    elif not snapshot:
        col_defs.append(f"{_quote_ident('_id')} INTEGER PRIMARY KEY AUTOINCREMENT")

    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {_quote_ident(table)} ({', '.join(col_defs)})"
    )

    # 已存在的表：补齐新增字段
    cur = conn.execute(f"PRAGMA table_info({_quote_ident(table)})")
    existing = {row[1] for row in cur.fetchall()}
    for k, t in field_types.items():
        if k not in existing:
            conn.execute(
                f"ALTER TABLE {_quote_ident(table)} ADD COLUMN {_quote_ident(k)} {t}"
            )
    conn.commit()


def save_records(
    conn: sqlite3.Connection,
    table: str,
    records: list[dict],
    primary_keys: list[str] | None = None,
    snapshot: bool = False,
) -> int:
    """保存记录。snapshot 追加，否则按主键 upsert。返回写入条数。"""
    if not records:
        return 0
    ensure_table(conn, table, records, primary_keys, snapshot)

    all_fields: set[str] = set()
    for r in records:
        all_fields.update(r.keys())
    # fetched_at 走 DEFAULT 子句，不显式插入，这样 INSERT OR REPLACE 也能刷新时间
    all_fields.discard("fetched_at")
    fields = sorted(all_fields)

    placeholders = ", ".join(["?"] * len(fields))
    col_list = ", ".join(_quote_ident(f) for f in fields)
    verb = "INSERT" if snapshot else "INSERT OR REPLACE"
    sql = f"{verb} INTO {_quote_ident(table)} ({col_list}) VALUES ({placeholders})"

    count = 0
    for r in records:
        vals = []
        for f in fields:
            v = r.get(f)
            # dict/list 转 JSON 字符串，避免 SQLite 报错
            if isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False)
            vals.append(v)
        try:
            conn.execute(sql, vals)
            count += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    return count


# ==================== 采集逻辑 ====================


def collect_one(
    conn: sqlite3.Connection,
    key: str,
    symbol: str | None = None,
    verbose: bool = True,
) -> int:
    """执行单个采集项，返回写入条数。"""
    cfg = COLLECTORS[key]
    interface = cfg["interface"]
    need_symbol = cfg.get("need_symbol", False)

    params: dict = {}
    sym_used: str | None = None
    if need_symbol:
        if not symbol:
            symbol = cfg.get("default_symbol", "")
            if not symbol:
                if verbose:
                    print(f"  [skip] {key} 需要参数 symbol，未提供")
                return 0
        params["symbol"] = symbol
        sym_used = symbol

    if verbose:
        extra = f" symbol={sym_used}" if sym_used else ""
        print(f"  → 采集 {key} ({cfg['desc']}){extra} ...", end=" ", flush=True)

    call_fn = _ensure_call_unified()
    try:
        ok, data, source = call_fn(interface, **params)
    except Exception as e:
        if verbose:
            print(f"失败: {type(e).__name__}: {str(e)[:150]}")
        return 0

    if not ok:
        err = data[0].get("error", "未知错误") if data else "未知错误"
        if verbose:
            print(f"失败 [{source}]: {err}")
        return 0

    if not data:
        if verbose:
            print(f"空 [{source}]")
        return 0

    # 注入 symbol（时序K线类的 record 本身没有 symbol 字段）
    if cfg.get("inject_symbol") and sym_used:
        for r in data:
            r.setdefault("symbol", sym_used)

    # 应用 limit
    limit = cfg.get("limit")
    if limit and len(data) > limit:
        data = data[:limit]

    written = save_records(
        conn,
        cfg["table"],
        data,
        primary_keys=cfg.get("primary_keys"),
        snapshot=(cfg["mode"] == "snapshot"),
    )
    if verbose:
        mode = "snapshot" if cfg["mode"] == "snapshot" else f"upsert@{cfg.get('primary_keys')}"
        print(f"OK [{source}] 拉取 {len(data)} 条 → 写入 {written} 条 ({mode})")
    return written


def collect_all_no_param(conn: sqlite3.Connection, verbose: bool = True) -> None:
    """采集所有无需 symbol 参数的项。"""
    keys = [k for k, c in COLLECTORS.items() if not c.get("need_symbol")]
    if verbose:
        print(f"\n=== 批量采集 {len(keys)} 项（无需参数）===")
    total = 0
    for k in keys:
        try:
            total += collect_one(conn, k, verbose=verbose)
        except KeyboardInterrupt:
            if verbose:
                print("\n  中断")
            break
    if verbose:
        print(f"=== 批量完成，共写入 {total} 条 ===\n")


# ==================== 交互式菜单 ====================


def _print_list() -> None:
    print(f"\n共 {len(COLLECTORS)} 个采集项：\n")
    for group_name, keys in GROUPS:
        print(f"【{group_name}】")
        for k in keys:
            c = COLLECTORS[k]
            tag = "需代码" if c.get("need_symbol") else "无参数"
            mode = "upsert" if c["mode"] == "upsert" else "snapshot"
            print(f"  {k:<26} {c['desc']:<22} [{tag}|{mode}]")
        print()


def _pick_symbol(cfg: dict) -> str | None:
    if not cfg.get("need_symbol"):
        return None
    default = cfg.get("default_symbol", "")
    label = cfg.get("symbol_label", "代码")
    hint = f"（回车默认 {default}）" if default else ""
    s = input(f"  输入{label}{hint}: ").strip()
    return s or default


def interactive_menu(conn: sqlite3.Connection) -> None:
    while True:
        print("\n" + "=" * 60)
        print("  金融数据采集 → SQLite (供 DBX / agent 查询)")
        print("=" * 60)
        print("  0. 退出")
        print("  a. 批量采集所有「无参数」项")
        idx = 1
        idx_map: dict[int, str] = {}
        for group_name, keys in GROUPS:
            print(f"\n  -- {group_name} --")
            for k in keys:
                c = COLLECTORS[k]
                tag = "*" if c.get("need_symbol") else " "
                print(f"  {idx:>2}.{tag} {k}  — {c['desc']}")
                idx_map[idx] = k
                idx += 1

        choice = input("\n请选择 [序号/a/0]: ").strip().lower()
        if choice == "0" or choice == "":
            break
        if choice == "a":
            collect_all_no_param(conn)
            continue

        try:
            n = int(choice)
            if n not in idx_map:
                print("  无效序号")
                continue
        except ValueError:
            print("  无效输入")
            continue

        key = idx_map[n]
        cfg = COLLECTORS[key]
        sym = _pick_symbol(cfg)
        collect_one(conn, key, symbol=sym)

        # 显示该表最近几行
        try:
            cur = conn.execute(
                f"SELECT COUNT(*) FROM {_quote_ident(cfg['table'])}"
            )
            cnt = cur.fetchone()[0]
            print(f"  表 {cfg['table']} 当前共 {cnt} 行")
        except sqlite3.OperationalError:
            pass


# ==================== CLI ====================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="金融数据采集 → SQLite (供 DBX / agent 查询)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
               "  python collect_to_dbx.py                       # 交互菜单\n"
               "  python collect_to_dbx.py --list                # 列出采集项\n"
               "  python collect_to_dbx.py -c stock_daily -s 600519\n"
               "  python collect_to_dbx.py -c limit_up_pool\n"
               "  python collect_to_dbx.py -c all                # 采集所有无参数项\n"
               "  python collect_to_dbx.py -c stock_daily,index_daily -s 600519,sh000001\n",
    )
    parser.add_argument("--list", "-l", action="store_true", help="列出所有采集项后退出")
    parser.add_argument(
        "-c", "--collect",
        help="采集项 key（多个用逗号分隔）；'all' 表示采集所有无参数项",
    )
    parser.add_argument(
        "-s", "--symbol",
        help="股票/指数/合约代码，多个用逗号分隔（按顺序对应 -c 的多个项）",
    )
    parser.add_argument("--db", default=str(DEFAULT_DB), help=f"SQLite 文件路径（默认 {DEFAULT_DB}）")
    parser.add_argument("--quiet", "-q", action="store_true", help="静默模式")
    args = parser.parse_args()

    if args.list:
        _print_list()
        return

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    verbose = not args.quiet

    try:
        if args.collect:
            keys = [k.strip() for k in args.collect.split(",") if k.strip()]
            if not keys:
                print("未指定采集项，使用 --list 查看")
                return

            if keys == ["all"]:
                collect_all_no_param(conn, verbose=verbose)
                return

            symbols = (
                [s.strip() for s in args.symbol.split(",")]
                if args.symbol else []
            )

            if verbose:
                print(f"\n数据库: {db_path}")
            total = 0
            for i, k in enumerate(keys):
                if k not in COLLECTORS:
                    print(f"  未知采集项: {k}（用 --list 查看）")
                    continue
                sym = symbols[i] if i < len(symbols) else None
                total += collect_one(conn, k, symbol=sym, verbose=verbose)
            if verbose:
                print(f"\n完成，共写入 {total} 条")
                _print_tables_summary(conn)
        else:
            if verbose:
                print(f"数据库: {db_path}")
            interactive_menu(conn)
    finally:
        conn.close()


def _print_tables_summary(conn: sqlite3.Connection) -> None:
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name LIKE 'ak_%' ORDER BY name"
        )
        tables = [r[0] for r in cur.fetchall()]
        if not tables:
            return
        print("\n各表行数：")
        for t in tables:
            n = conn.execute(f"SELECT COUNT(*) FROM {_quote_ident(t)}").fetchone()[0]
            if n > 0:
                print(f"  {t:<32} {n:>8}")
    except sqlite3.OperationalError:
        pass


if __name__ == "__main__":
    main()

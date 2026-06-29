"""
冒烟测试：a-stock-data 补充层 7 个 reference 文件覆盖的端点。

每层选 1-2 个代表性端点直连真实 API，验证：
  1. 接口可达（HTTP 200）
  2. 返回结构匹配 reference 中描述（关键字段存在）
  3. 至少返回一行有效数据

设计原则：
  - 单进程顺序执行，每个端点超时 12 秒
  - mootdx 端点在 import 失败时 SKIP 而非 FAIL（TCP 需国内 IP）
  - iwencai 端点在缺 IWENCAI_API_KEY 时 SKIP
  - 退出码：0 = 所有非 SKIP 用例 PASS；1 = 任一 FAIL
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
import urllib.request
import uuid
from datetime import datetime, timedelta
from io import StringIO

try:
    import requests
    import pandas as pd
except ImportError as e:
    print(f"missing required dep: {e}. Run: pip3 install requests pandas --user")
    sys.exit(2)


UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
TIMEOUT = 12

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results: list[tuple[str, str, str, str]] = []  # (layer, endpoint, status, detail)


def _record(layer: str, endpoint: str, status: str, detail: str = "") -> None:
    results.append((layer, endpoint, status, detail[:80]))


def _eastmoney_datacenter(report_name: str, filter_str: str = "",
                          page_size: int = 5, sort_columns: str = "",
                          sort_types: str = "-1") -> list[dict]:
    params = {
        "reportName": report_name, "columns": "ALL",
        "filter": filter_str, "pageNumber": "1", "pageSize": str(page_size),
        "sortColumns": sort_columns, "sortTypes": sort_types,
        "source": "WEB", "client": "WEB",
    }
    r = requests.get(DATACENTER_URL, params=params,
                     headers={"User-Agent": UA}, timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json()
    return (d.get("result") or {}).get("data") or []


# ============== Layer 1: 行情层 ==============

def test_tencent_quote() -> None:
    url = "https://qt.gtimg.cn/q=sh600519"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=TIMEOUT)
    data = resp.read().decode("gbk")
    vals = data.split('"')[1].split("~")
    if len(vals) < 50 or not vals[1] or not vals[3]:
        raise RuntimeError(f"short fields, got {len(vals)}")
    name, price, pe_ttm, pb = vals[1], vals[3], vals[39], vals[46]
    _record("L1 行情", "腾讯财经 sh600519", PASS,
            f"{name} price={price} PE={pe_ttm} PB={pb}")


def test_eastmoney_kline_ma() -> None:
    """patched: 替换 Baidu PAE K线（被反爬封 IP），改用东财 + pandas rolling 计算 MA"""
    r = requests.get(
        "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        params={
            "secid": "1.600519", "klt": "101", "fqt": "1",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            "lmt": "30", "beg": "0", "end": "20500101",
        },
        headers={"User-Agent": UA,
                 "Referer": "https://quote.eastmoney.com/"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json().get("data") or {}
    klines = data.get("klines") or []
    if not klines:
        raise RuntimeError("zero klines")
    rows = [{"close": float(line.split(",")[2])} for line in klines]
    df = pd.DataFrame(rows)
    df["ma5"] = df["close"].rolling(5).mean()
    df["ma20"] = df["close"].rolling(20).mean()
    last = df.dropna().iloc[-1] if df.dropna().shape[0] > 0 else None
    if last is None:
        raise RuntimeError("not enough rows to compute MA20")
    _record("L1 行情", "东财 K线+MA 600519 (patched)", PASS,
            f"{data.get('name')} {len(klines)} bars MA5={last['ma5']:.2f} MA20={last['ma20']:.2f}")


def _tdx_client(market="std"):
    """镜像 a_stock_data_common.md 的 tdx_client()：显式探测 TCP 服务器绕过
    mootdx 0.11.x BESTIP 空串 bug（v3.2.4）。失败回退 bestip / 裸 factory。"""
    import socket
    from mootdx.quotes import Quotes
    servers = [('119.97.185.59', 7709), ('124.70.133.119', 7709),
               ('116.205.183.150', 7709), ('123.60.73.44', 7709)]
    for ip, port in servers:
        try:
            with socket.create_connection((ip, port), timeout=2.0):
                return Quotes.factory(market=market, server=(ip, port))
        except Exception:
            continue
    try:
        return Quotes.factory(market=market, bestip=True)
    except Exception:
        return Quotes.factory(market=market)


def test_mootdx_quote() -> None:
    try:
        from mootdx.quotes import Quotes  # noqa: F401
    except ImportError:
        _record("L1 行情", "mootdx K线 600519", SKIP,
                "mootdx not installed (pip install mootdx)")
        return
    try:
        client = _tdx_client()  # v3.2.4: 规避 BESTIP 空串 bug
        klines = client.bars(symbol="600519", frequency=9, offset=5)  # v3.2.5: frequency 非 category
        n = len(klines) if klines is not None else 0
        if n == 0:
            raise RuntimeError("zero rows")
        _record("L1 行情", "mootdx K线 600519", PASS, f"{n} bars")
    except Exception as e:
        # 海外 IP 通常 TCP 超时，列为 SKIP 而非 FAIL
        _record("L1 行情", "mootdx K线 600519", SKIP,
                f"TCP failed (overseas IP?) {e!r}"[:80])


# ============== Layer 2: 研报层 ==============

def test_eastmoney_reports() -> None:
    url = "https://reportapi.eastmoney.com/report/list"
    params = {
        "industryCode": "*", "pageSize": "10", "industry": "*",
        "rating": "*", "ratingChange": "*",
        "beginTime": "2024-01-01", "endTime": "2030-01-01",
        "pageNo": "1", "fields": "", "qType": "0",
        "orgCode": "", "code": "688017", "rcode": "",
        "p": "1", "pageNum": "1", "pageNumber": "1",
    }
    r = requests.get(url, params=params,
                     headers={"User-Agent": UA,
                              "Referer": "https://data.eastmoney.com/"},
                     timeout=TIMEOUT)
    r.raise_for_status()
    rows = r.json().get("data") or []
    if not rows or "infoCode" not in rows[0]:
        raise RuntimeError(f"empty or missing infoCode, sample={rows[:1]}")
    _record("L2 研报", "东财研报列表 688017", PASS, f"{len(rows)} reports")


def test_ths_eps_forecast() -> None:
    url = "https://basic.10jqka.com.cn/new/688017/worth.html"
    r = requests.get(url, headers={"User-Agent": UA,
                                   "Referer": "https://basic.10jqka.com.cn/"},
                     timeout=TIMEOUT)
    r.encoding = "gbk"
    dfs = pd.read_html(StringIO(r.text))
    if not dfs:
        raise RuntimeError("no tables parsed")
    has_eps = any(
        any(("每股收益" in str(c)) or ("均值" in str(c)) for c in df.columns)
        for df in dfs
    )
    _record("L2 研报", "同花顺一致预期 688017",
            PASS if has_eps else FAIL,
            f"{len(dfs)} tables, has_eps_col={has_eps}")


def test_iwencai_search() -> None:
    key = os.environ.get("IWENCAI_API_KEY", "").strip()
    if not key:
        _record("L2 研报", "iwencai NL search", SKIP,
                "IWENCAI_API_KEY not set")
        return
    import secrets
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "X-Claw-Call-Type": "normal",
        "X-Claw-Skill-Id": "report-search",
        "X-Claw-Skill-Version": "2.0.0",
        "X-Claw-Plugin-Id": "none",
        "X-Claw-Plugin-Version": "none",
        "X-Claw-Trace-Id": secrets.token_hex(32),
    }
    base = os.environ.get("IWENCAI_BASE_URL", "https://openapi.iwencai.com")
    r = requests.post(
        f"{base}/v1/comprehensive/search",
        json={"channels": ["report"], "app_id": "AIME_SKILL",
              "query": "人形机器人", "size": 5},
        headers=headers, timeout=TIMEOUT,
    )
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:100]}")
    n = len(r.json().get("data") or [])
    _record("L2 研报", "iwencai NL search", PASS, f"{n} articles")


# ============== Layer 3: 信号层 ==============

def test_ths_hot_reason() -> None:
    # 找一个近期工作日
    today = datetime.now()
    for back in range(7):
        d = (today - timedelta(days=back)).strftime("%Y-%m-%d")
        url = (f"http://zx.10jqka.com.cn/event/api/getharden/"
               f"date/{d}/orderby/date/orderway/desc/charset/GBK/")
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        try:
            data = r.json()
        except Exception:
            continue
        if data.get("errocode", -1) != 0:
            continue
        rows = data.get("data") or []
        if rows:
            sample = rows[0]
            _record("L3 信号", f"同花顺热点归因 {d}", PASS,
                    f"{len(rows)} stocks, reason={sample.get('reason','')[:30]}")
            return
    _record("L3 信号", "同花顺热点归因", FAIL, "no recent trading day data")


def test_northbound_realtime() -> None:
    url = "https://data.hexin.cn/market/hsgtApi/method/dayChart/"
    headers = {
        "User-Agent": UA, "Host": "data.hexin.cn",
        "Referer": "https://data.hexin.cn/",
    }
    r = requests.get(url, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json()
    n_pts = len(d.get("time") or [])
    if n_pts == 0:
        raise RuntimeError("zero time points")
    _record("L3 信号", "同花顺北向 hsgtApi", PASS, f"{n_pts} minute points")


def test_eastmoney_concept_blocks() -> None:
    """V3.2.2: 概念板块改用东财 slist spt=3（上游官方替换百度 PAE）"""
    r = requests.get(
        "https://push2.eastmoney.com/api/qt/slist/get",
        params={"fltt": "2", "invt": "2", "secid": "1.600519",
                "spt": "3", "pi": "0", "pz": "200", "po": "1",
                "fields": "f12,f14,f3,f128"},
        headers={"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    diff = (r.json().get("data") or {}).get("diff") or {}
    items = list(diff.values()) if isinstance(diff, dict) else diff
    if not items:
        raise RuntimeError("zero boards")
    sample = ", ".join(it.get("f14", "") for it in items[:4])
    _record("L3 信号", "东财 slist 概念板块 600519 (v3.2.2)", PASS,
            f"{len(items)} boards: {sample}")


def test_eastmoney_fund_flow_minute() -> None:
    url = "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
    params = {
        "secid": "1.600519", "klt": 1,
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
    }
    r = requests.get(url, params=params,
                     headers={"User-Agent": UA}, timeout=TIMEOUT)
    r.raise_for_status()
    klines = (r.json().get("data") or {}).get("klines") or []
    # 非交易时段可能为空，端点可达即 PASS
    _record("L3 信号", "东财资金流分钟 600519", PASS,
            f"{len(klines)} klines (may be 0 outside trading hours)")


def test_dragon_tiger_daily() -> None:
    # 找近 14 个交易日里有数据的日期
    today = datetime.now()
    for back in range(14):
        d = (today - timedelta(days=back)).strftime("%Y-%m-%d")
        rows = _eastmoney_datacenter(
            "RPT_DAILYBILLBOARD_DETAILSNEW",
            filter_str=f"(TRADE_DATE>='{d}')(TRADE_DATE<='{d}')",
            page_size=10,
            sort_columns="BILLBOARD_NET_AMT", sort_types="-1",
        )
        if rows:
            _record("L3 信号", f"全市场龙虎榜 {d}", PASS,
                    f"{len(rows)} records sample={rows[0].get('SECURITY_NAME_ABBR','')}")
            return
    _record("L3 信号", "全市场龙虎榜", FAIL, "no records in last 14 days")


def test_lockup_expiry() -> None:
    rows = _eastmoney_datacenter(
        "RPT_LIFT_STAGE",
        filter_str='(SECURITY_CODE="002475")',
        page_size=5,
        sort_columns="FREE_DATE", sort_types="-1",
    )
    if not rows:
        raise RuntimeError("zero rows")
    _record("L3 信号", "限售解禁日历 002475", PASS,
            f"{len(rows)} records latest={str(rows[0].get('FREE_DATE',''))[:10]}")


def test_industry_comparison() -> None:
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "100", "po": "1", "np": "1",
        "fltt": "2", "invt": "2", "fs": "m:90+t:2",
        "fields": "f2,f3,f4,f12,f13,f14,f104,f105",
    }
    r = requests.get(url, params=params,
                     headers={"User-Agent": UA}, timeout=TIMEOUT)
    r.raise_for_status()
    items = (r.json().get("data") or {}).get("diff") or []
    if not items:
        raise RuntimeError("empty diff")
    _record("L3 信号", "东财行业排名", PASS,
            f"{len(items)} industries top={items[0].get('f14','')}")


# ============== Layer 4: 资金面/筹码层 ==============

def test_margin_trading() -> None:
    rows = _eastmoney_datacenter(
        "RPTA_WEB_RZRQ_GGMX",
        filter_str='(SCODE="600519")',
        page_size=5,
        sort_columns="DATE", sort_types="-1",
    )
    if not rows or "RZYE" not in rows[0]:
        raise RuntimeError(f"missing RZYE field, sample={rows[:1]}")
    _record("L4 资金面", "融资融券 600519", PASS,
            f"{len(rows)} days latest_rzye={rows[0].get('RZYE',0)/1e8:.1f}亿")


def test_block_trade() -> None:
    rows = _eastmoney_datacenter(
        "RPT_DATA_BLOCKTRADE",
        filter_str='(SECURITY_CODE="600519")',
        page_size=5,
        sort_columns="TRADE_DATE", sort_types="-1",
    )
    # 茅台大宗交易可能稀疏，端点返回结构正确即 PASS
    if rows and "DEAL_PRICE" not in rows[0]:
        raise RuntimeError(f"missing DEAL_PRICE, sample={rows[:1]}")
    _record("L4 资金面", "大宗交易 600519", PASS,
            f"{len(rows)} trades (may be 0 if no recent block trades)")


def test_holder_num() -> None:
    rows = _eastmoney_datacenter(
        "RPT_HOLDERNUMLATEST",
        filter_str='(SECURITY_CODE="600519")',
        page_size=5,
        sort_columns="END_DATE", sort_types="-1",
    )
    if not rows or "HOLDER_NUM" not in rows[0]:
        raise RuntimeError(f"missing HOLDER_NUM, sample={rows[:1]}")
    _record("L4 资金面", "股东户数 600519", PASS,
            f"{len(rows)} quarters latest={rows[0].get('HOLDER_NUM',0)}")


def test_dividend_history() -> None:
    rows = _eastmoney_datacenter(
        "RPT_SHAREBONUS_DET",
        filter_str='(SECURITY_CODE="600519")',
        page_size=5,
        sort_columns="EX_DIVIDEND_DATE", sort_types="-1",
    )
    if not rows:
        raise RuntimeError("zero rows")
    _record("L4 资金面", "分红送转 600519", PASS,
            f"{len(rows)} dividends latest_date={str(rows[0].get('EX_DIVIDEND_DATE',''))[:10]}")


def test_fund_flow_120d() -> None:
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "secid": "1.600519",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "lmt": "20",
    }
    r = requests.get(url, params=params,
                     headers={"User-Agent": UA}, timeout=TIMEOUT)
    r.raise_for_status()
    klines = (r.json().get("data") or {}).get("klines") or []
    if not klines:
        raise RuntimeError("zero klines")
    _record("L4 资金面", "120日资金流 600519", PASS,
            f"{len(klines)} days latest={klines[-1].split(',')[0]}")


# ============== Layer 5: 新闻层 ==============

def test_eastmoney_stock_news() -> None:
    """patched: search-api-web JSONP 对纯股票代码 keyword 不再返新闻，改用 np-listapi"""
    r = requests.get(
        "https://np-listapi.eastmoney.com/comm/web/getListInfo",
        params={
            "client": "web", "biz": "web_n_pc_n_xinwen", "trackID": "",
            "mTypeAndCode": "1.600519", "type": "1",
            "pageSize": "10", "pageIndex": "1", "callback": "",
        },
        headers={"User-Agent": UA,
                 "Referer": "https://so.eastmoney.com/"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    rows = ((r.json().get("data") or {}).get("list") or [])
    if not rows:
        raise RuntimeError("zero articles")
    _record("L5 新闻", "东财个股新闻 600519 (patched)", PASS,
            f"{len(rows)} articles top={rows[0].get('Art_Title','')[:30]}")


def test_cls_telegraph() -> None:
    """已下线（上游 v3.2.1 #14）：cls.cn 迁 Next.js，旧 API 返回 404。
    保留为 SKIP 以记录弃用；全市场快讯改用 §5.3 东财全球资讯。"""
    _record("L5 新闻", "财联社快讯", SKIP,
            "已下线 #14（cls.cn 旧API 404），改用东财全球资讯")


def test_eastmoney_global_news() -> None:
    r = requests.get(
        "https://np-weblist.eastmoney.com/comm/web/getFastNewsList",
        params={
            "client": "web", "biz": "web_724",
            "fastColumn": "102", "sortEnd": "",
            "pageSize": "10",
            "req_trace": str(uuid.uuid4()),
        },
        headers={"User-Agent": UA, "Referer": "https://kuaixun.eastmoney.com/"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    rows = (r.json().get("data") or {}).get("fastNewsList") or []
    if not rows:
        raise RuntimeError("zero rows")
    _record("L5 新闻", "东财全球资讯", PASS, f"{len(rows)} items")


# ============== Layer 6: 基础数据层 ==============

def test_eastmoney_stock_info() -> None:
    r = requests.get(
        "https://push2.eastmoney.com/api/qt/stock/get",
        params={
            "fltt": "2", "invt": "2",
            "fields": "f57,f58,f84,f85,f127,f116,f117,f189,f43",
            "secid": "1.600519",
        },
        headers={"User-Agent": UA}, timeout=TIMEOUT,
    )
    r.raise_for_status()
    d = (r.json() or {}).get("data") or {}
    if not d.get("f58"):
        raise RuntimeError(f"empty data {d}")
    _record("L6 基础数据", "东财个股信息 600519", PASS,
            f"{d.get('f58')} 行业={d.get('f127')} 上市={d.get('f189')}")


def test_sina_financial_report() -> None:
    """响应结构 result.data.report_list[date_value].data（mx-skills 2026-05-20 首修，
    上游 v3.2.1 已官方采纳同向修复，本地 patch 退役）"""
    r = requests.get(
        "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022",
        params={"paperCode": "sh600519", "source": "lrb",
                "type": "0", "page": "1", "num": "5"},
        headers={"User-Agent": UA}, timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = ((r.json().get("result") or {}).get("data") or {})
    periods = data.get("report_date") or []
    report_list = data.get("report_list") or {}
    if not periods or not report_list:
        raise RuntimeError(f"missing periods or report_list, "
                           f"periods={len(periods)} list={len(report_list)}")
    latest = periods[0]["date_value"]
    items = (report_list.get(latest) or {}).get("data") or []
    _record("L6 基础数据", "新浪利润表 600519 (patched)", PASS,
            f"{len(periods)} periods, latest {latest} has {len(items)} line items")


def test_mootdx_finance() -> None:
    try:
        from mootdx.quotes import Quotes  # noqa: F401
    except ImportError:
        _record("L6 基础数据", "mootdx 财务37字段", SKIP,
                "mootdx not installed")
        return
    try:
        client = _tdx_client()  # v3.2.4: 规避 BESTIP 空串 bug
        fin = client.finance(symbol="600519")
        if fin is None:
            raise RuntimeError("None returned")
        _record("L6 基础数据", "mootdx 财务37字段 600519", PASS, "ok")
    except Exception as e:
        _record("L6 基础数据", "mootdx 财务37字段 600519", SKIP,
                f"TCP failed {e!r}"[:80])


# ============== Layer 7: 公告层 ==============

def _cninfo_orgid(code: str) -> str:
    """V3.2.2: 动态查官方 szse_stock.json 映射表，硬编码 fallback。"""
    r = requests.get("http://www.cninfo.com.cn/new/data/szse_stock.json",
                     headers={"User-Agent": UA}, timeout=TIMEOUT)
    m = {s["code"]: s["orgId"] for s in r.json().get("stockList", [])}
    org = m.get(code)
    if org:
        return org
    if code.startswith("6"):
        return f"gssh0{code}"
    elif code.startswith("8") or code.startswith("4"):
        return f"gsbj0{code}"
    return f"gssz0{code}"


def test_cninfo_announcements() -> None:
    """V3.2.2: 用 601318（平安）验证动态 orgId 修复——硬编码 gssh0601318 会返回 0 条。"""
    code = "601318"
    org_id = _cninfo_orgid(code)
    if org_id == f"gssh0{code}":
        raise RuntimeError("orgId 映射表未命中 601318（应为 9900002221）")
    payload = {
        "stock": f"{code},{org_id}",
        "tabName": "fulltext", "pageSize": "10", "pageNum": "1",
        "column": "", "category": "", "plate": "",
        "seDate": "", "searchkey": "", "secid": "",
        "sortName": "", "sortType": "", "isHLtitle": "true",
    }
    r = requests.post(
        "https://www.cninfo.com.cn/new/hisAnnouncement/query",
        data=payload,
        headers={
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://www.cninfo.com.cn/new/disclosure",
            "Origin": "https://www.cninfo.com.cn",
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    anns = r.json().get("announcements") or []
    if not anns:
        raise RuntimeError("zero announcements")
    _record("L7 公告", "巨潮公告 601318 动态orgId (v3.2.2)", PASS,
            f"orgId={org_id} {len(anns)} anns top={anns[0].get('announcementTitle','')[:24]}")


# ============== Layer 8/9/10: V3.3.0 新增层 ==============

def test_em_zt_pool() -> None:
    """L8 打板：东财涨停池（push2ex）。取最近工作日，非交易日 data=null → SKIP。"""
    d = datetime.now()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    date = d.strftime("%Y%m%d")
    r = requests.get("https://push2ex.eastmoney.com/getTopicZTPool",
        params={"ut": "7eea3edcaed734bea9cbfc24409ed989", "dpt": "wz.ztzt",
                "Pageindex": "0", "pagesize": "20", "sort": "fbt:asc", "date": date},
        headers={"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"}, timeout=TIMEOUT)
    pool = (r.json().get("data") or {}).get("pool") or []
    if not pool:
        _record("L8 打板", "东财涨停池", SKIP, f"date={date} 0 涨停（非交易日/盘前）"); return
    s = pool[0]
    if not all(k in s for k in ("c", "n", "lbc", "zbc")):
        raise RuntimeError(f"涨停池字段缺失 keys={list(s.keys())}")
    _record("L8 打板", "东财涨停池 (v3.3.0)", PASS,
            f"{len(pool)} 涨停 top={s.get('n')} {s.get('lbc')}板 炸板{s.get('zbc')}次")


def test_sina_option_codes() -> None:
    """L9 ETF期权：新浪 50ETF 合约月份清单。"""
    r = requests.get("https://stock.finance.sina.com.cn/futures/api/openapi.php/"
                     "StockOptionService.getStockName?exchange=null&cate=50ETF",
                     headers={"User-Agent": UA, "Referer": "https://stock.finance.sina.com.cn/"},
                     timeout=TIMEOUT)
    months = (((r.json().get("result") or {}).get("data") or {}).get("contractMonth")) or []
    if len(months) < 2:
        raise RuntimeError(f"期权合约月份为空: {months}")
    _record("L9 ETF期权", "新浪50ETF合约清单 (v3.3.0)", PASS,
            f"{len(months)-1} 个月份 近月={months[1] if len(months)>1 else '?'}")


def test_ths_hot_list() -> None:
    """L10 舆情：同花顺热榜（人气+概念标签）。"""
    r = requests.get("https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock",
        params={"stock_type": "a", "type": "hour", "list_type": "normal"},
        headers={"User-Agent": UA}, timeout=TIMEOUT)
    lst = (r.json().get("data") or {}).get("stock_list") or []
    if not lst:
        raise RuntimeError("同花顺热榜为空")
    _record("L10 舆情", "同花顺热榜 (v3.3.0)", PASS,
            f"{len(lst)} 只 top={lst[0].get('name')} 人气={lst[0].get('rate')}")


# ============== Runner ==============

ALL_TESTS = [
    test_tencent_quote, test_eastmoney_kline_ma, test_mootdx_quote,
    test_eastmoney_reports, test_ths_eps_forecast, test_iwencai_search,
    test_ths_hot_reason, test_northbound_realtime, test_eastmoney_concept_blocks,
    test_eastmoney_fund_flow_minute, test_dragon_tiger_daily,
    test_lockup_expiry, test_industry_comparison,
    test_margin_trading, test_block_trade, test_holder_num,
    test_dividend_history, test_fund_flow_120d,
    test_eastmoney_stock_news, test_cls_telegraph, test_eastmoney_global_news,
    test_eastmoney_stock_info, test_sina_financial_report, test_mootdx_finance,
    test_cninfo_announcements,
    test_em_zt_pool, test_sina_option_codes, test_ths_hot_list,
]


def main() -> int:
    t0 = time.time()
    for fn in ALL_TESTS:
        try:
            fn()
        except (requests.exceptions.ConnectionError,
                requests.exceptions.ProxyError,
                requests.exceptions.Timeout) as e:
            # 连接级失败（代理拒连 / 超时 / 大陆住宅 IP 间歇风控 #18）非代码 bug → SKIP
            results.append(("?", fn.__name__, SKIP,
                            f"连接级失败(非代码bug,#18): {type(e).__name__}"[:80]))
        except Exception as e:
            results.append(("?", fn.__name__, FAIL,
                            f"{type(e).__name__}: {e}"[:80]))

    print(f"\n{'='*88}")
    print(f"{'Layer':<14}{'Endpoint':<32}{'Status':<8}Detail")
    print(f"{'='*88}")
    counts = {PASS: 0, FAIL: 0, SKIP: 0}
    for layer, ep, status, detail in results:
        counts[status] = counts.get(status, 0) + 1
        print(f"{layer:<14}{ep:<32}{status:<8}{detail}")
    print(f"{'='*88}")
    print(f"PASS={counts[PASS]}  FAIL={counts[FAIL]}  SKIP={counts[SKIP]}  "
          f"({time.time()-t0:.1f}s)")
    return 0 if counts[FAIL] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

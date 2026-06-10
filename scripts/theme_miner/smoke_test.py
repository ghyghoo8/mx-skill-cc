"""
冒烟测试：theme_miner 数据桥的补充端点（a-stock-data 暂缺、本层自带的部分）。

只测本层 *新增* 的东财端点（涨停池 / 跌停池 / 行业涨跌家数汇总）——
题材/个股打分是纯方法论（无代码），其余数据需求复用 a-stock-data
（已由 scripts/a_stock_data/smoke_test.py 覆盖），此处不重复测。

设计原则（对齐 a_stock_data/smoke_test.py）：
  - 单进程顺序执行，每端点超时 12 秒
  - 网络/代理异常 → SKIP（非 FAIL）：push2 系列在本地代理下偶发 ProxyError
  - 结构/字段不符 → FAIL
  - 退出码：0 = 无 FAIL；1 = 任一 FAIL
"""

from __future__ import annotations

import sys
import time
import random
from datetime import datetime, timedelta

try:
    import requests
except ImportError:
    print("缺少 requests：pip install requests", file=sys.stderr)
    sys.exit(2)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
TIMEOUT = 12
PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results: list[tuple[str, str, str]] = []  # (endpoint, status, detail)

_S = requests.Session()
_S.headers.update({"User-Agent": UA})
REF = {"Referer": "https://quote.eastmoney.com/"}


def _record(ep: str, status: str, detail: str = "") -> None:
    results.append((ep, status, detail[:90]))


def _recent_trade_date() -> str:
    """取最近一个工作日（粗略，忽略节假日）。"""
    d = datetime.now()
    while d.weekday() >= 5:  # 周六/日回退
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def _is_network_err(e: Exception) -> bool:
    s = repr(e).lower()
    return any(k in s for k in ("proxy", "timeout", "timed out", "connection",
                                 "max retries", "remotedisconnected"))


def test_zt_pool() -> None:
    date = _recent_trade_date()
    try:
        r = _S.get("https://push2ex.eastmoney.com/getTopicZTPool",
                   params={"ut": "7eea3edcaed734bea9cbfc24409ed989", "dpt": "wz.ztzt",
                           "Pageindex": "0", "pagesize": "200", "sort": "fbt:asc", "date": date},
                   headers=REF, timeout=TIMEOUT)
        pool = (r.json().get("data") or {}).get("pool") or []
    except Exception as e:
        if _is_network_err(e):
            _record("涨停池 getTopicZTPool", SKIP, f"network: {repr(e)[:60]}"); return
        raise
    if not pool:
        _record("涨停池 getTopicZTPool", SKIP, f"date={date} 0 涨停（可能非交易日/盘前）"); return
    s = pool[0]
    missing = [k for k in ("c", "n", "zdp", "lbc", "hybk") if k not in s]
    if missing:
        raise RuntimeError(f"涨停池字段缺失 {missing}; keys={list(s.keys())}")
    _record("涨停池 getTopicZTPool", PASS,
            f"{len(pool)} 涨停 top={s.get('n')} {s.get('lbc')}板 行业={s.get('hybk')}")


def test_dt_pool() -> None:
    date = _recent_trade_date()
    try:
        r = _S.get("https://push2ex.eastmoney.com/getTopicDTPool",
                   params={"ut": "7eea3edcaed734bea9cbfc24409ed989", "dpt": "wz.dtzt",
                           "Pageindex": "0", "pagesize": "200", "sort": "fund:asc", "date": date},
                   headers=REF, timeout=TIMEOUT)
        data = r.json().get("data")
    except Exception as e:
        if _is_network_err(e):
            _record("跌停池 getTopicDTPool", SKIP, f"network: {repr(e)[:60]}"); return
        raise
    # 绿盘日 0 跌停时东财返回 data=null（合法）；否则应为含 pool 的 dict。
    # 与 data_bridge 的 (r.json().get("data") or {}).get("pool") 取值方式一致。
    if data is not None and (not isinstance(data, dict) or "pool" not in data):
        raise RuntimeError(f"跌停池结构异常: {type(data)}")
    pool = (data or {}).get("pool") or []
    _record("跌停池 getTopicDTPool", PASS, f"{len(pool)} 跌停（data={'null' if data is None else 'dict'}，0 在绿盘日正常）")


def test_market_breadth() -> None:
    try:
        r = _S.get("https://push2.eastmoney.com/api/qt/clist/get",
                   params={"pn": "1", "pz": "500", "po": "1", "np": "1", "fltt": "2", "invt": "2",
                           "fs": "m:90+t:2", "fields": "f12,f14,f104,f105"},
                   headers=REF, timeout=TIMEOUT)
        diff = (r.json().get("data") or {}).get("diff") or []
    except Exception as e:
        if _is_network_err(e):
            _record("行业涨跌家数汇总 clist m:90+t:2", SKIP, f"network: {repr(e)[:60]}"); return
        raise
    if not diff:
        raise RuntimeError("行业板块返回空")
    up = sum((x.get("f104") or 0) for x in diff)
    down = sum((x.get("f105") or 0) for x in diff)
    if up == 0 and down == 0:
        raise RuntimeError(f"f104/f105 全 0，字段语义可能变化; sample={diff[0]}")
    _record("行业涨跌家数汇总 clist m:90+t:2", PASS,
            f"{len(diff)} 板块 Σ上涨={up} Σ下跌={down} 涨跌比={up/down:.2f}" if down else
            f"{len(diff)} 板块 Σ上涨={up} Σ下跌=0")


def test_concept_blocks_and_members() -> None:
    """slist 个股→所属板块（v3.2.2），再用 fs=b:BK 取板块→成分股。
    验证 data_bridge 对 eastmoney_concept_blocks 的「股→板块」语义理解 +
    theme_miner_board_members 的「板块→成分股」补充端点。"""
    try:
        r = _S.get("https://push2.eastmoney.com/api/qt/slist/get",
                   params={"fltt": "2", "invt": "2", "secid": "1.600519",
                           "spt": "3", "pi": "0", "pz": "50", "po": "1", "fields": "f12,f14"},
                   headers=REF, timeout=TIMEOUT)
        diff = (r.json().get("data") or {}).get("diff") or {}
    except Exception as e:
        if _is_network_err(e):
            _record("slist 股→板块 + 板块→成分股", SKIP, f"network: {repr(e)[:60]}"); return
        raise
    items = list(diff.values()) if isinstance(diff, dict) else diff
    bks = [(x.get("f12"), x.get("f14")) for x in items if str(x.get("f12", "")).startswith("BK")]
    if not bks:
        raise RuntimeError(f"slist 未返回 BK 板块码; sample={items[:1]}")
    # 板块→成分股
    bk = bks[0][0]
    try:
        r2 = _S.get("https://push2.eastmoney.com/api/qt/clist/get",
                    params={"pn": "1", "pz": "10", "po": "1", "np": "1", "fltt": "2", "invt": "2",
                            "fid": "f3", "fs": f"b:{bk}", "fields": "f12,f14,f3"},
                    headers=REF, timeout=TIMEOUT)
        mem = (r2.json().get("data") or {}).get("diff") or []
    except Exception as e:
        if _is_network_err(e):
            _record("slist 股→板块 + 板块→成分股", SKIP,
                    f"slist OK ({len(bks)}板块); members network: {repr(e)[:40]}"); return
        raise
    if not mem:
        raise RuntimeError(f"板块 {bk} 成分股为空")
    _record("slist 股→板块 + 板块→成分股", PASS,
            f"茅台 {len(bks)} 板块({bks[0][1]}…); {bk} 成分股 {len(mem)} 只")


TESTS = [test_zt_pool, test_dt_pool, test_market_breadth, test_concept_blocks_and_members]


def main() -> int:
    for t in TESTS:
        try:
            t()
        except Exception as e:
            _record(t.__name__, FAIL, repr(e)[:90])
        time.sleep(0.5 + random.uniform(0.1, 0.4))  # 礼貌节流

    print("=" * 78)
    print(f"{'Endpoint':<40}{'Status':<8}{'Detail'}")
    print("=" * 78)
    n_pass = n_fail = n_skip = 0
    for ep, status, detail in results:
        print(f"{ep:<40}{status:<8}{detail}")
        n_pass += status == PASS
        n_fail += status == FAIL
        n_skip += status == SKIP
    print("=" * 78)
    print(f"PASS={n_pass}  FAIL={n_fail}  SKIP={n_skip}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())

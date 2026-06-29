---
name: a_stock_market_data
description: A股行情层 — mootdx K线/盘口、腾讯财经 PE/PB/市值、百度股市通 K线带MA
metadata:
  upstream: simonlin1212/a-stock-data
  upstream_commit: bcda4054
  upstream_version: 3.3.0
  upstream_date: 2026-06-28
  license: Apache-2.0
  author: Simon 林
  layer: Layer 1 行情层
  patched: true
  patch_notes:
    - "2026-05-20 mx-skills: §1.3 百度 K线带 MA 接口已被 Baidu PAE 反爬封锁（ResultCode=403），改用东财 push2his K线 + 本地 pandas rolling 计算 MA5/10/20"
---

> Vendored from [simonlin1212/a-stock-data](https://github.com/simonlin1212/a-stock-data) (Apache-2.0, V3.3.0 @ 2026-06-28, commit bcda4054).
> Author: Simon 林 — please retain this attribution per Apache-2.0.
>
> **在 mx-skills 中的使用方式**：本文件是 mx-skills 的**补充/降级数据层**。SKILL.md 路由层决定何时读取此文件。共享辅助代码（UA、ticker 归一化、eastmoney_datacenter helper、估值公式）在 `a_stock_data_common.md` — 执行本文件代码前先读那个。
>
> **调用约定 D（内嵌 Python）**：本文件的代码块由模型用 `python3 -c "..."` 直接执行，**返回 Python 值**，不写文件。区别于 mx-skills 现有的脚本子进程模式（A/B/C 三种 stdout 约定）。

## Layer 1: 行情层（实时，不封IP）

### 1.1 mootdx — K线 + 五档盘口 + 逐笔成交

TCP 二进制协议，连通达信服务器(7709)，无需注册，不封IP。

```python
from mootdx.quotes import Quotes

client = tdx_client()  # 见 Prerequisites 的 tdx_client() helper（规避 0.11.x BESTIP bug；等价 Quotes.factory(market='std')）

# === K线数据 ===
# market: 0=深圳, 1=上海
# ⚠️ 参数名是 frequency（不是 category！传 category 会被 **kwargs 静默吞掉，
#    永远退化成默认 frequency=9 日线，拿不到分钟数据）。
# mootdx 0.11.7 实测频率值表：
#   0=5分钟  1=15分钟  2=30分钟  3=60分钟(1小时)  4=日线  5=周线  6=月线
#   8=1分钟  9=日线(默认)  10=季线  11=年线        （7=1分钟除权口径,少用）
klines = client.bars(symbol='688017', frequency=9, offset=10)    # 日线
min1   = client.bars(symbol='688017', frequency=8, offset=240)   # 1分钟（一个交易日≈240根）
min5   = client.bars(symbol='688017', frequency=0, offset=48)    # 5分钟
# 返回: open, close, high, low, vol, amount, datetime
# ⚠️ 复权：bars 返回【不复权】原始价（通达信原始数据，无 adjust 参数）。
#    跨除权除息日做估值/回测前需自行复权，或改用带前复权的日K数据源（腾讯财经）。

# === 实时报价 ===
quotes = client.quotes(symbol=['688017', '300476'])
# 返回 46 个字段:
#   price(现价), open, high, low, last_close(昨收)
#   bid1~bid5, ask1~ask5, bid_vol1~bid_vol5, ask_vol1~ask_vol5
#   vol(成交量), amount(成交额), servertime

# === 逐笔成交（非交易时间返回空）===
trades = client.transaction(symbol='688017', date='20260502')
# 返回: time, price, vol, num, buyorsell(0买/1卖/2中性)
```

**mootdx 不提供 PE / PB / 市值 / 换手率 / 涨跌停价** — 这些走腾讯财经。

### 1.2 腾讯财经 API — PE/PB/市值/换手率/涨跌停/指数/ETF

HTTP GET，GBK 编码，`~` 分隔 88 个字段，不封IP。

```python
import urllib.request

def tencent_quote(codes: list[str]) -> dict[str, dict]:
    """
    批量拉取腾讯财经实时行情。
    codes: ["688017", "300476", "002463"]
    也支持指数: ["000001", "000300", "399006"]
    也支持ETF: ["510050", "510300"]
    返回: {code: {name, price, pe_ttm, pb, mcap, ...}}
    """
    prefixed = []
    for c in codes:
        if c.startswith(("6", "9")):
            prefixed.append(f"sh{c}")
        elif c.startswith("8"):
            prefixed.append(f"bj{c}")
        else:
            prefixed.append(f"sz{c}")

    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk")

    result = {}
    for line in data.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        code = key[2:]
        result[code] = {
            "name":         vals[1],
            "price":        float(vals[3]) if vals[3] else 0,
            "last_close":   float(vals[4]) if vals[4] else 0,
            "open":         float(vals[5]) if vals[5] else 0,
            "change_amt":   float(vals[31]) if vals[31] else 0,
            "change_pct":   float(vals[32]) if vals[32] else 0,
            "high":         float(vals[33]) if vals[33] else 0,
            "low":          float(vals[34]) if vals[34] else 0,
            "amount_wan":   float(vals[37]) if vals[37] else 0,
            "turnover_pct": float(vals[38]) if vals[38] else 0,
            "pe_ttm":       float(vals[39]) if vals[39] else 0,
            "amplitude_pct":float(vals[43]) if vals[43] else 0,
            "mcap_yi":      float(vals[44]) if vals[44] else 0,
            "float_mcap_yi":float(vals[45]) if vals[45] else 0,
            "pb":           float(vals[46]) if vals[46] else 0,
            "limit_up":     float(vals[47]) if vals[47] else 0,
            "limit_down":   float(vals[48]) if vals[48] else 0,
            "vol_ratio":    float(vals[49]) if vals[49] else 0,
            "pe_static":    float(vals[52]) if vals[52] else 0,
        }
    return result

# 用法: 个股
quotes = tencent_quote(["688017", "300476", "002463"])
for code, q in quotes.items():
    print(f"{q['name']}({code}): {q['price']}元 PE={q['pe_ttm']} PB={q['pb']} 市值={q['mcap_yi']}亿")

# 用法: 指数 — sh000001=上证指数, sh000300=沪深300, sz399006=创业板指
index_quotes = tencent_quote(["000001", "000300", "399006"])

# 用法: ETF — sh510050=上证50ETF, sh510300=沪深300ETF
etf_quotes = tencent_quote(["510050", "510300"])
```

#### 腾讯财经字段索引速查（实测校准 2026-05-03）

| 索引 | 含义 | 示例 |
|------|------|------|
| 1 | 名称 | 绿的谐波 |
| 3 | 当前价 | 224.12 |
| 4 | 昨收 | 215.01 |
| 5 | 今开 | 214.10 |
| 9-18 | 买一~买五(价+量) | |
| 19-28 | 卖一~卖五(价+量) | |
| 31 | 涨跌额 | 9.11 |
| 32 | 涨跌幅% | 4.24 |
| 33 | 最高 | 229.62 |
| 34 | 最低 | 214.10 |
| 37 | 成交额(万) | 187040 |
| 38 | 换手率% | 4.55 |
| **39** | **PE(TTM)** | 300.45 |
| **43** | **振幅%（不是PB！）** | 7.22 |
| **44** | **总市值(亿)** | 410.88 |
| **45** | **流通市值(亿)** | 410.88 |
| **46** | **PB(市净率)** | 11.51 |
| **47** | **涨停价** | 258.01 |
| **48** | **跌停价** | 172.01 |
| 49 | 量比 | 1.20 |
| **52** | **PE(静)** | 314.76 |

> **踩坑提醒：** 网上很多教程把索引 43 写成 PB，实测是振幅%。PB 在索引 46。

### 1.3 K线 + MA5/MA10/MA20 — mx-skills patched

> **mx-skills patch（2026-05-20）**：上游 V3.1 的百度股市通 K 线接口（finance.pae.baidu.com/selfselect/getstockquotation）已被 Baidu PAE 反爬封锁，HTTP 200 但 `ResultCode="403"` + `Result: []`。改用东财 `push2his` K 线接口 + pandas `rolling().mean()` 本地计算均线。

```python
import requests
import pandas as pd

def eastmoney_kline_with_ma(code: str, period: str = "day", limit: int = 120) -> dict:
    """
    东财日/周/月/分钟 K 线 + 本地计算 MA5/MA10/MA20。
    period: "day"/"week"/"month"/"1min"/"5min"/"15min"/"30min"/"60min"
    返回: {"name": 股票名, "df": DataFrame(date,open,close,high,low,vol,amount,ma5,ma10,ma20)}
    """
    klt_map = {"day": "101", "week": "102", "month": "103",
               "1min": "1", "5min": "5", "15min": "15",
               "30min": "30", "60min": "60"}
    secid = (f"1.{code}" if code.startswith(("6", "9"))
             else f"0.{code}")
    r = em_get(  # 东财端点，走 em_get 内置限流（见 a_stock_data_common.md）
        "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        params={
            "secid": secid,
            "klt": klt_map.get(period, "101"),
            "fqt": "1",  # 1=前复权
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            "lmt": str(limit), "beg": "0", "end": "20500101",
        },
        headers={"Referer": "https://quote.eastmoney.com/"},
        timeout=15,
    )
    data = r.json().get("data") or {}
    rows = []
    for line in data.get("klines") or []:
        parts = line.split(",")
        rows.append({
            "date": parts[0], "open": float(parts[1]),
            "close": float(parts[2]), "high": float(parts[3]),
            "low": float(parts[4]), "vol": float(parts[5]),
            "amount": float(parts[6]),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["ma5"] = df["close"].rolling(5).mean()
        df["ma10"] = df["close"].rolling(10).mean()
        df["ma20"] = df["close"].rolling(20).mean()
    return {"name": data.get("name", ""), "df": df}

# 用法
result = eastmoney_kline_with_ma("600519")
print(result["name"], "K线数:", len(result["df"]))
print(result["df"][["date", "close", "ma5", "ma10", "ma20"]].tail())
```

---

---
name: theme_miner_data_bridge
description: 热门题材挖掘的数据桥 — 把题材挖掘的 6 类数据需求映射到 a-stock-data 的内嵌 Python 函数；并提供 a-stock-data 暂缺的「涨停池/跌停池/市场情绪」补充端点（option A：端点在本层，a-stock-data 不动）。
metadata:
  layer: theme-miner（a-stock-data 之上的可选分析层）
  depends_on: a_stock_data_common, a_stock_signals, a_stock_capital_flow, a_stock_fundamentals, a_stock_market_data, a_stock_research
  mx_skills_note: "本文件为 mx-skills 原创桥接层，非 upstream vendored。补充端点 2026-06-10 实测可用。"
---

> **作用**：题材挖掘分析层（[[theme_miner]]）本身不取数。本文件把它需要的 6 类数据，逐一映射到 **a-stock-data 已有的内嵌 Python 函数**（约定 D：读 reference → `python3 -c` 执行 → 返回 Python 值）。a-stock-data 暂时没有的「涨停股列表 / 跌停 / 全市场涨跌家数」，由本层**自带补充端点**补齐——**不修改 a-stock-data 任何文件**（保持其按上游 diff 独立升级的能力）。
>
> **前置**：使用任何东财端点前先读 [[a_stock_data_common]] 执行其「共用 helper」代码块（拿到 `UA` / `em_get` / `EM_SESSION`）。本层所有东财请求**一律走 `em_get()`**，与 a-stock-data v3.2+ 防封架构保持一致。

---

## 数据需求映射表

| # | 题材挖掘需要 | 来源 | a-stock-data 函数 / 本层补充 |
|---|---|---|---|
| 1 | 概念/行业板块行情（涨幅、成交额、换手、涨跌家数、领涨股） | a-stock-data | `a_stock_signals` 行业板块排名（东财 push2 `m:90+t:2`，含 f104/f105 涨跌家数）；概念板块归属 `eastmoney_concept_blocks()` |
| 2 | 板块成分股（行情、市值、换手、量比） | a-stock-data | `a_stock_signals` 概念板块成分 / 行业排名；个股行情用腾讯 `tencent_quote`（`a_stock_market_data`） |
| 3 | 个股资金流向（近 N 日主力净流入） | a-stock-data | `a_stock_capital_flow` `stock_fund_flow_120d()` 或 `a_stock_signals` `eastmoney_fund_flow_minute()` |
| 4 | 个股基本面（PE/PB/ROE/营收增速/净利增速/市值） | a-stock-data | `a_stock_fundamentals` `eastmoney_stock_info()` + 腾讯 `tencent_quote()`（PE/PB/市值）；增速用新浪三表 `sina_financial_report()` |
| 5 | **涨停股列表**（涨停原因/连板/封单金额） | **本层补充** | `theme_miner_zt_pool()` ↓（东财涨停池，含 `hybk` 行业归属） |
| 6 | **跌停股列表 + 全市场涨跌家数 + 涨停数** | **本层补充** | `theme_miner_dt_pool()` + `theme_miner_market_breadth()` ↓ |

> 资金趋势判定（持续流入/今日流入/流出）、PE 换算等清洗规则沿用上游 data_sources.md 口径，在打分前由模型对返回值计算。

---

## 补充端点 1：涨停池（含连板 / 封单 / 行业归属）

东财涨停池 `push2ex.eastmoney.com/getTopicZTPool`，零鉴权，返回当日全部涨停股。`hybk` 字段给出行业板块归属，可直接用于「涨停股 → 题材」匹配（替代上游靠"涨停原因文本关键词匹配"的脆弱做法）。

```python
# 前置：先执行 a_stock_data_common 的「共用 helper」代码块拿到 em_get / UA
import time
from datetime import datetime

def theme_miner_zt_pool(date: str | None = None) -> list[dict]:
    """东财涨停池。date 形如 '20260610'，默认取今天。
    返回: [{code, name, pct, lbc(连板次数), turnover_hs, seal_fund(封单元), industry(hybk), zt_stat}]
    注：交易日盘后数据最全；非交易日/盘前可能为空。"""
    date = date or datetime.now().strftime("%Y%m%d")
    r = em_get(
        "https://push2ex.eastmoney.com/getTopicZTPool",
        params={"ut": "7eea3edcaed734bea9cbfc24409ed989", "dpt": "wz.ztzt",
                "Pageindex": "0", "pagesize": "200", "sort": "fbt:asc", "date": date},
        headers={"Referer": "https://quote.eastmoney.com/"}, timeout=12,
    )
    pool = (r.json().get("data") or {}).get("pool") or []
    rows = []
    for x in pool:
        zt = x.get("zttj") or {}
        rows.append({
            "code": x.get("c", ""),
            "name": x.get("n", ""),
            "pct": x.get("zdp"),                 # 涨跌幅 %
            "lbc": x.get("lbc", 1),              # 连板次数
            "turnover_hs": x.get("hs"),          # 换手率 %
            "seal_fund": x.get("fund"),          # 封单金额（元）
            "industry": x.get("hybk", ""),       # 行业板块归属（题材匹配用）
            "zt_stat": {"days": zt.get("days"), "ct": zt.get("ct")},  # 涨停统计 N天M板
        })
    return rows

# 用法
zt = theme_miner_zt_pool()
print(f"今日涨停 {len(zt)} 只")
for s in zt[:5]:
    print(f"  {s['code']} {s['name']} {s['pct']}% {s['lbc']}板 行业={s['industry']} 封单={s['seal_fund']/1e8:.2f}亿" if s['seal_fund'] else f"  {s['code']} {s['name']}")
```

> **实测（2026-06-10）**：返回 20+ 涨停股，字段 `c/n/zdp/lbc/hs/fund/hybk/zttj` 齐全。

---

## 补充端点 2：跌停池

```python
# 前置：先执行 a_stock_data_common 的「共用 helper」代码块
from datetime import datetime

def theme_miner_dt_pool(date: str | None = None) -> list[dict]:
    """东财跌停池。返回 [{code, name, pct}]。绿盘日可能为 0。"""
    date = date or datetime.now().strftime("%Y%m%d")
    r = em_get(
        "https://push2ex.eastmoney.com/getTopicDTPool",
        params={"ut": "7eea3edcaed734bea9cbfc24409ed989", "dpt": "wz.dtzt",
                "Pageindex": "0", "pagesize": "200", "sort": "fund:asc", "date": date},
        headers={"Referer": "https://quote.eastmoney.com/"}, timeout=12,
    )
    pool = (r.json().get("data") or {}).get("pool") or []
    return [{"code": x.get("c", ""), "name": x.get("n", ""), "pct": x.get("zdp")} for x in pool]

# 用法
dt = theme_miner_dt_pool()
print(f"今日跌停 {len(dt)} 只")
```

---

## 补充端点 3：全市场涨跌家数（市场情绪）

不做 5000+ 个股逐页扫描，而是**汇总东财行业板块的每板块涨跌家数**（`m:90+t:2`，字段 `f104`=上涨家数、`f105`=下跌家数）。行业板块是全市场个股的一个划分（每只股票属于且仅属于一个行业），故求和即全市场涨跌家数——单次请求。

> 这与 a-stock-data `a_stock_signals` `industry_comparison()` 用的是同一个东财端点；如已在 Step 2 拉过行业板块，可直接复用其原始返回的 f104/f105，无需重复请求。

```python
# 前置：先执行 a_stock_data_common 的「共用 helper」代码块
def theme_miner_market_breadth() -> dict:
    """全市场涨跌家数（按行业板块 f104/f105 汇总）。
    返回: {up, down, ratio}。配合涨停/跌停数做情绪评级。"""
    r = em_get(
        "https://push2.eastmoney.com/api/qt/clist/get",
        params={"pn": "1", "pz": "500", "po": "1", "np": "1", "fltt": "2", "invt": "2",
                "fs": "m:90+t:2", "fields": "f12,f14,f104,f105"},
        headers={"Referer": "https://quote.eastmoney.com/"}, timeout=15,
    )
    diff = (r.json().get("data") or {}).get("diff") or []
    up = sum((x.get("f104") or 0) for x in diff)
    down = sum((x.get("f105") or 0) for x in diff)
    ratio = (up / down) if down else float("inf")
    return {"up": up, "down": down, "ratio": ratio, "boards": len(diff)}

def theme_miner_sentiment(date: str | None = None) -> dict:
    """组装市场情绪：涨停数/跌停数/涨跌家数/情绪评级。
    情绪评级口径见 theme_miner_execution.md。"""
    zt = theme_miner_zt_pool(date)
    dt = theme_miner_dt_pool(date)
    breadth = theme_miner_market_breadth()
    n_zt, n_dt = len(zt), len(dt)
    up, down, ratio = breadth["up"], breadth["down"], breadth["ratio"]
    if n_zt >= 80 and ratio >= 3:        rating = "高潮"
    elif n_zt >= 40 and up > down:       rating = "活跃"
    elif 0.8 <= (ratio if ratio != float("inf") else 99) <= 1.2: rating = "中性"
    elif down > up and n_zt < 20:        rating = "低迷"
    elif n_zt < 10 and (down / up if up else 99) >= 3: rating = "冰点"
    else:                                rating = "中性"
    return {"涨停数": n_zt, "跌停数": n_dt, "上涨家数": up, "下跌家数": down,
            "涨跌比": round(ratio, 2) if ratio != float("inf") else "∞", "情绪评级": rating}

# 用法
print(theme_miner_sentiment())
```

> **降级**：`theme_miner_market_breadth()` 若被东财风控（`em_get` 抛错/空），情绪评级回退为「仅用涨停数/跌停数」的粗口径（涨停≥80→高潮、≥40→活跃、<10→冰点、其余中性），不阻断主流程。

---

## 涨停股 → 题材匹配（替代上游脆弱做法）

上游用「涨停原因文本是否含板块名关键词」匹配，易漏。本层用涨停池的 `industry`(hybk) 字段 + 概念板块成分股双路匹配：

1. **行业归属直配**：`theme_miner_zt_pool()` 每只涨停股的 `industry` 直接给出其东财行业板块名——与 Step 2 的行业板块名精确匹配，统计每个行业板块的涨停家数。
2. **概念成分股补充**：对概念板块（非行业），用 a-stock-data `eastmoney_concept_blocks()` 取成分股代码集合，与涨停池代码集合取交集，得该概念的涨停家数。

两路结果即题材三维评分「驱动强度/可持续性」维度所需的「涨停家数」输入（见 [[theme_miner_theme_scoring]]）。

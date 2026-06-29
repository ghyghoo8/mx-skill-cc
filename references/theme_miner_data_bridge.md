---
name: theme_miner_data_bridge
description: 热门题材挖掘的数据桥 — 把题材挖掘的 6 类数据需求映射到 a-stock-data 的内嵌 Python 函数；涨停/跌停池复用 a-stock-data v3.3.0 官方 Layer 8（em_zt_pool/em_dt_pool），仅市场情绪汇总与板块成分股为本层补充。
metadata:
  layer: theme-miner（a-stock-data 之上的可选分析层）
  depends_on: a_stock_data_common, a_stock_signals, a_stock_capital_flow, a_stock_fundamentals, a_stock_market_data, a_stock_research, a_stock_limit_up
  mx_skills_note: "本文件为 mx-skills 原创桥接层。2026-06-28 起涨停/跌停池复用上游 Layer 8 em_zt_pool/em_dt_pool（之前是本层自建 theme_miner_zt_pool/dt_pool，上游 v3.3.0 出官方版后去重）；仅 market_breadth + board_members 仍为本层补充。"
---

> **作用**：题材挖掘分析层（[[theme_miner]]）本身不取数。本文件把它需要的 6 类数据，逐一映射到 **a-stock-data 已有的内嵌 Python 函数**（约定 D：读 reference → `python3 -c` 执行 → 返回 Python 值）。a-stock-data 暂时没有的「涨停股列表 / 跌停 / 全市场涨跌家数」，由本层**自带补充端点**补齐——**不修改 a-stock-data 任何文件**（保持其按上游 diff 独立升级的能力）。
>
> **前置**：使用任何东财端点前先读 [[a_stock_data_common]] 执行其「共用 helper」代码块（拿到 `UA` / `em_get` / `EM_SESSION`）。本层所有东财请求**一律走 `em_get()`**，与 a-stock-data v3.2+ 防封架构保持一致。

---

## 数据需求映射表

| # | 题材挖掘需要 | 来源 | a-stock-data 函数 / 本层补充 |
|---|---|---|---|
| 1 | 概念/行业板块行情（涨幅、成交额、换手、涨跌家数、领涨股） | a-stock-data | `a_stock_signals` 行业板块排名（东财 push2 `m:90+t:2`，含 f104/f105 涨跌家数 + 领涨股 f128）；**个股→所属板块** 用 `eastmoney_concept_blocks(code)`（v3.2.2 slist，返回 `{boards, concept_tags}`，是「股→板块」非「板块→成分股」） |
| 2 | 板块成分股（行情、市值、换手、量比） | **本层补充** | `theme_miner_board_members(bk_code)` ↓（东财 clist `fs=b:BK####`，板块→成分股；a-stock-data 无此函数）；个股行情/市值再用腾讯 `tencent_quote`（`a_stock_market_data`） |
| 3 | 个股资金流向（近 N 日主力净流入） | a-stock-data | `a_stock_capital_flow` `stock_fund_flow_120d()` 或 `a_stock_signals` `eastmoney_fund_flow_minute()` |
| 4 | 个股基本面（PE/PB/ROE/营收增速/净利增速/市值） | a-stock-data | `a_stock_fundamentals` `eastmoney_stock_info()` + 腾讯 `tencent_quote()`（PE/PB/市值）；增速用新浪三表 `sina_financial_report()` |
| 5 | **涨停股列表**（涨停原因/连板/封单/炸板/行业） | a-stock-data（**v3.3.0 Layer 8**） | `a_stock_limit_up` `em_zt_pool(date)`（含 `industry`=hybk 行业归属、`limit_days` 连板、`zt_stat` 几天几板）；炸板/昨涨停用 `em_zb_pool`/`em_yzt_pool` |
| 6 | **跌停股列表 + 全市场涨跌家数** | 混合 | 跌停 → a-stock-data `a_stock_limit_up` `em_dt_pool(date)`；全市场涨跌家数 → 本层 `theme_miner_market_breadth()` ↓（a-stock-data 无） |

> 资金趋势判定（持续流入/今日流入/流出）、PE 换算等清洗规则沿用上游 data_sources.md 口径，在打分前由模型对返回值计算。

---

## 涨停池 / 跌停池 → 复用 a-stock-data Layer 8（不再本层自建）

> **2026-06-28 去重（option A）**：a-stock-data **v3.3.0 新增 Layer 8 打板层**已提供官方涨停/跌停池端点，本层不再自建（旧 `theme_miner_zt_pool`/`theme_miner_dt_pool` 已删）。直接读 [[a_stock_limit_up]] 用：
>
> - **涨停池** `em_zt_pool(date)` → `[{code, name, price, pct, limit_days(连板), seal_fund(封板资金), break_times(炸板), industry(hybk), zt_stat(几天几板), ...}]`
> - **炸板池** `em_zb_pool(date)`、**昨日涨停池** `em_yzt_pool(date)`（晋级率/赚钱效应）、**跌停池** `em_dt_pool(date)`
> - 同花顺涨停揭秘 `ths_limit_up_pool(date)`（涨停原因题材 + 封板成功率 + 板型）
>
> `date` 必传（形如 `'20260628'`，交易日；非交易日返回空）。`industry` 字段即题材匹配用的行业归属（下文「涨停股 → 题材匹配」直接用它）。

---

## 补充端点 1：全市场涨跌家数（市场情绪，a-stock-data 无）

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
    情绪评级口径见 theme_miner_execution.md。
    涨停/跌停池复用 a-stock-data Layer 8（先读 a_stock_limit_up 执行其代码块拿到
    em_zt_pool/em_dt_pool）。"""
    from datetime import datetime
    date = date or datetime.now().strftime("%Y%m%d")
    zt = em_zt_pool(date)          # a_stock_limit_up（Layer 8）
    dt = em_dt_pool(date)          # a_stock_limit_up（Layer 8）
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

## 补充端点 2：板块成分股（板块 → 成分股）

⚠️ **务必区分**：a-stock-data v3.2.2 的 `eastmoney_concept_blocks(code)` 是「**个股 → 所属板块**」（输入股票代码，返回它属于哪些板块），**不是**「板块 → 成分股」。Step 4 选 Top3 题材的候选股需要后者，a-stock-data 无此函数，故本层补充（东财 clist `fs=b:{BK码}`）。

```python
# 前置：先执行 a_stock_data_common 的「共用 helper」代码块
def theme_miner_board_members(bk_code: str, top_n: int = 60) -> list[dict]:
    """板块成分股（东财 clist fs=b:BK####），按涨幅降序。
    bk_code 形如 'BK0438'（由 eastmoney_concept_blocks() 的 boards[].code 得到）。
    返回: [{code, name, pct, turnover_hs, vol_ratio, mcap}]，按 pct 降序。"""
    r = em_get(
        "https://push2.eastmoney.com/api/qt/clist/get",
        params={"pn": "1", "pz": str(top_n), "po": "1", "np": "1", "fltt": "2", "invt": "2",
                "fid": "f3", "fs": f"b:{bk_code}",
                "fields": "f12,f14,f3,f8,f10,f20"},
        headers={"Referer": "https://quote.eastmoney.com/"}, timeout=15,
    )
    diff = (r.json().get("data") or {}).get("diff") or []
    return [{
        "code": x.get("f12", ""), "name": x.get("f14", ""),
        "pct": x.get("f3"),            # 涨跌幅 %
        "turnover_hs": x.get("f8"),    # 换手率 %
        "vol_ratio": x.get("f10"),     # 量比
        "mcap": x.get("f20"),          # 总市值（元）
    } for x in diff]

# 用法：取「食品饮料」板块涨幅前 15 只
members = theme_miner_board_members("BK0438", top_n=15)
print(f"{len(members)} 只成分股 top={members[0]['name'] if members else '-'}")
```

> 实测：slist 已确认可返回个股 BK 码（如茅台 → BK0438 食品饮料 / BK0173 贵州板块）；`fs=b:BK####` 为东财成分股标准端点，与 a-stock-data `industry_comparison` 同主机同协议。

---

## 涨停股 → 题材匹配（替代上游脆弱做法）

上游用「涨停原因文本是否含板块名关键词」匹配，易漏。本层改用「**逐只涨停股归票到板块再计数**」（基于 v3.2.2 的「股→板块」语义，方向正确）：

1. **行业归属直配（快）**：`em_zt_pool(date)`（a-stock-data Layer 8）每只涨停股的 `industry`(hybk) 字段直接给出其东财行业板块名——与 Step 2 的行业板块名精确匹配，按行业累计涨停家数。
2. **板块归属精算（全）**：对每只涨停股 `c`，调用 `eastmoney_concept_blocks(c)` 得其 `concept_tags`（所属行业+概念+地域板块名列表），把该股计入这些板块——遍历完涨停池后，每个板块名累计到的涨停股数即「涨停家数」。这覆盖概念/地域板块（非仅行业），是题材三维评分「驱动强度/可持续性」的涨停家数输入（见 [[theme_miner_theme_scoring]]）。

```python
# 涨停家数按板块归票（方向：每只涨停股 → 它所属的板块们）
# 前置：读 a_stock_limit_up 执行 em_zt_pool；读 a_stock_signals 执行 eastmoney_concept_blocks
from collections import Counter
from datetime import datetime
zt = em_zt_pool(datetime.now().strftime("%Y%m%d"))   # a-stock-data Layer 8
board_zt = Counter()
for s in zt:
    if s["industry"]:
        board_zt[s["industry"]] += 1          # 1) 行业直配（省一次请求）
    blocks = eastmoney_concept_blocks(s["code"])   # 2) 概念/地域精算（每股一次 em_get，已限流）
    for name in blocks["concept_tags"]:
        board_zt[name] += 1
# board_zt[板块名] = 该板块当日涨停家数；去重提示：行业名可能与 concept_tags 重复计数，
# 若 industry 已含于 concept_tags，二选一即可（精度优先用 2）。
print(board_zt.most_common(10))
```

> 注：批量对每只涨停股调 `eastmoney_concept_blocks` 会发 N 次东财请求（N=涨停数，经 `em_get` 限流约 N 秒）。涨停股很多时，可只对「行业直配」无法归类或需要概念/地域归因的股票调用，控制请求量。

两路结果即题材三维评分「驱动强度/可持续性」维度所需的「涨停家数」输入（见 [[theme_miner_theme_scoring]]）。

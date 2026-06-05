---
name: a_stock_data_common
description: A股全栈数据工具包 — 共享层（依赖、市场前缀、ticker 归一化、东财 datacenter helper、估值公式、调研流程、数据源优先级、FAQ）。所有 a_stock_* reference 文件执行前必读。
metadata:
  upstream: simonlin1212/a-stock-data
  upstream_commit: 9379ab90
  upstream_version: 3.2.2
  upstream_date: 2026-06-03
  license: Apache-2.0
  author: Simon 林
  layer: common
---

> Vendored from [simonlin1212/a-stock-data](https://github.com/simonlin1212/a-stock-data) (Apache-2.0, V3.2.2 @ 2026-06-03, commit 9379ab90).
> Author: Simon 林 — please retain this attribution per Apache-2.0. See repo-root `NOTICE`.
>
> **在 mx-skills 中的使用方式**：本文件包含所有 7 层共用的辅助函数和常量。Router 路由到任何 `a_stock_*` 层之前，应先读取本文件以获取 `UA`、`DATACENTER_URL`、`eastmoney_datacenter()`、ticker 归一化规则等。
>
> **调用约定 D（内嵌 Python）**：本仓库的 a-stock-data 系列 reference 文件采用上游"自包含代码块"模式：模型直接读 reference 并用 `python3 -c "..."` 执行内嵌的 Python 代码，**返回 Python 值或 DataFrame**，不写文件。区别于 mx-skills 现有的脚本子进程模式（A: JSON envelope / B: 文件路径行 / C: Saved + Markdown）。

---

## 七层架构总览

```
```
行情层（实时，不封IP）
├── mootdx        → K线 + 五档盘口 + 逐笔成交 (TCP 7709)
├── 腾讯财经 API   → PE/PB/市值/换手率/涨跌停/指数/ETF (HTTP)
└── 百度股市通     → K线带MA5/10/20 (V3.0 新增，HTTP)

研报层
├── 东财 reportapi → 研报列表 + PDF下载 + 评级 + 三年EPS
├── 同花顺 THS     → 一致预期EPS (直连 basic.10jqka.com.cn)
└── iwencai        → NL语义搜索研报 (唯一能力，需X-Claw)

信号层
├── 同花顺热点     → 当日强势股 + 题材归因 reason tags (零鉴权 73ms)
├── 同花顺北向     → hgt/sgt 分钟资金流向 + 本地自缓存历史
├── 东财 slist     → 个股所属板块/概念归属 (V3.2.2 替换百度PAE)
├── 东财 push2     → 个股资金流向 分钟级 (V3.1 替换百度PAE)
├── 龙虎榜席位     → 上榜记录 + 买卖席位 TOP5 + 机构动向 (datacenter-web)
├── 全市场龙虎榜   → 每日全市场上榜股票 + 净买额排名 (datacenter-web)
├── 限售解禁日历   → 历史解禁 + 未来90天待解禁 (datacenter-web)
└── 行业板块排名   → 东财行业涨跌/上涨下跌家数 (V3.0 替换同花顺)

资金面 / 筹码层
├── 融资融券明细   → 日级融资余额/买入/偿还 + 融券 (datacenter-web)
├── 大宗交易       → 成交价/量 + 买卖方营业部 (datacenter-web)
├── 股东户数变化   → 季度股东户数 + 环比变化 (datacenter-web)
├── 分红送转       → 历史每股派息/送股/转增 (datacenter-web)
└── 个股资金流120日 → 主力/大单/中单/小单 日级净流入 (push2his)

新闻层
├── 东财个股新闻   → 个股相关新闻 (np-listapi getListInfo, mx-skills patched)
├── 财联社快讯     → ⚠️ 已下线 (cls.cn 迁 Next.js，旧API 404)
└── 东财全球资讯   → 7×24 财经快讯 (np-weblist，财联社替代)

基础数据层
├── mootdx finance → 季报快照 (37字段, EPS/ROE/净利)
├── mootdx F10     → 公司资料 (9大类文本)
├── 东财个股信息   → 行业/总股本/流通股/市值/上市日期 (push2)
└── 新浪财报三表   → 资产负债表/利润表/现金流量表 (quotes.sina.cn)

公告层
├── 巨潮 cninfo    → 公告全文检索+下载 (cninfo.com.cn)
└── mootdx F10     → 最新公告摘要
```

---

## 数据源优先级 & 东财防封（重要，先读）

### 优先级原则：能用通达信/腾讯，就别用东财

| 优先级 | 数据源 | 协议 | 封 IP 风险 | 覆盖 |
|--------|--------|------|-----------|------|
| **1（首选）** | **mootdx（通达信）** | TCP 7709 二进制 | **不封 IP** | K线、五档盘口、逐笔成交、财务快照、F10 |
| **2** | **腾讯财经** | HTTP GBK | **不封 IP** | 实时价、PE/PB/市值/换手率/涨跌停、指数、ETF |
| **3** | 新浪 / 巨潮 / 同花顺 | HTTP | 低 | 财报三表、公告、一致预期/热点 |
| **4（仅独有数据才用）** | **东财 eastmoney** | HTTP | **有风控，会封 IP** | 见下 |

**凡是行情 / K线 / 实时价 / 市值 / 财务三表能从 mootdx 或腾讯拿到的，一律走它们**——TCP 协议和腾讯接口实测不封 IP，可放心高频调用。

### 东财只用于它「独有、别处拿不到」的数据

下列数据**只有东财有**，通达信/腾讯/新浪都没有，必须用东财（但要限流）：

> 龙虎榜席位 · 全市场龙虎榜 · 限售解禁日历 · 融资融券 · 大宗交易 · 股东户数 · 分红送转 · 个股资金流向（分钟/日级）· 行业板块排名 · 研报列表/PDF · 个股新闻 · 全球资讯

### 东财风控阈值（社区实测，2026-05）

| 行为 | 触发封禁的阈值 | 风险 |
|------|---------------|------|
| 每秒请求数 | > 5 次/秒 | 高 |
| 单 IP 并发连接 | ≥ 10 | 高 |
| 1 分钟请求总数 | ≥ 200 次 | 中高 |
| 5 分钟请求总数 | ≥ 300 次 | 触发封禁 |
| User-Agent | 空 UA / 无浏览器特征 | 中 |

被封表现：连续请求后 `403` / `429` / 连接超时 / 返回空数据。临时封禁通常几分钟到几小时。

### 防封铁律（调用东财时必须遵守）

1. **串行，不并发**——绝不对东财开多线程/协程并发请求
2. **每次间隔 ≥ 1 秒 + 随机抖动**（QPS ≤ 2），批量筛选时调大到 1.5~2 秒
3. **复用 HTTP 会话**（Keep-Alive），不要每次新建连接
4. **带正常 UA + Referer**（本 SKILL 各端点已配好）
5. **批量场景每只股票之间 sleep**——AI 跑批量循环（如筛选 100 只股逐个拉龙虎榜/资金流）是被封的头号元凶

### 已内置限流：所有东财请求走 `em_get()`

本 SKILL 提供统一的节流入口 `em_get()`（定义见下方「东财数据中心统一查询（共用 helper）」），它自动做到：串行限流（最小间隔 `EM_MIN_INTERVAL=1.0s` + 随机抖动）+ 复用 `EM_SESSION`（Keep-Alive）+ 默认 UA。**所有 `eastmoney.com` 端点的代码块都已改用 `em_get` 而非裸 `requests.get`**，AI 直接抄代码即自带防封。批量任务把 `EM_MIN_INTERVAL` 调大即可进一步降速。

> 注：`em_get` / `EM_SESSION` / `EM_MIN_INTERVAL` 是所有东财代码块共用的前置定义，使用任一东财端点前需先执行「共用 helper」代码块。

---

## When to Activate（路由触发条件）

- 用户要查 A 股个股估值（一致预期 / PE / PEG / PE消化）
- 用户要拉实时行情（价格 / 五档盘口 / K线 / 涨跌停价）
- 用户要搜研报（按主题 / 按标的 / 按行业 / 下载PDF）
- 用户要看**当日强势股 / 题材归因 / 概念热点**
- 用户要看**北向资金动向**（沪股通/深股通分钟流向）
- 用户要看**概念板块归属**（行业/概念/地域）
- 用户要看**个股资金流向**（主力/散户/超大单/大单分钟级）
- 用户要看**龙虎榜席位**（营业部 + 机构买卖）
- 用户要看**全市场龙虎榜**（当日所有上榜股票 + 净买额排名）
- 用户要看**限售解禁日历**（历史解禁 + 未来待解禁）
- 用户要做**行业横向对比**（涨跌排名 / 资金流入 / 领涨股）
- 用户要看**融资融券 / 两融数据**（融资余额 + 融券余额）
- 用户要看**大宗交易**（成交价/量 + 买卖方营业部）
- 用户要看**股东户数变化**（筹码集中度）
- 用户要看**分红送转历史**（每股派息 + 送股 + 转增）
- 用户要看**指数/ETF行情**（上证指数 / 沪深300 / 创业板指 / ETF）
- 用户要看新闻资讯（个股新闻 / 财联社快讯 / 全球资讯）
- 用户要查公告（巨潮公告全文）
- 用户要做产业链调研 / 批量横向对比
- 关键词：估值、一致预期、机构预测、市盈率、PEG、市值、研报、产业链、行业研究、K线、盘口、公告、新闻、**强势股、题材、热点、概念归因、北向资金、沪股通、深股通、概念板块、资金流向、主力、龙虎榜、席位、营业部、全市场龙虎榜、净买入、解禁、限售、行业对比、行业轮动、融资融券、两融、大宗交易、股东户数、筹码集中、分红、派息、送股、指数、ETF**

---

## Prerequisites（依赖与全局 helper）

```bash
pip install mootdx requests pandas stockstats
```

| 依赖 | 版本要求 | 用途 |
|------|---------|------|
| mootdx | >= 0.10 | TCP行情+财务+F10（唯一非HTTP依赖） |
| requests | any | 所有HTTP API直连 |
| pandas | any | 数据处理+HTML表格解析 |
| stockstats | any | 技术指标计算（RSI/MACD/BOLL等） |

> **V3.0 架构：** 除 mootdx（TCP 二进制协议）外，所有数据源均为直连 HTTP API，零第三方数据封装依赖。每个端点的底层 URL/参数完全暴露，方便调试和定制。

### iwencai API Key（仅语义搜索需要）

```bash
# 环境变量方式
export IWENCAI_API_KEY="your_key_here"
export IWENCAI_BASE_URL="https://openapi.iwencai.com"

# 申请地址: https://www.iwencai.com/skillhub
# 注册后安装 SkillHub CLI，再安装 report-search 技能即可获得 Key
```

其他数据源（mootdx / 腾讯 / 东财 / 同花顺 / 百度股市通 / 新浪 / 巨潮）全部免费，无需 key。

### 市场前缀规则（全局通用）

```python
def get_prefix(code: str) -> str:
    """6位代码 → 市场前缀"""
    if code.startswith(("6", "9")):
        return "sh"
    elif code.startswith("8"):
        return "bj"
    else:
        return "sz"
```

### Ticker 格式归一化

所有接口统一支持多种输入格式，内部归一化为纯 6 位数字：

| 输入 | 归一化结果 |
|------|-----------|
| `688017` | `688017` |
| `SH688017` / `sh688017` | `688017` |
| `688017.SH` / `688017.sh` | `688017` |
| `SZ000001` | `000001` |
| `BJ832000` | `832000` |

### 东财数据中心统一查询（共用 helper）

龙虎榜/解禁/融资融券/大宗交易/股东户数/分红 共用同一 base URL：

```python
import time
import random
import requests

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

# ── 东财防封：全局节流 + 会话复用 ────────────────────────────────────
# 东财系 HTTP 接口（push2 / datacenter / reportapi / search / np-weblist）有风控：
#   每秒 >5 次 / 单 IP 并发 ≥10 / 1 分钟 ≥200 次  →  临时封 IP。
# 所有 eastmoney.com 请求一律走 em_get()：串行限流（最小间隔 + 随机抖动）+ 复用
# Keep-Alive 会话，批量调用时自动降速，避免被封。详见「数据源优先级 & 东财防封」章节。
EM_SESSION = requests.Session()
EM_SESSION.headers.update({"User-Agent": UA})
EM_MIN_INTERVAL = 1.0          # 两次东财请求最小间隔(秒)；批量筛选建议调大到 1.5~2
_em_last_call = [0.0]          # 模块级上次请求时间戳

def em_get(url: str, params: dict | None = None, headers: dict | None = None,
           timeout: int = 15, **kwargs):
    """东财统一请求入口：自动节流 + 复用 session + 默认 UA。
    所有 eastmoney.com 接口都应通过它请求，避免高频被封 IP。"""
    wait = EM_MIN_INTERVAL - (time.time() - _em_last_call[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))
    try:
        return EM_SESSION.get(url, params=params, headers=headers, timeout=timeout, **kwargs)
    finally:
        _em_last_call[0] = time.time()

def eastmoney_datacenter(report_name: str, columns: str = "ALL",
                          filter_str: str = "", page_size: int = 50,
                          sort_columns: str = "", sort_types: str = "-1") -> list[dict]:
    """东财数据中心统一查询 — 龙虎榜/解禁/融资融券/大宗交易/股东户数/分红 共用（已内置限流）"""
    params = {
        "reportName": report_name, "columns": columns,
        "filter": filter_str, "pageNumber": "1", "pageSize": str(page_size),
        "sortColumns": sort_columns, "sortTypes": sort_types,
        "source": "WEB", "client": "WEB",
    }
    r = em_get(DATACENTER_URL, params=params, timeout=15)
    d = r.json()
    if d.get("result") and d["result"].get("data"):
        return d["result"]["data"]
    return []

---

## 估值计算公式

### 前向PE

```python
def forward_pe(price: float, eps_forecast: float) -> float:
    """前向PE = 当前股价 / 未来年度一致预期EPS"""
    if eps_forecast <= 0:
        return float("inf")
    return price / eps_forecast
```

### PE消化时间

```python
import math

def pe_digestion(current_pe: float, cagr: float, target_pe: float = 30) -> float:
    """
    当前PE消化到目标PE需要多少年。
    target_pe 固定30x（A股成长股合理估值锚点）。
    cagr: 用 下一年EPS / 当年EPS - 1
    """
    if current_pe <= target_pe:
        return 0.0
    if cagr <= 0:
        return float("inf")
    return math.log(current_pe / target_pe) / math.log(1 + cagr)
```

### PEG

```python
def calc_peg(pe: float, cagr: float) -> float:
    """
    PEG = 前向PE / (CAGR * 100)
    PEG < 1   → 便宜
    PEG 1-1.5 → 合理
    PEG > 1.5 → 贵
    """
    if cagr <= 0:
        return float("inf")
    return pe / (cagr * 100)
```

### 投资框架速查

```
壁垒 → 增速 → PE消化 → PEG校验

1. 有壁垒吗？(tech_moat / capacity_moat) → 没有则排除
2. 增速多少？(CAGR > 30% 才有意义)
3. PE多久消化到30x？(< 2年合理, > 4年太贵)
4. PEG多少？(< 1 便宜, 1-1.5 合理, > 1.5 贵)

30x PE 锚点: A股成长股的合理估值重力线，所有行业统一用30x。
期权定价例外: PEG > 3 但壁垒极深时，本质是看涨期权，不适用PEG框架。
```

---

## 完整调研流程（跨层组合）

### 流程 A: 单票完整估值（30秒）

```python
import requests
import urllib.request
import math
import pandas as pd

def full_valuation(code: str) -> dict:
    """单票完整估值分析"""
    # 1. 腾讯实时行情
    prefix = "sh" if code.startswith(("6","9")) else ("bj" if code.startswith("8") else "sz")
    url = f"https://qt.gtimg.cn/q={prefix}{code}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk")
    vals = data.split('"')[1].split("~")
    price = float(vals[3])
    mcap = float(vals[44])
    pe_ttm = float(vals[39]) if vals[39] else 0
    pb = float(vals[46]) if vals[46] else 0

    # 2. 机构一致预期（直连同花顺）
    df = ths_eps_forecast(code)
    eps_cur = eps_next = None
    analyst_count = 0
    if not df.empty and len(df.columns) >= 3:
        # 解析表格（列结构因页面可能变化，取前两行数据行）
        try:
            for i, row in df.iterrows():
                if i == 0:
                    eps_cur = float(row.iloc[2]) if pd.notna(row.iloc[2]) else None
                    analyst_count = int(row.iloc[1]) if pd.notna(row.iloc[1]) else 0
                elif i == 1:
                    eps_next = float(row.iloc[2]) if pd.notna(row.iloc[2]) else None
        except (ValueError, IndexError):
            pass

    # 3. 估值指标
    pe_fwd = price / eps_cur if eps_cur else float("inf")
    cagr = (eps_next / eps_cur - 1) if (eps_cur and eps_next) else 0
    peg = pe_fwd / (cagr * 100) if cagr > 0 else float("inf")
    digest = (
        math.log(pe_fwd / 30) / math.log(1 + cagr)
        if pe_fwd > 30 and cagr > 0 else 0
    )

    return {
        "name": vals[1],
        "price": price,
        "mcap_yi": mcap,
        "pe_ttm": pe_ttm,
        "pb": pb,
        "eps_cur": eps_cur,
        "eps_next": eps_next,
        "pe_fwd": round(pe_fwd, 1) if eps_cur else None,
        "cagr_pct": round(cagr * 100, 0) if cagr else None,
        "peg": round(peg, 2) if peg != float("inf") else None,
        "digest_years": round(digest, 1),
        "analyst_count": analyst_count,
    }

# 用法
result = full_valuation("688017")
print(result)
```

### 流程 B: 批量估值对比

```python
stocks = ["688017", "300308", "300476", "002463"]
for code in stocks:
    try:
        r = full_valuation(code)
        print(f"{r['name']}({code}): PE_fwd={r['pe_fwd']}x PEG={r['peg']} 消化={r['digest_years']}年 覆盖={r['analyst_count']}家")
    except Exception as e:
        print(f"{code}: 失败 - {e}")
```

### 流程 C: 主题研报批量检索

```python
# Step 1: iwencai 多 query 语义搜索
queries = [
    "人形机器人产业链深度 2026",
    "人形机器人减速器 丝杠",
    "特斯拉Optimus 国产供应链",
]
seen_uids = set()
all_articles = []
for q in queries:
    arts = iwencai_search(q, channel="report", size=50)
    for a in arts:
        uid = a.get("uid", "")
        if uid not in seen_uids:
            seen_uids.add(uid)
            all_articles.append(a)
print(f"共 {len(all_articles)} 篇去重后研报")

# Step 2: 东财补充同标的研报 + PDF
for a in all_articles[:10]:
    stocks = a.get("stock_infos") or []
    for s in stocks:
        stock_code = s.get("code", "")
        if stock_code:
            em = eastmoney_reports(stock_code, max_pages=1)
            print(f"  {stock_code}: 东财 {len(em)} 篇")
```

### 流程 D: 新标的快速调研（V3.0 增强版）

```python
code = "688017"

# 1. 有无机构覆盖？
forecast = ths_eps_forecast(code)
print(f"机构覆盖: {'有' if not forecast.empty else '无'}")

# 2. 实时估值
quotes = tencent_quote([code])
q = quotes[code]
print(f"PE={q['pe_ttm']} PB={q['pb']} 市值={q['mcap_yi']}亿")

# 3. PE消化 → 用 full_valuation()
# 4. PEG校验

# 5. 概念板块归属
blocks = eastmoney_concept_blocks(code)
print(f"板块: {', '.join(blocks['concept_tags'][:10])}")

# 6. 资金流向（分钟级，当日盘中）
flow = eastmoney_fund_flow_minute(code)
if flow:
    total = sum(f["main_net"] for f in flow)
    print(f"当日主力累计净流入: {total/1e4:.0f}万")

# 7. 资金流向（东财120日）
flow_120 = stock_fund_flow_120d(code)
if flow_120:
    total = sum(d["main_net"] for d in flow_120[-20:])
    print(f"近20日主力累计净流入: {total/1e8:.2f}亿")

# 8. 龙虎榜
dtb = dragon_tiger_board(code, "2026-05-17")
print(f"近30日上龙虎榜: {len(dtb['records'])} 次")

# 9. 解禁预警
lockup = lockup_expiry(code, "2026-05-17")
print(f"未来90天待解禁: {len(lockup['upcoming'])} 批")

# 10. 融资融券
margin = margin_trading(code, page_size=5)
if margin:
    print(f"最新融资余额: {margin[0]['rzye']/1e8:.2f}亿")

# 11. 股东户数
holders = holder_num_change(code)
if holders:
    print(f"最新股东数: {holders[0]['holder_num']} 环比{holders[0]['change_ratio']}%")
```

---

## 数据源优先级

| 优先级 | 数据源 | 用途 | 可靠性 | 封IP风险 |
|--------|--------|------|--------|---------|
| 1 | **mootdx** (TCP) | K线+五档盘口+逐笔成交+财务快照+F10 | 极稳定 | 极低 |
| 2 | **腾讯财经** (HTTP) | 实时PE/PB/市值/换手率/涨跌停/指数/ETF | 稳定 | 低 |
| 3 | **东财 datacenter** (HTTP) | 龙虎榜/解禁/融资融券/大宗交易/股东户数/分红/个股信息 | 稳定 | 低 |
| 4 | **东财 push2/push2his** (HTTP) | 行业板块/个股资金流分钟级+120日 | 稳定 | 低 |
| 5 | **iwencai** (OpenAPI) | NL主题搜索研报(唯一能力) | 需X-Claw Header | 低 |
| 6 | **东财 reportapi/PDF** (HTTP) | 完整研报图表、评级 | 稳定 | 低 |
| 7 | **同花顺热点** (HTTP) | 当日强势股+题材归因 reason tags | 稳定 73ms | 极低（零鉴权） |
| 8 | **同花顺 hsgtApi** (HTTP) | 北向资金分钟级+自缓存历史 | 稳定 | 极低（零鉴权） |
| 9 | **百度股市通** (HTTP) | 概念板块+K线带MA | 稳定 | 极低（零鉴权） |
| 10 | **新浪财经** (HTTP) | 资产负债表/利润表/现金流量表 | 稳定 | 低 |
| 11 | **同花顺 basic** (HTTP) | 一致预期EPS | 稳定(需UA) | 低 |
| 12 | **财联社** (HTTP) | 全市场实时电报 | 稳定 | 低 |
| 13 | **巨潮 cninfo** (HTTP) | 公告全文检索+下载 | 稳定 | 低 |

**原则：** 行情走 mootdx+腾讯（不封IP），研报走东财+iwencai，资金面走东财 datacenter+push2，**信号层走同花顺+百度+东财直连接口**。全部直连 HTTP，零第三方数据封装依赖。

---

## FAQ（上游版）

### Q: mootdx 和腾讯有什么区别？
A: 互补关系。mootdx = 交易层（价格+盘口+K线），腾讯 = 估值层（PE/PB/市值/换手率/涨跌停价）。两者都不封IP。

### Q: V3.0 为什么移除 akshare？
A: akshare 本质是对东财/同花顺/新浪等公开 API 的封装，中间层增加了故障点（版本兼容 bug、pandas 3.0 ArrowInvalid 等）。V3.0 直连底层 HTTP API，零中间依赖，更稳定可控。

### Q: iwencai 返回 401
A: 检查两点：(1) API Key 是否有效 (2) 是否携带了 X-Claw-* Headers。SkillHub 2.0 后必须带 X-Claw Headers，否则一律 401。

### Q: 同花顺一致预期 ths_eps_forecast 返回空
A: 该股票无机构覆盖。小盘/次新/ST 股常见。可 fallback 到东财 reportapi 里的 predictThisYearEps 字段。

### Q: 东财 PDF 下载 403
A: 必须带 `Referer: https://data.eastmoney.com/` header。

### Q: 腾讯 API 返回乱码
A: 编码是 GBK，必须 `decode("gbk")`。

### Q: 腾讯 API 字段 43 是 PB 吗？
A: **不是！** 43=振幅%，46=PB。网上很多教程写错了，这里是实测校准结果。

### Q: iwencai search 返回条数太少
A: `size` 参数默认 10，调到 50。隐藏参数，文档未写明但实测可用。

### Q: 哪些数据源需要 API Key？
A: 只有 iwencai 需要。mootdx / 腾讯 / 东财 / 同花顺 / 百度股市通 / 新浪 / 巨潮 / 财联社全部免费无 key。

### Q: 同花顺热点接口需要 cookie 吗？
A: **不需要**。仅 User-Agent 即可，零鉴权 73ms 拿到 ~125 只当日强势股。但**不要去打 search.10jqka.com.cn 的 iwencai NL 选股接口** —— 那个有 hexin-v cookie JS 签名鉴权，跟热点接口完全两码事。

### Q: 百度股市通 ResultCode 有时是 0 有时是 "0"？
A: 已知坑。`ResultCode` 返回类型不稳定——有时 int，有时 string。代码里必须用 `str(d.get("ResultCode", -1)) != "0"` 统一比较。

### Q: 北向资金历史数据为什么只有最近几天？
A: 本地自缓存模式。eastmoney 全系北向数据自 2024-08 起断供（净买额字段返回 NaN/0）。每次调用实时 API 后自动写入本地 CSV，历史越跑越丰富。

### Q: 行业板块为什么从同花顺换成东财？
A: 同花顺 `stock_board_industry_summary_ths` 接口 2026 年初加了反爬 401（需要登录态）。东财 push2 行业板块数据（`m:90+t:2`）是完美替代，零鉴权且字段更丰富。

### Q: 在海外服务器跑，mootdx 接口超时？
A: mootdx 走 TCP 直连通达信行情服务器，需国内 IP 才稳定。海外环境建议走代理。腾讯财经和百度股市通不受影响。

### Q: 不用 Claude Code，能用吗？
A: 能。SKILL.md 本质是 Markdown + 内嵌 Python 代码。Codex、OpenClaw 或任何 AI 编程助手都能读取。你也可以直接把 Python 代码段复制出来在自己的脚本里跑。

---
name: a_stock_fundamentals
description: A股基础数据层 — mootdx 财务37字段/F10、东财个股基本面、新浪财报三表
metadata:
  upstream: simonlin1212/a-stock-data
  upstream_commit: 9379ab90
  upstream_version: 3.2.2
  upstream_date: 2026-06-03
  license: Apache-2.0
  author: Simon 林
  layer: Layer 6 基础数据层
  patched: false
  patch_history:
    - "§6.4 新浪三表 report_list 解析：mx-skills 2026-05-20 首修，上游 v3.2.1 采纳同向修复后本地 patch 退役，现为纯上游码（保留此条仅作历史记录）"
---

> Vendored from [simonlin1212/a-stock-data](https://github.com/simonlin1212/a-stock-data) (Apache-2.0, V3.2.2 @ 2026-06-03, commit 9379ab90).
> Author: Simon 林 — please retain this attribution per Apache-2.0.
>
> **在 mx-skills 中的使用方式**：本文件是 mx-skills 的**补充/降级数据层**。SKILL.md 路由层决定何时读取此文件。共享辅助代码（UA、ticker 归一化、eastmoney_datacenter helper、估值公式）在 `a_stock_data_common.md` — 执行本文件代码前先读那个。
>
> **调用约定 D（内嵌 Python）**：本文件的代码块由模型用 `python3 -c "..."` 直接执行，**返回 Python 值**，不写文件。区别于 mx-skills 现有的脚本子进程模式（A/B/C 三种 stdout 约定）。

## Layer 6: 基础数据层

### 6.1 mootdx 财务快照（37字段季报数据）

```python
from mootdx.quotes import Quotes

client = Quotes.factory(market='std')

# market: 0=深圳, 1=上海
fin = client.finance(symbol='688017')
# 返回 37 个字段的季报快照:
#   liutongguben(流通股本), zongguben(总股本)
#   eps(每股收益), bvps(每股净资产), roe(净资产收益率%)
#   profit(净利润), income(主营收入)
#   meigujingzichan(每股净资产), meigugongjijin(每股公积金)
#   meiguweifeipeili(每股未分配利润)
#   等37个季报财务字段
```

### 6.2 mootdx F10（公司文本资料）

```python
from mootdx.quotes import Quotes

client = Quotes.factory(market='std')

# 9 大类文本数据:
categories = [
    "最新提示", "公司概况", "财务分析",
    "股东研究", "股本结构", "资本运作",
    "业内点评", "行业分析", "公司大事",
]
for cat in categories:
    text = client.F10(symbol='688017', name=cat)
    print(f"=== {cat} ===")
    print(text[:200] if text else "(空)")
```

> **优化提示：** "股东研究" 中的【4.股东变化】章节含大量历史十大股东列表，实测 16000+ chars。建议只保留最新一期（-70% token）。

### 6.3 东财个股基本面（直连 push2 API）

```python
import requests

def eastmoney_stock_info(code: str) -> dict:
    """
    东财个股基本面信息。
    返回: {code, name, industry, total_shares, float_shares, mcap, float_mcap, list_date}
    """
    market_code = 1 if code.startswith("6") else 0
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "fltt": "2", "invt": "2",
        "fields": "f57,f58,f84,f85,f127,f116,f117,f189,f43",
        "secid": f"{market_code}.{code}",
    }
    headers = {"User-Agent": UA}
    r = em_get(url, params=params, headers=headers, timeout=10)
    d = r.json().get("data", {})
    return {
        "code": d.get("f57", ""),
        "name": d.get("f58", ""),
        "industry": d.get("f127", ""),
        "total_shares": d.get("f84", 0),     # 总股本(股)
        "float_shares": d.get("f85", 0),     # 流通股(股)
        "mcap": d.get("f116", 0),            # 总市值(元)
        "float_mcap": d.get("f117", 0),      # 流通市值(元)
        "list_date": str(d.get("f189", "")), # 上市日期 YYYYMMDD
        "price": d.get("f43", 0),
    }

# 用法
info = eastmoney_stock_info("688017")
print(f"{info['name']}({info['code']}): 行业={info['industry']} 总市值={info['mcap']/1e8:.0f}亿 上市={info['list_date']}")
```

### 6.4 新浪财报三表（直连 quotes.sina.cn）

> **此前为 mx-skills 本地 patch（2026-05-20），上游 v3.2.1（2026-05-30）已官方采纳同向修复，本地 patch 已退役**：上游 V3.1 假设响应结构是 `result.data[<report_type>]`（即 `result.data.lrb`），实际接口在 2026 后改为 `result.data.report_list`（按报告期为键的 dict，每期对象的 `data` 字段才是行项列表）。下面直接采用上游 v3.2.1 版本（新增 `num` 参数，返回「按报告期倒序的扁平记录列表」）。

```python
import requests

def sina_financial_report(code: str, report_type: str = "lrb", num: int = 8) -> list[dict]:
    """
    新浪财报三表。
    code: 6位代码
    report_type: "fzb"(资产负债表) / "lrb"(利润表) / "llb"(现金流量表)
    num: 取最近 N 期（默认 8 期）
    返回: 按报告期倒序的记录列表，每期一条 dict：
          {"报告期": "2026-03-31", "<科目>": "<值>", "<科目>_同比": <同比>, ...}
          （item_value 为新浪原始字符串数值，仅在有同比时附 "_同比" 键）
    """
    prefix = "sh" if code.startswith("6") else "sz"
    paper_code = f"{prefix}{code}"
    url = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"
    params = {
        "paperCode": paper_code,
        "source": report_type,
        "type": "0",
        "page": "1",
        "num": str(num),
    }
    headers = {"User-Agent": UA}
    r = requests.get(url, params=params, headers=headers, timeout=15)
    # 新浪实际结构: result.data.report_list 是「按报告期(如 '20260331')为键」的 dict,
    # 每期对象的 data 字段才是行项列表 [{item_title, item_value, item_tongbi}]。
    report_list = r.json().get("result", {}).get("data", {}).get("report_list", {}) or {}

    rows = []
    for period in sorted(report_list.keys(), reverse=True)[:num]:
        obj = report_list[period]
        rec = {"报告期": f"{period[:4]}-{period[4:6]}-{period[6:8]}"}
        for it in obj.get("data", []) or []:
            title = it.get("item_title", "")
            if not title or it.get("item_value") is None:
                continue
            rec[title] = it.get("item_value")
            tongbi = it.get("item_tongbi")
            if tongbi not in (None, ""):
                rec[title + "_同比"] = tongbi
        rows.append(rec)
    return rows

# 用法: 利润表
lrb = sina_financial_report("600519", "lrb")
for item in lrb[:3]:
    print(f"报告期: {item.get('报告期', '')} 净利润: {item.get('净利润', '')}")

# 用法: 资产负债表
fzb = sina_financial_report("600519", "fzb")
```

---

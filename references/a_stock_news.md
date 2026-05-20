---
name: a_stock_news
description: A股新闻层 — 东财个股新闻、财联社快讯、东财全球资讯
metadata:
  upstream: simonlin1212/a-stock-data
  upstream_commit: 2dd95e3c7cc8cd9ec43dbaeaab16bae938b69e0f
  upstream_version: 3.1
  upstream_date: 2026-05-19
  license: Apache-2.0
  author: Simon 林
  layer: Layer 5 新闻层
  patched: true
  patch_notes:
    - "2026-05-20 mx-skills: §5.1 东财 search-api-web JSONP 接口对纯股票代码 keyword 不再返回 cmsArticleWebOld（改返 passportWeb 用户档案），改用 np-listapi.eastmoney.com /comm/web/getListInfo + mTypeAndCode 拉个股新闻流"
---

> Vendored from [simonlin1212/a-stock-data](https://github.com/simonlin1212/a-stock-data) (Apache-2.0, V3.1 @ 2026-05-19, commit 2dd95e3c).
> Author: Simon 林 — please retain this attribution per Apache-2.0.
>
> **在 mx-skills 中的使用方式**：本文件是 mx-skills 的**补充/降级数据层**。SKILL.md 路由层决定何时读取此文件。共享辅助代码（UA、ticker 归一化、eastmoney_datacenter helper、估值公式）在 `a_stock_data_common.md` — 执行本文件代码前先读那个。
>
> **调用约定 D（内嵌 Python）**：本文件的代码块由模型用 `python3 -c "..."` 直接执行，**返回 Python 值**，不写文件。区别于 mx-skills 现有的脚本子进程模式（A/B/C 三种 stdout 约定）。

## Layer 5: 新闻层

### 5.1 东财个股新闻 — mx-skills patched

> **mx-skills patch（2026-05-20）**：上游 V3.1 用 `search-api-web.eastmoney.com/search/jsonp` 以 `keyword=<code>` 搜索 `cmsArticleWebOld`，2026 后该接口对纯 6 位股票代码不再返回文章列表（改返 `passportWeb` 用户档案匹配）。改用东财专门的个股新闻流接口 `np-listapi.eastmoney.com/comm/web/getListInfo`，直接按 `mTypeAndCode=<market>.<code>` 拉新闻。

```python
import requests

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

def eastmoney_stock_news(code: str, page_size: int = 20) -> list[dict]:
    """
    东财个股新闻流。
    返回: [{title, time, url, art_code}]
    """
    mt = (f"1.{code}" if code.startswith(("6", "9"))
          else (f"7.{code}" if code.startswith("8") else f"0.{code}"))
    r = requests.get(
        "https://np-listapi.eastmoney.com/comm/web/getListInfo",
        params={
            "client": "web", "biz": "web_n_pc_n_xinwen", "trackID": "",
            "mTypeAndCode": mt, "type": "1",
            "pageSize": str(page_size), "pageIndex": "1", "callback": "",
        },
        headers={"User-Agent": UA, "Referer": "https://so.eastmoney.com/"},
        timeout=15,
    )
    d = (r.json().get("data") or {})
    rows = []
    for a in d.get("list") or []:
        rows.append({
            "title": a.get("Art_Title", ""),
            "time": a.get("Art_ShowTime", ""),
            "url": a.get("Art_OriginUrl") or a.get("Art_Url", ""),
            "art_code": a.get("Art_Code", ""),
        })
    return rows

# 用法
news = eastmoney_stock_news("600519")
print(f"共 {len(news)} 条")
for n in news[:5]:
    print(f"  {n['time']} | {n['title'][:60]}")
```

### 5.2 财联社快讯（直连 cls.cn）

```python
import requests

def cls_telegraph(page_size: int = 50) -> list[dict]:
    """
    财联社电报（全市场实时快讯）。
    返回: [{title, content, time}]
    """
    url = "https://www.cls.cn/nodeapi/telegraphList"
    params = {"rn": str(page_size), "page": "1"}
    headers = {"User-Agent": UA, "Referer": "https://www.cls.cn/"}
    r = requests.get(url, params=params, headers=headers, timeout=10)
    d = r.json()

    rows = []
    for item in d.get("data", {}).get("roll_data", []):
        rows.append({
            "title": item.get("title", "") or item.get("brief", ""),
            "content": item.get("content", "") or item.get("brief", ""),
            "time": item.get("ctime", ""),
        })
    return rows

# 用法
news = cls_telegraph()
for n in news[:10]:
    print(f"  {n['time']} | {n['title'][:60]}")
```

### 5.3 东财全球资讯（7x24）

```python
import requests

import uuid

def eastmoney_global_news(page_size: int = 50) -> list[dict]:
    """
    东方财富全球财经资讯（7x24 滚动）。
    返回: [{title, summary, time}]
    """
    url = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
    params = {
        "client": "web", "biz": "web_724",
        "fastColumn": "102", "sortEnd": "",
        "pageSize": str(page_size),
        "req_trace": str(uuid.uuid4()),
    }
    headers = {"User-Agent": UA, "Referer": "https://kuaixun.eastmoney.com/"}
    r = requests.get(url, params=params, headers=headers, timeout=10)
    d = r.json()

    rows = []
    for item in d.get("data", {}).get("fastNewsList", []):
        rows.append({
            "title": item.get("title", ""),
            "summary": item.get("summary", "")[:200],
            "time": item.get("showTime", ""),
        })
    return rows

# 用法
news = eastmoney_global_news()
for n in news[:10]:
    print(f"  {n['time']} | {n['title']}")
```

---

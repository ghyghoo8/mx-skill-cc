---
name: a_stock_news
description: A股新闻层 — 东财个股新闻、财联社快讯、东财全球资讯
metadata:
  upstream: simonlin1212/a-stock-data
  upstream_commit: e40d0655
  upstream_version: 3.2.4
  upstream_date: 2026-06-20
  license: Apache-2.0
  author: Simon 林
  layer: Layer 5 新闻层
  patched: true
  patch_notes:
    - "2026-05-20 mx-skills: §5.1 东财 search-api-web JSONP 接口对纯股票代码 keyword 不再返回 cmsArticleWebOld（改返 passportWeb 用户档案），改用 np-listapi.eastmoney.com /comm/web/getListInfo + mTypeAndCode 拉个股新闻流。上游 v3.2.1 对 §5.1 走了不同修法（仍用 search-api jsonp，只修 cmsArticleWebOld 为直接列表）——但 2026-06-01 实测该 jsonp 对纯代码仍仅返回 passportWeb（0 条新闻），np-listapi 返回 10 条，故保留本 patch"
---

> Vendored from [simonlin1212/a-stock-data](https://github.com/simonlin1212/a-stock-data) (Apache-2.0, V3.2.4 @ 2026-06-20, commit e40d0655).
> Author: Simon 林 — please retain this attribution per Apache-2.0.
>
> **在 mx-skills 中的使用方式**：本文件是 mx-skills 的**补充/降级数据层**。SKILL.md 路由层决定何时读取此文件。共享辅助代码（UA、ticker 归一化、eastmoney_datacenter helper、估值公式）在 `a_stock_data_common.md` — 执行本文件代码前先读那个。
>
> **调用约定 D（内嵌 Python）**：本文件的代码块由模型用 `python3 -c "..."` 直接执行，**返回 Python 值**，不写文件。区别于 mx-skills 现有的脚本子进程模式（A/B/C 三种 stdout 约定）。

## Layer 5: 新闻层

### 5.1 东财个股新闻 — mx-skills patched

> **mx-skills patch（2026-05-20，2026-06-01 复核保留）**：上游 V3.1 用 `search-api-web.eastmoney.com/search/jsonp` 以 `keyword=<code>` 搜索 `cmsArticleWebOld`，2026 后该接口对纯 6 位股票代码不再返回文章列表（改返 `passportWeb` 用户档案匹配）。改用东财专门的个股新闻流接口 `np-listapi.eastmoney.com/comm/web/getListInfo`，直接按 `mTypeAndCode=<market>.<code>` 拉新闻。
>
> **与上游 v3.2.1 的分歧**：上游 v3.2.1 对 §5.1 也做了修复，但走的是「保留 search-api jsonp、把 `cmsArticleWebOld` 当作直接列表解析」的路子。2026-06-01 实测：该 jsonp 对纯股票代码仍只返回 `passportWeb`（`cmsArticleWebOld` 为 0 条），而本 patch 的 np-listapi 接口返回 10 条有效新闻。故**保留本地 np-listapi 修法**，不回退到上游版本。

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
    r = em_get(  # 东财端点，走 em_get 内置限流（见 a_stock_data_common.md）
        "https://np-listapi.eastmoney.com/comm/web/getListInfo",
        params={
            "client": "web", "biz": "web_n_pc_n_xinwen", "trackID": "",
            "mTypeAndCode": mt, "type": "1",
            "pageSize": str(page_size), "pageIndex": "1", "callback": "",
        },
        headers={"Referer": "https://so.eastmoney.com/"},
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

> **⚠️ 间歇性返回空（上游 #18）：** 部分大陆住宅 IP 调东财新闻接口会间歇被风控（返回空 list 或 `HTTP 000`）——这是 IP 级风控，非代码问题。代码已对空结果安全返回 `[]`；遇到时隔几分钟或换网络重试即可。（注：上游同名警告针对其 search-api jsonp 的 `passportWeb` 退化，本 patch 用的 np-listapi 表现为返回空 list，处理方式相同。）

### 5.2 财联社快讯（直连 cls.cn）— ⚠️ 已下线，改用 §5.3

> **⚠️ 2026-05 已失效（上游 #14）：** 财联社网站迁移到 Next.js 架构，旧版公开接口
> `cls.cn/nodeapi/telegraphList` 全面下线（返回 404），新版 API 需签名认证，无法
> 公开 HTTP 调用。**全市场实时快讯请改用 §5.3「东财全球资讯」**（7×24 滚动，免费无 key）。
> 下面代码仅作历史参考，已不可用。

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
    r = em_get(url, params=params, headers=headers, timeout=10)
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

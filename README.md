# mx-skills — 东方财富妙想金融智能技能集

基于东方财富权威金融数据库的一站式投研能力平台，覆盖数据查询、资讯搜索、智能选股、财报诊断、研报生成等 14 个专业化子技能。

## 安装

### 方式一：Claude Code 全局安装（推荐）

```bash
git clone git@github.com:ghyghoo8/mx-skill-cc.git ~/.claude/skills/mx-skills
```

重启 Claude Code 后自动识别并加载。

### 方式二：项目级安装

在项目根目录执行：

```bash
mkdir -p .claude/skills
git clone git@github.com:ghyghoo8/mx-skill-cc.git .claude/skills/mx-skills
```

### 依赖安装

```bash
# mx-skills 主路（14 个子技能）
pip3 install httpx pandas openpyxl --user

# a-stock-data 补充层（仅 A 股的实时/筹码/资金面/龙虎榜等互补能力）
pip3 install mootdx requests stockstats --user
```

### 环境变量配置

```bash
# 方式 1：写入 ~/.zshrc 或 ~/.bashrc（持久化）
export EM_API_KEY="your_api_key_here"

# 方式 2：多 Token 配额轮换（推荐高频场景使用）
export EM_API_KEY_POOL="em_xxx,em_yyy,em_zzz"

# 方式 3：使用项目本地 .env 文件
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

> `.env` 已加入 `.gitignore`，不会提交到仓库。
>
> **注意**：`EM_API_KEY_POOL` 需由外层调用封装实现轮换逻辑，原生脚本仅读取 `EM_API_KEY`。

## 使用

本技能集采用 **Router（路由层）** 设计。当用户提出金融相关请求时，Claude 会自动读取 `SKILL.md` 中的路由决策表，匹配正确的子技能并调用对应脚本。

**触发场景包括但不限于**：
- 提到股票代码（如 600519、300059）或公司名称
- 提到基金名称（如华夏成长混合）
- 要求查询数据、行情、财报、宏观指标
- 要求搜索资讯、公告、研报
- 要求分析/诊断/研究某只股票、基金或行业
- 要求选股、筛基金、对比公司
- 要求生成报告（行业研究、深度研究、业绩点评、专题研究等）

## 技能列表

> **上游快照版本**：基于东方财富妙想官方技能包 **2026-03-18** 发布版本 vendor 而来（本地快照日期 2026-05-28）。
> 各子技能上游版本号见下表 `meta.json` 列；本地相对上游的差异：①移除脚本中硬编码的默认 API Key，强制读取环境变量；②为 4 个 reference 文档补充「调用配额」说明段落。
> 后续上游升级时，可使用本仓库当前快照作为基准进行 diff 合并。

<details>
<summary>各子技能上游版本号（点击展开）</summary>

| 技能 | 上游 slug | 版本 | 发布日期 |
|---|---|---|---|
| 金融问答 | `mx-financial-assistant` | 1.0.4 | 2026-03-16 |
| 金融数据查询 | `mx-finance-data` | 1.0.13 | 2026-03-18 |
| 金融资讯搜索 | `mx-finance-search` | 1.0.11 | 2026-03-18 |
| 宏观经济数据 | `mx-macro-data` | 1.0.14 | 2026-03-18 |
| 智能选股 | `mx-stocks-screener` | 1.0.17 | 2026-03-18 |
| 行业研究报告 | `industry-research-report` | 1.0.5 | 2026-03-16 |
| 个股/行业跟踪 | `industry-stock-tracker` | 1.0.4 | 2026-03-16 |
| 首次覆盖/深度研究 | `initiation-of-coverage-or-deep-dive` | 1.0.6 | 2026-03-16 |
| 业绩点评 | `stock-earnings-review` | 1.0.5 | 2026-03-16 |
| 股票诊断 | `stock-diagnosis` | 1.0.3 | 2026-03-16 |
| 基金诊断 | `fund-diagnosis` | 1.0.2 | 2026-03-16 |
| 热点发现 | `stock-market-hotspot-discovery` | 1.0.2 | 2026-03-16 |
| 可比公司分析 | `comparable-company-analysis` | 1.0.2 | 2026-03-16 |
| 专题研究 | `topic-research-report` | 1.0.2 | 2026-03-16 |
| _私域知识库检索（未集成）_ | `mx-personal-kb-search` | 1.0.0 | 2026-03-16 |

</details>

| # | 技能 | 能力 | 输出格式 |
|---|---|---|---|
| 1 | 金融问答 | 自然语言问答（数据/资讯/知识/分析） | Markdown + 溯源参考 |
| 2 | 金融数据查询 | 结构化金融数据查询（A/港/美股、基金、债券） | Excel + txt |
| 3 | 金融资讯搜索 | 全网财经资讯检索（公告/研报/新闻/政策） | txt |
| 4 | 宏观经济数据 | GDP、CPI、M2、PMI、失业率等宏观指标 | CSV + txt |
| 5 | 智能选股 | 多维度筛选股票/基金/板块/ETF/可转债 | CSV + txt |
| 6 | 行业研究报告 | 生成指定行业的深度研究报告 | PDF + DOCX |
| 7 | 个股/行业跟踪 | 生成日报/周报/月报等跟踪报告 | PDF + DOCX |
| 8 | 首次覆盖/深度研究 | 生成公司首次覆盖或深度研究报告 | PDF + DOCX |
| 9 | 业绩点评 | 财报分析、业绩解读（分步骤编排） | PDF + DOCX |
| 10 | 股票诊断 | 单只A股综合诊断（基本面+资金面+风险面） | Markdown |
| 11 | 基金诊断 | 单只公募基金综合诊断 | Markdown |
| 12 | 热点发现 | A股市场热点总览与热门方向识别 | Markdown |
| 13 | 可比公司分析 | 同业对比、经营+估值横向比较 | Excel |
| 14 | 专题研究 | 主题投资、事件驱动、跨行业深度研究 | PDF + DOCX |

### 补充能力层 — a-stock-data（仅 A 股，免费免 Key）

Vendor 自 [simonlin1212/a-stock-data](https://github.com/simonlin1212/a-stock-data)（Apache-2.0，V3.2.1）。覆盖 mx-skills 没有的实时盘口、筹码、资金面能力；也作为 mx-skills 配额耗尽时的降级源。

| 层 | Reference | 互补能力 |
|---|---|---|
| Layer 1 行情 | `references/a_stock_market_data.md` | mootdx K线/盘口、腾讯 PE/PB/市值、百度 K线带 MA |
| Layer 2 研报 | `references/a_stock_research.md` | 东财 PDF 下载、同花顺一致预期 EPS、**iwencai NL 主题检索** |
| Layer 3 信号 | `references/a_stock_signals.md` | **龙虎榜、解禁、北向、题材归因、概念板块、行业排名、分钟级资金流** |
| Layer 4 资金面 | `references/a_stock_capital_flow.md` | **融资融券、大宗交易、股东户数、分红送转、120 日资金流** |
| Layer 5 新闻 | `references/a_stock_news.md` | 东财个股新闻、财联社快讯、全球资讯 |
| Layer 6 基础数据 | `references/a_stock_fundamentals.md` | mootdx 财务 37 字段/F10、新浪三表 |
| Layer 7 公告 | `references/a_stock_filings.md` | 巨潮公告全文检索 |

调用模式 D：模型读 reference → 直接 `python3 -c "<内嵌代码>"` 执行 → 返回 Python 值（不写文件）。详见 `SKILL.md` 路由规则。

### 分析层 — theme-miner 题材挖掘（仅 A 股，#22，建立在 a-stock-data 之上）

Vendor 自 `skills-xjx/hot-theme-miner` v2.0.0（commit `e7a022b3`，2026-04-15）。**不是数据源，而是打分大脑**：在 a-stock-data 数据之上跑「题材 Top3 → 个股 Top5 → 中长期目标价 → 操作策略」一条龙。

| Reference | 作用 |
|---|---|
| `references/theme_miner.md` | 入口：触发、与 #12 边界、流程概览 |
| `references/theme_miner_data_bridge.md` | 数据桥：6 类数据需求 → a-stock-data 函数；自带涨停池/跌停池/市场情绪补充端点 |
| `references/theme_miner_theme_scoring.md` | 题材三维评分 + 生命周期 + 题材级别 |
| `references/theme_miner_stock_scoring.md` | 个股五维评分 + 风险标注 |
| `references/theme_miner_price_prediction.md` | 中长期目标价（⚠️ 启发式、非回测）+ 操作策略 |
| `references/theme_miner_execution.md` | 7 步流水线 + 情绪评级 + 报告模板 |

- **单向依赖**：本层引用 a-stock-data，a-stock-data 不感知本层（后者继续按上游 diff 独立升级）。
- **路由切边**：简单「今天什么板块热」走 mx-skills #12（付费、快）；整条链路或 #12 配额耗尽走本层（免费、打分透明）。
- **⚠️ 价格模型为启发式、未回测**（用当前 PE 反推伪"历史分位"），目标价仅作相对排序参考，已在文档内强制免责。
- **许可证未知**：上游无 LICENSE、作者署名 "AI Assistant"，按指示在未核实许可证情况下 vendor，各文件 frontmatter 已如实标注（与 a-stock-data 的 Apache-2.0 不同，存在来源风险）。
- 补充端点回归测试：`scripts/theme_miner/smoke_test.py`。

## 使用限额

### 各技能配额/限制汇总

| 技能 | 每日调用限额 | 单次查询限制 |
|---|---|---|
| **金融数据查询** | ~50 次/日 | 单次最多 **5 个** 股票/金融实体，超出自动截断 |
| **金融问答** | ~50 次/日 | 自然语言问题长度建议 ≤500 字 |
| **资讯搜索** | ~50 次/日 | 无额外限制 |
| **宏观数据** | ~50 次/日 | 地域集合类查询建议上层复核完整性 |
| **智能选股** | ~50 次/日 | 无额外限制 |
| **行业研究 / 首次覆盖 / 专题研究 / 业绩点评 / 个股跟踪** | ~50 次/日/技能 | 报告生成耗时 1~5 分钟，需设置充足超时 |
| **股票诊断 / 基金诊断 / 热点发现 / 可比公司分析** | ~50 次/日/技能 | 无额外限制 |

### 详细说明

#### 1. 金融数据查询（mx-finance-data）

- 单次查询实体上限：**5 个**
- 超限处理：自动截取前 5 个实体，并在结果说明文件中提示
- 示例：查询 6 只股票时，仅返回前 5 只的数据
- 数据量过大时可能返回精简数据，需在提示中留意

#### 2. 其他 13 个技能

包括：金融问答、资讯搜索、宏观数据、智能选股、行业研究、个股跟踪、首次覆盖/深度研究、业绩点评、股票诊断、基金诊断、热点发现、可比公司分析、专题研究。

- 每个技能每日免费调用额度约为 **50 次**（独立计算，互不影响）
- 具体限额取决于您的东方财富妙想账户等级与平台策略
- 如出现限流提示（如 `rate limit`、`quota exceeded`、`调用次数已达上限` 等），说明已达到当日上限

#### 3. 配额优化建议

| 场景 | 建议 |
|---|---|
| 单 Token 高频调用 | 配置 `EM_API_KEY_POOL` 实现多 Token 轮换 |
| 批量诊断/回测 | 控制并发，预留余量（单 Token 调用接近 45 次时切换） |
| 配额耗尽 | 自动降级到 BaoStock / yfinance 等备用数据源 |
| 报告生成超时 | 设置超时 ≥300 秒，避免重复提交 |

#### 4. 获取更高额度

如需了解确切限额或提升配额：
1. 访问 [东方财富妙想官网](https://ai.eastmoney.com) 查看 API 套餐说明
2. 联系东方财富客服咨询账户升级方案

## 目录结构

```
mx-skills/
├── SKILL.md              # 主 Router：触发条件 + 路由决策表 + 快速调用索引
├── .env.example          # 环境变量模板
├── .gitignore
├── scripts/              # 14 个子技能执行脚本
│   ├── mx_financial_assistant/
│   ├── mx_finance_data/
│   ├── mx_finance_search/
│   ├── mx_macro_data/
│   ├── mx_stocks_screener/
│   ├── industry_research_report/
│   ├── industry_stock_tracker/
│   ├── initiation_of_coverage_or_deep_dive/
│   ├── stock_earnings_review/      # 多步骤脚本（validate + period + review）
│   ├── stock_diagnosis/
│   ├── fund_diagnosis/
│   ├── stock_market_hotspot_discovery/
│   ├── comparable_company_analysis/ # get_data + excel_theme
│   └── topic_research_report/
└── references/           # 15 个详细参考文档（按需读取）
    ├── mx_financial_assistant.md
    ├── mx_finance_data.md
    ├── ...
    └── stock_earnings_review_business_logic.md
```

## 致谢 / Credits

本仓库的 **a-stock-data 补充能力层** vendor 自：

- 项目主页：**[simonlin1212/a-stock-data](https://github.com/simonlin1212/a-stock-data)**
- 版本：V3.2.1（2026-05-30，commit `b428fad2`；初次 vendor 自 V3.1 `2dd95e3c`）
- 作者：**Simon 林**（抖音「Simon林」 / 公众号「硅基世纪」）
- License：Apache License 2.0

上游单文件 `SKILL.md`（78KB，覆盖 7 层架构 / 27 个端点 / 13 个数据源）按层拆分为 8 个 reference 文件（`references/a_stock_*.md`），保留原作者署名与许可声明。本地针对 2026 年后部分接口漂移做了 **3 处仍生效的 patch**（§1.3 百度 K线被封改东财 push2his、§3.3 百度概念板块被封改东财 emweb F10、§5.1 东财个股新闻 search-api 失效改 np-listapi；详见各文件 frontmatter 的 `patch_notes`）。另有 1 处历史 patch（§6.4 新浪三表）已被上游 v3.2.1 官方采纳、本地退役。所有改动经 `scripts/a_stock_data/smoke_test.py` 回归验证（21 PASS / 0 FAIL）。完整 Apache-2.0 声明见仓库根目录 `NOTICE`。

> **v3.2 升级要点（2026-05-30 跟进）**：上游新增「东财防封」架构——所有 `eastmoney.com` 请求统一走 `em_get()` 节流入口（串行限流 + 会话复用），本地 3 处 eastmoney patch 端点也已接入；财联社快讯（§5.2）因 cls.cn 迁站下线，全市场快讯改用东财全球资讯（§5.3）。

感谢 Simon 林开源这套高质量的 A 股数据工具集——它让 mx-skills 在妙想付费配额耗尽时拥有了可靠的免费降级源，也补齐了龙虎榜、解禁日历、北向资金、题材归因等 mx-skills 原本不覆盖的能力。如果它帮到了你的投研工作流，欢迎到[上游赞赏作者](https://github.com/simonlin1212/a-stock-data#donate)。

## 免责声明

所有分析仅供参考，不构成投资建议。股市有风险，投资需谨慎。

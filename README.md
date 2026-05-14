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
pip3 install httpx pandas openpyxl --user
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

## 免责声明

所有分析仅供参考，不构成投资建议。股市有风险，投资需谨慎。

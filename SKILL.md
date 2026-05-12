---
name: mx-skills
description: >
  东方财富妙想金融智能技能集（mx-skills）。一站式覆盖金融数据查询、资讯搜索、宏观数据、
  智能选股、金融问答、行业研究、个股跟踪、首次覆盖/深度研究、业绩点评、股票诊断、
  基金诊断、市场热点发现、可比公司分析、专题研究报告等全链条金融投研能力。

  **必须使用此技能的场景（包括但不限于）**：
  - 用户提到任何股票代码（如 600519、300059、AAPL、0700.HK）或公司名称（如贵州茅台、东方财富、腾讯控股）
  - 用户提到任何基金名称（如华夏成长混合、易方达蓝筹精选）
  - 用户提到任何行业/板块名称（如半导体、新能源、白酒、银行）
  - 用户要求查询数据、行情、价格、涨跌幅、市值、PE、ROE 等任何金融指标
  - 用户要求搜索资讯、公告、研报、新闻、政策解读
  - 用户要求分析/诊断/研究/报告/点评某只股票、基金、行业或宏观主题
  - 用户问"这只股票怎么样""值得买吗""该卖吗""如何操作"等持有决策问题
  - 用户要求选股、筛基金、选板块、构建投资组合
  - 用户要求查看宏观数据（GDP、CPI、M2、PMI、失业率、汇率、利率等）
  - 用户要求对比公司、同业分析、估值比较
  - 用户提到"业绩点评""财报分析""深度研究""首次覆盖""专题研究""热点追踪"等关键词
  - 用户使用口语化表达如"帮我看看""查一下""分析一下""总结一下"等涉及上述任何实体

  **关键约束**：即使用户的问题看起来简单（如"贵州茅台最新价""东方财富怎么样"），
  也不要仅凭知识库回答——必须使用此技能调用东方财富实时数据库获取真实数据。
  此技能支持自然语言交互，返回结构化数据、Markdown 报告、Excel/CSV/PDF/DOCX 附件。

  **不适用场景**：纯技术编程问题（如写排序算法）、与非金融无关的日常对话、
  纯数学计算（如解方程）、纯文件操作（如重命名文件）等。
---

# 东方财富妙想金融技能集（mx-skills）

## 概述

本技能集是围绕东方财富金融数据库构建的一站式投研能力平台，包含 14 个专业化子技能。
本文件为 **Router（路由层）**，负责根据用户意图匹配正确的子技能并调度执行。

**核心原则**：
- 不要自行编造金融数据或研究报告，必须通过调用脚本接口获取真实数据。
- 各子技能的详细指令（输入输出规范、错误处理、模板格式）存放在 `references/` 目录下。
- 路由确定后，先读取对应 reference 文件，再执行对应脚本。

---

## 环境变量

| 变量名 | 说明 | 来源 |
|---|---|---|
| `EM_API_KEY` | 东方财富妙想 API Key | 优先从环境变量读取；默认已配置在 `{baseDir}/.env` 中 |

如需自定义 Key，可设置环境变量覆盖：
```bash
export EM_API_KEY="your_key_here"
```

---

## 依赖安装

首次使用前确保依赖已安装：
```bash
pip3 install httpx pandas openpyxl --user
```

---

## 路由决策表

根据用户意图，按优先级匹配子技能：

| # | 用户意图 | 子技能 | Reference 文件 | 脚本路径 |
|---|---|---|---|---|
| 1 | 自然语言问答、概括性金融问题、"帮我查一下"/"分析一下"/"解释一下" | 金融问答 | `references/mx_financial_assistant.md` | `scripts/mx_financial_assistant/generate_answer.py` |
| 2 | 查询结构化金融数据（股价、财报、估值、盘口等） | 金融数据查询 | `references/mx_finance_data.md` | `scripts/mx_finance_data/get_data.py` |
| 3 | 搜索财经资讯、公告、研报、新闻、政策 | 金融资讯搜索 | `references/mx_finance_search.md` | `scripts/mx_finance_search/get_data.py` |
| 4 | 查询宏观经济数据（GDP、CPI、M2、PMI 等） | 宏观数据查询 | `references/mx_macro_data.md` | `scripts/mx_macro_data/get_data.py` |
| 5 | 选股、选板块、选基金、筛选 ETF/可转债 | 智能选股 | `references/mx_stocks_screener.md` | `scripts/mx_stocks_screener/get_data.py` |
| 6 | 生成行业研究报告 | 行业研究 | `references/industry_research_report.md` | `scripts/industry_research_report/get_data.py` |
| 7 | 生成行业/个股跟踪报告（日报/周报/月报） | 行业个股跟踪 | `references/industry_stock_tracker.md` | `scripts/industry_stock_tracker/generate_industry_stock_tracker_report.py` |
| 8 | 生成首次覆盖报告或深度研究报告 | 首次覆盖/深度研究 | `references/initiation_of_coverage_or_deep_dive.md` | `scripts/initiation_of_coverage_or_deep_dive/generate_deep_research_report.py` |
| 9 | 业绩点评、财报分析、季报/半年报/年报点评 | 业绩点评 | `references/stock_earnings_review.md` + `references/stock_earnings_review_business_logic.md` | `scripts/stock_earnings_review/`（多步骤） |
| 10 | 单只股票综合诊断（"怎么样"/"值得买吗"/"该卖吗"） | 股票诊断 | `references/stock_diagnosis.md` | `scripts/stock_diagnosis/get_data.py` |
| 11 | 单只基金综合诊断 | 基金诊断 | `references/fund_diagnosis.md` | `scripts/fund_diagnosis/get_data.py` |
| 12 | 发现市场热点、今日热点、热股、活跃赛道 | 热点发现 | `references/stock_market_hotspot_discovery.md` | `scripts/stock_market_hotspot_discovery/get_data.py` |
| 13 | 可比公司分析、同业对比、经营+估值横向比较 | 可比公司分析 | `references/comparable_company_analysis.md` | `scripts/comparable_company_analysis/`（get_data.py + excel_theme.py） |
| 14 | 专题研究报告、主题投资、事件驱动研究 | 专题研究 | `references/topic_research_report.md` | `scripts/topic_research_report/get_data.py` |

**路由冲突时的优先级规则**：
- 若用户请求包含明确的报告类型关键词（如"业绩点评""行业报告""深度研究"），优先按报告类型匹配。
- 若用户请求是笼统的问答型（如"帮我看看""分析一下"），优先走金融问答（#1），由金融问答内部再决定是否调用数据/搜索能力。
- 若用户明确要求数据/文件输出（如"导出 Excel""生成 CSV"），优先走对应的数据查询类技能。

---

## 通用调用规范

### 脚本执行方式

所有脚本通过 `{baseDir}` 引用 skill 根目录：
```bash
python3 {baseDir}/scripts/<子技能目录>/<脚本名>.py [参数]
```

**重要约束**：
- **禁止**使用任何「后台执行、稍后汇报」的方式运行脚本。
- 必须在当前会话中同步等待命令完成，获取 stdout 结果后再继续。

### 输出规范

- 脚本返回 JSON 时，优先提取 `ok=true` 的成功结果。
- 若脚本返回 `ok=false` 或包含 `message` 字段，**必须原样透传** `message`，不得改写或替换。
- 禁止在接口失败时编造数据或报告内容。

### 数学公式格式

所有子技能输出中的数学公式严格遵循：
- 行内公式：`\(...\)`（不使用 `$...$`）
- 行间公式：`\[...\]`

---

## 各子技能快速调用索引

### 1. 金融问答（mx-financial-assistant）
```bash
# 标准模式
python3 {baseDir}/scripts/mx_financial_assistant/generate_answer.py --query "用户问题"

# 深度思考模式
python3 {baseDir}/scripts/mx_financial_assistant/generate_answer.py --query "用户问题" --deep-think
```

### 2. 金融数据查询（mx-finance-data）
```bash
python3 {baseDir}/scripts/mx_finance_data/get_data.py --query "贵州茅台最近一年营收和净利润"
```
输出：Excel（多 sheet）+ 描述 txt。

### 3. 金融资讯搜索（mx-finance-search）
```bash
python3 {baseDir}/scripts/mx_finance_search/get_data.py "寒武纪最新研报与公告"
```
输出：txt 文本文件。

### 4. 宏观经济数据查询（mx-macro-data）
```bash
python3 {baseDir}/scripts/mx_macro_data/get_data.py --query "中国近五年GDP"
```
输出：CSV（按频率分文件）+ 描述 txt。

### 5. 智能选股（mx-stocks-screener）
```bash
python3 {baseDir}/scripts/mx_stocks_screener/get_data.py --query "股价大于100元，主力流入，成交额排名前50" --select-type "A股"
```
输出：CSV + 描述 txt。

### 6. 行业研究报告（industry-research-report）
```bash
python3 {baseDir}/scripts/industry_research_report/get_data.py --query "半导体"
```
输出：PDF + DOCX + 分享链接。

### 7. 行业/个股跟踪报告（industry-stock-tracker）
```bash
python3 {baseDir}/scripts/industry_stock_tracker/generate_industry_stock_tracker_report.py --query "跟踪新能源汽车板块"
```
输出：PDF + DOCX + 分享链接。

### 8. 首次覆盖/深度研究（initiation-of-coverage-or-deep-dive）
```bash
python3 {baseDir}/scripts/initiation_of_coverage_or_deep_dive/generate_deep_research_report.py --query "东方财富深度研究"
```
输出：PDF + DOCX + 分享链接。

### 9. 业绩点评（stock-earnings-review）——分步骤编排
```bash
# 第一步：实体识别
python3 {baseDir}/scripts/stock_earnings_review/validate_entity.py --query "东方财富 业绩点评"

# 第二步：获取报告期候选
python3 {baseDir}/scripts/stock_earnings_review/normalize_report_period.py \
  --secu-code 300059 --market-char SZ --class-code 002001

# 第三步：生成点评（外层模型选择 reportDate 后调用）
python3 {baseDir}/scripts/stock_earnings_review/call_review_api.py \
  --secu-code 300059 --market-char SZ --class-code 002001 \
  --report-date 2025-12-31 --secu-name 东方财富
```

### 10. 股票诊断（stock-diagnosis）
```bash
python3 {baseDir}/scripts/stock_diagnosis/get_data.py --query "东方财富股票咋样"
```
输出：Markdown 诊断报告（本地 .md 文件）。

### 11. 基金诊断（fund-diagnosis）
```bash
python3 {baseDir}/scripts/fund_diagnosis/get_data.py --query "华夏成长混合基金"
```
输出：Markdown 诊断报告（本地 .md 文件）。

### 12. 热点发现（stock-market-hotspot-discovery）
```bash
python3 {baseDir}/scripts/stock_market_hotspot_discovery/get_data.py --query "今日热点"
```
输出：Markdown 热点报告（本地 .md 文件）。

### 13. 可比公司分析（comparable-company-analysis）
```bash
# 仅取数
python3 {baseDir}/scripts/comparable_company_analysis/get_data.py --query "东方财富"

# 一键生成 Excel 报告
python3 {baseDir}/scripts/comparable_company_analysis/excel_theme.py --query "东方财富"
```
输出：Excel 可视化报告。

### 14. 专题研究报告（topic-research-report）
```bash
python3 {baseDir}/scripts/topic_research_report/get_data.py --query "东方财富专题研究"
```
输出：PDF + DOCX + 分享链接。

---

## 错误处理通用话术

| 场景 | 处理方式 |
|---|---|
| 缺少参数/查询文本 | "请输入您的查询内容。" |
| API 接口非 200 | "服务暂时不可用，请稍后重试。" |
| HTTP/网络错误 | "网络连接异常，请检查网络后重试。" |
| 请求超时 | "请求超时，请稍后重试。" |
| 空响应 | "未获取到有效结果，请稍后重试。" |
| 不支持实体/市场 | 原样透传脚本返回的 `message`，不得改写。 |

---

## 子技能详细文档索引

路由确定后，**必须**先读取对应 reference 文件获取完整指令：

- `references/mx_financial_assistant.md` — 金融问答详细规范（含溯源参考格式、深度思考模式）
- `references/mx_finance_data.md` — 金融数据查询规范（含配额限制、输出文件说明）
- `references/mx_finance_search.md` — 金融资讯搜索规范
- `references/mx_macro_data.md` — 宏观数据查询规范（含完整性复核协议）
- `references/mx_stocks_screener.md` — 智能选股规范（含 select-type 参数说明）
- `references/industry_research_report.md` — 行业研究报告生成规范
- `references/industry_stock_tracker.md` — 行业/个股跟踪报告规范
- `references/initiation_of_coverage_or_deep_dive.md` — 首次覆盖/深度研究规范
- `references/stock_earnings_review.md` — 业绩点评精简协议
- `references/stock_earnings_review_business_logic.md` — 业绩点评完整业务逻辑（含报告期匹配规则）
- `references/stock_diagnosis.md` — 股票诊断规范
- `references/fund_diagnosis.md` — 基金诊断规范
- `references/stock_market_hotspot_discovery.md` — 热点发现规范
- `references/comparable_company_analysis.md` — 可比公司分析规范
- `references/topic_research_report.md` — 专题研究报告规范

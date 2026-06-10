---
name: theme_miner
description: 热门题材挖掘分析层 — A股题材 Top3 + 个股 Top5 + 中长期目标价 + 操作策略一条龙。建立在 a-stock-data 免费数据层之上的可选分析层。当用户要「完整题材挖掘流水线」（题材+个股+目标价+策略），或 mx-skills #12 热点发现配额耗尽时使用。
metadata:
  upstream: skills-xjx/hot-theme-miner
  upstream_commit: e7a022b3a1a0a2aed34098b4431097999a3eb847
  upstream_version: 2.0.0
  upstream_date: 2026-04-15
  upstream_file: SKILL.md
  license: unknown（上游未附 LICENSE，作者署名 "AI Assistant"；按用户指示在未核实许可证情况下 vendor）
  author: "AI Assistant"
  layer: theme-miner（a-stock-data 之上的可选分析层）
---

> Vendored from skills-xjx/hot-theme-miner v2.0.0 (commit e7a022b3)，改编自其 `SKILL.md`。
>
> **定位**：这是建立在 **a-stock-data 免费数据层之上的「分析大脑」**。它本身不取数——所有 A 股数据通过 [[theme_miner_data_bridge]] 调用 a-stock-data 的内嵌 Python 函数获得。**单向依赖**：本层引用 a-stock-data，a-stock-data 不感知本层（a-stock-data 继续按上游 diff 独立升级）。
>
> **A 股 only**：题材/涨停/概念板块均为 A 股概念。港股/美股/基金/宏观/AI 研报生成不走本层。

# 热门题材挖掘 Skill

## 触发时机

仅当用户需要**完整题材挖掘流水线**时使用本层（否则简单「今天什么板块热」优先走 mx-skills #12 热点发现）：

- 「挖掘今日最热题材 Top3 **并选出潜力个股 Top5**」
- 「热门题材 + 龙头股 + 目标价 + 操作策略」整条链
- 「哪些题材最热、对应哪些股票最有上涨潜力、能涨多少、怎么操作」
- mx-skills #12 热点发现**配额耗尽**（`quota exceeded`/`rate limit`/`调用次数已达上限`）时的免费降级路径

### 与 mx-skills #12 热点发现的边界

| 场景 | 路由 |
|---|---|
| 「今天什么板块/方向热」简单总览 | **mx-skills #12**（付费 API，快，黑盒打分） |
| 完整 题材→个股→目标价→策略 链路 | **本层 theme_miner**（免费，a-stock-data 供数，打分透明） |
| #12 配额耗尽 | **降级到本层** |

## 核心能力

1. **热门题材挖掘 Top3** — 「驱动力 × 资金强度 × 可持续性」三维评分（见 [[theme_miner_theme_scoring]]）+ 生命周期阶段（潜伏/发酵/高潮/分化/衰退）+ 题材级别（事件/产业/战略）
2. **潜力个股 Top5** — 「题材核心度 × 技术 × 资金面 × 基本面 × 催化剂匹配度」五维评分（见 [[theme_miner_stock_scoring]]）
3. **中长期价格空间预测** — 三情景（乐观/中性/悲观）6/12 月目标价（见 [[theme_miner_price_prediction]]，⚠️ **启发式模型、非回测，仅作相对排序参考**）
4. **操作策略** — 仓位 / 入场 / 止损 / 出场 + 风险标注

## 执行流程概览

```
Step 1 市场情绪采集     → 涨跌停统计、情绪评级
Step 2 题材数据采集     → 概念/行业板块行情 + 涨停股匹配
Step 3 题材评分 Top3    → 三维评分 + 生命周期判定
Step 4 成分股数据采集   → 候选股资金流向 + 基本面
Step 5 个股评分 Top5    → 五维评分 + 龙头标注
Step 6 价格预测与策略   → 三情景目标价 + 操作建议
Step 7 报告组装         → 完整 Markdown 报告
```

详细流程、报告模板、数据流转约束见 [[theme_miner_execution]]。

## 参考文档

| 文档 | 说明 |
|------|------|
| [[theme_miner_data_bridge]] | **数据桥**：6 类数据需求 → a-stock-data 函数映射；涨停池/跌停池补充端点；市场情绪汇总 |
| [[theme_miner_theme_scoring]] | 题材三维评分模型、生命周期判定、题材级别分类、Top3 筛选 |
| [[theme_miner_stock_scoring]] | 个股五维评分模型、龙头标注、风险标注、Top5 筛选 |
| [[theme_miner_price_prediction]] | 中长期价格预测（⚠️ 启发式）、置信度、操作策略、风险提示 |
| [[theme_miner_execution]] | 7 步流水线、情绪评级、报告模板、数据约束、层间协作 |

## 数据源

全部来自 a-stock-data 的免费东财接口（经 `em_get()` 防封节流），无 mx-skills 付费配额消耗。映射详见 [[theme_miner_data_bridge]]。

## 使用方式

```
# 完整流水线
挖掘今日最热门的题材Top3和个股Top5（含目标价和操作策略）

# 指定关注方向
挖掘AI算力/半导体/新能源相关题材的热门机会
```

## 注意事项

1. **数据实时性**：建议交易日盘中（9:30-15:00）或收盘后运行
2. **题材周期滞后**：高潮期信号出现时可能已接近尾声
3. **价格预测启发式**：目标价模型未经回测，仅供相对排序参考，不构成价位依据（见 [[theme_miner_price_prediction]] 免责）
4. **仓位管理**：单一题材仓位 ≤ 总仓位 30%，严格止损
5. **免责声明**：本分析仅供参考，不构成投资建议。股市有风险，投资需谨慎。

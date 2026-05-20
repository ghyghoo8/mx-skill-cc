# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

This is **not an application** — it is a Claude Code Skill package (`~/.claude/skills/mx-skills/`) that wraps the 东方财富妙想 (Eastmoney Miaoxiang) financial API as 14 sub-skills. The entrypoint Claude reads at runtime is `SKILL.md` (Router). There is no build step, no test suite, and no CI. Each sub-skill is a standalone Python script invoked via `python3` with a `--query` argument.

When editing this repo, the consumer is **future Claude instances loading the skill**, not end users. Changes to `SKILL.md`, `references/*.md`, or script CLI surfaces directly change Claude's routing/invocation behavior.

## Architecture: Router + Reference + Script

The skill uses a three-layer pattern. Understanding it is required before editing:

1. **`SKILL.md` (Router layer)** — Single file Claude reads first. Contains:
   - Trigger conditions (when to activate the skill)
   - Routing decision table mapping user intent → sub-skill → reference file → script path
   - Universal calling conventions (output parsing, timeout, error handling)
   - Quick-invoke index for all 14 sub-skills

2. **`references/<sub_skill>.md` (Reference layer)** — Detailed per-skill spec. Claude is instructed in `SKILL.md` to **read the matching reference file before executing the script**. This is where input/output schemas, message templates, completeness protocols, and business logic live. `SKILL.md` deliberately omits these details to stay small.

3. **`scripts/<sub_skill>/*.py` (Execution layer)** — Python scripts that call the Eastmoney API. They are stateless and accept `--query` (and sometimes other flags). They write output files to `./miaoxiang/<sub_skill>/` under the **caller's CWD** (not the skill's directory) and print result locations to stdout.

When adding or changing a sub-skill, all three layers must stay in sync: the row in `SKILL.md`'s routing table, the reference doc, and the script's CLI.

## The four output conventions

Scripts/references deliberately use four different output shapes; the calling Claude parses based on sub-skill type. Preserve these conventions when editing:

- **A. JSON envelope** — `mx_financial_assistant`, `industry_research_report`, `initiation_of_coverage_or_deep_dive`, `topic_research_report`, `stock_earnings_review`. Emit `{"ok": true|false, "answer"/"message": "...", "references": [...]}`. On failure the `message` field must be **passed through verbatim** to the user — `SKILL.md` forbids rewriting it.
- **B. File-path lines** — `mx_finance_data`, `mx_macro_data`, `mx_stocks_screener`. Emit plain text lines: `文件: <abs path>`, `描述: <abs path>`, `行数: <int>`. Errors go to stderr prefixed with `错误:`.
- **C. `Saved:` + Markdown body** — `stock_diagnosis`, `fund_diagnosis`, `stock_market_hotspot_discovery`, `comparable_company_analysis`. First line `Saved: <abs path to .md>`, followed by the full Markdown content.
- **D. Inline Python returns (a-stock-data layer)** — `a_stock_*` references. **No** `scripts/` subprocess. Model copies the embedded Python code blocks from the reference and executes them via `python3 -c "..."`. Returns Python values/dicts/DataFrames; **does not write files**. The model formats Markdown from the return value before showing the user.

## a-stock-data complementary layer (vendored, Apache-2.0)

`references/a_stock_*.md` (8 files) are vendored from [simonlin1212/a-stock-data](https://github.com/simonlin1212/a-stock-data) V3.1 (commit `2dd95e3c`, 2026-05-19). They split the upstream single-file SKILL.md by its 7-layer architecture, plus a shared `a_stock_data_common.md`. Treat them as a **complementary/downgrade data layer for A-share only**, not a replacement for mx-skills:

- **A-share only.** Routing rules in `SKILL.md` force HK/US/funds/macro/AI-report-gen back to mx-skills #1-#14.
- **Complementary capabilities** (mx-skills has no equivalent): 龙虎榜 / 解禁 / 北向 / 题材归因 / 概念板块 / 融资融券 / 大宗交易 / 股东户数 / 分红送转 / iwencai NL search / realtime order book. Route directly here.
- **Overlapping capabilities** (basic quotes / news / financials / filings): mx-skills wins by default; degrade to a-stock-data on quota errors (`quota exceeded` / `rate limit` / `调用次数已达上限` / HTTP 429). The 50/day Miaoxiang quota was historically the bottleneck — a-stock-data is the new fallback (better than the BaoStock/yfinance fallback mentioned in `SKILL.md`).
- **Do not split into discrete `scripts/`.** Upstream's value is the self-contained inline-Python design. Future upstream updates merge via diff onto these 8 files, not by editing 28 Python scripts.
- **Upstream version is tracked in each file's frontmatter** (`upstream_commit`, `upstream_version`, `upstream_date`). On upstream update, fetch new SKILL.md, diff against pinned commit, re-apply slices.
- **Common helpers (`UA`, `DATACENTER_URL`, `eastmoney_datacenter()`, ticker normalization, valuation formulas) live in `a_stock_data_common.md`.** Layer files reference these but don't redeclare them — the model must read `_common` before executing any layer snippet.
- **`IWENCAI_API_KEY` is optional** and only used by `a_stock_research.md`'s NL search. The other 27 endpoints are free, no key.
- **Extra runtime deps**: `mootdx requests stockstats` (coexists with mx-skills' `httpx pandas openpyxl`).
- **License**: Apache-2.0. Attribution to Simon 林 is preserved in `NOTICE` and each layer file's frontmatter — do not remove.

## Two scripts are multi-step (not single-shot)

Most sub-skills are one `get_data.py --query "..."` call. Two are not:

- **`stock_earnings_review/`** — 3-step pipeline: `validate_entity.py` → `normalize_report_period.py` → `call_review_api.py`. The model picks a `reportDate` between steps 2 and 3. Business logic for matching report periods lives in `references/stock_earnings_review_business_logic.md`, not in `stock_earnings_review.md`.
- **`comparable_company_analysis/`** — Two entrypoints: `get_data.py` (raw data) or `excel_theme.py` (one-shot Excel report).

## Environment

Scripts read `EM_API_KEY` from the environment and **raise immediately** if it is missing (no fallback). The `.env` file in the repo root is the local default. `EM_API_KEY_POOL` is documented but **not implemented in these scripts** — token rotation is the caller's responsibility.

Install deps once:
```bash
pip3 install httpx pandas openpyxl --user
```

## Invoking scripts manually (for debugging)

```bash
# From any CWD — output lands in ./miaoxiang/<sub_skill>/ under that CWD
EM_API_KEY=xxx python3 scripts/mx_finance_data/get_data.py --query "贵州茅台最近一年营收"

# If stdout looks empty/buffered (common with subprocess.Popen):
PYTHONUNBUFFERED=1 python3 -u scripts/.../get_data.py --query "..."
```

Report-generation scripts (industry research, deep dive, topic research, earnings review) routinely take **1–5 minutes**. Set timeouts ≥ 300s; do not retry on apparent hangs — the backend may be queued.

## Quotas and entity limits (load-bearing)

- `mx_finance_data` truncates to **5 entities per call** silently and notes the truncation in the description txt. When changing this script, do not relax the limit without also updating `SKILL.md` and `references/mx_finance_data.md`.
- All other sub-skills are gated by a per-skill **~50 calls/day** quota on the Eastmoney side. Quota errors surface as Chinese strings like `调用次数已达上限`, `rate limit`, `quota exceeded` — the agent is expected to pass these through, not catch and retry.

## Math formula convention

All output (scripts and references) uses `\(...\)` for inline and `\[...\]` for display math. Do **not** introduce `$...$` — the router enforces this.

## Output directory

Scripts write to `./miaoxiang/<sub_skill>/...` relative to the caller's CWD. The top-level `miaoxiang/` directory in this repo holds historical output and is gitignored. Do not commit generated files.

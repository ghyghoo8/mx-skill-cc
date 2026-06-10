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

`references/a_stock_*.md` (8 files) are vendored from [simonlin1212/a-stock-data](https://github.com/simonlin1212/a-stock-data) V3.2.2 (commit `9379ab90`, 2026-06-03). They split the upstream single-file SKILL.md by its 7-layer architecture, plus a shared `a_stock_data_common.md`. Treat them as a **complementary/downgrade data layer for A-share only**, not a replacement for mx-skills:

- **A-share only.** Routing rules in `SKILL.md` force HK/US/funds/macro/AI-report-gen back to mx-skills #1-#14.
- **Complementary capabilities** (mx-skills has no equivalent): 龙虎榜 / 解禁 / 北向 / 题材归因 / 概念板块 / 融资融券 / 大宗交易 / 股东户数 / 分红送转 / iwencai NL search / realtime order book. Route directly here.
- **Overlapping capabilities** (basic quotes / news / financials / filings): mx-skills wins by default; degrade to a-stock-data on quota errors (`quota exceeded` / `rate limit` / `调用次数已达上限` / HTTP 429). The 50/day Miaoxiang quota was historically the bottleneck — a-stock-data is the new fallback (better than the BaoStock/yfinance fallback mentioned in `SKILL.md`).
- **Do not split into discrete `scripts/`.** Upstream's value is the self-contained inline-Python design. Future upstream updates merge via diff onto these 8 files, not by editing 28 Python scripts.
- **Upstream version is tracked in each file's frontmatter** (`upstream_commit`, `upstream_version`, `upstream_date`). On upstream update, fetch new SKILL.md, diff against pinned commit, re-apply slices.
- **Common helpers (`UA`, `DATACENTER_URL`, `em_get()`, `eastmoney_datacenter()`, ticker normalization, valuation formulas) live in `a_stock_data_common.md`.** Layer files reference these but don't redeclare them — the model must read `_common` before executing any layer snippet.
- **东财防封 (v3.2+): every `eastmoney.com` call routes through `em_get()`** — a serial throttle (`EM_MIN_INTERVAL=1.0s` + jitter) over a reused Keep-Alive session, defined once in `_common`. This includes mx-skills' own local-patch eastmoney endpoints (§1.3 K线, §3.3 概念板块, §5.1 个股新闻). When adding any new eastmoney endpoint, use `em_get`, not bare `requests.get`. Non-eastmoney sources (mootdx/腾讯/同花顺/新浪/巨潮/iwencai) keep plain `requests`.
- **`IWENCAI_API_KEY` is optional** and only used by `a_stock_research.md`'s NL search. The other 27 endpoints are free, no key.
- **Extra runtime deps**: `mootdx requests stockstats` (coexists with mx-skills' `httpx pandas openpyxl`).
- **License**: Apache-2.0. Attribution to Simon 林 is preserved in `NOTICE` and each layer file's frontmatter — do not remove.

## theme-miner analysis layer (vendored, sits *on top of* a-stock-data)

`references/theme_miner*.md` (6 files) are vendored from `skills-xjx/hot-theme-miner` v2.0.0 (commit `e7a022b3`, 2026-04-15). This is **not a data source** — it's an opinionated **analysis/scoring layer** (A-share theme→stock→target-price→strategy pipeline, sub-skill #22) that consumes a-stock-data for its data.

- **One-directional dependency.** theme_miner references a-stock-data functions; a-stock-data never references theme_miner (so a-stock-data keeps upgrading via upstream diff independently). Do **not** add miner-specific code into any `a_stock_*.md`.
- **`theme_miner_data_bridge.md` is the seam** — it maps the miner's 6 data needs to a-stock-data functions, and carries the only original code in this layer: supplemental 涨停池/跌停池 endpoints (`push2ex.eastmoney.com`, a-stock-data lacks these) + market breadth derived by summing per-industry `f104/f105` from a-stock-data's `m:90+t:2` industry-board call. These supplemental endpoints **also go through `em_get()`** (read `a_stock_data_common.md` first).
- **Routing vs mx-skills #12 热点发现**: simple "今天什么板块热" → #12 (paid, fast). Full pipeline (Top3 themes + Top5 stocks + target price + strategy) or #12 quota-exhausted → #22 theme_miner (free, transparent scoring).
- **Quality caveats baked into the docs**: the price-prediction model is heuristic/un-backtested (it fabricates a "PE historical percentile" from current PE alone). `theme_miner_price_prediction.md` carries a mandatory disclaimer; treat target prices as relative ranking signal only, not price forecasts.
- **License unknown**: the upstream package shipped no LICENSE and author is "AI Assistant". Vendored on explicit user instruction without license verification — flagged honestly in each file's frontmatter. Unlike a-stock-data (clean Apache-2.0), this carries unresolved provenance risk.
- **Regression test**: `scripts/theme_miner/smoke_test.py` covers only the supplemental endpoints (涨停池/跌停池/breadth); scoring is pure prose with no code. `push2` breadth SKIPs under a flaky proxy.

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

## Regression test for vendored patches

The only test in the repo is `scripts/a_stock_data/smoke_test.py` — it hits one representative endpoint per a-stock-data layer to verify the 4 local patches (see each `a_stock_*.md` frontmatter's `patch_notes`) still match upstream behavior. Run after editing any `references/a_stock_*.md`:

```bash
python3 scripts/a_stock_data/smoke_test.py
```

Exit 0 = all non-SKIPped cases pass. `mootdx` cases SKIP without a CN IP; `iwencai` cases SKIP without `IWENCAI_API_KEY`. There is no test for the mx-skills main path — those scripts hit a paid quota-gated API.

## Quotas and entity limits (load-bearing)

- `mx_finance_data` truncates to **5 entities per call** silently and notes the truncation in the description txt. When changing this script, do not relax the limit without also updating `SKILL.md` and `references/mx_finance_data.md`.
- All other sub-skills are gated by a per-skill **~50 calls/day** quota on the Eastmoney side. Quota errors surface as Chinese strings like `调用次数已达上限`, `rate limit`, `quota exceeded` — the agent is expected to pass these through, not catch and retry.

## Math formula convention

All output (scripts and references) uses `\(...\)` for inline and `\[...\]` for display math. Do **not** introduce `$...$` — the router enforces this.

## Output directory

Scripts write to `./miaoxiang/<sub_skill>/...` relative to the caller's CWD. The top-level `miaoxiang/` directory in this repo holds historical output and is gitignored. Do not commit generated files.

<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:
```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Build & Compile (80-90% savings)
```bash
rtk cargo build         # Cargo build output
rtk cargo check         # Cargo check output
rtk cargo clippy        # Clippy warnings grouped by file (80%)
rtk tsc                 # TypeScript errors grouped by file/code (83%)
rtk lint                # ESLint/Biome violations grouped (84%)
rtk prettier --check    # Files needing format only (70%)
rtk next build          # Next.js build with route metrics (87%)
```

### Test (60-99% savings)
```bash
rtk cargo test          # Cargo test failures only (90%)
rtk go test             # Go test failures only (90%)
rtk jest                # Jest failures only (99.5%)
rtk vitest              # Vitest failures only (99.5%)
rtk playwright test     # Playwright failures only (94%)
rtk pytest              # Python test failures only (90%)
rtk rake test           # Ruby test failures only (90%)
rtk rspec               # RSpec test failures only (60%)
rtk test <cmd>          # Generic test wrapper - failures only
```

### Git (59-80% savings)
```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### GitHub (26-87% savings)
```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

### JavaScript/TypeScript Tooling (70-90% savings)
```bash
rtk pnpm list           # Compact dependency tree (70%)
rtk pnpm outdated       # Compact outdated packages (80%)
rtk pnpm install        # Compact install output (90%)
rtk npm run <script>    # Compact npm script output
rtk npx <cmd>           # Compact npx command output
rtk prisma              # Prisma without ASCII art (88%)
```

### Files & Search (60-75% savings)
```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%). Format flags (-c, -l, -L, -o, -Z) run raw.
rtk find <pattern>      # Find grouped by directory (70%)
```

### Analysis & Debug (70-90% savings)
```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure (85% savings)
```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

### Network (65-70% savings)
```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

### Meta Commands
```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Claude Code sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to CLAUDE.md
rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
```

## Token Savings Overview

| Category | Commands | Typical Savings |
|----------|----------|-----------------|
| Tests | vitest, playwright, cargo test | 90-99% |
| Build | next, tsc, lint, prettier | 70-87% |
| Git | status, log, diff, add, commit | 59-80% |
| GitHub | gh pr, gh run, gh issue | 26-87% |
| Package Managers | pnpm, npm, npx | 70-90% |
| Files | ls, read, grep, find | 60-75% |
| Infrastructure | docker, kubectl | 85% |
| Network | curl, wget | 65-70% |

Overall average: **60-90% token reduction** on common development operations.
<!-- /rtk-instructions -->
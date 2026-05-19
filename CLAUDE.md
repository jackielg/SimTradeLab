# CLAUDE.md — SimTradeLab

## Project
回测引擎 v2.10.2，提供 62+ PTrade 兼容本地模拟 API (97 public methods)。策略代码零修改即可在 PTrade 实盘运行。

## Stack
Python >=3.10, Poetry, Ruff (lint), Pydantic (config), src/ layout

## Commands
- Backtest: `SIMTRADELAB_DATA_PATH=../SimTradeData/data python3 src/simtradelab/backtest/run_backtest.py --strategy <name> --start YYYY-MM-DD --end YYYY-MM-DD --frequency 1m`
- Backtest (Windows): `set SIMTRADELAB_DATA_PATH=..\SimTradeData\data\cn && python src/simtradelab/backtest/run_backtest.py --strategy <name> --start YYYY-MM-DD --end YYYY-MM-DD --frequency 1m`
- Test unit: `python3 -m pytest tests/unit/ -v`
- Test integration: `python3 -m pytest tests/integration/ -v`
- Test all + coverage: `python3 -m pytest tests/ --cov=simtradelab`
- Lint: `ruff check src/`
- Format: `ruff format src/`

## Architecture
- `src/simtradelab/backtest/` → Runner, Config (Pydantic), stats, export, batch, optimizer
- `src/simtradelab/ptrade/` → PtradeAPI (62+ APIs), lifecycle, sandbox, order processing
- `src/simtradelab/service/` → DataServer (Parquet loader)
- `strategies/<name>/backtest.py` → 策略代码
- `docs/PTrade_API_Complete_Reference.md` → PTrade 官方 API 完整参考
- `docs/ARCHITECTURE.md` → 引擎内部深度文档

## Rules
- IMPORTANT: PTrade API 兼容性是首要约束，PtradeAPI 所有接口签名和行为必须与 docs/PTrade_API_Complete_Reference.md 完全一致
- IMPORTANT: 策略通过 exec() 沙箱加载，受限 builtins (无 os/sys/subprocess/socket)
- LifecycleController 7阶段状态机限制每阶段可用 API（如 order() 仅在 handle_data 中）
- StrategyDataAnalyzer 用 AST 分析策略数据依赖，按需加载 Parquet
- 策略生命周期 hooks: initialize, handle_data, before_trading_start, after_trading_end
- 策略日志数字格式统一规则：金额/价格/现价/保本线/峰值用 `.2f`(两位小数)，数量/仓位用 `.0f`(整数)，得分用 `.3f`(三位小数)，收益率/回撤/涨幅用 `.2f%`(两位小数百分比)

## Pitfalls（已踩坑记录）
- macOS 上 `python` 命令不存在，必须用 `python3`；Windows 上 `python` 可用
- 数据路径默认为 SimTradeLab/data/，实际数据在 SimTradeData/data/cn/，必须通过 `SIMTRADELAB_DATA_PATH` 环境变量指定
- BaoStock parquet 的 date 索引为 datetime64[us]（微秒），而 pd.Timestamp.value 为纳秒，两者 view("i8") 差 1000 倍。所有 date_dict.get(ts.value) 查找前必须统一精度为 datetime64[ns]
- pd.Timestamp 上限约 2262-04-11（nanosecond 精度），不可使用 2900-01-01 等远未来日期作为占位值
- 分钟级回测中 get_history(frequency="1d") 需将 current_dt.normalize() 截断到日期再查找日线索引
- get_history(is_dict=True) 返回 {stock: DataFrame}（含日期索引），不是 {stock: {field: ndarray}}
- valuation parquet 仅含 pe_ttm/pb/ps_ttm/pcf/turnover_rate，不含 total_shares/a_floats（在 fundamentals 中）。get_fundamentals("valuation", ["total_shares"]) 返回空数据
- get_fundamentals("valuation", ["total_shares", "a_floats"]) 返回空数据（这些字段在 fundamentals 中而非 valuation 中），策略 Step3 市值过滤会全部降级为日线估算
- get_fundamentals 的表名在 SimTradeLab 和 PTrade 间不完全一致。SimTradeLab 支持 `capital_structure`（自定义），PTrade 不支持该表名（报 invalid table argument）。PTrade 支持的表含 `share_change`。策略中获取股本数据(total_shares/a_floats)时须依次尝试两个表名，兼容双环境

## Out of Scope
- 不修改 docs/ 下的参考文档
- 不自动推送到远程仓库

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **SimTradeLab** (5686 symbols, 8072 relationships, 174 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/SimTradeLab/context` | Codebase overview, check index freshness |
| `gitnexus://repo/SimTradeLab/clusters` | All functional areas |
| `gitnexus://repo/SimTradeLab/processes` | All execution flows |
| `gitnexus://repo/SimTradeLab/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

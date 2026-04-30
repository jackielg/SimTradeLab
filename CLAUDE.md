# CLAUDE.md — SimTradeLab

## Project
回测引擎 v2.10.2，提供 62+ PTrade 兼容本地模拟 API (97 public methods)。策略代码零修改即可在 PTrade 实盘运行。

## Stack
Python >=3.10, Poetry, Ruff (lint), Pydantic (config), src/ layout

## Commands
- Backtest: `poetry run python src/simtradelab/backtest/run_backtest.py --strategy <name> --start YYYY-MM-DD --end YYYY-MM-DD --frequency 1m`
- Test unit: `poetry run pytest tests/unit/ -v`
- Test integration: `poetry run pytest tests/integration/ -v`
- Test all + coverage: `poetry run pytest tests/ --cov=simtradelab`
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

## Out of Scope
- 不修改 docs/ 下的参考文档
- 不自动推送到远程仓库

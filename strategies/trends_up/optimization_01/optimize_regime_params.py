# -*- coding: utf-8 -*-
"""
trends_up 动态行情参数优化 (Phase 2)

分三阶段:
  Stage A: 优化bear参数(2024瓶颈), 固定bull/sideways为默认值
  Stage B: 优化bull参数, 固定bear为Stage A最优
  Stage C: 集成验证(2024+2025双周期)

运行方式:
  cd SimTradeLab
  SIMTRADELAB_DATA_PATH=../SimTradeData/data python3 strategies/trends_up/optimization/optimize_regime_params.py
"""

import os
import re
import sys
import time
import copy
import pprint

os.environ["SIMTRADELAB_DATA_PATH"] = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "SimTradeData", "data")
)

from simtradelab.backtest.runner import BacktestRunner
from simtradelab.backtest.config import BacktestConfig

STRATEGY_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "backtest.py")
)
TEMP_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "temp_strategy")
)
LOG_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "optimize_log.txt")
)

# ==================== 参数搜索空间 ====================

BULL_DEFAULT = {
    "MAX_POSITIONS": 9,
    "MAX_POSITIONS_DAILY": 4,
    "MAX_POS_RATIO": 0.90,
    "TARGET_POS_RATIO": 0.80,
    "STOP_MA_PERIOD": 120,
    "STOP_DATA_FREQUENCY": "daily",
    "TAKE_PROFIT_L1": 9.99,
    "TAKE_PROFIT_L2": 9.99,
    "MIN_SCORE_B": 0.20,
    "MORNING_ENTRY_ENABLED": True,
    "CONFIRM_STOP_BARS": 5,
    "MAX_DRAWDOWN": 0.20,
    "BREAKEVEN_THRESHOLD": 0.03,
    "TRAILING_TAKE_PROFIT": True,
}

SIDEWAYS_DEFAULT = {
    "MAX_POSITIONS": 6,
    "MAX_POSITIONS_DAILY": 3,
    "MAX_POS_RATIO": 0.60,
    "TARGET_POS_RATIO": 0.40,
    "STOP_MA_PERIOD": 60,
    "STOP_DATA_FREQUENCY": "daily",
    "TAKE_PROFIT_L1": 0.10,
    "TAKE_PROFIT_L2": 0.20,
    "MIN_SCORE_B": 0.30,
    "MORNING_ENTRY_ENABLED": True,
    "CONFIRM_STOP_BARS": 3,
    "MAX_DRAWDOWN": 0.12,
    "BREAKEVEN_THRESHOLD": 0.02,
    "TRAILING_TAKE_PROFIT": False,
}

# 择时参数组合: 核心是 TARGET_POS_RATIO 和 MAX_POSITIONS
# bear目标仓位越低, 熊市亏损越少; 但止损太紧会导致whipsaw
TIMING_COMBOS = [
    {
        "label": "T1_defensive",
        "bear": {"MAX_POSITIONS": 2, "MAX_POSITIONS_DAILY": 1, "MAX_POS_RATIO": 0.20,
                 "TARGET_POS_RATIO": 0.10, "STOP_MA_PERIOD": 40, "STOP_DATA_FREQUENCY": "daily",
                 "TAKE_PROFIT_L1": 0.05, "TAKE_PROFIT_L2": 0.10,
                 "MIN_SCORE_B": 0.50, "MORNING_ENTRY_ENABLED": False,
                 "CONFIRM_STOP_BARS": 2, "MAX_DRAWDOWN": 0.08,
                 "BREAKEVEN_THRESHOLD": 0.01, "TRAILING_TAKE_PROFIT": False},
        "sideways": {**SIDEWAYS_DEFAULT, "TARGET_POS_RATIO": 0.30, "MAX_POSITIONS": 5},
    },
    {
        "label": "T2_balanced",
        "bear": {"MAX_POSITIONS": 2, "MAX_POSITIONS_DAILY": 1, "MAX_POS_RATIO": 0.20,
                 "TARGET_POS_RATIO": 0.15, "STOP_MA_PERIOD": 60, "STOP_DATA_FREQUENCY": "daily",
                 "TAKE_PROFIT_L1": 0.08, "TAKE_PROFIT_L2": 0.12,
                 "MIN_SCORE_B": 0.40, "MORNING_ENTRY_ENABLED": False,
                 "CONFIRM_STOP_BARS": 3, "MAX_DRAWDOWN": 0.10,
                 "BREAKEVEN_THRESHOLD": 0.01, "TRAILING_TAKE_PROFIT": False},
        "sideways": SIDEWAYS_DEFAULT,
    },
    {
        "label": "T3_ultra_def",
        "bear": {"MAX_POSITIONS": 1, "MAX_POSITIONS_DAILY": 0, "MAX_POS_RATIO": 0.10,
                 "TARGET_POS_RATIO": 0.0, "STOP_MA_PERIOD": 40, "STOP_DATA_FREQUENCY": "daily",
                 "TAKE_PROFIT_L1": 0.03, "TAKE_PROFIT_L2": 0.05,
                 "MIN_SCORE_B": 0.80, "MORNING_ENTRY_ENABLED": False,
                 "CONFIRM_STOP_BARS": 1, "MAX_DRAWDOWN": 0.05,
                 "BREAKEVEN_THRESHOLD": 0.005, "TRAILING_TAKE_PROFIT": False},
        "sideways": {**SIDEWAYS_DEFAULT, "TARGET_POS_RATIO": 0.20, "MAX_POSITIONS": 4},
    },
    {
        "label": "T4_moderate",
        "bear": {"MAX_POSITIONS": 3, "MAX_POSITIONS_DAILY": 1, "MAX_POS_RATIO": 0.30,
                 "TARGET_POS_RATIO": 0.20, "STOP_MA_PERIOD": 60, "STOP_DATA_FREQUENCY": "daily",
                 "TAKE_PROFIT_L1": 0.08, "TAKE_PROFIT_L2": 0.15,
                 "MIN_SCORE_B": 0.30, "MORNING_ENTRY_ENABLED": False,
                 "CONFIRM_STOP_BARS": 3, "MAX_DRAWDOWN": 0.12,
                 "BREAKEVEN_THRESHOLD": 0.02, "TRAILING_TAKE_PROFIT": False},
        "sideways": {**SIDEWAYS_DEFAULT, "TARGET_POS_RATIO": 0.50, "MAX_POSITIONS": 7},
    },
]

# Bull参数组合 (Stage B)
BULL_COMBOS = [
    {
        "label": "X1_default",
        "params": copy.deepcopy(BULL_DEFAULT),
    },
    {
        "label": "X2_aggr",
        "params": {**BULL_DEFAULT, "TARGET_POS_RATIO": 0.90, "MAX_POS_RATIO": 0.95},
    },
]


# ==================== 代码替换工具 ====================

def replace_regime_params(code, regime_params_dict):
    lines = code.split("\n")
    start_idx = None
    end_idx = None
    brace_count = 0

    for i, line in enumerate(lines):
        if "    REGIME_PARAMS = {" in line and start_idx is None:
            start_idx = i
            brace_count = line.count("{") - line.count("}")
        elif start_idx is not None:
            brace_count += line.count("{") - line.count("}")
            if brace_count <= 0:
                end_idx = i
                break

    if start_idx is None or end_idx is None:
        print("WARNING: REGIME_PARAMS not found in strategy code!")
        return code

    params_str = pprint.pformat(regime_params_dict, width=120, sort_dicts=False)
    new_lines = (
        lines[:start_idx]
        + ["    REGIME_PARAMS = " + params_str]
        + lines[end_idx + 1 :]
    )
    return "\n".join(new_lines)


def run_backtest(code, start_date, end_date, label=""):
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

    strategy_path = os.path.join(TEMP_DIR, "backtest.py")
    with open(strategy_path, "w", encoding="utf-8") as f:
        f.write(code)

    runner = BacktestRunner()
    config = BacktestConfig(
        strategy_name="temp_strategy",
        start_date=start_date,
        end_date=end_date,
        initial_capital=100000.0,
        frequency="1m",
        enable_logging=False,
        enable_charts=False,
        optimization_mode=True,
    )

    # 不静默运行，输出到日志文件
    with open(LOG_FILE, "a", encoding="utf-8") as log_f:
        log_f.write(f"\n--- [{label}] {start_date}~{end_date} {time.strftime('%H:%M:%S')} ---\n")
        log_f.flush()

        import io
        from contextlib import redirect_stderr

        old_stdout = sys.stdout
        sys.stdout = log_f
        try:
            with redirect_stderr(log_f):
                report = runner.run(config=config)
        except Exception as e:
            log_f.write(f"EXCEPTION: {e}\n")
            log_f.flush()
            sys.stdout = old_stdout
            return {"total_return": -1.0, "max_drawdown": 0.0, "sharpe_ratio": 0.0}
        finally:
            sys.stdout = old_stdout

        log_f.write(f"RESULT: total_return={report.get('total_return', -1) if report else 'None'}\n")
        log_f.flush()

    if not report:
        return {"total_return": -1.0, "max_drawdown": 0.0, "sharpe_ratio": 0.0}

    return {
        "total_return": report.get("total_return", -1.0),
        "max_drawdown": report.get("max_drawdown", 0.0),
        "sharpe_ratio": report.get("sharpe_ratio", 0.0),
    }


# ==================== 主流程 ====================

def main():
    sys.stdout.reconfigure(line_buffering=True)

    # 清空旧日志
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"优化日志 {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    with open(STRATEGY_PATH, "r", encoding="utf-8") as f:
        original_code = f.read()

    results = []
    total_start = time.time()

    # ==================== Stage A: 择时参数优化 ====================
    print("\n" + "=" * 70)
    print("Stage A: 择时参数优化 (bear+sideways联合, 2024+2025双周期)")
    print("=" * 70)

    best_combo = None
    best_combined = -999.0

    for combo in TIMING_COMBOS:
        label = combo["label"]
        bear_params = combo["bear"]
        sideways_params = combo["sideways"]

        regime_params = {
            "bull": copy.deepcopy(BULL_DEFAULT),
            "bear": bear_params,
            "sideways": sideways_params,
        }

        modified = replace_regime_params(original_code, regime_params)
        trial_start = time.time()

        # 双周期回测
        m2024 = run_backtest(modified, "2024-01-02", "2024-12-31", label)
        ret_2024 = m2024["total_return"]
        dd_2024 = m2024["max_drawdown"]
        sharpe_2024 = m2024["sharpe_ratio"]

        m2025 = run_backtest(modified, "2025-01-02", "2025-12-31", label)
        ret_2025 = m2025["total_return"]
        dd_2025 = m2025["max_drawdown"]
        sharpe_2025 = m2025["sharpe_ratio"]

        elapsed = time.time() - trial_start
        combined = ret_2024 + ret_2025
        pass_2024 = ret_2024 >= 0.30
        pass_2025 = ret_2025 >= 0.50
        full_pass = pass_2024 and pass_2025
        status = "PASS" if full_pass else "FAIL"

        print(f"\n  [{label}] 2024: {ret_2024*100:>6.1f}% (dd:{dd_2024*100:.1f}%) | 2025: {ret_2025*100:>6.1f}% (dd:{dd_2025*100:.1f}%) | 综合: {combined*100:.1f}% [{status}] ({elapsed/60:.0f}min)")
        print(f"    bear: TARGET={bear_params['TARGET_POS_RATIO']:.0%}, POS={bear_params['MAX_POSITIONS']}, STOP={bear_params['STOP_MA_PERIOD']}")
        print(f"    side: TARGET={sideways_params.get('TARGET_POS_RATIO', 0.4):.0%}, POS={sideways_params.get('MAX_POSITIONS', 6)}")

        result = {
            "label": label,
            "regime_params": regime_params,
            "ret_2024": ret_2024, "dd_2024": dd_2024, "sharpe_2024": sharpe_2024,
            "ret_2025": ret_2025, "dd_2025": dd_2025, "sharpe_2025": sharpe_2025,
            "combined": combined, "full_pass": full_pass,
        }
        results.append(result)

        if combined > best_combined:
            best_combined = combined
            best_combo = result

    # ==================== Stage B: Bull参数优化 ====================
    if best_combo:
        print("\n" + "=" * 70)
        print(f"Stage B: Bull参数优化 (bear/sideways固定为 {best_combo['label']})")
        print("=" * 70)

        best_overall = best_combo

        for combo in BULL_COMBOS:
            label = combo["label"]
            bull_params = combo["params"]

            regime_params = {
                "bull": bull_params,
                "bear": best_combo["regime_params"]["bear"],
                "sideways": best_combo["regime_params"]["sideways"],
            }

            modified = replace_regime_params(original_code, regime_params)
            trial_start = time.time()

            m2024 = run_backtest(modified, "2024-01-02", "2024-12-31", label)
            m2025 = run_backtest(modified, "2025-01-02", "2025-12-31", label)
            elapsed = time.time() - trial_start

            ret_2024 = m2024["total_return"]
            ret_2025 = m2025["total_return"]
            combined = ret_2024 + ret_2025
            full_pass = ret_2024 >= 0.30 and ret_2025 >= 0.50

            print(f"\n  [{label}] 2024: {ret_2024*100:>6.1f}% | 2025: {ret_2025*100:>6.1f}% | 综合: {combined*100:.1f}% [{'PASS' if full_pass else 'FAIL'}] ({elapsed:.0f}s)")
            print(f"    bull: POS={bull_params['MAX_POSITIONS']}, STOP={bull_params['STOP_MA_PERIOD']}, DD={bull_params['MAX_DRAWDOWN']}")

            result = {
                "label": f"{best_combo['label']}+{label}",
                "stage": "B",
                "regime_params": regime_params,
                "ret_2024": ret_2024,
                "ret_2025": ret_2025,
                "dd_2024": m2024["max_drawdown"],
                "dd_2025": m2025["max_drawdown"],
                "sharpe_2024": m2024["sharpe_ratio"],
                "sharpe_2025": m2025["sharpe_ratio"],
                "combined": combined,
                "full_pass": full_pass,
            }
            results.append(result)

            if combined > best_combined:
                best_combined = combined
                best_overall = result

    # ==================== 结果汇总 ====================
    total_elapsed = time.time() - total_start

    print("\n" + "=" * 70)
    print("参数优化结果汇总")
    print("=" * 70)
    print(f"{'标签':<25} {'2024收益':>10} {'2025收益':>10} {'2024回撤':>10} {'2025回撤':>10} {'综合':>8} {'状态':<10}")
    print("-" * 95)

    for r in results:
        ret24 = f"{r['ret_2024']*100:>8.1f}%"
        ret25 = f"{r.get('ret_2025', -1)*100:>8.1f}%" if r.get('ret_2025') is not None else "    —"
        dd24 = f"{r['dd_2024']*100:>8.1f}%"
        dd25 = f"{r.get('dd_2025', 0)*100:>8.1f}%" if r.get('dd_2025') is not None else "    —"
        combined = f"{r.get('combined', r['ret_2024'])*100:>6.1f}%"
        status = "PASS" if r.get("full_pass") else "FAIL"

        print(f"{r['label']:<25} {ret24} {ret25} {dd24} {dd25} {combined} {status:<10}")

    print("=" * 95)

    # 最佳组合
    passed = [r for r in results if r.get("full_pass")]
    if passed:
        best = max(passed, key=lambda r: r["combined"])
        print(f"\n最佳组合: {best['label']}")
        print(f"  2024: {best['ret_2024']*100:.1f}% (回撤{best['dd_2024']*100:.1f}%, 夏普{best['sharpe_2024']:.2f})")
        print(f"  2025: {best['ret_2025']*100:.1f}% (回撤{best['dd_2025']*100:.1f}%, 夏普{best['sharpe_2025']:.2f})")
        print(f"  综合收益: {best['combined']*100:.1f}%")
    else:
        # 找2024最好的
        with_2025 = [r for r in results if r.get("ret_2025") is not None]
        if with_2025:
            best = max(with_2025, key=lambda r: r.get("combined", r["ret_2024"]))
            print(f"\n未达标，最佳组合: {best['label']}")
            print(f"  2024: {best['ret_2024']*100:.1f}% | 2025: {best.get('ret_2025',0)*100:.1f}%")
        else:
            best_2024 = max(results, key=lambda r: r["ret_2024"])
            print(f"\n仅2024结果，最佳: {best_2024['label']} = {best_2024['ret_2024']*100:.1f}%")

    print(f"\n总耗时: {total_elapsed:.0f}s ({total_elapsed/3600:.1f}h)")

    # 保存报告
    _write_report(results, total_elapsed)
    print(f"报告已保存: {os.path.join(os.path.dirname(__file__), 'optimization_report.md')}")


def _write_report(results, total_elapsed):
    report_path = os.path.join(os.path.dirname(__file__), "optimization_report.md")

    passed = [r for r in results if r.get("full_pass")]

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# trends_up 参数优化报告 (Phase 2: 动态行情参数)\n\n")
        f.write(f"> 最后更新: {time.strftime('%Y-%m-%d %H:%M')}\n\n")

        f.write("## 目标\n\n")
        f.write("| 指标 | 约束 |\n|---|---|\n")
        f.write("| 2024全年收益 | >= 30% |\n")
        f.write("| 2025全年收益 | >= 50% |\n")
        f.write("| 初始资金 | 10万 |\n")
        f.write("| 频率 | 1m (分钟级) |\n")
        f.write("| 策略模式 | 动态行情参数切换 |\n\n")

        f.write("---\n\n## Phase 1 结果 (固定MAX_POSITIONS)\n\n")
        f.write("所有组合2024年亏损，FAIL。详见历史版本。\n\n")

        f.write("---\n\n## Phase 2: 动态行情参数切换\n\n")
        f.write("### 行情分布\n\n")
        f.write("| 年份 | bear | sideways | bull |\n|---|---|---|---|\n")
        f.write("| 2024 | 66天(27.3%) | 52天(21.5%) | 124天(51.2%) |\n")
        f.write("| 2025 | 0天 | 107天(44.0%) | 136天(56.0%) |\n\n")

        f.write("### 结果汇总\n\n")
        f.write(f"{'| 标签':<25} {'| 2024收益':>10} {'| 2025收益':>10} {'| 2024回撤':>10} {'| 2025回撤':>10} {'| 综合':>8} {'| 状态':<8}|\n")
        f.write("|---|---|---|---|---|---|---|\n")

        for r in results:
            ret24 = f"{r['ret_2024']*100:.1f}%"
            ret25 = f"{r.get('ret_2025', -1)*100:.1f}%" if r.get("ret_2025") is not None else "—"
            dd24 = f"{r['dd_2024']*100:.1f}%"
            dd25 = f"{r.get('dd_2025', 0)*100:.1f}%" if r.get("dd_2025") is not None else "—"
            combined = f"{r.get('combined', r['ret_2024'])*100:.1f}%"
            status = "PASS" if r.get("full_pass") else "FAIL"
            f.write(f"| {r['label']} | {ret24} | {ret25} | {dd24} | {dd25} | {combined} | {status} |\n")

        if passed:
            best = max(passed, key=lambda r: r["combined"])
            f.write(f"\n### 最佳参数组合\n\n")
            f.write(f"**{best['label']}**\n\n")
            f.write(f"- 2024: {best['ret_2024']*100:.1f}% (回撤{best['dd_2024']*100:.1f}%, 夏普{best['sharpe_2024']:.2f})\n")
            f.write(f"- 2025: {best['ret_2025']*100:.1f}% (回撤{best['dd_2025']*100:.1f}%, 夏普{best['sharpe_2025']:.2f})\n")
            f.write(f"- 综合收益: {best['combined']*100:.1f}%\n\n")

            f.write("```python\nREGIME_PARAMS = \n")
            f.write(pprint.pformat(best["regime_params"], width=120, sort_dicts=False))
            f.write("\n```\n")
        else:
            f.write("\n### 未达标\n\n")
            with_2025 = [r for r in results if r.get("ret_2025") is not None]
            if with_2025:
                best = max(with_2025, key=lambda r: r.get("combined", r["ret_2024"]))
                f.write(f"最接近组合: **{best['label']}**\n\n")
                f.write(f"- 2024: {best['ret_2024']*100:.1f}%\n")
                f.write(f"- 2025: {best.get('ret_2025',0)*100:.1f}%\n\n")

        f.write(f"\n---\n总耗时: {total_elapsed/3600:.1f}小时\n")


if __name__ == "__main__":
    main()

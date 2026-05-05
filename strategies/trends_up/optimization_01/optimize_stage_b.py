# -*- coding: utf-8 -*-
"""
Stage B: Bull参数 + 混合bear/sideways参数优化 (并行版)

Stage A 结果:
  T1_defensive: 2024=10.6%, 2025=78.6% (bear TARGET=10%, sideways TARGET=30%)
  T2_balanced:  2024=47.9%, 2025=18.3% (bear TARGET=15%, sideways TARGET=40%)
  T3_ultra_def: 2024=20.2%, 2025=15.0% (bear TARGET=0%, sideways TARGET=20%)
  T4_moderate:  pending

并行策略: 每个组合在独立进程中运行, 独立temp目录和日志文件
  - 4组合 × 2周期 = 8个回测任务
  - 4个并行worker (每个~160% CPU, 4×160%=640%, 18核足够)
  - 每个worker内串行跑2024+2025

运行方式:
  cd SimTradeLab
  SIMTRADELAB_DATA_PATH=../SimTradeData/data python3 strategies/trends_up/optimization/optimize_stage_b.py
"""

import os
import re
import sys
import time
import copy
import pprint
import json
from multiprocessing import Pool, Lock
from functools import partial

os.environ["SIMTRADELAB_DATA_PATH"] = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "SimTradeData", "data")
)

STRATEGY_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "backtest.py")
)
OPT_DIR = os.path.dirname(os.path.abspath(__file__))
NUM_WORKERS = 4

# ==================== 参数定义 ====================

BEAR_T1 = {"MAX_POSITIONS": 2, "MAX_POSITIONS_DAILY": 1, "MAX_POS_RATIO": 0.20,
           "TARGET_POS_RATIO": 0.10, "STOP_MA_PERIOD": 40, "STOP_DATA_FREQUENCY": "daily",
           "TAKE_PROFIT_L1": 0.05, "TAKE_PROFIT_L2": 0.10,
           "MIN_SCORE_B": 0.50, "MORNING_ENTRY_ENABLED": False,
           "CONFIRM_STOP_BARS": 2, "MAX_DRAWDOWN": 0.08,
           "BREAKEVEN_THRESHOLD": 0.01, "TRAILING_TAKE_PROFIT": False}

BEAR_T2 = {"MAX_POSITIONS": 2, "MAX_POSITIONS_DAILY": 1, "MAX_POS_RATIO": 0.20,
           "TARGET_POS_RATIO": 0.15, "STOP_MA_PERIOD": 60, "STOP_DATA_FREQUENCY": "daily",
           "TAKE_PROFIT_L1": 0.08, "TAKE_PROFIT_L2": 0.12,
           "MIN_SCORE_B": 0.40, "MORNING_ENTRY_ENABLED": False,
           "CONFIRM_STOP_BARS": 3, "MAX_DRAWDOWN": 0.10,
           "BREAKEVEN_THRESHOLD": 0.01, "TRAILING_TAKE_PROFIT": False}

SIDEWAYS_T1 = {"MAX_POSITIONS": 5, "MAX_POSITIONS_DAILY": 3, "MAX_POS_RATIO": 0.60,
               "TARGET_POS_RATIO": 0.30, "STOP_MA_PERIOD": 60, "STOP_DATA_FREQUENCY": "daily",
               "TAKE_PROFIT_L1": 0.10, "TAKE_PROFIT_L2": 0.20,
               "MIN_SCORE_B": 0.30, "MORNING_ENTRY_ENABLED": True,
               "CONFIRM_STOP_BARS": 3, "MAX_DRAWDOWN": 0.12,
               "BREAKEVEN_THRESHOLD": 0.02, "TRAILING_TAKE_PROFIT": False}

SIDEWAYS_T2 = {"MAX_POSITIONS": 6, "MAX_POSITIONS_DAILY": 3, "MAX_POS_RATIO": 0.60,
               "TARGET_POS_RATIO": 0.40, "STOP_MA_PERIOD": 60, "STOP_DATA_FREQUENCY": "daily",
               "TAKE_PROFIT_L1": 0.10, "TAKE_PROFIT_L2": 0.20,
               "MIN_SCORE_B": 0.30, "MORNING_ENTRY_ENABLED": True,
               "CONFIRM_STOP_BARS": 3, "MAX_DRAWDOWN": 0.12,
               "BREAKEVEN_THRESHOLD": 0.02, "TRAILING_TAKE_PROFIT": False}

BULL_BASE = {
    "MAX_POSITIONS": 9, "MAX_POSITIONS_DAILY": 4, "MAX_POS_RATIO": 0.90,
    "TARGET_POS_RATIO": 0.80, "STOP_MA_PERIOD": 120, "STOP_DATA_FREQUENCY": "daily",
    "TAKE_PROFIT_L1": 9.99, "TAKE_PROFIT_L2": 9.99,
    "MIN_SCORE_B": 0.20, "MORNING_ENTRY_ENABLED": True,
    "CONFIRM_STOP_BARS": 5, "MAX_DRAWDOWN": 0.20,
    "BREAKEVEN_THRESHOLD": 0.03, "TRAILING_TAKE_PROFIT": True,
}

BEAR_T5 = {**BEAR_T2, "TARGET_POS_RATIO": 0.12, "STOP_MA_PERIOD": 50, "MAX_DRAWDOWN": 0.09}
SIDEWAYS_T5 = {**SIDEWAYS_T2, "TARGET_POS_RATIO": 0.35, "MAX_POSITIONS": 5}

BULL_COMBOS = [
    {"label": "X3_fast_entry", "params": {**BULL_BASE, "CONFIRM_STOP_BARS": 3, "MIN_SCORE_B": 0.10}},
    {"label": "X5_fast_notp", "params": {**BULL_BASE, "CONFIRM_STOP_BARS": 3, "MIN_SCORE_B": 0.10, "TRAILING_TAKE_PROFIT": False}},
]

MIX_COMBOS = [
    {"label": "M1_T1bear_T1side", "bear": BEAR_T1, "sideways": SIDEWAYS_T1},
    {"label": "M4_T5bear_T5side", "bear": BEAR_T5, "sideways": SIDEWAYS_T5},
]

# 生成所有组合
ALL_COMBOS = []
for mix in MIX_COMBOS:
    for bull in BULL_COMBOS:
        ALL_COMBOS.append({
            "label": f"{mix['label']}+{bull['label']}",
            "bear": mix["bear"],
            "sideways": mix["sideways"],
            "bull": bull["params"],
        })


def replace_regime_params(code, regime_params_dict):
    import pprint as _pp
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
        return code

    params_str = _pp.pformat(regime_params_dict, width=120, sort_dicts=False)
    new_lines = lines[:start_idx] + ["    REGIME_PARAMS = " + params_str] + lines[end_idx + 1:]
    return "\n".join(new_lines)


def run_backtest(code, start_date, end_date, label, worker_id):
    """独立进程内的回测函数, 使用独立temp目录和日志"""
    from simtradelab.backtest.runner import BacktestRunner
    from simtradelab.backtest.config import BacktestConfig

    temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", f"temp_strategy_w{worker_id}")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    strategy_path = os.path.join(temp_dir, "backtest.py")
    with open(strategy_path, "w", encoding="utf-8") as f:
        f.write(code)

    log_file = os.path.join(OPT_DIR, f"stage_b_worker_{worker_id}.log")

    runner = BacktestRunner()
    config = BacktestConfig(
        strategy_name=f"temp_strategy_w{worker_id}",
        start_date=start_date,
        end_date=end_date,
        initial_capital=100000.0,
        frequency="1m",
        enable_logging=False,
        enable_charts=False,
        optimization_mode=True,
    )

    with open(log_file, "a", encoding="utf-8") as log_f:
        log_f.write(f"\n--- [{label}] {start_date}~{end_date} {time.strftime('%H:%M:%S')} ---\n")
        log_f.flush()

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


def run_combo(args):
    """Worker函数: 一个组合(2024+2025)在一个进程内串行执行"""
    combo_idx, combo = args
    worker_id = combo_idx % NUM_WORKERS

    with open(STRATEGY_PATH, "r", encoding="utf-8") as f:
        original_code = f.read()

    label = combo["label"]
    regime_params = {
        "bull": combo["bull"],
        "bear": combo["bear"],
        "sideways": combo["sideways"],
    }
    modified = replace_regime_params(original_code, regime_params)

    status_file = os.path.join(OPT_DIR, f"stage_b_status_{combo_idx}.txt")
    result_file = os.path.join(OPT_DIR, f"stage_b_result_{combo_idx}.json")

    with open(status_file, "w") as f:
        f.write(f"RUNNING {label} 2024... (worker {worker_id})\n")

    m2024 = run_backtest(modified, "2024-01-02", "2024-12-31", label + "_2024", worker_id)

    with open(status_file, "a") as f:
        f.write(f"RUNNING {label} 2025... (2024={m2024['total_return']*100:.1f}%)\n")

    m2025 = run_backtest(modified, "2025-01-02", "2025-12-31", label + "_2025", worker_id)

    ret_2024 = m2024["total_return"]
    ret_2025 = m2025["total_return"]
    combined = ret_2024 + ret_2025
    full_pass = ret_2024 >= 0.30 and ret_2025 >= 0.50

    result = {
        "label": label,
        "ret_2024": ret_2024, "ret_2025": ret_2025,
        "dd_2024": m2024["max_drawdown"], "dd_2025": m2025["max_drawdown"],
        "sharpe_2024": m2024["sharpe_ratio"], "sharpe_2025": m2025["sharpe_ratio"],
        "combined": combined, "full_pass": full_pass,
        "worker_id": worker_id,
    }

    with open(result_file, "w") as f:
        json.dump(result, f, indent=2)

    status = "PASS" if full_pass else "FAIL"
    with open(status_file, "w") as f:
        f.write(f"DONE {label}: 2024={ret_2024*100:.1f}% 2025={ret_2025*100:.1f}% combined={combined*100:.1f}% [{status}]\n")

    return result


def main():
    print(f"Stage B 并行优化: {len(ALL_COMBOS)} 组合, {NUM_WORKERS} workers")
    print(f"预计耗时: ~{120/NUM_WORKERS:.0f}分钟 (并行) vs ~{len(ALL_COMBOS)*120/60:.0f}小时 (串行)")
    print()

    total_start = time.time()

    # 清理旧状态文件
    for i in range(len(ALL_COMBOS)):
        for suffix in [f"stage_b_status_{i}.txt", f"stage_b_result_{i}.json"]:
            p = os.path.join(OPT_DIR, suffix)
            if os.path.exists(p):
                os.remove(p)
        log_file = os.path.join(OPT_DIR, f"stage_b_worker_{i % NUM_WORKERS}.log")
        if os.path.exists(log_file):
            open(log_file, "w").close()

    # 并行执行
    with Pool(processes=NUM_WORKERS) as pool:
        results = pool.map(run_combo, enumerate(ALL_COMBOS))

    total_elapsed = time.time() - total_start

    # ==================== 结果汇总 ====================
    print("\n" + "=" * 100)
    print("Stage B 结果汇总")
    print("=" * 100)
    print(f"{'标签':<35} {'2024收益':>10} {'2025收益':>10} {'2024回撤':>10} {'2025回撤':>10} {'综合':>8} {'状态':<8}")
    print("-" * 100)

    for r in sorted(results, key=lambda x: x["combined"], reverse=True):
        ret24 = f"{r['ret_2024']*100:>8.1f}%"
        ret25 = f"{r['ret_2025']*100:>8.1f}%"
        dd24 = f"{r['dd_2024']*100:>8.1f}%"
        dd25 = f"{r['dd_2025']*100:>8.1f}%"
        combined = f"{r['combined']*100:>6.1f}%"
        status = "PASS" if r["full_pass"] else "FAIL"
        print(f"{r['label']:<35} {ret24} {ret25} {dd24} {dd25} {combined} {status}")

    print("=" * 100)

    passed = [r for r in results if r["full_pass"]]
    if passed:
        best = max(passed, key=lambda r: r["combined"])
        print(f"\n*** 达标组合: {best['label']} ***")
        print(f"  2024: {best['ret_2024']*100:.1f}% (回撤{best['dd_2024']*100:.1f}%, 夏普{best['sharpe_2024']:.2f})")
        print(f"  2025: {best['ret_2025']*100:.1f}% (回撤{best['dd_2025']*100:.1f}%, 夏普{best['sharpe_2025']:.2f})")
    else:
        best = max(results, key=lambda r: r["combined"])
        print(f"\n未达标，最佳组合: {best['label']}")
        print(f"  2024: {best['ret_2024']*100:.1f}% | 2025: {best['ret_2025']*100:.1f}%")

    print(f"\n总耗时: {total_elapsed:.0f}s ({total_elapsed/60:.0f}min)")
    print(f"加速比: {len(ALL_COMBOS)*120/60/(total_elapsed/3600):.1f}x (vs 串行)")


if __name__ == "__main__":
    main()

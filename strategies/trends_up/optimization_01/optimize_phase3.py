# -*- coding: utf-8 -*-
"""
Phase 3: 参数优化脚本 v3 (4进程并行版)

直接修改 calc_target_ratio 函数参数, 跳过已完成的combo。

运行方式:
  cd SimTradeLab
  SIMTRADELAB_DATA_PATH=../SimTradeData/data python3 strategies/trends_up/optimization/optimize_phase3.py
"""

import os
import re
import sys
import time
import json
import gc
from multiprocessing import Pool

os.environ["SIMTRADELAB_DATA_PATH"] = "/Users/jackie.liu/SynologyDrive/PtradeProjects/SimTradeData/data"

STRATEGY_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "backtest.py")
)
OPT_DIR = os.path.dirname(os.path.abspath(__file__))
NUM_WORKERS = 4

# ==================== 参数搜索空间 ====================

EARLY_BEAR_BASES = [0.15, 0.20, 0.25, 0.30]
BEAR_FLOORS = [0.10, 0.15, 0.20]
SIDEWAYS_BASES = [0.25, 0.30, 0.35]
CONFIRM_DAYS = [1, 2, 3]


def generate_combos():
    combos = []
    for eb_base in EARLY_BEAR_BASES:
        for b_floor in BEAR_FLOORS:
            combos.append({
                "label": f"EB{eb_base}_BF{b_floor}",
                "search_type": "defense_floor",
                "early_bear_base": eb_base,
                "bear_floor": b_floor,
            })
    for sw_base in SIDEWAYS_BASES:
        combos.append({
            "label": f"SW{sw_base}",
            "search_type": "sideways_base",
            "sideways_base": sw_base,
        })
    for cd in CONFIRM_DAYS:
        if cd == 2:
            continue
        combos.append({
            "label": f"CD{cd}",
            "search_type": "confirm_days",
            "confirm_days": cd,
        })
    return combos


def modify_calc_target_ratio(code, early_bear_base=None, bear_floor=None, sideways_base=None):
    if early_bear_base is not None:
        code = re.sub(
            r'elif score >= 5:\s+return 0\.\d+ \+ \(score - 5\) \* 0\.\d+',
            f'elif score >= 5:\n                return {early_bear_base} + (score - 5) * 0.010',
            code
        )
    if bear_floor is not None:
        code = re.sub(
            r'return max\(0\.\d+, score \* 0\.\d+\)',
            f'return max({bear_floor}, score * 0.01)',
            code
        )
    if sideways_base is not None:
        code = re.sub(
            r'elif score >= 20:\s+return 0\.\d+ \+ \(score - 20\) \* 0\.\d+',
            f'elif score >= 20:\n                return {sideways_base} + (score - 20) * 0.010',
            code
        )
    return code


def modify_confirm_days(code, days):
    old_confirm = """            prev_regime = getattr(g, "_current_regime", "sideways")
            pending = getattr(g, "_pending_regime", None)
            if regime != prev_regime:
                if pending == regime:
                    return regime  # 2nd day confirmed
                else:
                    g._pending_regime = regime
                    return prev_regime  # 1st day, don't switch
            else:
                g._pending_regime = None
                return regime"""
    if days == 1:
        new_confirm = """            return regime"""
    elif days == 2:
        return code
    elif days == 3:
        new_confirm = """            prev_regime = getattr(g, "_current_regime", "sideways")
            pending = getattr(g, "_pending_regime", None)
            pending_count = getattr(g, "_pending_count", 0)
            if regime != prev_regime:
                if pending == regime:
                    pending_count += 1
                    if pending_count >= 2:
                        g._pending_count = 0
                        return regime
                    else:
                        g._pending_regime = regime
                        g._pending_count = pending_count
                        return prev_regime
                else:
                    g._pending_regime = regime
                    g._pending_count = 0
                    return prev_regime
            else:
                g._pending_regime = None
                g._pending_count = 0
                return regime"""
    else:
        return code
    code = code.replace(old_confirm, new_confirm)
    return code


def modify_code(original_code, combo):
    code = original_code
    if combo["search_type"] == "defense_floor":
        code = modify_calc_target_ratio(code, early_bear_base=combo.get("early_bear_base"), bear_floor=combo.get("bear_floor"))
    elif combo["search_type"] == "sideways_base":
        code = modify_calc_target_ratio(code, sideways_base=combo.get("sideways_base"))
    elif combo["search_type"] == "confirm_days":
        code = modify_confirm_days(code, combo["confirm_days"])
    return code


def run_backtest(code, start_date, end_date, label, worker_id):
    from simtradelab.backtest.runner import BacktestRunner
    from simtradelab.backtest.config import BacktestConfig

    temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", f"temp_strategy_w{worker_id}")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    strategy_path = os.path.join(temp_dir, "backtest.py")
    with open(strategy_path, "w", encoding="utf-8") as f:
        f.write(code)

    log_file = os.path.join(OPT_DIR, f"phase3_worker_{worker_id}.log")

    runner = BacktestRunner()
    config = BacktestConfig(
        strategy_name=f"temp_strategy_w{worker_id}",
        start_date=start_date,
        end_date=end_date,
        initial_capital=1000000.0,
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

        ret = report.get("total_return", -1) if report else -1
        log_f.write(f"RESULT: total_return={ret}\n")
        log_f.flush()

    if not report:
        return {"total_return": -1.0, "max_drawdown": 0.0, "sharpe_ratio": 0.0}

    return {
        "total_return": float(report.get("total_return", -1.0)),
        "max_drawdown": float(report.get("max_drawdown", 0.0)),
        "sharpe_ratio": float(report.get("sharpe_ratio", 0.0)),
    }


def run_combo(args):
    combo_idx, combo = args
    worker_id = combo_idx % NUM_WORKERS

    with open(STRATEGY_PATH, "r", encoding="utf-8") as f:
        original_code = f.read()

    label = combo["label"]
    modified = modify_code(original_code, combo)

    if modified == original_code:
        return {
            "label": label, "error": "代码未变化",
            "ret_2024": -1.0, "ret_2025": -1.0, "combined": -2.0,
            "full_pass": False,
        }

    status_file = os.path.join(OPT_DIR, f"phase3_status_{combo_idx}.txt")

    with open(status_file, "w") as f:
        f.write(f"RUNNING {label} 2024... (worker {worker_id})\n")

    m2024 = run_backtest(modified, "2024-01-02", "2024-12-31", label + "_2024", worker_id)

    if m2024["total_return"] < 0.15:
        result = {
            "label": label, "params": combo,
            "ret_2024": m2024["total_return"], "ret_2025": -1.0,
            "dd_2024": m2024["max_drawdown"], "dd_2025": 0.0,
            "sharpe_2024": m2024["sharpe_ratio"], "sharpe_2025": 0.0,
            "combined": m2024["total_return"], "full_pass": False,
            "early_stop": True, "reason": f"2024={m2024['total_return']*100:.1f}% < 15%",
        }
        result_file = os.path.join(OPT_DIR, f"phase3_result_{combo_idx}.json")
        with open(result_file, "w") as f:
            json.dump(result, f, indent=2, default=str)
        with open(status_file, "w") as f:
            f.write(f"SKIP {label}: 2024={m2024['total_return']*100:.1f}% (< 15%, early stop)\n")
        gc.collect()
        return result

    with open(status_file, "a") as f:
        f.write(f"RUNNING {label} 2025... (2024={m2024['total_return']*100:.1f}%, worker {worker_id})\n")

    m2025 = run_backtest(modified, "2025-01-02", "2025-12-31", label + "_2025", worker_id)

    ret_2024 = m2024["total_return"]
    ret_2025 = m2025["total_return"]
    combined = ret_2024 + ret_2025
    full_pass = ret_2024 >= 0.30 and ret_2025 >= 0.50

    result = {
        "label": label, "params": combo,
        "ret_2024": ret_2024, "ret_2025": ret_2025,
        "dd_2024": m2024["max_drawdown"], "dd_2025": m2025["max_drawdown"],
        "sharpe_2024": m2024["sharpe_ratio"], "sharpe_2025": m2025["sharpe_ratio"],
        "combined": combined, "full_pass": bool(full_pass),
    }

    result_file = os.path.join(OPT_DIR, f"phase3_result_{combo_idx}.json")
    with open(result_file, "w") as f:
        json.dump(result, f, indent=2, default=str)

    status = "PASS" if full_pass else "FAIL"
    with open(status_file, "w") as f:
        f.write(f"DONE {label}: 2024={ret_2024*100:.1f}% 2025={ret_2025*100:.1f}% combined={combined*100:.1f}% [{status}]\n")

    gc.collect()
    return result


def find_completed_combos(num_combos):
    """检查哪些combo已有完成的结果(跳过已完成的)"""
    skip = set()
    for i in range(num_combos):
        result_file = os.path.join(OPT_DIR, f"phase3_result_{i}.json")
        if os.path.exists(result_file):
            try:
                with open(result_file) as f:
                    d = json.load(f)
                if "error" not in d and d.get("ret_2024", -1) >= 0:
                    skip.add(i)
                    print(f"  跳过已完成的 combo {i}: {d['label']}")
            except Exception:
                pass
    return skip


def main():
    combos = generate_combos()
    print(f"Phase 3 v3 参数优化: {len(combos)} 组合, {NUM_WORKERS} workers")
    print(f"搜索空间: defense_floor={len(EARLY_BEAR_BASES)*len(BEAR_FLOORS)}, "
          f"sideways_base={len(SIDEWAYS_BASES)}, confirm_days={len(CONFIRM_DAYS)-1}")
    print()

    # 清理旧worker日志
    for i in range(NUM_WORKERS):
        log_file = os.path.join(OPT_DIR, f"phase3_worker_{i}.log")
        if os.path.exists(log_file):
            open(log_file, "w").close()

    # 检查已完成的combo
    skip = find_completed_combos(len(combos))
    remaining = [(i, combos[i]) for i in range(len(combos)) if i not in skip]
    print(f"\n已完成: {len(skip)}, 剩余: {len(remaining)}")
    print()

    if not remaining:
        print("所有组合已完成!")
        return

    total_start = time.time()

    with Pool(processes=NUM_WORKERS) as pool:
        results = pool.map(run_combo, remaining)

    total_elapsed = time.time() - total_start

    # 合并已有结果
    all_results = []
    for i in range(len(combos)):
        result_file = os.path.join(OPT_DIR, f"phase3_result_{i}.json")
        if os.path.exists(result_file):
            try:
                with open(result_file) as f:
                    all_results.append(json.load(f))
            except Exception:
                pass
        else:
            matched = [r for r in results if r.get("label") == combos[i]["label"]]
            if matched:
                all_results.append(matched[0])

    # ==================== 结果汇总 ====================
    print("\n" + "=" * 100)
    print("Phase 3 v3 结果汇总")
    print("=" * 100)
    print(f"{'标签':<20} {'2024收益':>10} {'2025收益':>10} {'2024回撤':>10} {'2025回撤':>10} {'综合':>8} {'状态':<6}")
    print("-" * 100)

    for r in sorted(all_results, key=lambda x: x.get("combined", -999), reverse=True):
        if "error" in r:
            print(f"{r['label']:<20} ERROR: {r['error']}")
            continue
        ret24 = f"{r['ret_2024']*100:>8.1f}%" if r.get("ret_2024", -1) >= 0 else "   SKIP"
        ret25 = f"{r['ret_2025']*100:>8.1f}%" if r.get("ret_2025", -1) >= 0 else "   SKIP"
        dd24 = f"{r['dd_2024']*100:>8.1f}%" if r.get("dd_2024") else "     N/A"
        dd25 = f"{r['dd_2025']*100:>8.1f}%" if r.get("dd_2025") else "     N/A"
        combined = f"{r['combined']*100:>6.1f}%"
        status = "PASS" if r.get("full_pass") else "FAIL"
        early = " [EARLY_STOP]" if r.get("early_stop") else ""
        print(f"{r['label']:<20} {ret24} {ret25} {dd24} {dd25} {combined} {status}{early}")

    print("=" * 100)

    passed = [r for r in all_results if r.get("full_pass")]
    if passed:
        best = max(passed, key=lambda r: r["combined"])
        print(f"\n*** 达标组合: {best['label']} ***")
        print(f"  2024: {best['ret_2024']*100:.1f}% (回撤{best['dd_2024']*100:.1f}%, 夏普{best['sharpe_2024']:.2f})")
        print(f"  2025: {best['ret_2025']*100:.1f}% (回撤{best['dd_2025']*100:.1f}%, 夏普{best['sharpe_2025']:.2f})")
        print(f"  参数: {json.dumps(best.get('params', {}), indent=2)}")
    else:
        best = max(all_results, key=lambda r: r.get("combined", -999))
        print(f"\n未达标，最佳组合: {best['label']}")
        print(f"  2024: {best.get('ret_2024', -1)*100:.1f}% | 2025: {best.get('ret_2025', -1)*100:.1f}%")
        print(f"  参数: {json.dumps(best.get('params', {}), indent=2)}")

    print(f"\n本轮耗时: {total_elapsed:.0f}s ({total_elapsed/60:.0f}min)")

    summary_file = os.path.join(OPT_DIR, "phase3_summary.json")
    with open(summary_file, "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_combos": len(combos),
            "completed": len(skip) + len(results),
            "elapsed_seconds": total_elapsed,
            "results": all_results,
        }, f, indent=2, default=str)
    print(f"汇总已保存: {summary_file}")


if __name__ == "__main__":
    main()

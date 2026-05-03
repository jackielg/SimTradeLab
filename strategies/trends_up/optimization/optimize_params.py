# -*- coding: utf-8 -*-
"""
trends_up 策略参数优化（基于本地回测框架）

评估周期: 2024全年 + 2025全年 (分钟级频率)
参数空间: MAX_POSITIONS = [5, 6, 7, 8]
初始资金: 10万
约束: 2024 >= 30%, 2025 >= 50%
目标: 最大化综合收益率

运行方式:
  cd SimTradeLab
  SIMTRADELAB_DATA_PATH=../SimTradeData/data python3 strategies/trends_up/optimization/optimize_params.py

注意事项:
  - 单次全年回测约需 55~60 分钟，全量优化约 7~8 小时
  - 框架使用 DataServer 单例 + BacktestRunner 单实例复用数据缓存
  - 已修复框架两个 bug:
    1. StrategyOptimizer 缺少 frequency 参数传递给 BacktestConfig
    2. _execute_lifecycle 中 data.current_dt 应为 data.current_date
"""

import os
import sys
import time

os.environ["SIMTRADELAB_DATA_PATH"] = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "SimTradeData", "data")
)

from simtradelab.backtest.optimizer_framework import (
    ParameterSpace,
    ScoringStrategy,
    StrategyOptimizer,
)


# ==================== 参数空间定义 ====================

class TrendsUpParamSpace(ParameterSpace):
    MAX_POSITIONS = [5, 6, 7, 8]


class MaxReturnScoring(ScoringStrategy):
    @staticmethod
    def calculate_score(metrics):
        return metrics.get("total_return", 0.0)


# ==================== 主函数 ====================

def main():
    sys.stdout.reconfigure(line_buffering=True)

    strategy_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "backtest.py")
    )

    optimizer = StrategyOptimizer(
        strategy_path=strategy_path,
        parameter_space=TrendsUpParamSpace(),
        scoring_strategy=MaxReturnScoring(),
        start_date="2024-01-02",
        end_date="2025-12-31",
        initial_capital=100000.0,
        custom_mapping={"MAX_POSITIONS": "MAX_POSITIONS"},
        use_walk_forward=False,
        frequency="1m",
        verbose=False,
    )

    results = []
    total_start = time.time()

    def objective(trial):
        params = TrendsUpParamSpace.suggest_parameters(trial)
        mp = params["MAX_POSITIONS"]
        trial_start = time.time()

        print("\n" + "=" * 60)
        print("Trial {}: MAX_POSITIONS = {}".format(trial.number + 1, mp))

        # 2024 全年回测
        _, m2024 = optimizer.run_backtest_with_params(
            params, "2024-01-02", "2024-12-31"
        )
        ret_2024 = m2024.get("total_return", -1.0)
        dd_2024 = m2024.get("max_drawdown", 0.0)
        sharpe_2024 = m2024.get("sharpe_ratio", 0.0)

        # 2025 全年回测
        _, m2025 = optimizer.run_backtest_with_params(
            params, "2025-01-02", "2025-12-31"
        )
        ret_2025 = m2025.get("total_return", -1.0)
        dd_2025 = m2025.get("max_drawdown", 0.0)
        sharpe_2025 = m2025.get("sharpe_ratio", 0.0)

        elapsed = time.time() - trial_start

        pass_2024 = ret_2024 >= 0.30
        pass_2025 = ret_2025 >= 0.50
        status = "PASS" if (pass_2024 and pass_2025) else "FAIL"

        print(
            "  2024: {:>6.1f}% (dd:{:.1f}%, sharpe:{:.2f}) {}".format(
                ret_2024 * 100, dd_2024 * 100, sharpe_2024,
                "" if pass_2024 else "[<30%]"
            )
        )
        print(
            "  2025: {:>6.1f}% (dd:{:.1f}%, sharpe:{:.2f}) {}".format(
                ret_2025 * 100, dd_2025 * 100, sharpe_2025,
                "" if pass_2025 else "[<50%]"
            )
        )
        print("  Status: {} | {:.0f}s".format(status, elapsed))

        results.append({
            "MAX_POSITIONS": mp,
            "ret_2024": ret_2024,
            "ret_2025": ret_2025,
            "dd_2024": dd_2024,
            "dd_2025": dd_2025,
            "sharpe_2024": sharpe_2024,
            "sharpe_2025": sharpe_2025,
            "pass": pass_2024 and pass_2025,
        })

        # 约束不满足时给惩罚分
        if not (pass_2024 and pass_2025):
            penalty = 0.0
            if not pass_2024:
                penalty += (0.30 - ret_2024)
            if not pass_2025:
                penalty += (0.50 - ret_2025)
            return -penalty

        return ret_2024 + ret_2025

    # 执行优化（4个候选值 = 4个trial）
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=4, show_progress_bar=False)

    # ==================== 结果汇总 ====================
    total_elapsed = time.time() - total_start
    print("\n" + "=" * 70)
    print("参数优化结果汇总")
    print("=" * 70)
    print(
        "{:<15} {:>10} {:>10} {:>10} {:>10} {:>10} {:>8}".format(
            "MAX_POSITIONS", "2024收益", "2025收益", "2024回撤", "2025回撤", "综合收益", "状态"
        )
    )
    print("-" * 73)

    best_combo = None
    best_score = -float("inf")
    for r in sorted(results, key=lambda x: x["MAX_POSITIONS"]):
        status_str = "PASS" if r["pass"] else "FAIL"
        combined = r["ret_2024"] + r["ret_2025"]
        print(
            "{:<15} {:>9.1f}% {:>9.1f}% {:>9.1f}% {:>9.1f}% {:>9.1f}% {:>8}".format(
                r["MAX_POSITIONS"],
                r["ret_2024"] * 100,
                r["ret_2025"] * 100,
                r["dd_2024"] * 100,
                r["dd_2025"] * 100,
                combined * 100,
                status_str,
            )
        )
        if r["pass"]:
            combined = r["ret_2024"] + r["ret_2025"]
            if combined > best_score:
                best_score = combined
                best_combo = r

    print("=" * 73)

    if best_combo:
        print(
            "\n最佳参数: MAX_POSITIONS = {}".format(best_combo["MAX_POSITIONS"])
        )
        print(
            "  2024: {:.1f}% (回撤{:.1f}%, 夏普{:.2f})".format(
                best_combo["ret_2024"] * 100,
                best_combo["dd_2024"] * 100,
                best_combo["sharpe_2024"],
            )
        )
        print(
            "  2025: {:.1f}% (回撤{:.1f}%, 夏普{:.2f})".format(
                best_combo["ret_2025"] * 100,
                best_combo["dd_2025"] * 100,
                best_combo["sharpe_2025"],
            )
        )
        print(
            "  综合收益: {:.1f}%".format(
                (best_combo["ret_2024"] + best_combo["ret_2025"]) * 100
            )
        )
    else:
        print("\n未找到满足约束的参数组合 (需要2024>=30%, 2025>=50%)")
        # 找出最接近的组合
        best_near = max(results, key=lambda r: r["ret_2025"])
        print("最接近的组合: MAX_POSITIONS = {}".format(best_near["MAX_POSITIONS"]))
        print("  2024: {:.1f}%, 2025: {:.1f}%".format(
            best_near["ret_2024"] * 100, best_near["ret_2025"] * 100
        ))
        print("建议放宽约束条件或调整参数范围")

    print("总耗时: {:.0f}s ({:.1f}h)".format(total_elapsed, total_elapsed / 3600))

    # ==================== 生成报告 ====================
    _write_report(results, best_combo, total_elapsed)
    print("报告已保存: {}".format(os.path.join(os.path.dirname(__file__), "optimization_report.md")))


def _write_report(results, best_combo, total_elapsed):
    report_path = os.path.join(os.path.dirname(__file__), "optimization_report.md")

    commit_info = ""
    try:
        import subprocess
        commit_info = subprocess.check_output(
            ["git", "log", "-1", "--format=%h %s"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        pass

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# trends_up 参数优化报告\n\n")
        if commit_info:
            f.write("策略版本: `{}`\n\n".format(commit_info))
        f.write("## 优化配置\n\n")
        f.write("| 配置项 | 值 |\n|---|---|\n")
        f.write("| 参数空间 | MAX_POSITIONS = {} |\n".format([5, 6, 7, 8]))
        f.write("| 初始资金 | 100000 |\n")
        f.write("| 频率 | 1m (分钟级) |\n")
        f.write("| 评估周期 | 2024全年 + 2025全年 |\n")
        f.write("| 约束条件 | 2024>=30%, 2025>=50% |\n")
        f.write("| 框架 | SimTradeLab StrategyOptimizer (optuna) |\n")
        f.write("| 运行日期 | {} |\n\n".format(time.strftime("%Y-%m-%d %H:%M")))

        f.write("## 结果汇总\n\n")
        f.write("| MAX_POSITIONS | 2024收益 | 2025收益 | 2024回撤 | 2025回撤 | 2024夏普 | 2025夏普 | 综合收益 | 状态 |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        for r in sorted(results, key=lambda x: x["MAX_POSITIONS"]):
            combined = r["ret_2024"] + r["ret_2025"]
            status_str = "PASS" if r["pass"] else "FAIL"
            f.write(
                "| {} | {:.1f}% | {:.1f}% | {:.1f}% | {:.1f}% | {:.2f} | {:.2f} | {:.1f}% | {} |\n".format(
                    r["MAX_POSITIONS"],
                    r["ret_2024"] * 100, r["ret_2025"] * 100,
                    r["dd_2024"] * 100, r["dd_2025"] * 100,
                    r["sharpe_2024"], r["sharpe_2025"],
                    combined * 100, status_str,
                )
            )

        f.write("\n## 最佳参数\n\n")
        if best_combo:
            f.write("**MAX_POSITIONS = {}**\n\n".format(best_combo["MAX_POSITIONS"]))
            f.write("- 2024: {:.1f}% (回撤{:.1f}%, 夏普{:.2f})\n".format(
                best_combo["ret_2024"] * 100,
                best_combo["dd_2024"] * 100,
                best_combo["sharpe_2024"],
            ))
            f.write("- 2025: {:.1f}% (回撤{:.1f}%, 夏普{:.2f})\n".format(
                best_combo["ret_2025"] * 100,
                best_combo["dd_2025"] * 100,
                best_combo["sharpe_2025"],
            ))
            combined = best_combo["ret_2024"] + best_combo["ret_2025"]
            f.write("- 综合收益: {:.1f}%\n".format(combined * 100))
        else:
            f.write("未找到满足约束的参数组合\n")
            best_near = max(results, key=lambda r: r["ret_2025"])
            f.write("\n最接近的组合: MAX_POSITIONS = {}\n".format(best_near["MAX_POSITIONS"]))
            for yr in ["2024", "2025"]:
                ret = best_near["ret_{}".format(yr)]
                dd = best_near["dd_{}".format(yr)]
                sharpe = best_near["sharpe_{}".format(yr)]
                f.write("- {}: {:.1f}% (回撤{:.1f}%, 夏普{:.2f})\n".format(yr, ret * 100, dd * 100, sharpe))

        f.write("\n---\n总耗时: {:.1f}小时\n".format(total_elapsed / 3600))


if __name__ == "__main__":
    main()

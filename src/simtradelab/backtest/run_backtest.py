# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2025 Kay
#
# This file is part of SimTradeLab, dual-licensed under AGPL-3.0 and a
# commercial license. See LICENSE-COMMERCIAL.md or contact kayou@duck.com
#
"""
本地回测入口 - 配置与启动

简化的入口文件，仅保留配置参数
"""


import sys
import argparse
from pathlib import Path

# 不强制设置编码，让 Python 自动使用终端默认编码（Windows GBK 936）
# 这样可以避免终端乱码问题

from simtradelab.backtest.runner import BacktestRunner
from simtradelab.backtest.config import BacktestConfig
from simtradelab.utils.paths import get_data_path

# ==================== 命令行参数配置 ====================
# 示例用法:
#   python run_backtest.py                              # 使用默认参数运行
#   python run_backtest.py --strategy 5mv              # 指定策略名称
#   python run_backtest.py --start 2025-01-01 --end 2025-03-31  # 指定回测周期
#   python run_backtest.py --capital 50000             # 指定初始本金
#   python run_backtest.py --strategy myTrend --start 2024-01-01 --end 2024-12-31 --capital 100000


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="SimTradeLab 回测运行器 - 用于执行量化策略回测",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default="5mv",
        help="策略名称 (默认：5mv)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default="2025-04-01",
        help="回测开始日期，格式：YYYY-MM-DD (默认：2025-04-01)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default="2025-04-30",
        help="回测结束日期，格式：YYYY-MM-DD (默认：2025-04-30)",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=1000000.0,
        help="初始本金，单位：元 (默认：1000000.0)",
    )
    args = parser.parse_args()

    # ==================== 启动回测 ====================

    # 使用相对路径获取数据目录（跨平台兼容 Windows/macOS/Linux）
    # 优先级：
    # 1. 环境变量 SIMTRADELAB_DATA_PATH（如果设置）
    # 2. 项目根目录下的 data 目录（自动查找）
    # 3. 默认值：当前文件上级目录的 data 文件夹
    data_path = get_data_path()

    # 确定策略路径：优先从环境变量读取，否则使用默认路径
    # 批量回测时，通过环境变量确保输出到正确的 optimize_XX 目录
    # 路径计算：run_backtest.py -> backtest -> simtradelab -> src -> SimTradeLab -> strategies
    import os
    strategies_path = os.environ.get(
        'SIMTRADELAB_STRATEGIES_PATH',
        str(Path(__file__).parent.parent.parent.parent / "strategies")
    )
    
    # 读取输出子目录（用于批量回测）
    output_subdir = os.environ.get('SIMTRADELAB_OUTPUT_SUBDIR', '')

    # 创建配置
    config = BacktestConfig(
        strategy_name=args.strategy,
        start_date=args.start,
        end_date=args.end,
        initial_capital=args.capital,
        data_path=str(data_path),
        strategies_path=strategies_path,
        output_subdir=output_subdir,
    )

    # 运行回测
    runner = BacktestRunner()
    report = runner.run(config=config)

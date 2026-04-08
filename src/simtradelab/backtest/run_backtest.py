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

# 确保控制台 UTF-8 编码和实时输出（兼容 Windows）
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8')

from simtradelab.backtest.runner import BacktestRunner
from simtradelab.backtest.config import BacktestConfig


if __name__ == '__main__':
    # ==================== 回测配置 ====================

    parser = argparse.ArgumentParser(description="Run SimTradeLab Backtest")
    parser.add_argument('-strategy', '--strategy', type=str, default='trends_up', help='Strategy name')
    parser.add_argument('--start', type=str, default='2025-01-02', help='Start date')
    parser.add_argument('--end', type=str, default='2025-01-31', help='End date')
    parser.add_argument('--capital', type=float, default=1000000.0, help='Initial capital')
    parser.add_argument('--frequency', type=str, default='1m', help='Frequency')
    
    args = parser.parse_args()

    config = BacktestConfig(
        strategy_name=args.strategy,
        start_date=args.start,
        end_date=args.end,
        initial_capital=args.capital,
        frequency=args.frequency
    )

    # 运行回测
    runner = BacktestRunner()
    report = runner.run(config=config)

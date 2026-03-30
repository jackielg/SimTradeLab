# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2025 Kay
#
# This file is part of SimTradeLab, dual-licensed under AGPL-3.0 and a
# commercial license. See LICENSE-COMMERCIAL.md or contact kayou@duck.com
#
"""
回测配置类
"""


from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional
import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator

from simtradelab.i18n import _DEFAULT_LOCALE


def _default_data_path():
    """获取默认数据路径"""
    from ..utils.paths import DATA_PATH

    return str(DATA_PATH)


def _default_strategies_path():
    """获取默认策略路径"""
    from ..utils.paths import STRATEGIES_PATH

    return str(STRATEGIES_PATH)


class BacktestConfig(BaseModel):
    """回测配置参数"""

    strategy_name: str
    start_date: str | pd.Timestamp
    end_date: str | pd.Timestamp
    data_path: str = Field(default_factory=_default_data_path)
    strategies_path: str = Field(default_factory=_default_strategies_path)
    initial_capital: float = Field(
        default=100000.0, gt=0, description="初始资金必须大于0"
    )
    use_data_server: bool = True

    # 回测频率配置
    frequency: str = Field(default="1d", description="回测频率: '1d'日线, '1m'分钟线")

    # 基准配置
    benchmark_code: str = Field(default='', description="基准代码，空串时使用市场默认基准")

    # 性能优化配置
    enable_multiprocessing: bool = True
    num_workers: Optional[int] = Field(
        default=None, ge=1, description="多进程worker数量"
    )
    enable_charts: bool = True
    enable_logging: bool = True
    enable_export: bool = False

    # 沙箱模式：True=限制import和builtins（Ptrade兼容），False=本地开发无限制
    sandbox: bool = False

    # 市场选择: CN=A股, US=美股
    market: str = Field(default="CN", description="市场代码")

    # T+1 覆盖：None=使用市场默认（CN=True, US=False），显式值覆盖市场默认
    t_plus_1: Optional[bool] = None

    # 优化模式：跳过策略验证/数据分析/日志配置（由优化器管理）
    optimization_mode: bool = False

    # 语言：None=自动（CN市场→zh，其他→系统检测），可显式指定 zh/en/de
    locale: Optional[str] = Field(default=None, description="语言")

    # 策略文件名（默认 backtest.py，实盘模拟用 live.py）
    strategy_file: str = 'backtest.py'

    model_config = {"arbitrary_types_allowed": True}

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def convert_to_timestamp(cls, v) -> pd.Timestamp:
        """转换日期为pd.Timestamp"""
        if isinstance(v, pd.Timestamp):
            return v
        return pd.Timestamp(v)

    @model_validator(mode="after")
    def validate_date_range(self):
        """验证日期范围

        此时start_date和end_date已被field_validator转换为pd.Timestamp
        """
        if self.start_date >= self.end_date:  # type: ignore
            raise ValueError("start_date必须早于end_date")
        if self.locale is None:
            self.locale = "zh" if self.market == "CN" else _DEFAULT_LOCALE
        return self

    @property
    def strategy_path(self) -> str:
        """策略文件完整路径"""
        return str(Path(self.strategies_path) / self.strategy_name / self.strategy_file)

    @property
    def log_dir(self) -> str:
        """日志目录"""
        return str(Path(self.strategies_path) / self.strategy_name / "stats")

    @property
    def _file_prefix(self) -> str:
        return Path(self.strategy_file).stem

    def get_log_filename(self) -> str:
        """生成日志文件名"""
        name = '{}_{}_{}_{}.log'.format(
            self._file_prefix,
            self.start_date.strftime("%y%m%d"),  # type: ignore
            self.end_date.strftime("%y%m%d"),  # type: ignore
            datetime.now().strftime("%y%m%d_%H%M%S"),
        )
        return str(Path(self.log_dir) / name)

    def get_chart_filename(self) -> str:
        """生成图表文件名"""
        name = '{}_{}_{}_{}.png'.format(
            self._file_prefix,
            self.start_date.strftime("%y%m%d"),  # type: ignore
            self.end_date.strftime("%y%m%d"),  # type: ignore
            datetime.now().strftime("%y%m%d_%H%M%S"),
        )
        return str(Path(self.log_dir) / name)

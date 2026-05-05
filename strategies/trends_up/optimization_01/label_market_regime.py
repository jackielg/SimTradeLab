# -*- coding: utf-8 -*-
"""
Step 0: 行情标注
用沪深300(000300.SS)日线数据，标注2024-01-02至2025-12-31每个交易日的行情标签(bull/bear/sideways)

识别规则:
  - bull:  MA20 > MA60 且 MA60上升, close > MA60, 低波动率
  - bear:  MA20 < MA60 且 MA60下降, close < MA60, 高波动率
  - sideways: 其余情况

运行方式:
  cd SimTradeLab
  python3 strategies/trends_up/optimization/label_market_regime.py
"""

import os
import pandas as pd
import numpy as np

BENCHMARK_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "..", "SimTradeData", "data", "cn", "metadata", "benchmark.parquet",
)
BENCHMARK_PATH = os.path.abspath(BENCHMARK_PATH)

# 行情识别参数
MA_SHORT = 20
MA_LONG = 60
VOL_WINDOW = 20
VOL_LOW = 0.015   # 低波动率阈值
VOL_HIGH = 0.025  # 高波动率阈值


def load_benchmark():
    df = pd.read_parquet(BENCHMARK_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df


def compute_indicators(df):
    df = df.copy()
    df["ma_short"] = df["close"].rolling(MA_SHORT).mean()
    df["ma_long"] = df["close"].rolling(MA_LONG).mean()
    df["ma_long_slope"] = df["ma_long"].diff(5) / df["ma_long"].shift(5)  # 5日变化率
    # 波动率: 20日收益率标准差
    df["returns"] = df["close"].pct_change()
    df["volatility"] = df["returns"].rolling(VOL_WINDOW).std()
    # 成交量趋势: 5日均量 / 20日均量
    df["vol_ma5"] = df["volume"].rolling(5).mean()
    df["vol_ma20"] = df["volume"].rolling(20).mean()
    df["vol_ratio"] = df["vol_ma5"] / df["vol_ma20"]
    return df


def label_regime(row):
    if pd.isna(row["ma_short"]) or pd.isna(row["ma_long"]):
        return "unknown"

    bull_score = 0
    bear_score = 0

    # 指标1: MA20 vs MA60
    if row["ma_short"] > row["ma_long"]:
        bull_score += 1
    elif row["ma_short"] < row["ma_long"]:
        bear_score += 1

    # 指标2: MA60斜率(上升/下降)
    if pd.notna(row["ma_long_slope"]):
        if row["ma_long_slope"] > 0.005:  # 5日涨幅>0.5%
            bull_score += 1
        elif row["ma_long_slope"] < -0.005:
            bear_score += 1

    # 指标3: close vs MA60
    if row["close"] > row["ma_long"]:
        bull_score += 1
    elif row["close"] < row["ma_long"]:
        bear_score += 1

    # 指标4: 波动率
    if pd.notna(row["volatility"]):
        if row["volatility"] < VOL_LOW:
            bull_score += 1  # 低波动=稳定上涨
        elif row["volatility"] > VOL_HIGH:
            bear_score += 1  # 高波动=恐慌

    if bull_score >= 3:
        return "bull"
    elif bear_score >= 3:
        return "bear"
    else:
        return "sideways"


def apply_confirm_buffer(labels, n=3):
    """行情切换需连续N天确认才生效"""
    result = labels.copy()
    current_confirmed = labels.iloc[0]
    pending_regime = None
    pending_count = 0

    for i in range(1, len(labels)):
        today = labels.iloc[i]
        if today == current_confirmed:
            pending_regime = None
            pending_count = 0
            continue

        if today == pending_regime:
            pending_count += 1
            if pending_count >= n:
                current_confirmed = pending_regime
                pending_regime = None
                pending_count = 0
        else:
            pending_regime = today
            pending_count = 1

        result.iloc[i] = current_confirmed

    return result


def main():
    print("加载沪深300日线数据...")
    df = load_benchmark()
    df = compute_indicators(df)

    # 筛选2024-2025
    mask = (df.index >= "2024-01-01") & (df.index <= "2025-12-31")
    period = df[mask].copy()

    print(f"日期范围: {period.index[0].strftime('%Y-%m-%d')} ~ {period.index[-1].strftime('%Y-%m-%d')}")
    print(f"交易日数: {len(period)}")

    # 原始标注
    period["regime_raw"] = period.apply(label_regime, axis=1)

    # 应用确认缓冲(N=3)
    period["regime"] = apply_confirm_buffer(period["regime_raw"], n=3)

    # 统计
    print("\n===== 行情分布(原始) =====")
    raw_counts = period["regime_raw"].value_counts()
    for r, c in raw_counts.items():
        print(f"  {r:10s}: {c:3d}天 ({c/len(period)*100:.1f}%)")

    print("\n===== 行情分布(缓冲N=3) =====")
    buffered_counts = period["regime"].value_counts()
    for r, c in buffered_counts.items():
        print(f"  {r:10s}: {c:3d}天 ({c/len(period)*100:.1f}%)")

    # 按年统计
    for year in [2024, 2025]:
        year_mask = period.index.strftime("%Y") == str(year)
        year_data = period[year_mask]
        print(f"\n===== {year}年行情分布 =====")
        year_counts = year_data["regime"].value_counts()
        for r, c in year_counts.items():
            print(f"  {r:10s}: {c:3d}天 ({c/len(year_data)*100:.1f}%)")

    # 行情切换统计
    regime_changes = (period["regime"] != period["regime"].shift(1)).sum() - 1
    print(f"\n行情切换次数: {regime_changes}")

    # 输出详细标注
    print("\n===== 详细标注(行情切换点) =====")
    prev = None
    for date, row in period.iterrows():
        if row["regime"] != prev:
            close_val = row["close"]
            ma20_val = row["ma_short"]
            ma60_val = row["ma_long"]
            vol_val = row["volatility"]
            print(
                f"  {date.strftime('%Y-%m-%d')}: {row['regime']:10s} "
                f"close={close_val:.1f} MA20={ma20_val:.1f} MA60={ma60_val:.1f} "
                f"vol={vol_val:.3f}" if pd.notna(ma60_val) else ""
            )
        prev = row["regime"]

    # 保存结果
    output_dir = os.path.dirname(__file__)
    output_path = os.path.join(output_dir, "market_regime_labels.csv")
    out_df = period[["close", "ma_short", "ma_long", "volatility", "regime_raw", "regime"]].copy()
    out_df.index.name = "date"
    out_df.to_csv(output_path)
    print(f"\n标注结果已保存: {output_path}")

    # 输出连续行情段
    print("\n===== 连续行情段 =====")
    segments = []
    seg_start = period.index[0]
    seg_regime = period["regime"].iloc[0]
    for i in range(1, len(period)):
        if period["regime"].iloc[i] != seg_regime:
            seg_end = period.index[i - 1]
            seg_days = (seg_end - seg_start).days + 1
            trading_days = i - period.index.get_loc(seg_start)
            segments.append({
                "start": seg_start.strftime("%Y-%m-%d"),
                "end": seg_end.strftime("%Y-%m-%d"),
                "regime": seg_regime,
                "calendar_days": seg_days,
                "trading_days": trading_days,
            })
            print(
                f"  {seg_start.strftime('%Y-%m-%d')} ~ {seg_end.strftime('%Y-%m-%d')}: "
                f"{seg_regime:10s} ({trading_days}天)"
            )
            seg_start = period.index[i]
            seg_regime = period["regime"].iloc[i]

    # 最后一段
    seg_end = period.index[-1]
    trading_days = len(period) - period.index.get_loc(seg_start)
    segments.append({
        "start": seg_start.strftime("%Y-%m-%d"),
        "end": seg_end.strftime("%Y-%m-%d"),
        "regime": seg_regime,
        "calendar_days": (seg_end - seg_start).days + 1,
        "trading_days": trading_days,
    })
    print(
        f"  {seg_start.strftime('%Y-%m-%d')} ~ {seg_end.strftime('%Y-%m-%d')}: "
        f"{seg_regime:10s} ({trading_days}天)"
    )

    return period, segments


if __name__ == "__main__":
    main()

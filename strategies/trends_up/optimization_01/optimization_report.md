# trends_up 参数优化报告

> 最后更新: 2026-05-05 21:45

## 目标

| 指标 | 约束 |
|---|---|
| 2024全年收益 | >= 30% |
| 2025全年收益 | >= 50% |
| 初始资金 | 100万 |
| 频率 | 1m (分钟级) |

---

## 总览：各Phase最佳结果对比

| Phase | 方案 | 2024收益 | 2025收益 | 综合 | 2024回撤 | 状态 |
|-------|------|----------|----------|------|----------|------|
| 基线 | MAX_POSITIONS=15 | +21.8% | — | — | -19.2% | 参考基线 |
| Phase 1 | 固定MAX_POSITIONS=5 | -10%~-5% | — | — | — | FAIL |
| Phase 2 T1 | 静态标注+防御性仓位 | +10.6% | **+78.6%** | 89.2% | — | FAIL(24<30) |
| Phase 2 T2 | 静态标注+均衡仓位 | +47.9% | +18.3% | 66.2% | — | FAIL(25<50) |
| Phase 3 | 动态行情识别(默认参数) | +23.3% | +0.4% | 23.7% | -33.3% | FAIL |
| Phase 3+v2/v3最优 | 动态+参数优化(17组合) | +27.4% | -1.2% | 26.2% | -31.8% | FAIL |
| Phase 3.5基线 | 5天确认+5日EMA | -32.2% | +8.0% | — | — | FAIL(未提交) |

**核心矛盾**: 2024和2025存在强tradeoff，无法同时达标。

---

## Phase 1: 固定MAX_POSITIONS (FAIL)

> 2026-05-03

MAX_POSITIONS = [5, 6, 7, 8] 扫描，所有组合2024年亏损(-5%~-10%)。

**根因**: 无行情识别，bull期仓位带入bear期，系统性亏损。

---

## Phase 2: 静态行情标注 + 择时调仓 (FAIL)

> 2026-05-04

### 架构

静态REGIME_PERIODS(12段人工标注) → REGIME_PARAMS三组参数 → 择时减仓模块

### 行情分布 (静态标注)

| 年份 | bear | sideways | bull |
|---|---|---|---|
| 2024 | 66天(27.3%) | 52天(21.5%) | 124天(51.2%) |
| 2025 | **0天** | 107天(44.0%) | 136天(56.0%) |

**注意**: 2025年静态标注无bear期，这是Phase 2表现远优于Phase 3的关键因素。

### Stage A: Bear参数扫描 (FAIL)

6组bear参数，2024全线亏损(-8%~-22%)。更紧止损反而更差(whipsaw)。

### Stage B: 择时调仓 (FAIL)

| 组合 | bear仓位 | sideways仓位 | 2024 | 2025 | 综合 | 状态 |
|------|----------|-------------|------|------|------|------|
| T1_defensive | 10% | 30% | +10.6% | **+78.6%** | 89.2% | FAIL(24<30) |
| T2_balanced | 15% | 40% | +47.9% | +18.3% | 66.2% | FAIL(25<50) |
| T3_ultra_def | 0% | 20% | +20.2% | +15.0% | 35.3% | FAIL |
| T4_moderate | 20% | 50% | -11.0% | +50.0% | 39.0% | FAIL(24<30) |

**核心tradeoff**: bear防御越强→2025越好(因无bear)但2024不够；sideways 30% vs 40%导致2025差60%(78.6% vs 18.3%)。

### Stage B+: Bull参数优化 (零影响)

Bull入场/出场/止盈参数对结果零影响。瓶颈完全在bear/sideways期。

### Phase 2 局限性

1. **静态标注是前视偏差** — 实盘不可用
2. **二元切换** — bull→bear 80%→10%骤降
3. **sideways离散跳变** — 30% vs 40%差60%收益
4. **3天确认延迟** — bear期多亏2-3天

---

## Phase 3: 动态行情识别 + 结构性改进 (FAIL)

> 2026-05-04 ~ 05-05

### 架构变更

从Phase 2的"静态标注+参数调优"转向Phase 3的"动态检测+结构性改进"。

| 模块 | Phase 2 | Phase 3 |
|------|---------|---------|
| 行情识别 | 12段静态REGIME_PERIODS | RegimeDetector 6指标实时评分 |
| 仓位映射 | 3级(bear/sideways/bull)离散跳变 | 5级连续函数calc_target_ratio |
| 调仓方式 | 一天到位 | TRANSITION_DAYS分多天渐进 |
| 评分系统 | 4维固定权重 | 5维+动量+行情自适应权重 |
| 防御机制 | bear期统一减仓 | score<30预警止损 |

### 实现的改进 (已提交到未暂存改动)

| 改进 | 说明 | 代码位置 |
|------|------|----------|
| RegimeDetector | CSI300六指标(MA20/MA60/斜率/波动率/RSI/价格偏离) → 0-100分 | :293-456 |
| calc_target_ratio | 连续仓位函数, 消除离散跳变 | :429-441 |
| 渐进调仓 | TRANSITION_DAYS分多天减仓(1-2天) | :2598-2657 |
| 预警止损 | score<30收紧止损 | :1835-1991 |
| 5维评分+动量 | 新增MOMENTUM维度+REGIME_SCORING_WEIGHTS | :1120-1190 |
| 量能过滤 | 5d/20d均量<0.5过滤 | _filter_by_volume_quality |
| 3天确认+3日EMA | 连续2天新regime才切换+EMA平滑 | :337-346, :313-318 |
| MAX_POSITIONS=10 | 配合MIN_POSITION_VALUE=10000 | ConfigManager |

### 连续仓位函数

```python
# calc_target_ratio (backtest.py:429-441)
score >= 60: ratio = 0.70 + (score-60)*0.005   # bull: 70%-90%
score >= 45: ratio = 0.50 + (score-45)*0.010   # weak_bull: 50%-65%
score >= 20: ratio = 0.25 + (score-20)*0.010   # sideways: 25%-50%
score >=  5: ratio = 0.10 + (score-5)*0.010    # early_bear: 10%-25%
score <   5: ratio = max(0.05, score*0.01)      # bear: 5%-10%
```

**重要**: `get_params()`用calc_target_ratio(score)覆盖了REGIME_PARAMS中的TARGET_POS_RATIO，所以修改REGIME_PARAMS的TARGET_POS_RATIO无效。

### Phase 3 基准回测

| 年份 | 收益 | 最大回撤 | 夏普 | 切换次数 |
|------|------|----------|------|----------|
| 2024 | +23.3% | -33.3% | 0.71 | 16次 |
| 2025 | **+0.4%** | -16.3% | 0.13 | **14次** |

**严重退步**: 2025从Phase 2 T1的78.6%降到0.4%。

### 根因: 动态检测 vs 静态标注切换对比

**2025年 (关键年份)**:

| 时间 | 动态检测 | 静态标注(Phase 2) | 差异影响 |
|------|----------|-------------------|----------|
| 1月2-6日 | sideways | sideways | 一致 |
| **1月7-23日** | **early_bear(17天)** | **sideways** | 动态多了bear期 |
| 1月24日-2月13日 | sideways | sideways | 一致 |
| 2月14日-4月8日 | bull | sideways→bull | 基本一致 |
| 4月9-14日 | sideways | bull | 轻微差异 |
| **4月15-24日** | **bear(10天)** | **bull** | 动态多了bear期 |
| **4月25-28日** | **early_bear(4天)** | **bull** | 动态多了bear期 |
| 4月29日-5月13日 | sideways | bull | 差异 |
| 5月14日-11月25日 | bull | bull | 一致(主升浪) |
| 11月26日-12月2日 | weak_bull | sideways | 轻微差异 |
| 12月3-14日 | bull | sideways | 差异 |
| 12月15-23日 | sideways | sideways | 一致 |
| 12月24-31日 | bull | sideways | 差异 |

**2025年切换次数**: 动态**14次** vs 静态**3次**

**2024年切换次数**: 动态**16次** vs 静态**6次**

**核心问题**: 每次切换触发卖出+重建，频繁切换累积巨大交易损失。动态检测在1月和4月识别出Phase 2没有的bear期（CSI300确实下跌），但策略过度防御导致错过后续反弹。

### Phase 3 参数优化

#### v1 (已崩溃, FAIL)

> 运行: 05-05 02:43~05:16 (~2.5h), multiprocessing 2 workers

搜索空间: sideways_func(9组) + defense(9组) + warning(9组) = 27组

**问题1**: defense类型修改REGIME_PARAMS.TARGET_POS_RATIO，但被calc_target_ratio覆盖，**完全无效**。

**问题2**: 完成2组后内存崩溃(2 workers × ~4GB = ~8GB)。

| # | 组合 | 2024 | 2025 | 综合 | 状态 |
|---|------|------|------|------|------|
| 0 | SW_sl0.008_b0.2 | 23.3% | 11.6% | 34.9% | FAIL |
| 4 | SW_sl0.01_b0.25 | 23.3% | 0.4% | 23.7% | FAIL |

#### v2 串行 + v3 并行 (全部FAIL)

> v2串行: 05-05 05:21~10:00 (2组)
> v3并行4 workers: 05-05 10:23~19:15 (15组), 总耗时530分钟

**修正**: 直接修改calc_target_ratio函数参数，而非无效的REGIME_PARAMS。

搜索空间: defense_floor(9组) + sideways_base(3组) + confirm_days(2组, ERROR) + v1遗留(2组) = 17组（含2组ERROR）

**全部17组结果 (按综合收益排序)**:

| # | 组合 | 类型 | 2024 | 2025 | 2024回撤 | 综合 | 状态 |
|---|------|------|------|------|----------|------|------|
| v1 | SW_sl0.012_b0.2 | sideways_func | **+27.4%** | -1.2% | -31.8% | 26.2% | FAIL |
| v1 | SW_sl0.008_b0.3 | sideways_func | +23.3% | +0.4% | -33.3% | 23.7% | FAIL |
| v1 | SW_sl0.01_b0.3 | sideways_func | +23.3% | +0.4% | -33.3% | 23.7% | FAIL |
| 12 | SW0.25 | sideways_base | +23.3% | +0.4% | -33.3% | 23.7% | FAIL |
| 13 | SW0.3 | sideways_base | +23.3% | +0.4% | -33.3% | 23.7% | FAIL |
| 14 | SW0.35 | sideways_base | +23.3% | +0.4% | -33.3% | 23.7% | FAIL |
| 0 | EB0.15_BF0.1 | defense_floor | +21.6% | +0.3% | -30.6% | 21.9% | FAIL |
| 1 | EB0.15_BF0.15 | defense_floor | +21.6% | +0.3% | -30.6% | 21.9% | FAIL |
| 3 | EB0.2_BF0.1 | defense_floor | +18.4% | +0.3% | -29.2% | 18.6% | FAIL |
| 4 | EB0.2_BF0.15 | defense_floor | +18.4% | +0.3% | -29.2% | 18.6% | FAIL |
| 7 | EB0.25_BF0.15 | defense_floor | +18.4% | +0.3% | -29.2% | 18.6% | FAIL |
| 8 | EB0.25_BF0.2 | defense_floor | +18.4% | +0.3% | -29.2% | 18.6% | FAIL |
| 9 | EB0.3_BF0.1 | defense_floor | +18.4% | +0.3% | -29.2% | 18.6% | FAIL |
| 10 | EB0.3_BF0.15 | defense_floor | +18.4% | +0.3% | -29.2% | 18.6% | FAIL |
| 11 | EB0.3_BF0.2 | defense_floor | +18.4% | +0.3% | -29.2% | 18.6% | FAIL |
| 15 | CD1 | confirm_days | ERROR | ERROR | — | — | ERROR(代码未变化) |
| 16 | CD3 | confirm_days | ERROR | ERROR | — | — | ERROR(代码未变化) |

**v3统计**: 4 workers × 15组 × ~530min总耗时，单组平均~35min

---

## Phase 3.5: 降低切换频率 (设计中，未实施)

> 2026-05-05 提出方案

### 背景

Phase 3参数优化(v1~v3)确认：**参数调整对2025无效**，根因是切换频率(14次 vs Phase 2的3次)。

### 基线回测结果 (手动验证)

调整确认天数(3→5天)和EMA平滑(3日→5日)后的一次性回测:

| 指标 | Phase 3默认 | Phase 3.5基线 | 变化 |
|------|------------|---------------|------|
| 2024收益 | +23.3% | **-32.2%** | 退步 |
| 2025收益 | +0.4% | **+8.0%** | 改善 |
| 2024切换 | 16次 | **8次** | 减半 |
| 2025切换 | 14次 | **7次** | 减半 |

**结论**: 切换频率确实减半，2025小幅改善(+0.4%→+8.0%)，但2024严重退步(+23.3%→-32.2%)。降低灵敏度对2024的伤害远大于对2025的帮助。

### 设计方案 (待实施)

| 改进项 | 当前值 | 方案值 | 预期效果 |
|--------|--------|--------|----------|
| 确认天数 | 3天(pending_count>=2) | 5天(pending_count>=4) | 减少误切换 |
| EMA平滑 | 3日(alpha=0.5) | 5日(alpha=0.33) | 进一步平滑噪音 |
| MA周期 | MA60 | MA120 | 更长期趋势判断 |

**状态**: 方案已设计但未提交到代码。代码中仍为Phase 3默认参数(3天确认+3日EMA+MA60)。

---

## 关键发现汇总

### 1. 切换频率是2025表现的决定性因素

| 方案 | 2025切换次数 | 2025收益 |
|------|-------------|----------|
| Phase 2 静态标注 | 3次 | **+78.6%** |
| Phase 3.5 (5天确认) | 7次 | +8.0% |
| Phase 3 (3天确认) | 14次 | +0.4% |

**结论**: 切换次数与2025收益强相关。Phase 2的78.6%收益来自极少切换+2025年静态标注无bear期。

### 2. 2024-2025存在不可调和的tradeoff

```
2024有真实bear期 → 需要防御(低仓位/快切换) → 2024收益下降
2025无bear期(静态标注) → 不需要防御 → 切换=纯损失

Phase 2 T1: 防御强 → 2024=10.6%(不够), 2025=78.6%
Phase 2 T2: 防御弱 → 2024=47.9%(好), 2025=18.3%(不够)
Phase 3:   动态频繁切换 → 两边都不好
```

### 3. 参数优化在错误层面工作

- **calc_target_ratio覆盖REGIME_PARAMS**: get_params()第410行用calc_target_ratio(score)覆盖TARGET_POS_RATIO，v1优化脚本的defense参数完全无效
- **defense_floor参数**: 9组覆盖early_bear=0.15-0.30和bear=0.10-0.20，2025收益恒定0.3%，说明bear期仓位不是2025的瓶颈
- **sideways_base参数**: 4组覆盖0.25-0.35，2025收益恒定0.4%，说明sideways仓位也不是瓶颈
- **confirm_days参数**: 脚本未正确修改代码，结果全部ERROR

### 4. 动态检测的"正确性"悖论

动态检测在1月和4月识别出的bear信号是真实的（CSI300确实下跌），但这些是短期回调而非趋势性下跌。策略的防御响应在参数层面是正确的，但在时机层面是错误的——过度防御导致错过反弹。

### 5. Phase 2的78.6%依赖前视偏差

Phase 2 T1的2025年78.6%收益依赖静态标注"2025年无bear期"这一结论。这是基于全年数据的事后判断，实盘中无法获得。

---

## 后续方向 (待讨论)

### 方案A: 降低动态检测灵敏度

在Phase 3.5基础上继续调参：
- 确认天数 3→5→7天
- EMA平滑 3日→5日→10日
- 提高bear评分阈值(5→15, 20→30)
- 添加切换冷却期(N天内不再切换)

**风险**: Phase 3.5基线已证明，降低灵敏度对2024伤害更大(-32.2%)。

### 方案B: 混合方案 (静态约束+动态辅助)

- 保留Phase 2的静态标注作为宏观框架
- 动态检测仅在静态标注的bear/sideways期内启动防御
- 非bear期即使动态检测到bear也保持bull仓位
- 解决Phase 2的前视偏差问题: 用MA200/MA250等超长期指标替代静态标注

**优势**: 结合Phase 2的收益潜力和Phase 3的实时性。

### 方案C: 回退Phase 2 + 提升选股能力

- 回退到Phase 2静态标注(T1: 24=10.6%, 25=78.6%)
- 专注提升2024从10.6%→30%:
  - bear期不完全空仓(bear=0%→10-15%)
  - bear期选防御性股票(高股息/低波动)
  - 优化bull期收益(Phase 2 T2已做到47.9%)
- 用长周期指标(MA200)自动判断是否进入bear期，替代人工标注

### 方案D: 放弃双年达标，分年优化

- 2024和2025市场结构不同，同一策略难以同时适应
- 分市场环境优化: 震荡市策略(2024适用) vs 趋势市策略(2025适用)
- 用regime检测切换策略模式(而非切换仓位)

---

## 文件改动清单

### Phase 3 新增/修改 (未提交)

| 文件 | 改动 | 位置 |
|------|------|------|
| backtest.py | MAX_POSITIONS 5→10, 新增MIN_POSITION_VALUE=10000 | ConfigManager |
| backtest.py | SCORING_WEIGHTS 4维→5维(+MOMENTUM) | ConfigManager |
| backtest.py | 新增REGIME_SCORING_WEIGHTS 5组行情自适应权重 | ConfigManager |
| backtest.py | 新增REGIME_PARAMS 5个regime完整参数 | ConfigManager |
| backtest.py | 新增RegimeDetector类(动态行情引擎) | :293-456 |
| backtest.py | score_breakout_stock增加动量+自适应权重 | :1120-1190 |
| backtest.py | 新增_filter_by_volume_quality量能过滤 | 新方法 |
| backtest.py | check_intraday_exit预警止损 | :1835-1991 |
| backtest.py | _rebalance_on_regime_change渐进式调仓 | :2598-2657 |
| backtest.py | before_trading_start动态检测 | :2576-2596 |
| optimization/optimize_phase3.py | v2串行优化脚本(17组) | 重写 |

### 优化脚本

| 文件 | 用途 | 大小 |
|------|------|------|
| optimization/optimize_params.py | Phase 1: MAX_POSITIONS扫描 | 10K |
| optimization/optimize_regime_params.py | Phase 2 Stage A: bear参数扫描 | 17K |
| optimization/optimize_stage_b.py | Phase 2 Stage B: 择时调仓并行优化 | 11K |
| optimization/optimize_phase3.py | Phase 3 v2/v3: 17组参数优化 | 14K |
| optimization/label_market_regime.py | 行情标注工具(离线) | 7.3K |

### 结果文件

| 文件 | 说明 |
|------|------|
| optimization/phase3_summary.json | Phase 3全部17组结果汇总 |
| optimization/phase3_result_0~14.json | 15组独立结果 |
| optimization/stage_b_result_0~3.json | Phase 2 Stage B结果 |
| optimization/market_regime_labels.csv | 离线行情标注数据(41K) |

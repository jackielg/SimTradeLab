# Trends_Up 策略 v4.3 优化计划 - 牛股特征学习版

## 📋 任务概述

**目标**：基于 v4.2 的失败教训，重新设计选股模型，学习牛股的周线/日线特征，在起涨初期精准买入。

**核心思想**：
- **选股为王**：牛股特征提取 + 多维度验证
- **起涨点买入**：周线 MACD 金叉 + 日线突破 + 成交量放大
- **严格风控**：总回撤控制 + 动态止损

**约束条件**：
- 必须使用 Strategy-Arch, Strategy-Engr, Strategy-QA 多智能体协作模式
- 保持策略名称为 trends_up
- 所有文档保存在 `strategies/trends_up/optimize_03/` 目录
- 优化前备份 v4.2 代码

---

## 🎯 优化目标

### 收益目标
- 总收益率 > 50%（3 个测试周期中至少 2 个达标）
- 年化收益率 > 60%

### 风控目标
- 最大回撤 < 15%（3 个测试周期全部达标）
- 盈亏比 > 1.5
- 胜率 > 55%

### 测试周期
1. **震荡市**：2025-04-01 ~ 2025-07-31（v4.2: -37.08% ❌）
2. **牛市**：2024-09-01 ~ 2024-12-31（v4.2: +31.75% ❌）
3. **完整年**：2024-01-01 ~ 2024-12-31（v4.2: -30.84% ❌）

---

## 🔍 第一阶段：牛股特征学习（Strategy-QA + Strategy-Arch 主导）

### 1.1 样板股票特征分析

**任务描述**：
- 分析用户提供的牛股图表（周线 + 日线）
- 提取关键技术特征
- 量化特征阈值

**样板股票特征**（从图表中提取）：

#### **周线特征**（大趋势）
1. **均线系统**
   - MA5 > MA10 > MA20 > MA60（多头排列）
   - MA20 向上拐头角度 > 30 度
   - 股价回踩 MA20 不破

2. **MACD 指标**
   - DIF 和 DEA 在 0 轴上方
   - DIF 上穿 DEA（金叉）
   - 红柱持续放大

3. **成交量**
   - 上涨周成交量 > 下跌周成交量（量价配合）
   - 成交量 MA5 > MA20（资金持续流入）
   - 突破周成交量放大 50%+

#### **日线特征**（起涨点）
1. **均线系统**
   - MA5/MA10/MA20 多头排列
   - 股价突破平台（20-60 天横盘）
   - 突破日涨幅 > 3%

2. **MACD 指标**
   - DIF 在 0 轴上方回踩后再次金叉
   - 金叉位置高于前一次（底背离）
   - 红柱放大速度加快

3. **成交量**
   - 突破日成交量 > 前 5 日均量 100%
   - 量比 > 2.0
   - 连续 3 日放量

### 1.2 特征量化阈值

**周线阈值**：
```python
WEEKLY_FEATURES = {
    # 均线
    "MA5_MA20_RATIO": 1.05,      # MA5/MA20 > 1.05（多头 5%）
    "MA20_ANGLE": 30,            # MA20 角度 > 30 度
    "PRICE_MA20_RATIO": 1.02,    # 股价/MA20 > 1.02（回踩不破）
    
    # MACD
    "MACD_GOLDEN_CROSS": True,   # 金叉
    "DIF_ABOVE_ZERO": True,      # DIF > 0
    "MACD_RED_BAR_INCREASE": 0.1 # 红柱放大 10%
    
    # 成交量
    "VOL_MA5_MA20_RATIO": 1.3,   # 成交量 MA5/MA20 > 1.3
    "BREAKOUT_VOL_RATIO": 1.5,   # 突破周成交量/前周 > 1.5
}
```

**日线阈值**：
```python
DAILY_FEATURES = {
    # 均线
    "MA5_MA10_MA20_ORDER": True, # 多头排列
    "PLATFORM_DAYS": 20,         # 横盘天数 20-60
    "BREAKOUT_PCT": 0.03,        # 突破日涨幅 > 3%
    
    # MACD
    "DAILY_MACD_GOLDEN": True,   # 日线金叉
    "DIF_HIGHER": True,          # 金叉位置更高
    
    # 成交量
    "BREAKOUT_VOL_RATIO": 2.0,   # 突破日量/前 5 日均量 > 2
    "VOL_RATIO": 2.0,            # 量比 > 2
    "CONTINUOUS_VOL_DAYS": 3,    # 连续放量天数
}
```

### 1.3 输出文档
- `strategies/trends_up/optimize_03/bull_stock_features.md` - 牛股特征详细分析

---

## 🏗️ 第二阶段：优化方案设计（Strategy-Arch 主导）

### 2.1 核心修复方案

基于 v4.2 的失败教训和牛股特征，设计以下修复：

#### **P0：选股模型重构**（权重 50%）

**问题**：v4.2 胜率仅 42-57%，选股质量差

**方案**：
1. **周线筛选**（初选）
   - 均线多头排列（MA5>MA10>MA20>MA60）
   - MACD 金叉且 DIF>0
   - 成交量 MA5>MA20

2. **日线确认**（精选）
   - 突破平台（20-60 天横盘）
   - 突破日涨幅>3%，成交量>200%
   - MACD 二次金叉

3. **评分系统**（排序）
   - 趋势强度（40%）：均线多头程度 + MACD 强度
   - 成交量（30%）：放量程度 + 持续天数
   - 突破质量（20%）：平台整理时间 + 突破力度
   - 基本面（10%）：营收增长 + 利润率

**预期效果**：胜率从 45% 提升至 60%+

#### **P0：退出策略重构**（权重 30%）

**问题**：v4.2 盈亏比仅 0.66-1.06，止损过大/止盈过早

**方案**：
1. **动态止损**
   - ATR 止损：1.8 倍（从 3.0 倍下调）
   - 平台低点止损：跌破突破平台低点
   - MA20 止损：收盘价跌破 MA20

2. **分级止盈**（优化）
   - 第一档：盈利 10% 卖出 30%（提前锁定）
   - 第二档：盈利 20% 卖出 30%
   - 第三档：盈利 30% 卖出 20%
   - 剩余：移动止盈（回撤 8% 清仓）

3. **时间止损**
   - 15 天盈利<5% → 卖出
   - 10 天亏损>5% → 卖出

**预期效果**：盈亏比从 1.0 提升至 1.8+

#### **P0：风险控制强化**（权重 20%）

**问题**：v4.2 回撤 -22%~-47%，风控失效

**方案**：
1. **总回撤控制**
   - 组合回撤>10% → 仓位上限 50%
   - 组合回撤>15% → 强制空仓

2. **单行业集中度**
   - 单行业持仓≤30%

3. **动态仓位**
   - 牛市：20%（保持）
   - 震荡市：12%（保持）
   - 熊市：5% → 3%（进一步降低）

**预期效果**：最大回撤从 -47% 控制在 -15% 以内

### 2.2 输出文档
- `strategies/trends_up/optimize_03/optimization_design_v43.md` - 详细设计方案

---

## 💻 第三阶段：代码实现（Strategy-Engr 主导）

### 3.1 备份代码
- 复制 `backtest.py` 到 `optimize_03/backtest_v42_backup.py`

### 3.2 实现选股模型

**新增类**：
```python
class WeeklyTrendAnalyzer:
    """周线趋势分析"""
    def check_ma_alignment(self, stock) -> bool
    def check_macd_golden_cross(self, stock) -> bool
    def check_volume_trend(self, stock) -> bool

class BreakoutScanner:
    """突破扫描仪"""
    def detect_platform(self, stock, min_days=20, max_days=60) -> bool
    def confirm_breakout(self, stock) -> bool
    def calculate_breakout_score(self, stock) -> float

class BullStockScorer:
    """牛股评分器"""
    def score_trend_strength(self, stock) -> float
    def score_volume(self, stock) -> float
    def score_breakout_quality(self, stock) -> float
    def score_fundamentals(self, stock) -> float
```

**修改类**：
```python
class TrendStrengthScorer:
    # 重写评分逻辑，加入周线特征
    def score_stock(self, stock, df) -> float

class ExitStrategy:
    # 重写退出逻辑，加入动态止损
    def check_exit(self, pos, current_price, df, holding_days, trend_score, market_state)
```

### 3.3 实现退出策略
- 实现 ATR 动态止损（1.8 倍）
- 实现分级止盈（10%/20%/30%）
- 实现移动止盈（回撤 8%）
- 实现时间止损（15 天/10 天）

### 3.4 实现风险控制
- 增加组合回撤监控
- 增加行业集中度检查
- 优化仓位计算公式

### 3.5 输出
- 更新 `backtest.py`（v4.3 正式版）
- 代码修改说明文档

---

## 🧪 第四阶段：回测验证（Strategy-Engr 主导）

### 4.1 运行回测

**回测周期**：
1. **震荡市**：2025-04-01 ~ 2025-07-31
2. **牛市**：2024-09-01 ~ 2024-12-31
3. **完整年**：2024-01-01 ~ 2024-12-31

**回测命令**：
```bash
python run_backtest.py --strategy trends_up --start 2025-04-01 --end 2025-07-31 --capital 1000000
python run_backtest.py --strategy trends_up --start 2024-09-01 --end 2024-12-31 --capital 1000000
python run_backtest.py --strategy trends_up --start 2024-01-01 --end 2024-12-31 --capital 1000000
```

### 4.2 结果对比
- v4.2 vs v4.3 收益率对比
- 胜率/盈亏比改善情况
- 最大回撤控制效果

---

## 📊 第五阶段：结果分析（Strategy-QA 主导）

### 5.1 回测结果分析

**分析维度**：
1. 收益率是否达标（>50%）
2. 最大回撤是否达标（<15%）
3. 胜率/盈亏比是否改善
4. 牛股特征是否有效

### 5.2 生成 QA 报告

**输出文档**：
- `strategies/trends_up/optimize_03/qa_report_v43.md`

---

## ✅ 第六阶段：最终验收（Strategy-Arch 主导）

### 6.1 验收标准

**必须满足**：
- [ ] 3 个回测周期中至少 2 个收益率 > 50%
- [ ] 3 个回测周期最大回撤全部 < 15%
- [ ] 盈亏比 > 1.5（至少 2 个周期）
- [ ] 胜率 > 55%（至少 2 个周期）

### 6.2 验收结论
- 验收通过：进入生产环境部署
- 验收不通过：继续优化或终止项目

---

## 📅 工作计划

### 时间估算
- 第一阶段（牛股特征学习）：2 小时
- 第二阶段（方案设计）：1 小时
- 第三阶段（代码实现）：2-3 小时
- 第四阶段（回测验证）：15 分钟（并行运行）
- 第五阶段（结果分析）：30 分钟
- 第六阶段（最终验收）：15 分钟

### 里程碑
1. ✅ 完成牛股特征分析
2. ✅ 完成优化设计
3. ✅ 完成代码实现
4. ✅ 完成回测验证
5. ✅ 通过最终验收

---

## 📋 多智能体职责

### Strategy-Arch（架构师）
- 牛股特征提取指导
- 优化方案架构设计
- 最终验收决策

### Strategy-Engr（工程师）
- 选股模型实现
- 退出策略实现
- 风险控制实现
- 回测执行

### Strategy-QA（质量保障）
- 牛股特征分析
- 代码质量审查
- 回测结果分析
- 验收测试

---

## 📝 文档清单

### 必须输出
- [ ] `strategies/trends_up/optimize_03/bull_stock_features.md`
- [ ] `strategies/trends_up/optimize_03/optimization_design_v43.md`
- [ ] `strategies/trends_up/optimize_03/backtest_v42_backup.py`
- [ ] `strategies/trends_up/optimize_03/qa_report_v43.md`

### 可选输出
- [ ] `strategies/trends_up/optimize_03/optimization_summary_v43.md`（如优化成功）

---

## ⚠️ 注意事项

1. **牛股特征学习**：必须仔细分析样板股票的周线/日线特征
2. **起涨点识别**：关键是周线 MACD 金叉 + 日线突破 + 成交量放大
3. **多智能体协作**：每个阶段必须由指定的智能体主导
4. **文档组织**：所有文档保存在 `optimize_03/` 目录
5. **代码备份**：优化前必须备份 v4.2 代码
6. **严格验收**：不达标不通过

---

## 🔄 迭代机制

如果 v4.3 优化未达到验收标准：
1. 分析失败原因（选股模型？退出策略？风控？）
2. 创建 `optimize_04` 继续迭代
3. 考虑是否调整策略思路（如转向其他选股逻辑）

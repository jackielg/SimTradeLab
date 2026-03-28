# 任务单：Trends_Up v4.0 紧急修复

**任务 ID**: TASK-V4FIX  
**创建日期**: 2026-03-28  
**优先级**: 🔴 P0（紧急）  
**状态**: 待开始  

---

## 任务描述

根据 QA 诊断报告（[完整报告](file:///c:/Users/Admin/SynologyDrive/PtradeProjects/workspace_qa/trends_up_v4_backtest_diagnosis_report.md)），trends_up v4.0 策略在回测中全面失败，需要紧急修复六大核心问题。

### 回测失败数据

| 市场类型 | 总收益率 | 最大回撤 | 胜率 | 目标收益率 | 达标情况 |
|---------|---------|---------|------|-----------|---------|
| **震荡市** | **-33.45%** | -33.45% | 36.6% | > 50% | ❌ 严重不达标 |
| **牛市** | **+12.59%** | -20.20% | 54.4% | > 50% | ❌ 不达标 |
| **完整年** | **-31.77%** | -41.28% | 46.5% | > 50% | ❌ 严重不达标 |

---

## 核心问题（按严重程度）

| 排名 | 问题 | 严重程度 | 对收益影响 | 修复方案 |
|------|------|---------|-----------|---------|
| 1 | **选股评分标准过严** | ⭐⭐⭐⭐⭐ | -40% | 放宽阈值 + 降低门槛 |
| 2 | **无市场环境判断** | ⭐⭐⭐⭐⭐ | -30% | 添加牛熊判断 + 动态仓位 |
| 3 | **止盈策略缺失** | ⭐⭐⭐⭐⭐ | -20% | 分级止盈 + 移动止盈 |
| 4 | **动态仓位缺失** | ⭐⭐⭐⭐ | -15% | 根据市场状态调整 |
| 5 | **ATR 止损参数不合理** | ⭐⭐⭐⭐ | -10% | 优化 ATR 倍数到 2.0 |
| 6 | **时间止损缺失** | ⭐⭐⭐ | -5% | 25 天收益<5% 时间止损 |

---

## 修复目标

| 指标 | 目标值 | 当前值（完整年） | 改善幅度 |
|------|--------|----------------|---------|
| 总收益率 | > 50% | -31.77% | +80%+ |
| 最大回撤 | < 15% | -41.28% | -26%+ |
| 胜率 | > 55% | 46.5% | +8.5%+ |
| 盈亏比 | > 1.5 | < 1.0 | +50%+ |

---

## 执行清单

### P0 任务（紧急）

- [ ] **TASK-V4FIX-001**: 实现优化版评分系统（放宽阈值）
  - 横盘整理：从 [0.20, 0.30, 0.40] 放宽到 [0.30, 0.40, 0.50]
  - 成交量萎缩：从 [0.70, 0.80, 0.90] 放宽到 [0.80, 0.90, 1.00]
  - 突破信号：从 [0.05, 0.03, 0.01] 降低到 [0.03, 0.02, 0.01]
  - 相对强度：从 [0.05, 0.02, 0.00] 降低到 [0.03, 0.01, 0.00]
  - 选股门槛：从 >= 60 分降低到 >= 35 分

- [ ] **TASK-V4FIX-002**: 实现 MarketStateAnalyzer 类
  - 牛熊判断逻辑（均线排列 + 斜率）
  - 市场趋势评分（0-1）

- [ ] **TASK-V4FIX-003**: 实现 PositionManager 类（动态仓位）
  - 根据市场状态调整仓位（牛市 15%、震荡市 10%、熊市 5%）
  - 根据趋势评分调整仓位
  - 最大持仓数动态调整（5-15 只）

- [ ] **TASK-V4FIX-004**: 实现 ExitStrategy 类（完整退出策略）
  - 整合所有退出逻辑
  - 按优先级执行：固定止损 → ATR 止损 → 趋势反转 → 时间止损 → 分级止盈 → 移动止盈

- [ ] **TASK-V4FIX-005**: 实现分级止盈逻辑
  - +15%：卖出 20%
  - +25%：卖出 30%
  - +45%：卖出 50%
  - +70%：清仓

- [ ] **TASK-V4FIX-006**: 实现移动止盈逻辑
  - 盈利>10% 启动移动止盈
  - 高点回撤 12% 触发
  - 盈利>30% 时回撤阈值收紧到 8%

- [ ] **TASK-V4FIX-009**: 集成所有组件到主策略
  - 初始化组件
  - 盘前处理（市场状态 + 选股）
  - 盘中处理（退出检查 + 买入）

- [ ] **TASK-V4FIX-010**: 运行回测验证
  - 震荡市：2025-04-01 ~ 2025-07-31
  - 牛市：2024-09-01 ~ 2024-12-31
  - 完整年：2024-01-01 ~ 2024-12-31

### P1 任务（高优先级）

- [ ] **TASK-V4FIX-007**: 实现时间止损逻辑
  - 25 天收益<5%：时间止损
  - 20 天亏损>5%：强制止损
  - 15 天亏损>10%：紧急止损

- [ ] **TASK-V4FIX-008**: 实现 ATR 动态止损
  - 动态 ATR 倍数（牛市 2.5、震荡市 2.0、熊市 1.5）
  - 吊灯止损逻辑

---

## 技术要点

### 1. 优化版评分函数

```python
def score_stock_optimized(stock, context):
    """优化版评分系统（放宽阈值）"""
    
    try:
        df = get_price(stock, count=65, frequency='1d', 
                      fields=['open', 'high', 'low', 'close', 'volume'])
        if df.empty or len(df) < 65:
            return 0
        
        score = 0
        
        # 条件 1: 横盘整理（25 分）- 放宽 10%
        high_60d = df['high'].iloc[-65:-1].max()
        low_60d = df['low'].iloc[-65:-1].min()
        consolidation_ratio = (high_60d - low_60d) / low_60d
        
        if consolidation_ratio < 0.30:  # 从 0.20 放宽到 0.30
            score += 25
        elif consolidation_ratio < 0.40:
            score += 15
        elif consolidation_ratio < 0.50:
            score += 5
        
        # 条件 2: 成交量萎缩（25 分）- 放宽 0.1
        avg_volume_20d = df['volume'].iloc[-20:].mean()
        avg_volume_60d = df['volume'].iloc[-65:-1].mean()
        volume_ratio = avg_volume_20d / avg_volume_60d
        
        if volume_ratio < 0.80:  # 从 0.70 放宽到 0.80
            score += 25
        elif volume_ratio < 0.90:
            score += 15
        elif volume_ratio < 1.00:
            score += 5
        
        # 条件 3: 突破信号（25 分）- 降低 2%
        daily_return = (df['close'].iloc[-1] - df['open'].iloc[-1]) / df['open'].iloc[-1]
        
        if daily_return > 0.03:  # 从 0.05 降低到 0.03
            score += 25
        elif daily_return > 0.02:
            score += 15
        elif daily_return > 0.01:
            score += 5
        
        # 条件 4: 相对强度（25 分）- 降低 2%
        stock_return = df['close'].iloc[-1] / df['close'].iloc[-20] - 1
        benchmark_return = get_benchmark_return(context)
        
        if stock_return > benchmark_return + 0.03:  # 从 0.05 降低到 0.03
            score += 25
        elif stock_return > benchmark_return + 0.01:
            score += 15
        elif stock_return > benchmark_return:
            score += 5
        
        return score
        
    except Exception as e:
        log.debug(f"股票{stock}评分失败：{e}")
        return 0
```

### 2. 市场环境判断

```python
class MarketStateAnalyzer:
    """市场状态分析器"""
    
    def __init__(self):
        self.benchmark = '000300.SS'  # 沪深 300
    
    def analyze_market_state(self, context):
        """分析市场状态"""
        
        benchmark_df = get_price(self.benchmark, count=120, frequency='1d', fields=['close'])
        
        if benchmark_df.empty:
            return "unknown"
        
        ma20 = benchmark_df['close'].iloc[-20:].mean()
        ma60 = benchmark_df['close'].iloc[-60:].mean()
        ma120 = benchmark_df['close'].iloc[-120:].mean()
        current_price = benchmark_df['close'].iloc[-1]
        
        ma20_slope = ma20 / benchmark_df['close'].iloc[-20] - 1
        
        if current_price > ma20 > ma60 > ma120 and ma20_slope > 0.02:
            return "bull"
        elif current_price < ma20 < ma60 < ma120 and ma20_slope < -0.02:
            return "bear"
        else:
            return "neutral"
```

### 3. 退出策略整合

```python
class ExitStrategy:
    """完整退出策略管理器"""
    
    def __init__(self):
        self.profit_taking = ProfitTakingStrategy()
        self.atr_stop = ATRStopLoss()
        self.time_stop = TimeStopLoss()
        self.holding_days = {}
        self.highest_price = {}
    
    def check_exit(self, position, context, data, df):
        """检查退出条件（按优先级）"""
        
        # 1. 固定止损（硬止损，最高优先级）
        if self.check_fixed_stop_loss(position, current_price):
            return (True, 1.0, "固定止损：亏损>8%")
        
        # 2. ATR 吊灯止损
        atr_result = self.atr_stop.check_atr_stop_loss(
            position, current_price, df, market_state
        )
        if atr_result[0]:
            return (True, 1.0, atr_result[2])
        
        # 3. 趋势反转止损
        if self.check_trend_reversal(position, current_price, df):
            return (True, 1.0, "趋势反转：跌破 20 日均线")
        
        # 4. 时间止损
        time_result = self.time_stop.check_time_stop_loss(position, current_price)
        if time_result[0]:
            return (True, 1.0, time_result[1])
        
        # 5. 分级止盈
        profit_result = self.profit_taking.check_take_profit(
            position, current_price, context
        )
        if profit_result[0]:
            return (True, profit_result[1], profit_result[2])
        
        # 6. 移动止盈
        trailing_result = self.profit_taking.check_trailing_stop(
            position, current_price
        )
        if trailing_result[0]:
            return (True, 1.0, trailing_result[1])
        
        return (False, 0, None)
```

---

## 验收标准

### 回测指标要求

| 指标 | 目标值 | 当前值（完整年） |
|------|--------|----------------|
| 总收益率 | > 50% | -31.77% |
| 最大回撤 | < 15% | -41.28% |
| 胜率 | > 55% | 46.5% |
| 盈亏比 | > 1.5 | < 1.0 |

### 分市场验收标准

| 市场类型 | 总收益率 | 最大回撤 | 胜率 |
|---------|---------|---------|------|
| **震荡市** | > 15% | < 12% | > 50% |
| **牛市** | > 40% | < 15% | > 55% |
| **完整年** | > 20% | < 15% | > 50% |

### 功能验收

- ✅ 选股评分分布合理（平均分 40-45 分）
- ✅ 市场环境判断准确（牛/熊/震荡识别）
- ✅ 动态仓位生效（根据市场状态调整）
- ✅ 分级止盈执行正确（15%/25%/45%/70%）
- ✅ 移动止盈保护利润（高点回撤 12%/8%）
- ✅ ATR 止损动态调整（1.5-2.5 倍）
- ✅ 时间止损生效（25 天收益<5%）
- ✅ 回撤控制生效（-15%/-20%/-30%）

---

## 参考文档

- **设计文档**: [trends_up_v4_fix_plan.md](file:///c:/Users/Admin/SynologyDrive/PtradeProjects/SimTradeLab/docs/trends_up_v4_fix_plan.md)
- **QA 诊断报告**: [trends_up_v4_backtest_diagnosis_report.md](file:///c:/Users/Admin/SynologyDrive/PtradeProjects/workspace_qa/trends_up_v4_backtest_diagnosis_report.md)
- **QA 总结报告**: [trends_up_v4_diagnosis_summary.md](file:///c:/Users/Admin/SynologyDrive/PtradeProjects/workspace_qa/trends_up_v4_diagnosis_summary.md)

---

## 交付物

1. ✅ 完整的策略代码（trends_up_v4_fix.py）
2. ✅ 回测结果报告（三个市场周期）
3. ✅ 代码自测报告
4. ✅ 提交 @Strategy-QA 审查

---

## 时间安排

- **开始日期**: 2026-03-28
- **预计完成**: 2026-03-29（1 个工作日）
- **QA 审查**: 2026-03-30

---

**负责人**: @Strategy-Engr  
**创建人**: Strategy-Arch  
**状态**: 待开始  
**最后更新**: 2026-03-28

# Trends_Up v4.0 紧急修复方案

**版本**: v4.0 Fix  
**创建日期**: 2026-03-28  
**策略类型**: 趋势跟踪 + 动态风控  
**适用市场**: A 股  
**优先级**: 🔴 P0（紧急修复）

---

## 1. 策略概述

### 1.1 问题背景

根据 QA 诊断报告（[完整报告](file:///c:/Users/Admin/SynologyDrive/PtradeProjects/workspace_qa/trends_up_v4_backtest_diagnosis_report.md)），trends_up v4.0 策略在回测中全面失败：

| 市场类型 | 总收益率 | 最大回撤 | 胜率 | 目标收益率 | 达标情况 |
|---------|---------|---------|------|-----------|---------|
| **震荡市** | **-33.45%** | -33.45% | 36.6% | > 50% | ❌ 严重不达标 |
| **牛市** | **+12.59%** | -20.20% | 54.4% | > 50% | ❌ 不达标 |
| **完整年** | **-31.77%** | -41.28% | 46.5% | > 50% | ❌ 严重不达标 |

### 1.2 修复目标

| 指标 | 目标值 | 当前值（完整年） | 改善幅度 |
|------|--------|----------------|---------|
| 总收益率 | > 50% | -31.77% | +80%+ |
| 最大回撤 | < 15% | -41.28% | -26%+ |
| 胜率 | > 55% | 46.5% | +8.5%+ |
| 盈亏比 | > 1.5 | < 1.0 | +50%+ |

### 1.3 基本信息

| 项目 | 值 |
|------|-----|
| 策略名称 | trends_up_v4_fix |
| 策略类型 | 趋势跟踪 + 动态风控 |
| 交易标的 | A 股主板股票（剔除 ST、科创板、创业板） |
| 回测周期 | 震荡市：2025-04-01 ~ 2025-07-31<br>牛市：2024-09-01 ~ 2024-12-31<br>完整年：2024-01-01 ~ 2024-12-31 |
| 初始资金 | 1,000,000 元 |
| 交易频率 | 日线级别调仓 |
| 持仓数量 | 动态调整（5-15 只） |

---

## 2. 核心问题与修复方案

### 2.1 问题清单（按严重程度）

| 排名 | 问题 | 严重程度 | 对收益影响 | 修复方案 |
|------|------|---------|-----------|---------|
| 1 | **选股评分标准过严** | ⭐⭐⭐⭐⭐ | -40% | 放宽阈值 + 降低门槛 |
| 2 | **无市场环境判断** | ⭐⭐⭐⭐⭐ | -30% | 添加牛熊判断 + 动态仓位 |
| 3 | **止盈策略缺失** | ⭐⭐⭐⭐⭐ | -20% | 分级止盈 + 移动止盈 |
| 4 | **动态仓位缺失** | ⭐⭐⭐⭐ | -15% | 根据市场状态调整 |
| 5 | **ATR 止损参数不合理** | ⭐⭐⭐⭐ | -10% | 优化 ATR 倍数到 2.0 |
| 6 | **时间止损缺失** | ⭐⭐⭐ | -5% | 25 天收益<5% 时间止损 |

---

## 3. 详细修复方案

### 3.1 选股系统优化（P0）⭐⭐⭐⭐⭐

#### 3.1.1 当前评分标准（过于严格）

```python
# 横盘整理（25 分）
consolidation_ratio < 0.2:  25 分  # 60 日波动率<20% ❌ 过严
consolidation_ratio < 0.3:  15 分
consolidation_ratio < 0.4:  5 分

# 成交量萎缩（25 分）
volume_ratio < 0.7:  25 分  # 20 日均量/60 日均量<0.7 ❌ 过严
volume_ratio < 0.8:  15 分
volume_ratio < 0.9:  5 分

# 突破信号（25 分）
daily_return > 0.05:  25 分  # 单日涨幅>5% ❌ 过严
daily_return > 0.03:  15 分
daily_return > 0.01:  5 分

# 相对强度（25 分）
stock_return > benchmark + 0.05:  25 分  # 20 日超额收益>5% ❌ 过严
stock_return > benchmark + 0.02:  15 分
stock_return > benchmark:  5 分
```

**问题分析**:
- **横盘整理 < 20%**: A 股个股 60 日波动率普遍在 30-50%，<20% 只占 5%
- **成交量萎缩 < 0.7**: 正常股票成交量比率在 0.8-1.2，<0.7 只占 10%
- **突破信号 > 5%**: 震荡市单日涨幅>5% 的股票仅 3-8%
- **相对强度 +5%**: 20 日跑赢大盘 5% 意味着年化超额收益>100%，只有 10% 股票能达到

**综合影响**:
```
平均分估算：25 分（满分 100 分）
- 横盘整理平均分：5.5 分
- 成交量萎缩平均分：7.0 分
- 突破信号平均分：5.25 分
- 相对强度平均分：7.25 分
```

#### 3.1.2 优化后评分标准（放宽 10-20%）

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
        
        if consolidation_ratio < 0.30:  # 从 0.20 放宽到 0.30 (+50%)
            score += 25
        elif consolidation_ratio < 0.40:  # 从 0.30 放宽到 0.40 (+33%)
            score += 15
        elif consolidation_ratio < 0.50:  # 从 0.40 放宽到 0.50 (+25%)
            score += 5
        
        # 条件 2: 成交量萎缩（25 分）- 放宽 0.1
        avg_volume_20d = df['volume'].iloc[-20:].mean()
        avg_volume_60d = df['volume'].iloc[-65:-1].mean()
        volume_ratio = avg_volume_20d / avg_volume_60d
        
        if volume_ratio < 0.80:  # 从 0.70 放宽到 0.80 (+14%)
            score += 25
        elif volume_ratio < 0.90:  # 从 0.80 放宽到 0.90 (+12.5%)
            score += 15
        elif volume_ratio < 1.00:  # 从 0.90 放宽到 1.00 (+11%)
            score += 5
        
        # 条件 3: 突破信号（25 分）- 降低 2%
        daily_return = (df['close'].iloc[-1] - df['open'].iloc[-1]) / df['open'].iloc[-1]
        
        if daily_return > 0.03:  # 从 0.05 降低到 0.03 (-40%)
            score += 25
        elif daily_return > 0.02:  # 从 0.03 降低到 0.02 (-33%)
            score += 15
        elif daily_return > 0.01:
            score += 5
        
        # 条件 4: 相对强度（25 分）- 降低 2%
        stock_return = df['close'].iloc[-1] / df['close'].iloc[-20] - 1
        benchmark_return = get_benchmark_return(context)
        
        if stock_return > benchmark_return + 0.03:  # 从 0.05 降低到 0.03 (-40%)
            score += 25
        elif stock_return > benchmark_return + 0.01:  # 从 0.02 降低到 0.01 (-50%)
            score += 15
        elif stock_return > benchmark_return:
            score += 5
        
        return score
        
    except Exception as e:
        log.debug(f"股票{stock}评分失败：{e}")
        return 0
```

#### 3.1.3 选股门槛调整

```python
# 从 >= 60 分降低到 >= 35 分
selected_stocks = [s[0] for s in sorted_stocks[:10] if s[1] >= 35]
```

**预期效果**:
- 平均分：25 分 → 40-45 分
- 40 分以上股票：10% → 40-50%
- 选股成功率：0% → 85-95%
- 选股质量：保持中上水平

---

### 3.2 市场环境判断（P0）⭐⭐⭐⭐⭐

#### 3.2.1 市场状态识别逻辑

```python
class MarketStateAnalyzer:
    """市场状态分析器"""
    
    def __init__(self):
        self.benchmark = '000300.SS'  # 沪深 300
    
    def analyze_market_state(self, context):
        """
        分析市场状态
        
        返回:
            str: 'bull' (牛市), 'neutral' (震荡市), 'bear' (熊市), 'unknown'
        """
        
        # 获取基准指数
        benchmark_df = get_price(self.benchmark, count=120, frequency='1d', fields=['close'])
        
        if benchmark_df.empty:
            return "unknown"
        
        # 计算均线
        ma20 = benchmark_df['close'].iloc[-20:].mean()
        ma60 = benchmark_df['close'].iloc[-60:].mean()
        ma120 = benchmark_df['close'].iloc[-120:].mean()
        current_price = benchmark_df['close'].iloc[-1]
        
        # 计算均线斜率
        ma20_slope = ma20 / benchmark_df['close'].iloc[-20] - 1
        ma60_slope = ma60 / benchmark_df['close'].iloc[-60] - 1
        
        # 判断市场状态
        if current_price > ma20 > ma60 > ma120 and ma20_slope > 0.02:
            # 牛市：价格在所有均线上方，且均线多头排列
            return "bull"
        elif current_price < ma20 < ma60 < ma120 and ma20_slope < -0.02:
            # 熊市：价格在所有均线下方，且均线空头排列
            return "bear"
        else:
            # 震荡市：其他情况
            return "neutral"
    
    def get_market_trend_score(self, context):
        """
        计算市场趋势评分（0-1）
        
        返回:
            float: 趋势评分（1=强牛市，0.5=震荡市，0=强熊市）
        """
        market_state = self.analyze_market_state(context)
        
        if market_state == "bull":
            return 0.8
        elif market_state == "neutral":
            return 0.5
        elif market_state == "bear":
            return 0.2
        else:
            return 0.5  # 未知情况默认中性
```

#### 3.2.2 市场状态特征

| 市场状态 | 均线排列 | 20 日斜率 | 仓位建议 | 操作策略 |
|---------|---------|---------|---------|---------|
| **牛市** | 价格>MA20>MA60>MA120 | > +2% | 80-100% | 满仓操作，积极选股 |
| **震荡市** | 均线交织 | -2% ~ +2% | 50-70% | 精选个股，快进快出 |
| **熊市** | 价格<MA20<MA60<MA120 | < -2% | 0-20% | 空仓避险，轻仓试错 |

---

### 3.3 动态仓位管理（P1）⭐⭐⭐⭐

#### 3.3.1 仓位管理逻辑

```python
class PositionManager:
    """动态仓位管理器"""
    
    def __init__(self):
        self.market_state = "neutral"
        self.consecutive_losses = 0
        self.max_positions = 10
    
    def calculate_position_size(self, trend_score, market_state):
        """
        计算仓位大小
        
        参数:
            trend_score: 个股趋势评分（0-1）
            market_state: 市场状态（'bull', 'neutral', 'bear'）
        
        返回:
            float: 单只股票仓位比例（0-0.20）
        """
        
        # 基础仓位根据市场状态
        base_positions = {
            "bull": 0.15,      # 牛市 15%（最多 6-7 只）
            "neutral": 0.10,   # 震荡市 10%（最多 10 只）
            "bear": 0.05,      # 熊市 5%（最多 20 只，但实际很少选股）
        }
        
        base = base_positions.get(market_state, 0.10)
        
        # 根据趋势评分调整
        if trend_score >= 0.7:
            multiplier = 1.0   # 强势趋势，满仓
        elif trend_score >= 0.5:
            multiplier = 0.8   # 中强势，8 折
        elif trend_score >= 0.35:
            multiplier = 0.6   # 中等，6 折
        else:
            multiplier = 0.4   # 弱势，4 折
        
        # 熊市额外限制
        if market_state == "bear":
            multiplier = min(multiplier, 0.5)
        
        return min(base * multiplier, 0.20)  # 单股不超过 20%
    
    def calculate_max_positions(self, market_state, trend_score):
        """
        计算最大持仓数量
        
        返回:
            int: 最大持仓数（5-15）
        """
        base_max = {
            "bull": 12,        # 牛市最多 12 只
            "neutral": 10,     # 震荡市 10 只
            "bear": 5,         # 熊市最多 5 只
        }
        
        base = base_max.get(market_state, 10)
        
        # 根据趋势评分微调
        if trend_score >= 0.6:
            return min(base + 2, 15)
        elif trend_score >= 0.4:
            return base
        else:
            return max(base - 2, 5)
    
    def check_drawdown_control(self, context):
        """
        回撤控制
        
        返回:
            bool: 是否允许开新仓
        """
        
        if not hasattr(context.portfolio, 'portfolio_value_history'):
            return True
        
        peak_value = max(context.portfolio.portfolio_value_history)
        current_value = context.portfolio.portfolio_value
        drawdown = (current_value - peak_value) / peak_value
        
        if drawdown < -0.30:  # 回撤>30%
            self.max_positions = 0  # 强制空仓
            log.critical(f"强制空仓：回撤{drawdown:.2%}")
            return False
        
        elif drawdown < -0.20:  # 回撤>20%
            self.max_positions = 3  # 限制到 3 只
            log.warning(f"限制仓位：回撤{drawdown:.2%}")
            return True
        
        elif drawdown < -0.15:  # 回撤>15%
            self.max_positions = 5  # 限制到 5 只
            log.info(f"降低仓位：回撤{drawdown:.2%}")
            return True
        
        else:
            # 根据市场状态恢复
            self.max_positions = {
                "bull": 12,
                "neutral": 10,
                "bear": 5,
            }.get(self.market_state, 10)
            return True
```

#### 3.3.2 仓位配置表

| 市场状态 | 基础仓位 | 趋势评分 0.7+ | 趋势评分 0.5-0.7 | 趋势评分 0.35-0.5 | 趋势评分<0.35 |
|---------|---------|-------------|----------------|-----------------|-------------|
| **牛市** | 15% | 15% | 12% | 9% | 6% |
| **震荡市** | 10% | 10% | 8% | 6% | 4% |
| **熊市** | 5% | 2.5% | 2% | 1.5% | 1% |

---

### 3.4 止盈策略（P0）⭐⭐⭐⭐⭐

#### 3.4.1 分级止盈逻辑

```python
class ProfitTakingStrategy:
    """止盈策略管理器"""
    
    def __init__(self):
        self.highest_price = {}  # 记录持仓期间最高价
    
    def check_take_profit(self, position, current_price, context):
        """
        检查止盈条件
        
        返回:
            tuple: (是否止盈，止盈比例，原因)
        """
        stock = position.stock
        cost_basis = position.cost_basis
        profit = (current_price - cost_basis) / cost_basis
        
        # 更新最高价记录
        if stock not in self.highest_price:
            self.highest_price[stock] = current_price
        else:
            self.highest_price[stock] = max(self.highest_price[stock], current_price)
        
        # 分级止盈
        if profit >= 0.70:
            # 收益>70%，清仓
            return (True, 1.0, "止盈：收益>70%")
        
        elif profit >= 0.45:
            # 收益>45%，卖出 50%
            return (True, 0.5, "止盈：收益>45%，卖出 50%")
        
        elif profit >= 0.25:
            # 收益>25%，卖出 30%
            return (True, 0.3, "止盈：收益>25%，卖出 30%")
        
        elif profit >= 0.15:
            # 收益>15%，卖出 20%
            return (True, 0.2, "止盈：收益>15%，卖出 20%")
        
        return (False, 0, None)
    
    def check_trailing_stop(self, position, current_price):
        """
        移动止盈（高点回撤保护）
        
        返回:
            tuple: (是否止盈，原因)
        """
        stock = position.stock
        cost_basis = position.cost_basis
        
        # 只有盈利>10% 才启动移动止盈
        if (current_price - cost_basis) / cost_basis < 0.10:
            return (False, None)
        
        # 获取最高价
        highest = self.highest_price.get(stock, cost_basis)
        
        # 计算回撤
        drawdown_from_high = (highest - current_price) / highest
        
        # 高点回撤超过 12% 则止盈
        if drawdown_from_high > 0.12:
            return (True, f"移动止盈：高点回撤{drawdown_from_high:.1%}")
        
        # 如果收益>30%，回撤阈值收紧到 8%
        if (current_price - cost_basis) / cost_basis >= 0.30:
            if drawdown_from_high > 0.08:
                return (True, f"移动止盈：高收益回撤{drawdown_from_high:.1%}")
        
        return (False, None)
```

#### 3.4.2 止盈策略配置

| 盈利幅度 | 止盈动作 | 剩余仓位 | 移动止盈回撤阈值 |
|---------|---------|---------|----------------|
| **+15%** | 卖出 20% | 80% | 12% |
| **+25%** | 卖出 30% | 50% | 12% |
| **+45%** | 卖出 50% | 20% | 10% |
| **+70%** | 清仓 100% | 0% | - |
| **任意盈利>10%** | - | - | 高点回撤 12% 触发 |
| **盈利>30%** | - | - | 高点回撤 8% 触发 |

---

### 3.5 ATR 止损优化（P1）⭐⭐⭐⭐

#### 3.5.1 ATR 动态止损逻辑

```python
class ATRStopLoss:
    """ATR 动态止损器"""
    
    def __init__(self):
        self.atr_multiplier = 2.0  # 从 3.0 降低到 2.0
    
    def calculate_atr(self, df, period=14):
        """计算 ATR"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr.iloc[-1]
    
    def check_atr_stop_loss(self, position, current_price, df, market_state):
        """
        ATR 吊灯止损
        
        返回:
            tuple: (是否止损，止损价格，原因)
        """
        if len(df) < 20:
            return (False, 0, None)
        
        # 计算 ATR
        atr = self.calculate_atr(df, period=14)
        
        # 动态调整 ATR 倍数
        atr_multiplier = self.get_dynamic_atr_multiplier(market_state)
        
        # 吊灯止损：最高点回撤 N 倍 ATR
        highest_high = df['high'].iloc[-20:].max()
        stop_loss_price = highest_high - atr_multiplier * atr
        
        if current_price < stop_loss_price:
            return (True, stop_loss_price, f"ATR 止损：跌破{atr_multiplier}倍 ATR 支撑")
        
        return (False, 0, None)
    
    def get_dynamic_atr_multiplier(self, market_state):
        """
        根据市场状态动态调整 ATR 倍数
        
        返回:
            float: ATR 倍数（1.5-2.5）
        """
        if market_state == "bull":
            return 2.5  # 牛市放宽，避免被洗出
        elif market_state == "neutral":
            return 2.0  # 震荡市标准
        elif market_state == "bear":
            return 1.5  # 熊市收紧，快速止损
        else:
            return 2.0
```

#### 3.5.2 ATR 参数对比

| 市场状态 | 原参数 (3.0 倍) | 新参数 (动态) | 止损空间 | 改善效果 |
|---------|---------------|-------------|---------|---------|
| **牛市** | 3.0 倍 | 2.5 倍 | 5-8% | 减少利润回吐 |
| **震荡市** | 3.0 倍 | 2.0 倍 | 4-6% | 平衡胜率与盈亏比 |
| **熊市** | 3.0 倍 | 1.5 倍 | 3-5% | 快速止损，控制回撤 |

---

### 3.6 时间止损机制（P2）⭐⭐⭐

#### 3.6.1 时间止损逻辑

```python
class TimeStopLoss:
    """时间止损器"""
    
    def __init__(self):
        self.holding_days = {}  # 记录持仓天数
    
    def update_holding_days(self, positions):
        """更新持仓天数"""
        for position in positions:
            stock = position.stock
            if stock not in self.holding_days:
                self.holding_days[stock] = 0
            else:
                self.holding_days[stock] += 1
    
    def check_time_stop_loss(self, position, current_price):
        """
        时间止损
        
        返回:
            tuple: (是否止损，原因)
        """
        stock = position.stock
        holding_days = self.holding_days.get(stock, 0)
        cost_basis = position.cost_basis
        profit = (current_price - cost_basis) / cost_basis
        
        # 规则 1: 25 天收益<5%，时间止损
        if holding_days > 25 and profit < 0.05:
            return (True, f"时间止损：持仓{holding_days}天，收益{profit:.2%}<5%")
        
        # 规则 2: 20 天亏损>5%，强制止损
        if holding_days > 20 and profit < -0.05:
            return (True, f"强制时间止损：持仓{holding_days}天，亏损{profit:.2%}")
        
        # 规则 3: 15 天亏损>10%，紧急止损
        if holding_days > 15 and profit < -0.10:
            return (True, f"紧急时间止损：持仓{holding_days}天，亏损{profit:.2%}")
        
        return (False, None)
    
    def reset_holding_days(self, stock):
        """重置持仓天数（卖出后）"""
        if stock in self.holding_days:
            del self.holding_days[stock]
```

#### 3.6.2 时间止损配置

| 持仓天数 | 收益条件 | 动作 | 说明 |
|---------|---------|------|------|
| **> 25 天** | 收益 < 5% | 时间止损 | 资金效率低，释放资金 |
| **> 20 天** | 亏损 > 5% | 强制止损 | 判断错误，及时离场 |
| **> 15 天** | 亏损 > 10% | 紧急止损 | 严重错误，立即离场 |

---

## 4. 完整退出策略整合

### 4.1 退出策略优先级

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
        """
        检查退出条件（按优先级）
        
        返回:
            tuple: (是否退出，退出比例，原因)
        """
        stock = position.stock
        current_price = data[stock]['close']
        
        # 1. 固定止损（硬止损，最高优先级）
        if self.check_fixed_stop_loss(position, current_price):
            return (True, 1.0, "固定止损：亏损>8%")
        
        # 2. ATR 吊灯止损
        market_state = context.market_state  # 从 context 获取
        atr_result = self.atr_stop.check_atr_stop_loss(
            position, current_price, df, market_state
        )
        if atr_result[0]:
            return (True, 1.0, atr_result[2])
        
        # 3. 趋势反转止损（跌破 20 日均线）
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
        
        # 6. 移动止盈（高点回撤保护）
        trailing_result = self.profit_taking.check_trailing_stop(
            position, current_price
        )
        if trailing_result[0]:
            return (True, 1.0, trailing_result[1])
        
        return (False, 0, None)
    
    def check_fixed_stop_loss(self, position, current_price):
        """固定止损（8% 硬止损）"""
        cost_basis = position.cost_basis
        if (cost_basis - current_price) / cost_basis > 0.08:
            return True
        return False
    
    def check_trend_reversal(self, position, current_price, df):
        """趋势反转止损（跌破 20 日均线）"""
        if len(df) < 20:
            return False
        
        ma20 = df['close'].iloc[-20:].mean()
        if current_price < ma20:
            return True
        return False
```

### 4.2 退出策略执行流程图

```
持仓股票
    ↓
检查固定止损（8% 硬止损）
    ↓ 是 → 清仓
    ↓ 否
检查 ATR 吊灯止损
    ↓ 是 → 清仓
    ↓ 否
检查趋势反转（跌破 MA20）
    ↓ 是 → 清仓
    ↓ 否
检查时间止损
    ↓ 是 → 清仓
    ↓ 否
检查分级止盈
    ↓ 是 → 部分/全部清仓
    ↓ 否
检查移动止盈（高点回撤）
    ↓ 是 → 清仓
    ↓ 否
继续持有
```

---

## 5. SimTradeLab 接口定义

### 5.1 初始化函数

```python
def initialize(context):
    """策略初始化"""
    # 设置基准
    set_benchmark('000300.SS')
    
    # 设置交易成本
    set_commission(0.0003)  # 万三佣金
    set_slippage(0.002)     # 0.2% 滑点
    
    # 设置股票池
    set_universe('ALL')
    
    # 全局变量
    g.max_positions = 10           # 最大持仓数（动态调整）
    g.stop_loss = 0.08             # 固定止损 8%
    
    # 初始化组件
    g.market_analyzer = MarketStateAnalyzer()
    g.position_manager = PositionManager()
    g.exit_strategy = ExitStrategy()
    
    # 记录初始化日期
    g.init_date = context.current_dt
```

### 5.2 盘前处理

```python
def before_trading_start(context):
    """盘前准备：分析市场状态 + 计算选股信号"""
    
    # 1. 分析市场状态
    g.market_state = g.market_analyzer.analyze_market_state(context)
    g.market_trend_score = g.market_analyzer.get_market_trend_score(context)
    
    log.info(f"市场状态：{g.market_state}, 趋势评分：{g.market_trend_score:.2f}")
    
    # 2. 获取全市场股票列表
    all_stocks = get_index_stocks('000906.XBHS')  # 中证全指
    
    # 3. 过滤 ST、科创板、创业板
    filtered_stocks = filter_stocks(all_stocks)
    
    # 4. 计算选股评分
    stock_scores = {}
    for stock in filtered_stocks[:500]:  # 限制计算量
        score = score_stock_optimized(stock, context)
        if score > 0:
            stock_scores[stock] = score
    
    # 5. 选择前 N 只（至少 35 分）
    sorted_stocks = sorted(stock_scores.items(), key=lambda x: x[1], reverse=True)
    g.selected_stocks = [s[0] for s in sorted_stocks[:15] if s[1] >= 35]
    
    # 6. 根据市场状态调整最大持仓数
    g.max_positions = g.position_manager.calculate_max_positions(
        g.market_state, g.market_trend_score
    )
    
    log.info(f"选股数量：{len(g.selected_stocks)}, 最大持仓：{g.max_positions}")
    
    # 7. 记录评分分布
    if sorted_stocks:
        log.info(f"最高分：{sorted_stocks[0][1]}, 平均分：{sum(s[1] for s in sorted_stocks)/len(sorted_stocks):.1f}")
```

### 5.3 盘中处理

```python
def handle_data(context, data):
    """主交易逻辑"""
    # 获取持仓
    positions = get_positions()
    
    # 1. 更新持仓天数
    for position in positions:
        stock = position.stock
        if stock not in g.exit_strategy.holding_days:
            g.exit_strategy.holding_days[stock] = 0
        else:
            g.exit_strategy.holding_days[stock] += 1
    
    # 2. 检查退出条件
    for position in positions:
        stock = position.stock
        
        # 获取历史数据
        df = get_price(stock, count=65, frequency='1d', 
                      fields=['open', 'high', 'low', 'close', 'volume'])
        
        # 检查退出
        should_exit, exit_ratio, reason = g.exit_strategy.check_exit(
            position, context, data, df
        )
        
        if should_exit:
            if exit_ratio == 1.0:
                # 清仓
                order_target(stock, 0)
                log.info(f"清仓：{stock}, 原因：{reason}")
                g.exit_strategy.holding_days.pop(stock, None)
                g.exit_strategy.highest_price.pop(stock, None)
            else:
                # 部分止盈
                current_amount = position.amount
                sell_amount = int(current_amount * exit_ratio)
                if sell_amount > 0:
                    order(stock, -sell_amount)
                    log.info(f"部分止盈：{stock}, 卖出{exit_ratio:.0%}, 原因：{reason}")
    
    # 3. 检查回撤控制
    if not g.position_manager.check_drawdown_control(context):
        # 强制空仓，卖出所有持仓
        for position in positions:
            order_target(position.stock, 0)
        return
    
    # 4. 买入新股票
    if len(positions) < g.max_positions:
        # 过滤已持仓股票
        buy_candidates = [s for s in g.selected_stocks 
                         if s not in [p.stock for p in positions]]
        
        # 计算仓位
        for stock in buy_candidates[:g.max_positions - len(positions)]:
            # 获取趋势评分（简化版，实际应从评分系统获取）
            trend_score = 0.5  # 默认中等
            
            # 计算仓位大小
            position_size = g.position_manager.calculate_position_size(
                trend_score, g.market_state
            )
            
            # 计算买入金额
            target_value = context.portfolio.portfolio_value * position_size
            
            # 检查资金
            if context.portfolio.cash >= target_value * 1.05:  # 5% 缓冲
                order_value(stock, target_value)
                log.info(f"买入：{stock}, 仓位：{position_size:.1%}")
```

### 5.4 辅助函数

```python
def filter_stocks(stocks):
    """过滤 ST、科创板、创业板股票"""
    filtered = []
    for stock in stocks:
        # 剔除科创板 (688 开头)
        if stock.startswith('688'):
            continue
        # 剔除创业板 (300 开头)
        if stock.startswith('300'):
            continue
        # 剔除 ST 股票
        if 'ST' in stock:
            continue
        filtered.append(stock)
    return filtered

def get_benchmark_return(context):
    """获取基准收益率（20 日）"""
    benchmark_df = get_price('000300.SS', count=25, frequency='1d', fields=['close'])
    if benchmark_df.empty or len(benchmark_df) < 20:
        return 0
    
    return benchmark_df['close'].iloc[-1] / benchmark_df['close'].iloc[-20] - 1
```

---

## 6. 数据需求

### 6.1 必需数据

| 数据类型 | 用途 | 频率 | 备注 |
|---------|------|------|------|
| 日线价格（OHLCV） | 计算技术指标、评分 | 日频 | 至少 65 天历史 |
| 基准指数（000300.SS） | 市场状态判断、相对强度 | 日频 | 至少 120 天历史 |

### 6.2 数据质量要求

- **价格数据**: 无缺失、无异常值
- **复权处理**: 使用后复权价格
- **成交量**: 真实成交量（非手）

---

## 7. 风险控制

### 7.1 个股风险

| 风险类型 | 控制措施 | 阈值 |
|---------|---------|------|
| **价格风险** | 固定止损 + ATR 止损 | 8% 硬止损 / 2 倍 ATR |
| **趋势风险** | 趋势反转止损 | 跌破 20 日均线 |
| **时间风险** | 时间止损 | 25 天收益<5% |
| **波动风险** | 动态 ATR 倍数 | 1.5-2.5 倍 ATR |

### 7.2 组合风险

| 风险类型 | 控制措施 | 阈值 |
|---------|---------|------|
| **回撤风险** | 回撤控制机制 | -15% 降仓 / -30% 空仓 |
| **集中度风险** | 单股仓位限制 | 单股不超过 20% |
| **市场风险** | 动态仓位管理 | 熊市最低 5% 仓位 |

### 7.3 系统性风险

| 市场状态 | 仓位上限 | 操作策略 |
|---------|---------|---------|
| **牛市** | 100% | 满仓操作，积极选股 |
| **震荡市** | 70% | 精选个股，快进快出 |
| **熊市** | 20% | 空仓避险，轻仓试错 |

---

## 8. 验收标准

### 8.1 回测指标要求

| 指标 | 目标值 | 当前值（完整年） | 改善幅度 |
|------|--------|----------------|---------|
| 总收益率 | > 50% | -31.77% | +80%+ |
| 年化收益率 | > 30% | - | - |
| 夏普比率 | > 1.0 | - | - |
| 最大回撤 | < 15% | -41.28% | -26%+ |
| 胜率 | > 55% | 46.5% | +8.5%+ |
| 盈亏比 | > 1.5 | < 1.0 | +50%+ |

### 8.2 分市场验收标准

| 市场类型 | 总收益率 | 最大回撤 | 胜率 | 测试周期 |
|---------|---------|---------|------|---------|
| **震荡市** | > 15% | < 12% | > 50% | 2025-04-01 ~ 2025-07-31 |
| **牛市** | > 40% | < 15% | > 55% | 2024-09-01 ~ 2024-12-31 |
| **完整年** | > 20% | < 15% | > 50% | 2024-01-01 ~ 2024-12-31 |

### 8.3 功能验收

- ✅ 选股评分分布合理（平均分 40-45 分）
- ✅ 市场环境判断准确（牛/熊/震荡识别）
- ✅ 动态仓位生效（根据市场状态调整）
- ✅ 分级止盈执行正确（15%/25%/45%/70%）
- ✅ 移动止盈保护利润（高点回撤 12%/8%）
- ✅ ATR 止损动态调整（1.5-2.5 倍）
- ✅ 时间止损生效（25 天收益<5%）
- ✅ 回撤控制生效（-15%/-20%/-30%）

### 8.4 性能要求

- **回测速度**: < 5 分钟（完整年回测）
- **内存占用**: < 2GB
- **选股成功率**: > 85%

---

## 9. 参数配置汇总

### 9.1 选股评分参数

```python
# 横盘整理阈值
CONSOLIDATION_THRESHOLDS = [0.30, 0.40, 0.50]  # 从 [0.20, 0.30, 0.40] 放宽
CONSOLIDATION_SCORES = [25, 15, 5]

# 成交量萎缩阈值
VOLUME_RATIO_THRESHOLDS = [0.80, 0.90, 1.00]  # 从 [0.70, 0.80, 0.90] 放宽
VOLUME_RATIO_SCORES = [25, 15, 5]

# 突破信号阈值
DAILY_RETURN_THRESHOLDS = [0.03, 0.02, 0.01]  # 从 [0.05, 0.03, 0.01] 降低
DAILY_RETURN_SCORES = [25, 15, 5]

# 相对强度阈值
RELATIVE_STRENGTH_THRESHOLDS = [0.03, 0.01, 0.00]  # 从 [0.05, 0.02, 0.00] 降低
RELATIVE_STRENGTH_SCORES = [25, 15, 5]

# 选股门槛
MIN_SCORE_THRESHOLD = 35  # 从 60 分降低到 35 分
```

### 9.2 仓位管理参数

```python
# 基础仓位
BASE_POSITIONS = {
    "bull": 0.15,      # 牛市 15%
    "neutral": 0.10,   # 震荡市 10%
    "bear": 0.05,      # 熊市 5%
}

# 最大持仓数
MAX_POSITIONS = {
    "bull": 12,        # 牛市 12 只
    "neutral": 10,     # 震荡市 10 只
    "bear": 5,         # 熊市 5 只
}

# 趋势评分乘数
TREND_SCORE_MULTIPLIERS = {
    0.7: 1.0,
    0.5: 0.8,
    0.35: 0.6,
    0.0: 0.4,
}
```

### 9.3 退出策略参数

```python
# 固定止损
FIXED_STOP_LOSS = 0.08  # 8% 硬止损

# ATR 止损
ATR_MULTIPLIERS = {
    "bull": 2.5,       # 牛市 2.5 倍
    "neutral": 2.0,    # 震荡市 2.0 倍
    "bear": 1.5,       # 熊市 1.5 倍
}

# 分级止盈
PROFIT_TAKING_LEVELS = [
    (0.70, 1.0),   # 收益>70%，清仓
    (0.45, 0.5),   # 收益>45%，卖出 50%
    (0.25, 0.3),   # 收益>25%，卖出 30%
    (0.15, 0.2),   # 收益>15%，卖出 20%
]

# 移动止盈
TRAILING_STOP_THRESHOLD = 0.12  # 高点回撤 12%
TRAILING_STOP_HIGH_PROFIT_THRESHOLD = 0.30  # 收益>30%
TRAILING_STOP_HIGH_PROFIT_DRAWNDOWN = 0.08  # 高点回撤 8%

# 时间止损
TIME_STOP_DAYS_1 = 25
TIME_STOP_PROFIT_1 = 0.05
TIME_STOP_DAYS_2 = 20
TIME_STOP_PROFIT_2 = -0.05
TIME_STOP_DAYS_3 = 15
TIME_STOP_PROFIT_3 = -0.10
```

### 9.4 回撤控制参数

```python
# 回撤控制
DRAWDOWN_LEVELS = [
    (-0.30, 0),    # 回撤>30%，强制空仓
    (-0.20, 3),    # 回撤>20%，限制 3 只
    (-0.15, 5),    # 回撤>15%，限制 5 只
]
```

---

## 10. 优化方向

### 10.1 短期优化（P1）

1. **参数敏感性测试**
   - ATR 倍数测试：[1.5, 2.0, 2.5, 3.0]
   - 止盈阈值测试：[10%, 15%, 20%]
   - 时间止损天数测试：[15, 20, 25, 30]

2. **选股因子优化**
   - 添加动量因子（10 日/20 日动量）
   - 添加波动率因子（ATR/收盘价）
   - 添加资金流因子（主力净流入）

3. **市场状态细化**
   - 强牛/弱牛/震荡/弱熊/强熊
   - 添加市场情绪指标（成交量、换手率）

### 10.2 长期优化（P2）

1. **机器学习优化**
   - 使用历史数据训练最优评分权重
   - 预测市场状态转换概率
   - 动态调整止盈止损参数

2. **行业分散**
   - 限制单一行业持仓比例（<30%）
   - 行业轮动策略
   - 行业景气度评分

3. **风险控制增强**
   - 添加 VaR 风险价值指标
   - 添加相关性控制（持仓股票相关性<0.7）
   - 添加流动性风险控制

---

## 11. 任务分解

### 11.1 开发任务

| 任务 ID | 任务描述 | 负责人 | 优先级 | 状态 |
|--------|---------|--------|--------|------|
| TASK-V4FIX-001 | 实现优化版评分系统（放宽阈值） | @Strategy-Engr | P0 | 待开始 |
| TASK-V4FIX-002 | 实现 MarketStateAnalyzer 类 | @Strategy-Engr | P0 | 待开始 |
| TASK-V4FIX-003 | 实现 PositionManager 类（动态仓位） | @Strategy-Engr | P0 | 待开始 |
| TASK-V4FIX-004 | 实现 ExitStrategy 类（完整退出策略） | @Strategy-Engr | P0 | 待开始 |
| TASK-V4FIX-005 | 实现分级止盈逻辑 | @Strategy-Engr | P0 | 待开始 |
| TASK-V4FIX-006 | 实现移动止盈逻辑 | @Strategy-Engr | P0 | 待开始 |
| TASK-V4FIX-007 | 实现时间止损逻辑 | @Strategy-Engr | P1 | 待开始 |
| TASK-V4FIX-008 | 实现 ATR 动态止损 | @Strategy-Engr | P1 | 待开始 |
| TASK-V4FIX-009 | 集成所有组件到主策略 | @Strategy-Engr | P0 | 待开始 |
| TASK-V4FIX-010 | 运行回测验证 | @Strategy-Engr | P0 | 待开始 |

### 11.2 验收任务

| 任务 ID | 任务描述 | 负责人 | 优先级 | 状态 |
|--------|---------|--------|--------|------|
| TASK-V4FIX-101 | 代码审查（代码质量、规范性） | @Strategy-QA | P0 | 待开始 |
| TASK-V4FIX-102 | 验证评分分布（平均分 40-45 分） | @Strategy-QA | P0 | 待开始 |
| TASK-V4FIX-103 | 验证回测结果（收益率、回撤、胜率） | @Strategy-QA | P0 | 待开始 |
| TASK-V4FIX-104 | 验证退出策略（止盈、止损执行） | @Strategy-QA | P1 | 待开始 |
| TASK-V4FIX-105 | 输出 QA 审查报告 | @Strategy-QA | P0 | 待开始 |

---

## 12. 预期优化效果

### 12.1 核心指标改善

| 市场类型 | 当前收益率 | 目标收益率 | 当前回撤 | 目标回撤 | 当前胜率 | 目标胜率 |
|---------|-----------|-----------|---------|---------|---------|---------|
| **震荡市** | -33.45% | +15-25% | -33.45% | < -12% | 36.6% | > 50% |
| **牛市** | +12.59% | +40-60% | -20.20% | < -15% | 54.4% | > 55% |
| **完整年** | -31.77% | +20-40% | -41.28% | < -15% | 46.5% | > 50% |

### 12.2 改善来源分解

| 改善来源 | 对收益率贡献 | 对回撤改善 | 对胜率改善 |
|---------|------------|-----------|-----------|
| **选股优化** | +20% | -5% | +8% |
| **市场判断** | +15% | -15% | +5% |
| **止盈策略** | +10% | -3% | +3% |
| **动态仓位** | +5% | -8% | +2% |
| **ATR 优化** | +3% | -5% | +2% |
| **时间止损** | +2% | -2% | +1% |
| **合计** | **+55%** | **-38%** | **+21%** |

---

## 13. 验证步骤

### 13.1 回测验证

**测试周期**:
1. 震荡市：2025-04-01 ~ 2025-07-31
2. 牛市：2024-09-01 ~ 2024-12-31
3. 完整年：2024-01-01 ~ 2024-12-31

**验证指标**:
- ✅ 总收益率 > 50%（各周期）
- ✅ 最大回撤 < 15%
- ✅ 胜率 > 55%
- ✅ 盈亏比 > 1.5

### 13.2 评分分布验证

**验证代码**:
```python
def analyze_score_distribution(context):
    """分析评分分布"""
    
    all_stocks = get_all_stocks(context)
    filtered_stocks = filter_stocks(all_stocks)
    
    scores = []
    for stock in filtered_stocks[:500]:
        score = score_stock_optimized(stock, context)
        if score > 0:
            scores.append(score)
    
    if not scores:
        log.warning("无股票得分 > 0")
        return
    
    # 统计分布
    log.info(f"评分股票数量：{len(scores)}")
    log.info(f"最高分：{max(scores)}")
    log.info(f"最低分：{min(scores)}")
    log.info(f"平均分：{sum(scores)/len(scores):.1f}")
    log.info(f"中位数：{sorted(scores)[len(scores)//2]}")
    
    # 分数段分布
    score_ranges = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100)]
    for low, high in score_ranges:
        count = len([s for s in scores if low <= s < high])
        log.info(f"{low}-{high}分：{count}只 ({count/len(scores)*100:.1f}%)")
```

**期望结果**:
- 平均分：40-45 分
- 40 分以上股票：40-50%
- 选股成功率：> 85%

### 13.3 退出策略验证

**验证项目**:
- ✅ 固定止损执行率：100%（触发时）
- ✅ ATR 止损执行率：100%（触发时）
- ✅ 分级止盈执行率：100%（触发时）
- ✅ 移动止盈执行率：100%（触发时）
- ✅ 时间止损执行率：100%（触发时）

**验证方法**:
- 回测日志分析
- 交易记录审查
- 退出原因统计

---

## 14. 参考文档

- **QA 诊断报告**: [trends_up_v4_backtest_diagnosis_report.md](file:///c:/Users/Admin/SynologyDrive/PtradeProjects/workspace_qa/trends_up_v4_backtest_diagnosis_report.md)
- **QA 总结报告**: [trends_up_v4_diagnosis_summary.md](file:///c:/Users/Admin/SynologyDrive/PtradeProjects/workspace_qa/trends_up_v4_diagnosis_summary.md)
- **v4 评分诊断**: [trends_up_v4_score_diagnosis_report.md](file:///c:/Users/Admin/SynologyDrive/PtradeProjects/workspace_qa/trends_up_v4_score_diagnosis_report.md)
- **v2 策略文档**: [strategy_trends_up_v2.md](file:///c:/Users/Admin/SynologyDrive/PtradeProjects/SimTradeLab/docs/strategy_trends_up_v2.md)

---

## 15. 附录

### 15.1 关键代码片段

#### 15.1.1 优化版评分函数

参见 [3.1.2 优化后评分标准](#312-优化后评分标准放宽 10-20)

#### 15.1.2 市场状态分析器

参见 [3.2.1 市场状态识别逻辑](#321-市场状态识别逻辑)

#### 15.1.3 完整退出策略

参见 [4.1 退出策略优先级](#41-退出策略优先级)

### 15.2 参数调优建议

**第一轮测试**（基准参数）:
- 使用本文档推荐的默认参数
- 验证策略逻辑正确性

**第二轮测试**（参数敏感性）:
- ATR 倍数：[1.5, 2.0, 2.5]
- 止盈阈值：[10%, 15%, 20%]
- 时间止损：[15, 20, 25] 天

**第三轮测试**（最优参数）:
- 选择各市场环境下最优参数组合
- 验证参数稳健性

---

**文档状态**: ✅ 完成  
**创建时间**: 2026-03-28  
**作者**: Strategy-Arch  
**审核**: 待审核  
**下一步**: 提交 @Strategy-Engr 执行修复

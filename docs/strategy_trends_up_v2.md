# Trends_Up 策略 v2 设计文档

**版本**: v2.0  
**创建日期**: 2026-03-27  
**策略类型**: 趋势跟踪 + 估值筛选  
**适用市场**: A 股  

---

## 1. 策略概述

### 1.1 基本信息

| 项目 | 值 |
|------|-----|
| 策略名称 | trends_up_v2 |
| 策略类型 | 趋势跟踪 + 基本面筛选 |
| 交易标的 | A 股主板股票（剔除 ST、科创板、创业板） |
| 回测周期 | 2025-04-01 至 2025-07-31 |
| 初始资金 | 1,000,000 元 |
| 交易频率 | 日线级别调仓 |
| 持仓数量 | 最多 10 只股票 |

### 1.2 策略理念

本策略结合趋势跟踪和估值筛选，旨在：
1. **趋势跟踪**: 捕捉股价上升趋势，顺势而为
2. **估值保护**: 通过基本面筛选避免高估值股票
3. **风险分散**: 多只股票分散投资，降低单一股票风险

---

## 2. 核心逻辑

### 2.1 选股流程（简化版）

```
股票池 → 趋势筛选 → 估值筛选 → 流动性筛选 → 最终候选池
```

#### 2.1.1 趋势筛选（核心）

**条件**:
- 当前收盘价 > 20 日均线
- 20 日均线 > 60 日均线
- 近 20 日涨幅 > 5%（确认上升趋势）

**逻辑**:
```python
close > MA20 > MA60 AND (close - close_20d_ago) / close_20d_ago > 0.05
```

#### 2.1.2 估值筛选（宽松）

**条件**:
- PE(TTM) > 0 且 PE(TTM) < 100（剔除亏损和极端高估值）
- PB > 0 且 PB < 10（剔除极端高估）

**注意**: 估值数据为可选条件，若获取失败则跳过此筛选

#### 2.1.3 流动性筛选

**条件**:
- 日均成交额 > 1 亿元（近 20 日）
- 换手率 > 1%（确保流动性）

### 2.2 入场规则

1. **买入时机**: 每日收盘前（14:55）
2. **买入数量**: 等权重配置，单只股票不超过总资金的 10%
3. **买入条件**: 
   - 股票在候选池中
   - 当前无持仓
   - 有可用资金

### 2.3 出场规则

**止损条件**（满足任一即卖出）:
1. **趋势反转**: 收盘价 < 20 日均线
2. **固定止损**: 亏损达到 8%
3. **持仓超出**: 持仓数量 > 10 只时，卖出最弱的股票

**止盈条件**:
- 不设固定止盈，让利润奔跑
- 若趋势反转则自动离场

### 2.4 仓位管理

- **单只股票**: 不超过 10% 仓位
- **最大持仓**: 10 只股票
- **仓位控制**: 满仓操作，不主动择时

---

## 3. SimTradeLab 接口定义

### 3.1 初始化函数

```python
def initialize(context):
    """策略初始化"""
    # 设置基准
    set_benchmark('000300.SS')
    
    # 设置交易成本
    set_commission(0.0003)  # 万三佣金
    set_slippage(0.002)     # 0.2% 滑点
    
    # 设置股票池（全市场，后续动态筛选）
    set_universe('ALL')
    
    # 全局变量
    g.max_positions = 10           # 最大持仓数
    g.stock_weight = 0.1           # 单只股票权重 10%
    g.stop_loss = 0.08             # 止损 8%
    g.ma_short = 20                # 短期均线
    g.ma_long = 60                 # 长期均线
```

### 3.2 盘前处理

```python
def before_trading_start(context):
    """盘前准备：计算选股信号"""
    # 获取全市场股票列表
    all_stocks = get_index_stocks('000906.XBHS')  # 中证全指
    
    # 过滤掉 ST、科创板、创业板
    filtered_stocks = filter_stocks(all_stocks)
    
    # 计算趋势信号
    trend_stocks = []
    for stock in filtered_stocks:
        if check_trend(stock, context):
            trend_stocks.append(stock)
    
    # 估值筛选（可选）
    value_stocks = filter_by_valuation(trend_stocks, context)
    
    # 保存候选池到全局变量
    g.candidate_pool = value_stocks if value_stocks else trend_stocks
```

### 3.3 盘中处理

```python
def handle_data(context, data):
    """主交易逻辑"""
    # 获取持仓
    positions = get_positions()
    
    # 1. 检查止损
    for pos in positions:
        if check_stop_loss(pos, context, data):
            order_target(pos.stock, 0)
    
    # 2. 检查趋势反转
    for pos in positions:
        if not check_trend(pos.stock, context):
            order_target(pos.stock, 0)
    
    # 3. 买入新股票
    if len(positions) < g.max_positions:
        buy_candidates = [s for s in g.candidate_pool 
                         if s not in [p.stock for p in positions]]
        
        for stock in buy_candidates[:g.max_positions - len(positions)]:
            if context.portfolio.cash > context.portfolio.portfolio_value * g.stock_weight:
                order_value(stock, context.portfolio.portfolio_value * g.stock_weight)
```

### 3.4 盘后处理

```python
def after_trading_end(context):
    """盘后统计"""
    # 记录当日持仓和收益
    pass
```

### 3.5 辅助函数

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

def check_trend(stock, context):
    """检查趋势条件"""
    # 获取历史数据
    df = get_price(stock, count=65, frequency='1d', fields=['close'])
    if len(df) < 65:
        return False
    
    close = df['close'].iloc[-1]
    ma20 = df['close'].iloc[-20:].mean()
    ma60 = df['close'].iloc[-60:].mean()
    close_20d = df['close'].iloc[-20]
    
    # 趋势条件
    trend_up = close > ma20 > ma60
    momentum = (close - close_20d) / close_20d > 0.05
    
    return trend_up and momentum

def filter_by_valuation(stocks, context):
    """估值筛选（宽松条件）"""
    filtered = []
    for stock in stocks:
        try:
            fundamentals = get_fundamentals([stock], 'valuation', 
                                          ['pe_ttm', 'pb'], 
                                          date=context.current_dt.strftime('%Y-%m-%d'))
            if fundamentals is None or fundamentals.empty:
                # 估值数据获取失败，跳过筛选
                filtered.append(stock)
                continue
            
            pe = fundamentals['pe_ttm'].iloc[0]
            pb = fundamentals['pb'].iloc[0]
            
            # 宽松估值条件
            if 0 < pe < 100 and 0 < pb < 10:
                filtered.append(stock)
        except Exception as e:
            # 异常时保留股票，避免错过机会
            filtered.append(stock)
    
    return filtered

def check_stop_loss(position, context, data):
    """检查止损条件"""
    current_price = data[position.stock]['close']
    cost_basis = position.cost_basis
    
    # 固定止损
    if (cost_basis - current_price) / cost_basis > g.stop_loss:
        return True
    
    return False
```

---

## 4. 数据需求

### 4.1 必需数据

| 数据类型 | 用途 | 频率 |
|---------|------|------|
| 日线价格 | 计算均线、趋势 | 日频 |
| 成交量 | 流动性筛选 | 日频 |

### 4.2 可选数据

| 数据类型 | 用途 | 频率 |
|---------|------|------|
| 估值数据 (PE/PB) | 估值筛选 | 日频 |

**重要**: 估值数据为可选，若获取失败不影响策略运行

### 4.3 数据日期范围

- **回测期**: 2025-04-01 至 2025-07-31
- **数据需求**: 2025-01-01 至 2025-07-31（需 60 日均线数据）

---

## 5. 风险控制

### 5.1 个股风险

- **止损**: 8% 硬止损
- **趋势反转**: 跌破 20 日均线自动离场
- **分散投资**: 单只股票不超过 10% 仓位

### 5.2 系统性风险

- **满仓操作**: 不主动择时，通过趋势判断间接规避风险
- **多股票分散**: 最多持有 10 只股票

### 5.3 数据风险

- **估值数据容错**: 若估值数据获取失败，自动跳过估值筛选
- **价格数据校验**: 确保历史数据充足（至少 65 天）

---

## 6. 验收标准

### 6.1 回测指标要求

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 总收益率 | > 10% | 4 个月回测期 |
| 年化收益率 | > 30% | 折算年化 |
| 夏普比率 | > 1.0 | 风险调整后收益 |
| 最大回撤 | < 15% | 风险控制 |
| 胜率 | > 45% | 交易胜率 |
| 盈亏比 | > 1.5 | 平均盈利/平均亏损 |

### 6.2 功能验收

- ✅ 策略能够正常运行，无报错
- ✅ 能够正确计算均线和技术指标
- ✅ 选股逻辑正确，筛选条件生效
- ✅ 交易执行正常，订单正确生成
- ✅ 估值数据获取失败时策略仍能运行

### 6.3 性能要求

- **回测速度**: < 5 分钟（4 个月回测期）
- **内存占用**: < 2GB

---

## 7. 优化方向

### 7.1 参数优化

可优化的参数：
- 均线周期 (MA20, MA60)
- 止损比例 (8%)
- 持仓数量 (10 只)
- 涨幅阈值 (5%)

### 7.2 策略改进

1. **动态仓位**: 根据市场趋势调整仓位
2. **行业分散**: 限制单一行业持仓比例
3. **止盈策略**: 添加移动止盈机制
4. **市场状态**: 加入牛熊判断，空仓避险

---

## 8. 任务分解

### 8.1 开发任务

| 任务 ID | 任务描述 | 负责人 | 状态 |
|--------|---------|--------|------|
| TASK-001 | 实现选股逻辑和趋势判断 | @Strategy-Engr | 待开始 |
| TASK-002 | 实现交易执行逻辑 | @Strategy-Engr | 待开始 |
| TASK-003 | 添加估值数据容错处理 | @Strategy-Engr | 待开始 |
| TASK-004 | 单元测试和边界测试 | @Strategy-QA | 待开始 |
| TASK-005 | 回测验证和参数调优 | @Strategy-Engr | 待开始 |

### 8.2 验收任务

| 任务 ID | 任务描述 | 负责人 | 状态 |
|--------|---------|--------|------|
| TASK-101 | 代码审查 | @Strategy-QA | 待开始 |
| TASK-102 | 回测结果验证 | @Strategy-QA | 待开始 |
| TASK-103 | 性能测试 | @Strategy-QA | 待开始 |

---

## 9. 附录

### 9.1 关键问题说明

#### 问题 1: get_fundamentals 返回空 DataFrame

**根本原因**:
1. SimTradeData 的估值数据存储在 `valuation/` 目录，按股票分开存储
2. 数据日期范围取决于 SimTradeData 下载时的配置（`START_DATE` 和 `END_DATE`）
3. 若回测日期（2025-04-01 至 2025-07-31）超出估值数据范围，则返回空 DataFrame

**解决方案**:
1. **容错处理**: 在策略中添加 try-except，估值数据获取失败时跳过筛选
2. **简化条件**: 将估值筛选从必需改为可选
3. **数据检查**: 运行回测前确认 SimTradeData 数据已更新到 2025-07

#### 问题 2: 数据日期范围确认

**确认方法**:
```bash
# 检查 SimTradeData 导出数据的日期范围
cd SimTradeData
python scripts/check_data_quality.py --check valuation --date-range 2025-04-01,2025-07-31
```

**推荐配置** (SimTradeData/scripts/download_efficient.py):
```python
START_DATE = "2024-01-01"  # 确保覆盖回测期
END_DATE = None  # 自动使用当前日期
```

### 9.2 参考文档

- [SimTradeLab API 参考](./PTrade_API_Complete_Reference.md)
- [PTrade 财务数据 API](../SimTradeData/docs/PTrade_API_mini_Reference.md)
- [SimTradeData 数据格式](../SimTradeData/docs/PTRADE_PARQUET_FORMAT.md)

---

**文档状态**: ✅ 完成  
**最后更新**: 2026-03-27  
**审核人**: Strategy-Arch

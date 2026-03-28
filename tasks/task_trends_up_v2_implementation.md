# 任务单：Trends_Up v2 策略实现

**任务 ID**: TASK-TRENDS-UP-V2-001  
**创建日期**: 2026-03-27  
**优先级**: 高  
**状态**: 待开始  

---

## 任务描述

实现 trends_up_v2 策略，解决原策略在 2025 年 4-7 月回测期间 `get_fundamentals` 返回空 DataFrame 的问题。

### 背景

原 trends_up 策略在回测时遇到选股问题：
- `get_fundamentals` 返回空 DataFrame，导致无法选股
- 原因是 SimTradeData 的估值数据日期范围可能未覆盖 2025-04-01 至 2025-07-31
- 原策略选股条件过于复杂，依赖估值数据

### 解决方案

采用**简化选股逻辑 + 容错处理**:
1. 将估值筛选从必需改为可选
2. 添加异常处理，估值数据获取失败时自动跳过筛选
3. 核心筛选条件基于价格趋势（不依赖估值数据）

---

## 工作内容

### 1. 策略文件结构

创建文件：`strategies/trends_up_v2/backtest.py`

```
strategies/
└── trends_up_v2/
    ├── backtest.py          # 策略主文件
    └── README.md            # 策略说明
```

### 2. 核心实现

#### 2.1 初始化函数

```python
def initialize(context):
    set_benchmark('000300.SS')
    set_commission(0.0003)
    set_slippage(0.002)
    set_universe('ALL')
    
    g.max_positions = 10
    g.stock_weight = 0.1
    g.stop_loss = 0.08
    g.ma_short = 20
    g.ma_long = 60
```

#### 2.2 盘前选股

```python
def before_trading_start(context):
    # 1. 获取股票池
    all_stocks = get_index_stocks('000906.XBHS')
    
    # 2. 过滤 ST、科创板、创业板
    filtered = filter_stocks(all_stocks)
    
    # 3. 趋势筛选（核心）
    trend_stocks = [s for s in filtered if check_trend(s, context)]
    
    # 4. 估值筛选（可选，容错处理）
    value_stocks = filter_by_valuation(trend_stocks, context)
    
    # 5. 保存候选池
    g.candidate_pool = value_stocks if value_stocks else trend_stocks
```

#### 2.3 盘中交易

```python
def handle_data(context, data):
    positions = get_positions()
    
    # 1. 止损检查
    for pos in positions:
        if check_stop_loss(pos, context, data):
            order_target(pos.stock, 0)
    
    # 2. 趋势反转检查
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

### 3. 关键函数实现

#### 3.1 趋势判断

```python
def check_trend(stock, context):
    df = get_price(stock, count=65, frequency='1d', fields=['close'])
    if len(df) < 65:
        return False
    
    close = df['close'].iloc[-1]
    ma20 = df['close'].iloc[-20:].mean()
    ma60 = df['close'].iloc[-60:].mean()
    close_20d = df['close'].iloc[-20]
    
    # 趋势条件：close > MA20 > MA60 AND 近 20 日涨幅 > 5%
    return close > ma20 > ma60 and (close - close_20d) / close_20d > 0.05
```

#### 3.2 估值筛选（容错）

```python
def filter_by_valuation(stocks, context):
    filtered = []
    for stock in stocks:
        try:
            fundamentals = get_fundamentals([stock], 'valuation', 
                                          ['pe_ttm', 'pb'], 
                                          date=context.current_dt.strftime('%Y-%m-%d'))
            if fundamentals is None or fundamentals.empty:
                # 估值数据获取失败，保留股票
                filtered.append(stock)
                continue
            
            pe = fundamentals['pe_ttm'].iloc[0]
            pb = fundamentals['pb'].iloc[0]
            
            # 宽松估值条件
            if 0 < pe < 100 and 0 < pb < 10:
                filtered.append(stock)
        except Exception as e:
            # 异常时保留股票
            filtered.append(stock)
    
    return filtered
```

#### 3.3 止损检查

```python
def check_stop_loss(position, context, data):
    current_price = data[position.stock]['close']
    cost_basis = position.cost_basis
    return (cost_basis - current_price) / cost_basis > g.stop_loss
```

---

## 技术要求

### 代码规范

- ✅ 遵循 Python 3.5+ 语法（兼容 SimTradeLab）
- ✅ 使用 SimTradeLab PTrade 兼容 API
- ✅ 添加必要的注释和文档字符串
- ✅ 异常处理完善

### 性能要求

- 单次选股耗时 < 30 秒（全市场约 4000 只股票）
- 回测速度 < 5 分钟（4 个月周期）

### 容错要求

- ✅ 估值数据获取失败不影响策略运行
- ✅ 价格数据不足时自动跳过股票
- ✅ 交易失败时记录日志但不中断回测

---

## 验收标准

### 功能验收

- [ ] 策略能够正常初始化
- [ ] 盘前选股函数正确计算趋势信号
- [ ] 估值数据获取失败时策略仍能运行
- [ ] 止损逻辑正确执行
- [ ] 趋势反转判断准确
- [ ] 买入卖出订单正确生成

### 回测指标

运行回测（2025-04-01 至 2025-07-31）:

```bash
cd SimTradeLab/src/simtradelab/backtest
python run_backtest.py --strategy trends_up_v2 --start 2025-04-01 --end 2025-07-31 --capital 1000000
```

**预期结果**:
- 总收益率 > 10%
- 最大回撤 < 15%
- 夏普比率 > 1.0
- 持仓股票数：5-10 只
- 交易次数：20-50 次

### 代码审查

- [ ] 代码结构清晰，函数职责单一
- [ ] 变量命名规范
- [ ] 注释充分
- [ ] 无明显的性能瓶颈
- [ ] 异常处理完善

---

## 交付物

1. **策略代码**: `strategies/trends_up_v2/backtest.py`
2. **策略说明**: `strategies/trends_up_v2/README.md`
3. **回测报告**: 回测结果截图或导出文件
4. **自测报告**: 开发者自检结果

---

## 任务分配

| 角色 | 任务 | 负责人 |
|------|------|--------|
| **开发** | 策略实现 | @Strategy-Engr |
| **审查** | 代码审查 | @Strategy-QA |
| **验收** | 回测验证 | @Strategy-QA |

---

## 时间安排

- **开发完成**: 2026-03-28
- **代码审查**: 2026-03-29
- **回测验收**: 2026-03-30

---

## 参考文档

- [策略设计文档](../docs/strategy_trends_up_v2.md)
- [SimTradeLab API 参考](../docs/PTrade_API_Complete_Reference.md)
- [PTrade 财务数据 API](../../SimTradeData/docs/PTrade_API_mini_Reference.md)

---

**创建人**: Strategy-Arch  
**审核人**: Strategy-QA  

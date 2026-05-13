# trends_up 策略设计文档

> 版本: S2终版+perf (2026-05-06)
> 文件: `strategies/trends_up/backtest.py` (2775行, 8个核心类 + 5个生命周期函数)

---

## 1. 策略概述

**trends_up** 是一个基于趋势跟踪的A股日内量化策略，运行在分钟级回测引擎（SimTradeLab v2.10.2）上。策略核心思路：

1. **14:30 选股买入** — 每日收盘前90分钟，通过7步选股漏斗筛选具备突破形态的中小盘股
2. **四维打分分级** — 对候选股进行均线粘合度、突破幅度、量能比、MACD强度的四维综合评分，分为 S/A/B 三级
3. **MA20 跟踪止损** — 持仓期间以MA20均线为核心风控线，配合峰值回撤保护、成本价锁定、移动止盈
4. **双模市场自适应** — 根据持仓组合表现自动识别市场模式（震荡/上升/下降），动态调整止损参数和仓位比例

**初始资金**: 100万 | **最大持仓**: 5只 | **基准**: 沪深300 (000300.SS)

---

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                    PTrade 生命周期引擎                            │
│  initialize → before_trading_start → handle_data → after_trading_end │
└────────┬──────────────┬──────────────────┬──────────────────────┘
         │              │                  │
         ▼              ▼                  ▼
   ┌──────────┐  ┌─────────────┐   ┌──────────────┐
   │ Config   │  │ DataCache   │   │ MarketDetector│
   │ Manager  │  │ (数据层)     │   │ (市场感知)    │
   └──────────┘  └──────┬──────┘   └──────┬───────┘
                        │                  │
         ┌──────────────┼──────────────────┤
         ▼              ▼                  ▼
  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
  │SelectionAgent│ │ExecutionAgent│ │ PositionAgent │
  │ (选股漏斗)   │ │ (订单执行)   │ │ (风控止损)    │
  └──────────────┘ └──────────────┘ └──────────────┘
                        │
                        ▼
                 ┌──────────────┐
                 │ ReportAgent  │
                 │ (盘后报表)   │
                 └──────────────┘
```

### 类职责一览

| 类名 | 职责 | 核心方法 |
|------|------|----------|
| `ConfigManager` | 所有超参数、阈值、功能开关的统一管理 | 纯配置类，无方法 |
| `Common` | 文件I/O、字符串格式化等通用工具 | `safe_read_file`, `safe_write_file`, `pad_string` |
| `DataCache` | 数据缓存与PTrade API封装 | `get_daily_data`, `get_5m_data`, `get_15m_data`, `preload_daily_data` |
| `SelectionAgent` | 7步选股漏斗 + 四维打分 + 跳空检测 | `build_watchlist`, `select`, `score_breakout_stock`, `detect_morning_gap_up` |
| `ExecutionAgent` | 买入执行、持仓轮换、早盘入场 | `buy_new`, `buy_morning_entry`, `find_weakest_position` |
| `MarketDetector` | 市场模式识别（震荡/上升/下降） | `detect_market_mode` |
| `PositionAgent` | MA20跟踪止损 + 峰值回撤 + 成本锁定 + 止盈 | `check_intraday_exit`, `simple_take_profit`, `calc_profit_ratio_safely` |
| `ReportAgent` | 盘后持仓报表 + PnL统计 + 选股列表 | `generate_daily_reports`, `generate_profit_loss_report`, `log_selection_list` |

---

## 3. 生命周期流程

### 3.1 initialize — 策略初始化

```
设置基准指数 (000300.SS)
初始化全局状态变量:
  - g.long_term_candidates    # 候选股池
  - g._peak_prices            # 持仓峰值价格
  - g._buy_prices             # 买入价格
  - g._holding_start_date     # 持仓起始日
  - g._trade_history          # 交易历史
  - g._traded_stocks          # 交易过的股票集合
  - g._warning_state          # 预警节流状态
加载 pkl 缓存
```

### 3.2 before_trading_start — 开盘前

```
更新日期字符串
清理旧缓存（内存优化）
```

### 3.3 handle_data — 盘中核心逻辑（每分钟触发）

```
5分钟截流: m % 5 != 0 → return

├── 09:35  早盘入场分支
│   ├── 检测市场模式
│   ├── 如果 MORNING_ENTRY_ENABLED → 检测跳空高开
│   └── 最多买入3只，使用10%总资金
│
├── 每15分钟  盘中风控
│   └── PositionAgent.check_intraday_exit()
│       ├── 峰值回撤保护
│       ├── MA跟踪止损（双模自适应）
│       ├── 成本价锁定
│       ├── 双模止盈
│       └── 移动止盈（仅uptrend模式）
│
└── 14:30  主力入场
    ├── SelectionAgent.build_watchlist()  # Step1~7选股漏斗
    ├── SelectionAgent.select()           # 四维打分 + 分级
    └── ExecutionAgent.buy_new()          # 买入或轮换
```

### 3.4 after_trading_end — 盘后结算

```
检测市场模式 → 日志
生成盘后报表:
  - 账户汇总（总资产/盈亏/仓位水平）
  - 持仓明细（每只股票的当日/累计盈亏）
  - PnL统计报表（盈利/亏损次数、金额）
更新 daily_pnl_report.csv
保存 pkl 缓存
```

---

## 4. 选股漏斗 (SelectionAgent.build_watchlist)

每日14:30执行，从全市场~5500只股票中筛选：

```
Step1  股票池初始化          ~5500只  get_Ashares() 获取全市场A股
  │
Step2  异常股过滤            ~4500只  排除科创板(688)、北交所(8xx/43xx)
  │
  ├── 数据预加载: 批量加载65日日线数据（100只/批）
  │
Step3  财务过滤（市值约束）   ~1400只
  │   ├── 向量化路径: valuation表直接获取市值（PTrade）
  │   ├── 回退路径: 逐批获取股本 × 收盘价（SimTradeLab）
  │   ├── 分位数动态过滤: P20~P80 范围内
  │   ├── 绝对值过滤: 30亿 < 总市值 < 200亿, 流通市值 < 80亿
  │   ├── 成交额过滤: > P30分位 且 > 3000万
  │   └── 换手率过滤: 当日量/5日均量 > 0.5
  │
Step4  股价预过滤            ~1370只  股价 < 80元
  │
Step5  技术面初筛            ~700只   增强版趋势过滤（满足2/3即通过）
  │   ├── 条件1: 收盘价 > MA20
  │   ├── 条件2: MA20 > MA60（中期趋势向上）
  │   └── 条件3: 近10日收盘价不下跌
  │
Step6  月线趋势确认          ~700只   (当前与Step5合并)
  │
Step7  预选池最终确认         ~700只   保存到 g.long_term_candidates
```

### 4.1 市值过滤的双路径设计

```
路径A (PTrade): valuation表 → total_value/float_value → 向量化过滤
路径B (SimTradeLab): capital_structure/share_change表 → 股本×股价 → 向量化过滤（利用预加载缓存）
路径C (降级): 成交额/换手率反推估算市值
```

**路径B优化说明**: 利用 `build_watchlist` 在 Step2 后已调用的 `preload_daily_data(candidates, 65)` 缓存，
批量提取收盘价和成交额到 `price_map`/`money_map` 字典，消除逐只 `get_daily_data` 调用。
每日可减少 ~4500 次冗余API调用，Step3 耗时预计从 ~10秒降至 ~1秒。

### 4.2 Step4+5 合并过滤

Step4（股价<80）和 Step5（趋势过滤）原为两次独立循环，各遍历全部候选股。
优化后合并为 `_filter_by_price_and_trend()` 单次遍历，一轮循环同时完成价格和趋势检查：

```
优化前: Step4 遍历 ~1370只 (0.1s) → Step5 遍历 ~1370只 (0.1s) = 0.2s
优化后: Step4+5 合并遍历 ~1370只 = 0.1s
```

### 4.3 增强版趋势过滤 (enhanced_trend_filter)

```python
# 满足以下3个条件中的2个即通过
cond1 = close > MA20                    # 价格在短期均线上方
cond2 = MA20 > MA60                     # 中期趋势向上
cond3 = 近10日收盘价[-1] >= 收盘价[0]   # 近期不下跌
```

---

## 5. 四维打分与分级系统 (SelectionAgent.select)

对 Step7 通过的候选股进行形态识别和综合评分。

### 5.1 四个条件维度

| 条件 | 定义 | 判定标准 |
|------|------|----------|
| **均线粘合** | MA10/MA30/MA60 三线收敛 | (max-min)/min ≤ 7% |
| **突破近期高点** | 收盘价 > 近20日最高价 | 直接比较 |
| **成交量突发** | 当日量 vs 5日均量 | 强: ≥1.5倍, 弱: ≥0.8倍 |
| **MACD金叉** | MACD线上穿信号线 | 标准金叉 或 正轴强势模式 |

### 5.2 分级准入逻辑

```
met_count = 满足的条件数

4/4 条件全部满足:
  ├── base_score > 0.75 → S级 (得分+0.2)
  ├── base_score ≥ 0.55 → A级 (得分+0.1)
  └── base_score < 0.55 → B级 (得分不变)

3/4 条件满足 (ALLOW_3_OF_4=True):
  └── base_score > MIN_SCORE_B → B级

2/4 条件满足 (ALLOW_2_OF_4=True):
  └── base_score > MIN_SCORE_B - 0.05 → B级
```

### 5.3 四维综合评分 (score_breakout_stock)

```
总分 = 均线粘合度(30%) + 突破幅度(25%) + 量能比(25%) + MACD强度(20%)

维度1 均线粘合度: score = max(0, 1 - (max_ma - min_ma) / min_ma / 0.07)
维度2 突破幅度:   score = min(max(0, 突破百分比) × 20, 1.0)
维度3 量能比:     score = min(vol_ratio / 3, 1.0)
维度4 MACD强度:   score = min(abs(macd) × 2, 1.0)
```

**性能优化**: `select` 方法中每只股票只需计算一次 MACD 和 MA10/30/60，
结果通过 `macd_score_override` 和 `ma_values_override` 参数传递给 `score_breakout_stock`，
避免评分阶段重复计算（原每只股票重复计算 1 次 MACD + 3 次 rolling）。

### 5.4 动态参数调整

根据市场模式动态调整选股参数：

| 参数 | sideways | trending_uptrend | trending_downtrend |
|------|----------|------------------|-------------------|
| MIN_SCORE_B | 0.20 | 0.20 | 0.30 |
| MAX_DAILY | 6 | 6 | 6 |

---

## 6. 订单执行 (ExecutionAgent)

### 6.1 新股买入 (buy_new)

**仓位分配逻辑**:

```
1. 计算可用仓位 = min(可用槽位, MAX_POSITIONS_DAILY)
2. 计算可用资金 = min(现金, 组合价值 × 仓位上限比例)
   - uptrend: 98%, sideways: 80%, downtrend: 60%
3. 按级别分配资金权重:
   - S级: 权重3.0（高配）
   - A级/B级: 权重1.0
4. 日内涨幅过滤:
   - S级: >15% 放弃, >5% 仓位减半
   - A级: >10% 放弃
   - B级: >8% 放弃
5. 执行 order_value() 下单
6. 记录买入价格和持仓起始日
```

### 6.2 持仓轮换 (当持仓满5只时)

```
触发条件: 持仓满5只 且 ROTATE_ENABLED=True
轮换逻辑:
  1. 找到最弱持仓（收益最低）
  2. 评估是否替换:
     - 最弱收益 < -5% 且 新标的为S/A/B级 → 替换
     - 最弱收益 < -3% 且 新标的为S/A级 → 替换
  3. 冷却期检查: 被卖出的股票进入冷却期，短期内不可再次轮换
  4. 执行: 卖出最弱 → 买入新标的
```

### 6.3 早盘入场 (buy_morning_entry)

```
时间窗口: 09:35
资金限制: 最多使用10%总资金
数量限制: 最多3只
选股逻辑: 跳空高开检测 (detect_morning_gap_up)
  - 今日开盘价 > 昨日最高价
  - 跳空幅度 0.5% ~ 7.0%
  - 早盘成交额 > 昨日成交额的20%
  - 置信度 = (跳空幅度/3 + 量比) / 2
```

---

## 7. 市场模式检测 (MarketDetector)

基于持仓组合的平均盈亏水平判断市场环境，不依赖外部指数数据。

### 7.1 检测逻辑

```python
avg_profit = 所有持仓的平均盈利比例

if avg_profit > 0.03:   → "trending_uptrend"   # 上升趋势
elif avg_profit < -0.03: → "trending_downtrend" # 下降趋势
else:                     → "sideways"           # 震荡市

# 持仓不足3只或运行不足5天 → "unknown"
```

### 7.2 三种模式的参数差异

| 参数 | sideways | trending_uptrend | trending_downtrend |
|------|----------|------------------|-------------------|
| **止损均线周期** | MA120 (日线) | MA120 (日线) | MA120 (日线) |
| **止损确认K线数** | 5根 | 5根 | 3根 |
| **固定止盈L1** | 999%（不触发） | 999%（不触发） | 10% |
| **固定止盈L2** | 999%（不触发） | 999%（不触发） | 20% |
| **峰值回撤阈值** | 15% | 20% | 12% |
| **成本锁定阈值** | 2% | 3% | 1% |
| **最大仓位比例** | 80% | 98% | 60% |
| **B级最低分** | 0.20 | 0.20 | 0.30 |
| **早盘入场** | 启用 | 启用 | 启用 |
| **移动止盈** | 不启用 | 启用(盈利>20%,回撤15%) | 不启用 |

---

## 8. 风控体系 (PositionAgent)

### 8.1 盘中风控流程 (check_intraday_exit)

每15分钟执行一次，对每只持仓按以下顺序检查：

> **性能优化**: MA确认逻辑中 rolling mean 只计算一次（`ma_series`），主检查和确认检查复用同一结果。

```
T+1 检查: 当日买入的股票不执行止损
    │
    ▼
保护机制1: 峰值回撤保护
    │  盈利状态下，从峰值回撤超过阈值 → 全部卖出
    │  sideways: 15%, uptrend: 20%, downtrend: 12%
    │
    ▼
保护机制2: MA跟踪止损（核心机制）
    │  收盘价 < MA120 → 触发止损
    │  sideways: 需要连续5根K线确认（避免假突破）
    │  uptrend/downtrend: 立即执行
    │
    ▼
保护机制3: 成本价锁定
    │  盈利超过阈值后，锁定部分浮盈
    │  锁定价 = 成本价 × (1 + 盈利比例 × 50%)
    │  现价 < 锁定价 且 现价 < MA → 卖出（保本）
    │
    ▼
保护机制4: 双模自适应止盈
    │  sideways: L1=10%卖30%, L2=20%卖30%
    │  uptrend:  L1=999%(不触发), L2=999%(不触发)
    │  downtrend: L1=10%卖30%, L2=20%卖30%
    │
    ▼
保护机制5: 移动止盈（仅uptrend模式）
       盈利 > 20% 后，跟踪最高价
       现价 < 最高价 × 85%（回撤15%）→ 全部卖出
```

### 8.2 安全盈利计算 (calc_profit_ratio_safely)

```python
# 关键: cost_basis 是每股成本价（元/股），不是总成本
avg_price = pos.cost_basis
current_price = pos.last_sale_price  # 或 pos.price
profit_ratio = (current_price - avg_price) / avg_price

# 边界检查: 截断到 [-99%, +500%] 范围
# 防止因数据异常导致的386674%异常盈利BUG
```

---

## 9. 数据层 (DataCache)

### 9.1 数据获取接口

| 方法 | 频率 | 数据源 | 用途 |
|------|------|--------|------|
| `get_daily_data` | 日线 | PTrade `get_history` | 选股、均线计算、止损 |
| `get_5m_data` | 5分钟 | PTrade `get_history` | 早盘跳空检测 |
| `get_15m_data` | 15分钟 | 5m聚合+前复权 | 高频风控（备用） |
| `get_valuation_data` | 日级 | PTrade `get_fundamentals` | 市值过滤 |
| `preload_daily_data` | 日线 | 批量预加载 | 性能优化 |

### 9.2 缓存策略

```
内存缓存: 按日期+股票+周期 做key，每日自动清理
pkl文件缓存: 日线数据持久化，跨日复用
valuation缓存: 日级缓存，避免重复查询
5分钟缓存: 日内缓存（key含_5m_标记），早盘检测复用
批量预加载: 100只/批，减少API调用次数
```

### 9.3 15m数据的三层降级

```
方案A: 本地parquet读取（跳过：未复权，与日线不一致）
方案B: 5分钟数据实时聚合 + 动态前复权  ← 实际使用
方案C: 返回空DataFrame（优雅降级，跳过风控检查）
```

---

## 10. 盘后报表 (ReportAgent)

### 10.1 账户汇总报表

```
总资产 / 总盈亏 / 当日参考盈亏
总市值 / 可用资金 / 仓位水平
```

### 10.2 持仓明细表

```
每只股票: 代码/名称/当日盈亏/累计盈亏/持仓市值/浮动盈亏
         持股数量/持股天数/成本价/当前价/持仓比例/策略名
```

### 10.3 PnL统计报表

```
每只交易过的股票: 代码/起止日期/期初价/期末价/价格变动/涨跌幅
                盈利次数/亏损次数/盈利金额/亏损金额/手续费/净盈亏
```

### 10.4 选股列表输出

```
每日Top10候选: 代码/名称/总市值/流通市值/当前价/得分/仓位比例
```

---

## 11. 核心配置参数速查

### 11.1 持仓管理

| 参数 | 值 | 说明 |
|------|-----|------|
| MAX_POSITIONS | 5 | 最大同时持仓数 |
| BENCHMARK_INDEX | 000300.SS | 基准指数 |
| BUY_TIME | (14, 30) | 主力买入时间 |
| ROTATE_ENABLED | True | 持仓轮换开关 |

### 11.2 市值过滤

| 参数 | 值 | 说明 |
|------|-----|------|
| MIN_TOTAL_CAPITAL | 30亿 | 总市值下限 |
| MAX_TOTAL_CAPITAL | 200亿 | 总市值上限 |
| MAX_FLOAT_CAPITAL | 80亿 | 流通市值上限 |
| MAX_PRICE | 80元 | 股价上限 |
| MIN_TURNOVER | 3000万 | 最小成交额 |

### 11.3 均线参数

| 参数 | 值 | 说明 |
|------|-----|------|
| SHORT | MA10 | 短期均线 |
| MID | MA30 | 中期均线 |
| LONG | MA60 | 长期均线 |
| STOP_MA_PERIOD | MA120 | 止损均线周期 |

### 11.4 突破与打分

| 参数 | 值 | 说明 |
|------|-----|------|
| LOOKBACK_DAYS | 20 | 突破回望天数 |
| MA_CONVERGENCE | 7% | 均线粘合阈值 |
| VOL_MULTIPLIER_STRONG | 1.5 | 强势放量倍数 |
| VOL_MULTIPLIER_WEAK | 0.8 | 弱势放量倍数 |
| SCORING_WEIGHTS | 30/25/25/20 | 均线/突破/量能/MACD权重 |

### 11.5 止损止盈

| 参数 | 值 | 说明 |
|------|-----|------|
| SIMPLE_STOP.MA_PERIOD | 20 | MA20止损均线 |
| SIMPLE_STOP.MAX_DRAWDOWN_FROM_PEAK | 20% | 峰值回撤上限 |
| SIMPLE_STOP.PROFIT_LOCK_THRESHOLD | 3% | 成本锁定启用阈值 |
| SIMPLE_STOP.PROFIT_LOCK_RATIO | 50% | 浮盈锁定比例 |

---

## 12. 回测结果

### 2024年全年回测

| 指标 | 数值 |
|------|------|
| 总收益率 | +2.57% |
| 年化收益 | +2.67% |
| 最大回撤 | -32.15% |
| 夏普比率 | 0.266 |
| 信息比率 | -0.439 |
| 本金 | 100万 → 102.6万 |

### 2025年全年回测

| 指标 | 数值 |
|------|------|
| 总收益率 | +40.68% |
| 年化收益 | +42.47% |
| 最大回撤 | -24.35% |
| 夏普比率 | 1.237 |
| 信息比率 | 0.701 |
| 本金 | 100万 → 140.7万 |

### 表现差异分析

- **2024年** (+2.57%): A股整体震荡偏弱，策略在下跌趋势中频繁触发止损，最大回撤较大(-32.15%)
- **2025年** (+40.68%): 市场回暖，趋势跟踪策略在上升行情中表现出色，夏普比率1.237
- 两年均无程序错误，策略功能完整验证通过

---

## 13. 已知限制与注意事项

1. **MarketDetector 基于持仓表现**: 不使用外部指数数据，市场模式判断滞后于实际行情
2. **15m数据依赖5m聚合**: 前复权精度受除权因子影响
3. **B级选股放宽**: ALLOW_2_OF_4 模式可能引入质量较低的标的
4. **S2终版取消固定止盈**: L1/L2设为999%，仅依赖MA止损和移动止盈
5. **T+1限制**: 当日买入的股票不执行盘中止损
6. **数据兼容性**: SimTradeLab 与 PTrade 的 get_fundamentals 表名不完全一致（capital_structure vs share_change）

---

## 14. 性能优化记录

### 14.1 优化一: Step3 市值过滤向量化 (2026-05-06)

**问题**: `_filter_by_market_cap` SimTradeLab 回退路径逐只调用 `get_daily_data` 获取收盘价，~4500 次 API 调用/天。

**优化**: 利用 `build_watchlist` 已调用的 `preload_daily_data(candidates, 65)` 缓存，批量提取 `price_map`/`money_map` 字典，消除逐只调用。

**效果**: Step3 耗时从 ~10秒降至 ~6.5秒（~35% 提升）。

### 14.2 优化二: 六项全局性能优化 (2026-05-06)

| 优化项 | 问题 | 方案 | 效果 |
|--------|------|------|------|
| MACD 去重 | `select` 和 `score_breakout_stock` 各算一次 MACD | `macd_score_override` 参数传递 | 评分阶段 MACD 计算减半 |
| 双循环合并 | Step4 和 Step5 两次独立遍历 | `_filter_by_price_and_trend` 单次遍历 | Step4+5 从 0.2s 降至 0.1s |
| rolling 去重 | `score_breakout_stock` 重算 MA10/30/60 | `ma_values_override` 参数传递 | 评分阶段 rolling 减半 |
| 5m 数据缓存 | `get_5m_data` 每次调 API | 日内缓存（key含 `_5m_` 标记） | 早盘检测 100次→0次 API |
| 冗余过滤移除 | `select` 中重复检查价格 | 删除 `filter_by_fundamentals_and_price` 调用 | 减少无用比较 |
| MA 确认优化 | `check_intraday_exit` 两次 rolling | 复用 `ma_series` 一次计算 | 止损确认 rolling 减半 |

# 趋势跟踪新策略 (trends_up_new) 设计文档

**当前版本**: S2终版 (2026-04-13)

## 1. 核心设计理念与背景

基于历史策略（如 `trends_up` 和 `myTrendStrategy`）回测中暴露的"买入滞后"、"拿不住主升浪"、"形态识别不足"等问题，本策略从"自下而上"的角度出发，侧重个股的**早期形态识别**与**状态化持仓**。经过多轮优化（v01→S2），当前版本采用**双模市场自适应体系 + MA20跟踪止损 + 只买S级重仓出击**的核心架构。

### 优化演进历史

| 版本 | 核心变更 | 震荡市收益 | 牛市收益 |
|------|---------|-----------|---------|
| v01~v05 | 基础架构→选股漏斗→ATR止损 | -15% ~ -24% | -3% ~ -4% |
| v06~v08 | 参数调优（边际递减） | +2.65% → +5.67% | -6.40% → +19.58% |
| v09 (Phase 2) | 结构性重构：15分钟K线+自适应止损 | +12.70% ✅ | +39.83% ✅ |
| v10 | 市场状态引擎+全链路参数矩阵 | -7.69% ⚠️ | +22.38% ⚠️ |
| opt_14 | 全面重构：删除ATR/状态引擎/RiskManager，MA20止损+简单止盈 | — | — |
| opt_15 | Cost Basis语义BUG修复(500%截断)+双模市场自适应(DUAL_MODE_PARAMS) | **+0.33%** | **-2.79%** |
| **S2终版** | **统一60m止损+取消固定止盈+移动止盈+只买S级+按模式差异化仓位** | **+24.14%** 🎉 | **+71.45%** 🚀 |

### S2终版核心创新

- **统一60分钟止损频率**：所有市场模式使用60m数据计算MA20，平衡灵敏度与稳定性
- **取消uptrend固定止盈**（L1=L2=999%）：让利润在牛市中充分奔跑
- **移动止盈安全网**（盈利>20%后回撤15%触发）：防止极端回撤同时不干扰正常趋势
- **只买入S级股票**：质量优于数量，集中火力打最强标的
- **S级3x权重分配**：S级单只获得B级3倍的仓位权重
- **按模式差异化总仓位**：sideways=50%（保守）、uptrend=95%（激进）、downtrend=30%（极度保守）
- **基于持仓组合的市场检测**（MarketDetector）：用组合平均盈亏自适应判断市场冷暖（000300.SS数据已动态化，但当前版本验证基于持仓检测有效）

---

## 2. 核心机制设计

### 2.1 早期形态识别 (Early Breakout Detection)

`SelectionAgent.select()` 执行四重条件检测（支持2/4宽松模式）：

- **均线粘合** (MA20/MA60/MA120)：要求三条长期均线极差百分比 ≤ `MA_CONVERGENCE` (7%)，代表筹码集中。
- **价格突破**：收盘价 > 近 `LOOKBACK_DAYS` (20) 个交易日的震荡平台高点。
- **成交量突发（双档制）**：
  - **强量突破**：当日量 ≥ 5日均量 × `VOL_MULTIPLIER_STRONG` (1.5)，量能得分 = 1.0
  - **弱量突破**：当日量 ≥ 5日均量 × `VOL_MULTIPLIER_WEAK` (0.8)，量能得分 = 0.7
- **MACD 金叉（放宽版）**：`macd_prev <= signal_prev and macd > signal and abs(macd) < MACD_ZERO_AXIS_LIMIT` (2.0)。允许强势股在正轴金叉。

**分级系统**：
- **S级**：满足全部4个条件（得分≥0.85）
- **A级**：满足3/4条件（得分0.70~0.84）
- **B级**：满足2/4条件（得分<0.70）
- **C级**：不满足最低条件

**🆕 S2关键变更**：实际买入时**只接受S级**，A/B/C级仅用于选池排序。

### 2.2 四维综合打分排序 (Multi-Dimensional Scoring)

通过 `SelectionAgent.score_breakout_stock()` 计算加权综合得分：

| 维度 | 计算方式 | 权重 |
|------|---------|------|
| 均线粘合度 | `(1 - 极差% / 阈值)` 归一化 | 30% |
| 突破幅度 | `(close / recent_high - 1) × 20` 封顶 1.0 | 25% |
| 量能比 | `min(vol_ratio / 3, 1.0)` | 25% |
| MACD 强度 | `min(abs(macd) × 2, 1.0)` | 20% |

返回数量：`max(available_slots * 2, SCORING_TOP_K_MIN)`，默认最少返回 3 只。

### 2.3 双模市场自适应系统 (Dual Mode Adaptation)

#### 2.3.1 市场模式检测 (MarketDetector)

`MarketDetector.detect_market_mode()` 基于持仓组合平均表现判断市场状态：

| 模式 | 判定条件 | 含义 |
|------|---------|------|
| `trending_uptrend` | 平均盈利 > 3% | 上升趋势 |
| `sideways` | 平均盈利 ±3% 以内 | 震荡市 |
| `trending_downtrend` | 平均亏损 < -3% | 下降趋势 |
| `unknown` | 持仓 < 3只 或 运行 < 5天 | 数据不足 |

**设计考量**：000300.SS数据已动态化（548行，每日close均不同）。当前版本选择基于持仓组合的自适应检测，原因：
1. **自适应性更强**：持仓组合表现直接反映策略所处环境
2. **已验证有效**：S2终版在震荡市+24.14%、牛市+71.45%
3. **后续可优化**：如需进一步提升，可考虑融合外部指数信号作为辅助判断

#### 2.3.2 DUAL_MODE_PARAMS 参数矩阵

```python
DUAL_MODE_PARAMS = {
    "sideways": {
        "STOP_MA_PERIOD": 20,           # MA20均线周期
        "STOP_DATA_FREQUENCY": "60m",   # 统一60分钟频率
        "TAKE_PROFIT_L1": 0.10,         # 止盈第一档10%
        "TAKE_PROFIT_L2": 0.20,         # 止盈第二档20%
        "MAX_POSITIONS_DAILY": 3,       # 每日最多买3只
        "MIN_SCORE_B": 0.60,
        "MORNING_ENTRY_ENABLED": False,
        "CONFIRM_STOP_BARS": 2,         # 止损需2根K线确认
    },
    "trending_uptrend": {
        "STOP_MA_PERIOD": 20,
        "STOP_DATA_FREQUENCY": "60m",
        "TAKE_PROFIT_L1": 9.99,         # 🆕 取消固定止盈（≈∞）
        "TAKE_PROFIT_L2": 9.99,         # 🆕 取消固定止盈
        "MAX_POSITIONS_DAILY": 5,
        "MIN_SCORE_B": 0.45,
        "MORNING_ENTRY_ENABLED": True,
        "CONFIRM_STOP_BARS": 1,
    },
    "trending_downtrend": {
        "STOP_MA_PERIOD": 10,
        "STOP_DATA_FREQUENCY": "60m",
        "TAKE_PROFIT_L1": 0.05,
        "TAKE_PROFIT_L2": 0.10,
        "MAX_POSITIONS_DAILY": 2,
        "MIN_SCORE_B": 0.70,
        "MORNING_ENTRY_ENABLED": False,
        "CONFIRM_STOP_BARS": 1,
    },
}
```

#### 2.3.3 按模式差异化总仓位

```python
max_pos_ratio = {
    "trending_uptrend": 0.95,   # 牛市95%满仓出击
    "sideways":          0.50,   # 震荡市半仓防守
    "trending_downtrend": 0.30,  # 熊市30%极度保守
}
```

### 2.4 状态化持仓管理 (Stateful Holding)

`PositionAgent.check_intraday_exit()` 在盘中每5分钟执行，包含**五层保护机制**：

#### 保护机制1：峰值回撤保护（双模参数）

```
sideways:           峰值回撤 > 15% → 卖出
trending_downtrend: 峰值回撤 > 12% → 卖出
trending_uptrend:   峰值回撤 > 20% → 卖出（更宽容）
```

#### 保护机制2：MA跟踪止损（核心！）

- 统一使用MA20均线（或downtrend用MA10）
- 统一60分钟频率
- **sideways模式需要确认**：最近N根(CONFIRM_STOP_BARS=2)K线的收盘价都低于对应MA才确认止损
- **uptrend/downtrend模式立即止损**

#### 保护机制3：成本价锁定（保本机制）

```
盈利 > breakeven_threshold 后启用:
  sideways:           盈利>2%  → 锁定价格 = 成本 × (1 + 利润×50%)
  trending_downtrend: 盈利>1%  → 锁定价格 = 成本 × (1 + 利润×50%)
  trending_uptrend:   盈利>3%  → 锁定价格 = 成本 × (1 + 利润×50%)
现价 < 锁定价格 且 现价 < MA → 卖出
```

#### 保护机制4：双模自适应止盈

- **sideways**: L1=10%(卖30%), L2=20%(再卖30%)
- **trending_uptrend**: L1=999%, L2=999%（**取消固定止盈**，让利润奔跑）
- **trending_downtrend**: L1=5%(卖30%), L2=10%(再卖30%)

每档卖出金额需 ≥2000元且 ≥100股才执行（PTrade最小交易单位约束）。

#### 保护机制5：🆕 移动止盈（仅uptrend模式）

```
触发条件: 模式=trending_uptrend AND 盈利 > 20%
逻辑:
  1. 记录该股票的历史最高价(context._trailing_peaks[stock])
  2. 当现价 < 最高价 × (1 - 15%) 时触发卖出
  3. 卖出后清除记录
作用: 作为安全网防止极端回撤，不影响正常趋势运行
```

### 2.5 持仓轮换机制 (Position Rotation)

`ExecutionAgent.buy_new()` 在仓位已满(6只)时触发轮换：

1. 调用 `find_weakest_position()` 找出收益最低的持仓
2. 轮换阈值：
   - 最弱持仓亏损 > -5% 且 新标的是S/A/B级 → 轮换
   - 最弱持仓亏损 > -3% 且 新标的是S/A级 → 轮换
3. 先卖出最弱持仓，再买入新标的

### 2.6 买入执行与仓位分配 (S2核心变更)

`ExecutionAgent.buy_new()` 的S2版本关键逻辑：

```
1. 计算可用槽位 = min(MAX_POSITIONS - 当前持仓数, MAX_POSITIONS_DAILY[mode])
2. 计算可用资金 = min(cash, portfolio_value × max_pos_ratio[mode])
3. 过滤候选：只保留 grade == "S" 的标的（🆕 关键变更）
4. S级权重分配：
   total_weight = sum(3.0 for each S-grade target)
   each_stock_cash = available_cash × (3.0 / total_weight)
5. 日内涨幅过滤（放宽版）：
   S级: 允许日内涨幅 ≤ 15%
   A级: 允许日内涨幅 ≤ 10%
   B级: 允许日内涨幅 ≤ 8%
   超过预警线(5%)时仓位减半
6. 执行 order_value(stock, cash_per_stock)
```

### 2.7 定时机制与数据缓存规范

- **9:35 早盘入场分支**：仅当 `MORNING_ENTRY_ENABLED=True`（即uptrend模式）时触发早盘跳空高开检测
- **14:30 主力入场**：全市场选股 + 买入操作（核心入口）
- **09:35~14:55 盘中风控**：每5分钟截流，执行五层保护机制
- **pkl 缓存机制**：全市场选股时强制采用 `.pkl` 文件缓存

### 2.8 严格的选股漏斗 (Stock Filtering)

`SelectionAgent.build_watchlist()` 完整执行 Step1~7：

| Step | 过滤内容 | 实现方式 |
|------|---------|---------|
| 1️⃣ | 股票池初始化 | `get_Ashares()` 获取全 A 股 |
| 2️⃣ | 异常股过滤 | 排除科创板(688)、北交所(8/43/83)，保留 ST |
| 3️⃣ | **市值+流动性多维过滤** | 分位数动态过滤（batch_size=100） |
| 4️⃣ | 股价预过滤 | 日线 close < MAX_PRICE (80元) |
| 5️⃣ | 趋势初筛 | close > MA20_daily |
| 6️⃣ | 月线趋势确认 | 与 Step5 合并输出 |
| 7️⃣ | 预选池最终确认 | 输出最终候选数量 |

#### Step3 详细实现

两阶段分位数动态过滤：

**第一阶段 — 数据收集**（批量获取，batch_size=100）：
- 通过 `get_fundamentals(batch, "valuation", ["total_shares", "a_floats"], date)` 获取股本数据
- 结合日K线收盘价计算市值

**第二阶段 — 多维过滤**：
1. 分位数市值过滤：P20~P80 分位数，保留中间 60%
2. 绝对值安全网：30亿 < 总市值 < 200亿
3. 流通市值上限：< 80亿
4. 成交额过滤：> 3000万
5. 换手率过滤：换手率 > 0.5%

### 2.9 安全盈利比例计算（opt_15 BUG修复）

**重要发现**：SimTradeLab框架中 `Position.cost_basis` 存储的是**每股成本价（元/股）**，不是总成本！

```python
@staticmethod
def calc_profit_ratio_safely(pos):
    """
    安全盈利比例计算
    
    Position.cost_basis 是【每股成本价】（元/股），不是总成本！
    正确公式: profit_ratio = (current_price - cost_basis) / cost_basis
    错误公式(已修复): profit_ratio = (current_price - cost_basis/amount) / (cost_basis/amount)
    
    修复效果: 消除386674%、4919827%等异常盈利比例
    """
```

---

## 3. 技术实现与编码约束

### 3.1 代码结构与 PTrade 规范

- **单文件沙盒限制**：必须采用单文件结构，绝对禁止 `import <其他自定义.py>`
- **禁止底层操作**：绝对禁止导入和使用 `os` 和 `sys`
- **本地回测执行**：统一通过 `run_backtest.py` 启动
- **生命周期方法**：`initialize`, `before_trading_start`, `handle_data`, `after_trading_end`, `on_order_response`, `on_trade_response`
- **静态类归类**：所有业务逻辑封装在功能类的静态方法中

### 3.2 类职责划分

| 类名 | 行号 | 职责 | 关键方法 |
|------|------|------|---------|
| `ConfigManager` | 18 | 统一参数配置中心 | 所有超参数/阈值/DUAL_MODE_PARAMS |
| `Common` | 149 | 通用工具 | `get_log_path`, `safe_read_file`, `safe_write_file` |
| `DataCache` | 197 | 数据缓存与API封装 | `get_daily_data`, `get_15m_data`, `load/save_pkl_cache` |
| `SelectionAgent` | 414 | 选股漏斗与形态识别 | `build_watchlist`, `select`, `score_breakout_stock`, `detect_morning_gap_up` |
| `ExecutionAgent` | 1080 | 订单执行与轮换 | `buy_new`, `find_weakest_position`, `_get_day_change` |
| `MarketDetector` | 1344 | 基于持仓的市场环境检测 | `detect_market_mode` |
| `PositionAgent` | 1407 | 高频风控与持仓管理 | `check_intraday_exit`, `simple_take_profit`, `calc_profit_ratio_safely` |

### 3.3 官方 API 优先

- 日志输出必须使用 PTrade 的全局 `log.info/warn/error`
- 技术指标计算优先使用原生接口（如 `get_MACD`），禁止引入 `talib`
- `get_history` 参数：`is_dict=True`, `include=False`, 日线 `fq='dypre'`, 5分钟 `fq=None`

### 3.4 核心流程

#### initialize(context)
- 设置基准指数(000300.SS)、初始化全局变量（峰值价格、买入日期、预警状态等）
- 加载pkl缓存

#### before_trading_start(context, data)
- 更新日期字符串、清理旧缓存

#### handle_data(context, data)
- **5分钟截流**：只在每5分钟的bar上执行
- **9:35 早盘入场**（仅uptrend模式开启）：检测跳空高开
- **14:30 主力入场**：四重条件选股 → S级过滤 → 权重分配 → 买入
- **09:35~14:55 盘中风控**：调用 `PositionAgent.check_intraday_exit()` 执行五层保护

#### after_trading_end(context, data)
- 输出市场模式日志和持仓评估
- 持仓盈亏 CSV 持久化
- 保存 pkl 缓存

---

## 4. 参数化配置中心 (ConfigManager)

### 4.1 基础配置

```python
MAX_POSITIONS = 6              # 最大持仓股票数
BENCHMARK_INDEX = "000300.SS"  # 沪深300
BUY_TIME = (14, 30)            # 主力买入时间
```

### 4.2 选股漏斗阈值

```python
FILTER_CAPITAL = {
    "MIN_TOTAL_CAPITAL": 30e8,    # 总市值 > 30亿
    "MAX_TOTAL_CAPITAL": 200e8,   # 总市值 < 200亿
    "MAX_FLOAT_CAPITAL": 80e8,    # 流通市值 < 80亿
    "MAX_PRICE": 80.0,            # 股价 < 80元
    "MIN_TURNOVER": 30e6,         # 最小成交额 3000万
}
```

### 4.3 突破检测

```python
BREAKOUT = {
    "LOOKBACK_DAYS": 20,
    "VOL_MULTIPLIER_WEAK": 0.8,      # 弱量突破倍数
    "VOL_MULTIPLIER_STRONG": 1.5,    # 强量突破倍数
    "MA_CONVERGENCE": 0.07,          # 均线粘合度 7%
    "MACD_ZERO_AXIS_LIMIT": 2.0,     # MACD零轴限制
    "MACD_OPTIONAL_MODE": True,      # MACD可选模式
    "ALLOW_3_OF_4": True,            # 允许3/4条件
    "ALLOW_2_OF_4": True,            # 允许2/4条件(B级)
}
```

### 4.4 打分权重

```python
SCORING_WEIGHTS = {
    "MA_CONVERGENCE": 0.30,
    "BREAKOUT_RATIO": 0.25,
    "VOLUME_RATIO": 0.25,
    "MACD_STRENGTH": 0.20,
}
SCORING_TOP_K_MIN = 3
```

### 4.5 止损止盈

```python
SIMPLE_STOP = {
    "MA_PERIOD": 20,                  # MA20均线周期
    "MAX_DRAWDOWN_FROM_PEAK": 0.20,   # 峰值回撤>20%强制卖出
    "PROFIT_LOCK_THRESHOLD": 0.03,    # 盈利>3%后启用成本价锁定
    "PROFIT_LOCK_RATIO": 0.50,        # 锁定50%浮盈
}

SIMPLE_TAKE_PROFIT = {
    "L1": {"PROFIT_MIN": 0.20, "SELL_RATIO": 0.30},  # 盈利20%卖30%
    "L2": {"PROFIT_MIN": 0.40, "SELL_RATIO": 0.30},  # 盈利40%再卖30%
}
```

### 4.6 买入价格限制

```python
BUY_PRICE_LIMIT = {
    "MAX_INTRADAY_RISE": 0.05,
    "WARN_DAY_CHANGE": 0.05,
    "MAX_DAY_CHANGE": 0.03,
    "GRADE_MAX_CHANGE": {"S": 0.15, "A": 0.10, "B": 0.08, "C": 0.02},
}
```

### 4.7 轮换

```python
ROTATE_ENABLED = True
ROTATE_SCORE_THRESHOLD = 1.0
```

---

## 5. 避坑与修复记录

### 5.1 盘中5分钟级止盈止损未触发与 RuntimeError (v01)
- 时间条件修正为完整覆盖；遍历前 `list()` 转换防迭代器失效

### 5.2 PTrade沙盒环境文件读写 (v01)
- 路径纠正到策略目录；IO封装入Common类；CSV写入GBK编码

### 5.3 API参数硬编码约束 (v01)
- `get_history` 参数写死；Config从Config重命名

### 5.4 官方对象属性误用 (v01)
- 可用资金用 `context.portfolio.cash`；订单代码用 `order.symbol`

### 5.5 Step3市值过滤穿透 (v03)
- 使用本地字段 `total_shares`/`a_floats`；位置参数形式；batch_size=100

### 5.6 预警日志爆炸 (v03)
- 引入 `_warning_state` 字典，30分钟节流

### 5.7 突破信号稀疏 (v03)
- MACD零轴放宽至2.0；量能双档制；熊市粘合设下限

### 5.8 轮换机制从未触发 (v03)
- 阈值从1.2下调至1.0

### 5.9 市场状态引擎输出100%静态值 (opt_10) → ✅ 已解决
- **原始问题**（opt_10时代）：000300.SS日线数据完全静态（每日close=4753.87，117天完全相同）
- **根因**：当时指数数据文件缺失或损坏
- **修复**：重新下载指数数据后问题解决
- **当前状态** (S2终版)：`data/cn/stocks/000300.SS.parquet` 包含548行动态数据（2024-01~2026-04），每日close均不同（范围3159~4791）
- **架构决策**：虽然外部指数已动态化，但S2版本继续使用MarketDetector（基于持仓组合），因其在当前版本中已验证有效

### 5.10 时间止损盈利比例异常 (opt_10)
- 出现411767%、4919827%等异常值
- **根因**：误将 `cost_basis` 当作总成本除以 `amount`
- **修复**：`cost_basis` 本身就是每股成本价，直接用于计算

### 5.11 🆕 opt_16 止损频率一刀切导致严重退化
- 将所有模式的 STOP_DATA_FREQUENCY 改为 daily 导致震荡市从+0.33%退化至-16.85%
- **根因**：止损频率改变导致MarketDetector模式检测级联效应（uptrend天数37→89天）
- **教训**：不能随意修改止损频率，会破坏模式检测平衡

### 5.12 🆕 固定止盈是牛市最大敌人
- C1实验证明：取消固定止盈使牛市从+7.13%跃升至+27.73%（+20.6pp）
- 回撤反而从-17.53%降至-5.25%
- **结论**：牛市中"让利润奔跑"远胜于"频繁止盈锁利"

### 5.13 🆕 集中持仓在当前选股质量下有害
- C2实验：MAX_POSITIONS从6减至3，牛市从+27.73%跌至-12.06%
- **原因**：烂股(-13%)在3只中权重太大拖垮整体；6只分散时赢家可弥补输家

### 5.14 🆕 按模式差异化仓位是震荡市优化的关键
- S2实验：sideways模式下max_pos_ratio从0.95降至0.50
- 震荡市从-5.00%跃升至+24.14%（改善29pp）
- 牛市不降反升至+71.45%（因uptrend仍保持0.95激进仓位）

---

## 附录 A: 回测结果汇总 (S2终版)

| 回测周期 | 总收益率 | 年化收益率 | 最大回撤 | 夏普比率 | 索提诺比率 | 最终资产 |
|---------|---------|-----------|---------|---------|-----------|---------|
| **震荡市 (2025-01~06)** | **+24.14%** | **+59.33%** | -20.09% | 1.428 | 1.876 | **124.1万** |
| **牛市 (2025-07~12)** | **+71.45%** | **+193.94%** | **-9.26%** | **2.705** | **6.695** | **171.5万** |

### vs 历史版本对比

| 版本 | 震荡市 | 牛市 | 震荡市年化 | 牛市年化 | 牛市最大回撤 |
|------|--------|------|----------|---------|------------|
| opt_10 | +14.15% | +6.00% | +32.99% | +12.35% | -19.14% |
| opt_15 | +0.33% | -2.79% | +0.66% | -5.50% | -17.53% |
| **S2终版** | **+24.14%** | **+71.45%** | **+59.33%** | **+193.94%** | **-9.26%** |

### 牛市典型持仓亮点（2025-12-31）

| 股票代码 | 收益率 | 备注 |
|---------|--------|------|
| 603091.SS | +84.27% | 最大赢家 🔥 |
| 300818.SZ | +71.29% | 第二大赢家 🔥 |
| 300811.SZ | +55.98% | 超级牛股（曾被止盈切碎，S2不再切碎） |
| 603773.SS | +51.72% | 稳定牛股 |
| 000796.SZ | +48.33% | 不错 |

### 市场模式分布统计（牛市126天）

| 市场模式 | 天数 | 占比 |
|---------|------|------|
| trending_uptrend | ~112天 | ~89% |
| sideways | ~14天 | ~11% |
| trending_downtrend | ~0天 | ~0% |

---

## 附录 B: S2终版生成的文件列表

| 文件类型 | 文件路径 |
|---------|---------|
| 策略文件 | strategies/trends_up_new/backtest.py |
| 震荡市日志 | stats/backtest_250101_250630_260414_071111.log |
| 震荡市图表 | stats/backtest_250101_250630_260414_071111.png |
| 牛市日志 | stats/backtest_250701_251231_260414_090350.log |
| 牛市图表 | stats/backtest_250701_251231_260414_090350.png |

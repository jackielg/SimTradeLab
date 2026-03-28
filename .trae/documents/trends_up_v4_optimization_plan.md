# trends_up 策略优化计划 v4.0

**制定日期**: 2026-03-27  
**优化目标**: 收益率从 +7.64% 提升至 **> 50%**  
**参考策略**: myTrendStrategy (内部类架构、ATR 止损、动态仓位)

---

## 一、当前策略分析

### 1.1 当前状态 (v3.0)

**策略逻辑**: 横盘突破 + 相对强度

**核心问题**:
1. ❌ **硬编码 fallback**: 使用了 10 只蓝筹股作为 fallback（违反要求）
2. ❌ **固定止损**: 8% 固定止损，不够灵活
3. ❌ **静态仓位**: 固定 10% 仓位，没有根据大盘动态调整
4. ❌ **简单评分**: 评分系统过于简单，缺乏多维度分析
5. ❌ **无止盈策略**: 只有止损，没有主动止盈

**回测表现** (2025-04-01 ~ 2025-07-31):
- 总收益率：+7.64% (目标 > 50%)
- 最大回撤：-9.22% (优秀)
- 胜率：54.9% (良好)
- 盈亏比：0.96 (待提升)

### 1.2 可借鉴的历史经验 (myTrendStrategy)

**核心优势**:
1. ✅ **内部类架构**: ConfigManager, Common, TrendStrengthScorer, PositionManager, ExitStrategy
2. ✅ **ATR 吊灯止损**: 根据波动率动态调整止损位
3. ✅ **动态仓位管理**: 根据大盘状态 (牛/熊/震荡) 调整仓位
4. ✅ **多维度趋势评分**: 方向 (40%) + 动量 (35%) + 成交量 (15%) + 质量 (10%)
5. ✅ **分级止盈**: 12%/25%/45%/70% 四档止盈
6. ✅ **移动止盈**: 高点回撤保护
7. ✅ **时间止损**: 超时无收益自动退出

---

## 二、优化方案

### 2.1 核心优化点

#### 优化 1: 去除硬编码 fallback
**当前问题**: `get_all_stocks()` 失败时使用 10 只蓝筹股 fallback  
**优化方案**: 
- 完全去除 fallback 代码
- 增强错误处理，失败时返回空列表
- 依赖 get_Ashares() 的稳定性

#### 优化 2: 引入 ATR 吊灯止损
**当前问题**: 固定 8% 止损，不适应不同波动率的股票  
**优化方案**:
```python
# ATR 吊灯止损公式
atr = ATR(high, low, close, period=14)
stop_loss_price = highest_high - ATR_MULTIPLIER * atr
# ATR_MULTIPLIER = 3.0 (可调整)
```

**优势**:
- 高波动率股票：止损位更宽，避免被洗出
- 低波动率股票：止损位更紧，保护利润

#### 优化 3: 动态仓位管理
**当前问题**: 固定 10% 仓位，没有根据大盘调整  
**优化方案**:
```python
# 根据大盘状态动态调整仓位
if market_state == "bull":
    base_position = 0.20  # 牛市 20%
elif market_state == "neutral":
    base_position = 0.15  # 震荡市 15%
else:  # bear
    base_position = 0.10  # 熊市 10% (最低也允许买股票)
```

**大盘状态判断**:
- 牛市：指数 > MA20 且 MA20 > MA60
- 熊市：指数 < MA20 且 MA20 < MA60
- 震荡市：其他情况

#### 优化 4: 引入内部类架构
**当前问题**: 函数式代码，难以维护和扩展  
**优化方案**: 引入 5 个内部类

1. **ConfigManager**: 配置参数统一管理
2. **TrendStrengthScorer**: 趋势强度评分器
3. **PositionManager**: 仓位管理器
4. **ExitStrategy**: 退出策略管理器
5. **MarketStateAnalyzer**: 大盘状态分析器

#### 优化 5: 多维度趋势评分系统
**当前问题**: 简单 4 维度评分，缺乏深度  
**优化方案**:
```python
# 趋势强度评分 (0-1 分)
direction_score (40%):
  - MA5 > MA20 (0.5 分)
  - MA20 > MA60 (0.25 分)
  - Price > MA20 (0.25 分)

momentum_score (35%):
  - 5 日涨幅 (0.4 分)
  - 20 日涨幅 (0.45 分)
  - 60 日涨幅 (0.15 分)

volume_score (15%):
  - 量比 MA5/MA20 (0.25 分)
  - 价量相关性 (0.5 分)
  - 成交量突增 (0.25 分)

quality_score (10%):
  - 波动率 ATR (0.3 分)
  - 夏普比率 20 日 (0.45 分)
  - 最大回撤 (0.25 分)
```

#### 优化 6: 分级止盈 + 移动止盈
**当前问题**: 无止盈策略  
**优化方案**:
```python
# 分级止盈
if profit >= 0.12: sell 30%
if profit >= 0.25: sell 30%
if profit >= 0.45: sell 20%
if profit >= 0.70: clear all

# 移动止盈 (高点回撤保护)
if highest_price > cost * 1.10:
    trailing_stop = highest_price * 0.92
    if current_price < trailing_stop: sell
```

#### 优化 7: 时间止损
**当前问题**: 无时间止损  
**优化方案**:
```python
# 时间止损规则
if holding_days > 25 and profit < 0.05:
    sell  # 25 天收益<5%，时间止损

# 亏损时间止损
if holding_days > 25 and profit < -0.10:
    sell  # 25 天亏损>10%，强制止损
```

---

### 2.2 技术实现细节

#### ATR 计算实现
```python
def calculate_atr(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    return atr
```

#### 大盘状态判断实现
```python
def analyze_market_state(context):
    benchmark = get_price('000300.SS', count=65, fields=['close'])
    
    ma20 = benchmark['close'].rolling(20).mean().iloc[-1]
    ma60 = benchmark['close'].rolling(60).mean().iloc[-1]
    current_price = benchmark['close'].iloc[-1]
    
    if current_price > ma20 and ma20 > ma60:
        return "bull"
    elif current_price < ma20 and ma20 < ma60:
        return "bear"
    else:
        return "neutral"
```

#### 动态仓位计算实现
```python
def calculate_position_size(trend_score, market_state):
    # 基础仓位根据市场状态
    if market_state == "bull":
        base = 0.20
    elif market_state == "neutral":
        base = 0.15
    else:
        base = 0.10
    
    # 根据趋势评分调整
    if trend_score >= 0.7:
        position = base * 1.0  # 强势趋势，满仓
    elif trend_score >= 0.5:
        position = base * 0.8  # 中强势，8 折
    elif trend_score >= 0.35:
        position = base * 0.6  # 中等，6 折
    else:
        position = base * 0.4  # 弱势，4 折
    
    return min(position, 0.20)  # 单股不超过 20%
```

---

## 三、实施计划

### Phase 1: 代码重构 (1-2 天)

**任务**:
1. ✅ 创建内部类架构
   - ConfigManager (配置管理)
   - TrendStrengthScorer (趋势评分)
   - PositionManager (仓位管理)
   - ExitStrategy (退出策略)
   - MarketStateAnalyzer (大盘分析)

2. ✅ 去除硬编码 fallback
   - 删除 10 只蓝筹股 fallback 代码
   - 增强错误处理

3. ✅ 重构主流程
   - initialize: 初始化类实例
   - select_stocks: 使用新的评分系统
   - handle_data: 使用新的退出策略

**输出**: `strategies/trends_up/optimize_02/backtest.py`

### Phase 2: 核心功能实现 (1-2 天)

**任务**:
1. ✅ 实现 ATR 吊灯止损
   - ATR 计算函数
   - 动态止损位计算
   - 集成到 ExitStrategy

2. ✅ 实现动态仓位管理
   - 大盘状态判断函数
   - 仓位计算函数
   - 集成到 PositionManager

3. ✅ 实现多维度趋势评分
   - 4 个维度评分函数
   - 权重配置
   - 集成到 TrendStrengthScorer

**输出**: 完整的内部类实现

### Phase 3: 止盈策略实现 (0.5-1 天)

**任务**:
1. ✅ 实现分级止盈
   - 4 档止盈阈值
   - 卖出比例计算
   - 集成到 ExitStrategy

2. ✅ 实现移动止盈
   - 高点跟踪
   - 回撤计算
   - 触发条件判断

3. ✅ 实现时间止损
   - 持仓天数跟踪
   - 时间止损条件
   - 集成到 ExitStrategy

**输出**: 完整的退出策略系统

### Phase 4: 回测验证 (1 天)

**任务**:
1. ✅ 回测 2025-04-01 ~ 2025-07-31 (震荡市)
   - 验证收益率是否提升至 > 50%
   - 验证最大回撤 < 15%
   - 验证盈亏比 > 1.5

2. ✅ 回测 2024-09-01 ~ 2024-12-31 (牛市)
   - 验证牛市弹性
   - 验证动态仓位效果

3. ✅ 回测 2024-01-01 ~ 2024-12-31 (完整年)
   - 验证全年稳定性
   - 验证不同市场环境适应性

**输出**: 回测结果保存到 `strategies/trends_up/optimize_02/stats/`

### Phase 5: QA 审查 (0.5 天)

**任务**:
1. ✅ 代码质量审查
   - 检查内部类实现
   - 检查代码规范
   - 检查注释完整性

2. ✅ 回测结果验证
   - 验证收益率达标
   - 验证风险指标
   - 生成 QA 报告

**输出**: `strategies/trends_up/optimize_02/qa_report.md`

---

## 四、验收标准

### 4.1 核心指标 (必须达标)

| 指标 | 当前值 | 目标值 | 验收标准 |
|------|--------|--------|----------|
| 总收益率 | +7.64% | > 50% | ✅ 必须达标 |
| 最大回撤 | -9.22% | < 15% | ✅ 必须达标 |
| 盈亏比 | 0.96 | > 1.5 | ✅ 必须达标 |
| 胜率 | 54.9% | > 55% | ✅ 必须达标 |

### 4.2 功能验收 (必须完成)

- ✅ 去除硬编码 fallback
- ✅ 实现 ATR 吊灯止损
- ✅ 实现动态仓位管理
- ✅ 引入内部类架构
- ✅ 实现多维度趋势评分
- ✅ 实现分级止盈 + 移动止盈
- ✅ 实现时间止损

### 4.3 代码质量验收

- ✅ 代码结构清晰，内部类职责明确
- ✅ 注释完整，关键逻辑有说明
- ✅ 无死代码、无冗余导入
- ✅ 遵循 PTrade API 规范
- ✅ 文档齐全 (design.md, qa_report.md)

---

## 五、风险评估

### 5.1 技术风险

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| ATR 计算错误 | 低 | 高 | 单元测试验证 |
| 动态仓位计算错误 | 中 | 高 | 日志记录详细计算过程 |
| 内部类初始化失败 | 低 | 高 | 异常处理和 fallback |
| 回测结果不达标 | 中 | 高 | 多轮回测调优 |

### 5.2 时间风险

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 代码重构超时 | 低 | 中 | 分阶段实施，每阶段验收 |
| 回测运行超时 | 中 | 中 | 使用优化框架，并行回测 |
| QA 审查发现问题 | 高 | 中 | 预留缓冲时间 |

---

## 六、文档管理

### 6.1 文档输出清单

按照 agents_rules.md 要求:

1. ✅ **design.md**: 策略设计文档 (更新现有)
   - 位置：`strategies/trends_up/design.md`
   - 内容：优化方案设计、内部类架构、算法说明

2. ✅ **qa_report.md**: QA 审查报告
   - 位置：`strategies/trends_up/optimize_02/qa_report.md`
   - 内容：代码审查、回测验证、问题清单

3. ✅ **回测结果**: 统计图表
   - 位置：`strategies/trends_up/optimize_02/stats/`
   - 内容：backtest_*.png, backtest_*.log

### 6.2 文档结构

```
strategies/trends_up/
├── design.md                    # 策略设计文档 (更新)
├── backtest.py                  # 当前策略
└── optimize_02/                 # 第 2 次优化
    ├── backtest.py              # 优化版本
    ├── backtest_backup_20260327.py  # 备份
    ├── optimization_plan.md     # 本优化计划
    ├── qa_report.md             # QA 审查报告
    └── stats/
        ├── backtest_20250401_20250731.png
        ├── backtest_20240901_20241231.png
        └── backtest_20240101_20241231.png
```

---

## 七、多智能体协作

### 7.1 角色分工

**Strategy-Arch (架构师)**:
- ✅ 制定优化方案和架构设计
- ✅ 设计内部类结构
- ✅ 定义评分系统和仓位管理逻辑
- ✅ 审批最终方案
- ✅ 输出：design.md, optimization_plan.md

**Strategy-Engr (工程师)**:
- ✅ 实现内部类 (ConfigManager 等)
- ✅ 实现 ATR 止损、动态仓位、趋势评分
- ✅ 实现止盈策略
- ✅ 运行回测验证
- ✅ 输出：backtest.py, stats/

**Strategy-QA (质量保障)**:
- ✅ 审查代码质量
- ✅ 分析回测结果
- ✅ 验证是否达到目标
- ✅ 提出改进建议
- ✅ 输出：qa_report.md

### 7.2 协作流程

```
1. Strategy-Arch 制定优化方案
   ↓
   输出：optimization_plan.md (本文件)

2. Strategy-Engr 备份代码
   ↓
   输出：backtest_backup_20260327.py

3. Strategy-Engr 实现优化
   ↓
   输出：optimize_02/backtest.py

4. Strategy-Engr 运行回测
   ↓
   输出：optimize_02/stats/

5. Strategy-QA 审查代码和回测结果
   ↓
   输出：optimize_02/qa_report.md

6. Strategy-Arch 最终验收
   ↓
   输出：验收结论
```

---

## 八、下一步行动

### 立即执行

1. **Strategy-Arch**: 审批本优化计划 ✅
2. **Strategy-Engr**: 备份当前代码 ⏳
3. **Strategy-Engr**: 创建 optimize_02 目录 ⏳

### 待执行

4. **Strategy-Engr**: 实现内部类架构
5. **Strategy-Engr**: 实现 ATR 止损
6. **Strategy-Engr**: 实现动态仓位
7. **Strategy-Engr**: 实现趋势评分系统
8. **Strategy-Engr**: 实现止盈策略
9. **Strategy-Engr**: 运行回测验证
10. **Strategy-QA**: 审查代码和回测
11. **Strategy-Arch**: 最终验收

---

**计划版本**: v4.0  
**制定日期**: 2026-03-27  
**制定人**: 多智能体协作系统  
**状态**: 待审批

---

## 附录：关键代码片段参考

### A.1 ConfigManager 参考
```python
class ConfigManager:
    STRATEGY_PARAMS = {
        "MAX_HOLDING": 6,
        "TOTAL_VALUE_CAP_LIMIT": 300e8,
        "RISK_CONTROL": {
            "MAX_POSITION_PCT": 0.45,
            "MIN_CASH_RATIO": 0.01,
        },
        "TREND_STRENGTH": {
            "DIRECTION_WEIGHT": 0.40,
            "MOMENTUM_WEIGHT": 0.35,
            "VOLUME_WEIGHT": 0.15,
            "QUALITY_WEIGHT": 0.10,
        },
        "DYNAMIC_RISK": {
            "ATR_PERIOD": 14,
            "STOP_LOSS_ATR": 3.0,
        },
    }
```

### A.2 ATR 止损参考
```python
class ExitStrategy:
    def check_atr_stop_loss(self, position, current_price, df):
        atr = self.calculate_atr(df, period=14)
        highest_high = df['high'].iloc[-20:].max()
        
        stop_loss_price = highest_high - 3.0 * atr
        if current_price < stop_loss_price:
            return True, "ATR 吊灯止损"
        
        return False, None
```

### A.3 动态仓位参考
```python
class PositionManager:
    def calculate_position_size(self, trend_score, market_state):
        base_positions = {
            "bull": 0.20,
            "neutral": 0.15,
            "bear": 0.10,
        }
        
        base = base_positions.get(market_state, 0.15)
        
        score_multipliers = {
            "strong": 1.0,
            "medium": 0.8,
            "weak": 0.6,
        }
        
        if trend_score >= 0.7:
            multiplier = score_multipliers["strong"]
        elif trend_score >= 0.5:
            multiplier = score_multipliers["medium"]
        else:
            multiplier = score_multipliers["weak"]
        
        return min(base * multiplier, 0.20)
```

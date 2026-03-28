# 任务单：Trends_UP v4.3 策略实现

## 任务基本信息

| 项目 | 内容 |
|------|------|
| **任务 ID** | task_trends_up_v43_implementation |
| **任务名称** | Trends_UP v4.3 策略代码实现 |
| **优先级** | 高 |
| **预计工期** | 12 天 |
| **创建日期** | 2026-03-28 |
| **执行者** | @Strategy-Engr |
| **验收者** | @Strategy-QA |
| **状态** | pending |

---

## 任务描述

根据设计文档 `strategies/trends_up/optimize_03/optimization_design_v43.md`，完成 Trends_UP v4.3 策略的代码实现。

### 核心目标

1. **选股质量提升**：胜率从 v4.2 的 42-57% 提升至>60%
2. **盈亏比改善**：从 v4.2 的 0.66-1.06 提升至>1.5
3. **回撤控制**：从 v4.2 的 -22%~-47% 控制在<20%

---

## 实现要求

### 1. 文件结构

创建以下文件：

```
strategies/trends_up/v43/
├── __init__.py              # 包初始化
├── config.py                # 配置参数
├── trends_up_v43.py         # 主策略文件
├── stock_selection.py       # 选股模块
├── exit_strategy.py         # 退出策略模块
├── risk_control.py          # 风控模块
└── utils.py                 # 辅助工具函数
```

### 2. 核心模块实现

#### 2.1 选股模块（权重 50%）

**文件**：`stock_selection.py`

**实现内容**：
- `filter_stock_pool()` - 初筛股票池（剔除 ST、*ST、上市<60 天）
- `check_weekly_conditions()` - 周线筛选（硬性条件）
  - 均线多头排列（MA5>MA10>MA20>MA60）
  - MACD 金叉且在 0 轴上方
  - 成交量 MA5>MA20
- `check_daily_conditions()` - 日线确认（硬性条件）
  - 平台突破（20-60 天）
  - 成交量>200%
  - MACD 二次金叉
- `calculate_stock_score()` - 综合评分（100 分制）
  - 趋势评分（40 分）
  - 成交量评分（30 分）
  - 突破评分（20 分）
  - 基本面评分（10 分）
- `select_stocks()` - 执行选股流程

**关键代码参考**：设计文档附录 A.1 和 A.2

#### 2.2 退出策略模块（权重 30%）

**文件**：`exit_strategy.py`

**实现内容**：
- `check_atr_stop_loss()` - ATR 止损（1.8 倍）
- `check_profit_target()` - 分级止盈（3 档：10%/20%/30%）
- `check_trailing_stop()` - 移动止盈（回撤 8% 清仓）
- `check_time_stop()` - 时间止损（15 天盈利<5% 或 10 天亏损>5%）
- `check_exit_conditions()` - 统一检查所有退出条件（按优先级）

**退出优先级**：
1. ATR 止损（最高优先级）
2. 时间止损
3. 移动止盈（盈利>5% 后启用）
4. 分级止盈

#### 2.3 风控模块（权重 20%）

**文件**：`risk_control.py`

**实现内容**：
- `update_portfolio_metrics()` - 更新组合指标
  - peak_capital 更新
  - current_drawdown 计算
  - industry_positions 统计
- `get_position_limit()` - 获取仓位上限
  - 回撤>10% → 仓位上限 50%
  - 回撤>15% → 强制空仓
- `check_industry_concentration()` - 行业集中度控制（单行业≤30%）
- `check_market_state()` - 熊市判断（沪深 300 在年线下方 5%）
  - 熊市仓位 3%
  - 正常仓位 5%

#### 2.4 主策略文件

**文件**：`trends_up_v43.py`

**实现内容**：
- `TrendsUpV43` 类结构
- `initialize()` - 初始化策略
- `handle_data()` - 每日数据处理
- `before_trading_start()` - 开盘前处理
- `after_trading_end()` - 收盘后处理
- `rebalance_portfolio()` - 调仓执行

#### 2.5 配置参数

**文件**：`config.py`

**实现内容**：
```python
CONFIG = {
    # 选股参数
    'max_positions': 10,
    'min_total_score': 75,
    'min_trend_score': 28,
    'min_volume_score': 20,
    'min_breakout_score': 14,
    
    # 退出参数
    'atr_stop_multiple': 1.8,
    'profit_targets': [0.10, 0.20, 0.30],
    'profit_sell_ratios': [0.30, 0.30, 0.20],
    'trailing_stop_pct': 0.08,
    'time_stop_days_1': 15,
    'time_stop_profit_1': 0.05,
    'time_stop_days_2': 10,
    'time_stop_profit_2': -0.05,
    
    # 风控参数
    'drawdown_level_1': -0.10,
    'drawdown_level_2': -0.15,
    'max_industry_ratio': 0.30,
    'bear_market_ratio': 0.03,
    'normal_market_ratio': 0.05,
    'max_single_stock': 0.10,
}
```

#### 2.6 辅助工具

**文件**：`utils.py`

**实现内容**：
- `calculate_ma_angle()` - 计算均线角度
- `check_golden_cross_in_range()` - 检查指定范围内金叉
- `calculate_volume_ratio()` - 计算量比
- `get_fundamental_data()` - 获取基本面数据
- `get_stock_industry()` - 获取股票所属行业

---

## 技术要求

### 1. 代码规范

- 遵循 PEP 8 编码规范
- 所有函数必须有 docstring
- 关键逻辑必须有注释
- 使用类型注解（Type Hints）

### 2. 错误处理

- 数据获取失败时捕获异常并记录日志
- 关键计算前进行数据有效性检查
- 避免除零错误、空指针异常

### 3. 性能要求

- 单次选股耗时 < 5 秒
- 内存占用 < 500MB
- 支持并发处理（可选优化）

### 4. 日志系统

```python
import logging

logger = logging.getLogger('trends_up_v43')

# 日志级别
- INFO: 正常交易操作
- WARNING: 警告信息（如数据缺失）
- ERROR: 错误信息（如 API 调用失败）
```

---

## 交付物

### 1. 代码文件

- [ ] `strategies/trends_up/v43/__init__.py`
- [ ] `strategies/trends_up/v43/config.py`
- [ ] `strategies/trends_up/v43/trends_up_v43.py`
- [ ] `strategies/trends_up/v43/stock_selection.py`
- [ ] `strategies/trends_up/v43/exit_strategy.py`
- [ ] `strategies/trends_up/v43/risk_control.py`
- [ ] `strategies/trends_up/v43/utils.py`

### 2. 测试文件

- [ ] `tests/test_v43_stock_selection.py` - 选股模块测试
- [ ] `tests/test_v43_exit_strategy.py` - 退出策略测试
- [ ] `tests/test_v43_risk_control.py` - 风控模块测试
- [ ] `tests/test_v43_integration.py` - 集成测试

### 3. 文档

- [ ] `strategies/trends_up/v43/README.md` - 模块说明
- [ ] `strategies/trends_up/v43/CHANGELOG.md` - 变更日志

---

## 验收标准

### 1. 功能验收

| 功能 | 验收标准 | 验证方法 |
|------|----------|----------|
| 周线筛选 | 正确率 100% | 单元测试，100 只已知牛股测试 |
| 日线确认 | 正确率 100% | 单元测试，100 只已知牛股测试 |
| 评分系统 | 误差<5% | 与手工评分对比 |
| ATR 止损 | 触发准确 | 回测验证止损执行 |
| 分级止盈 | 三档正确执行 | 回测验证止盈记录 |
| 移动止盈 | 回撤<10% 清仓 | 回测验证最高价回撤 |
| 时间止损 | 15 天/10 天规则生效 | 回测验证持仓天数 |
| 组合回撤控制 | >10% 降仓 50%，>15% 空仓 | 模拟回撤场景测试 |
| 行业集中度 | 单行业≤30% | 检查持仓行业分布 |
| 熊市仓位 | 沪深 300 年线下方 3% 仓位 | 历史熊市数据验证 |

### 2. 性能指标

| 指标 | 目标值 | 验证方法 |
|------|--------|----------|
| 年化收益率 | > 30% | 2018-2025 回测 |
| 最大回撤 | < 20% | 回测报告 |
| 胜率 | > 60% | 回测报告 |
| 盈亏比 | > 1.5 | 回测报告 |
| 夏普比率 | > 1.5 | 回测报告 |
| 选股耗时 | < 5 秒 | 性能测试 |

### 3. 代码质量

| 指标 | 目标值 | 验证方法 |
|------|--------|----------|
| 单元测试覆盖率 | > 80% | coverage 报告 |
| 代码审查通过率 | 100% | Strategy-QA 审查 |
| 文档完整度 | 100% | 文档检查清单 |

---

## 实现步骤（建议）

### 第 1-2 天：核心框架搭建

1. 创建文件结构
2. 实现 `config.py` 配置参数
3. 实现 `utils.py` 辅助函数
4. 实现 `TrendsUpV43` 类框架

### 第 3-5 天：选股模块实现

1. 实现 `filter_stock_pool()`
2. 实现 `check_weekly_conditions()`
3. 实现 `check_daily_conditions()`
4. 实现 `calculate_stock_score()`
5. 编写选股模块单元测试

### 第 6-7 天：退出策略模块实现

1. 实现 `check_atr_stop_loss()`
2. 实现 `check_profit_target()`
3. 实现 `check_trailing_stop()`
4. 实现 `check_time_stop()`
5. 编写退出策略单元测试

### 第 8-9 天：风控模块实现

1. 实现 `update_portfolio_metrics()`
2. 实现 `get_position_limit()`
3. 实现 `check_industry_concentration()`
4. 实现 `check_market_state()`
5. 编写风控模块单元测试

### 第 10 天：集成与调仓

1. 实现 `rebalance_portfolio()`
2. 集成所有模块到 `handle_data()`
3. 编写集成测试

### 第 11-12 天：测试与修复

1. 运行所有单元测试
2. 修复 bug
3. 性能优化
4. 准备验收

---

## 依赖关系

### 输入依赖

- 设计文档：`strategies/trends_up/optimize_03/optimization_design_v43.md`
- 牛股特征文档：`strategies/trends_up/optimize_03/bull_stock_features.md`

### 输出依赖

- 代码审查：@Strategy-QA
- 回测验证：@Strategy-QA

---

## 风险提示

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| 数据质量 | 选股准确性下降 | 增加数据质量检查，缺失数据跳过 |
| API 限制 | 选股超时 | 分批处理，每批 100 只股票 |
| 过拟合 | 实盘表现不佳 | 使用 2018-2023 训练，2024-2025 验证 |
| 市场风格切换 | 策略失效 | 每季度评估参数有效性 |

---

## 备注

1. **优先保证代码质量**，不要为了赶工期牺牲代码规范
2. **充分测试**，每个模块都要有对应的单元测试
3. **及时沟通**，遇到问题及时与 Strategy-Arch 和 Strategy-QA 沟通
4. **文档同步**，代码完成后及时更新 README 和 CHANGELOG

---

**任务创建者**：Strategy-Arch  
**创建日期**：2026-03-28  
**最后更新**：2026-03-28

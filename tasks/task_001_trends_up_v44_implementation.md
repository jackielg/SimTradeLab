# 任务单：Trends Up v4.4 策略实现

## 任务信息
- **任务编号**: TASK-001
- **任务名称**: Trends Up v4.4 策略核心逻辑实现
- **优先级**: P0（最高优先级）
- **状态**: 待执行
- **创建日期**: 2026-03-28
- **负责人**: @Strategy-Engr
- **验收人**: @Strategy-QA

---

## 任务描述
基于设计文档 [v44_optimization_design.md](file:///c:/Users/Admin/SynologyDrive/PtradeProjects/SimTradeLab/strategies/trends_up/optimize_03/v44_optimization_design.md)，实现 Trends Up v4.4 策略的核心逻辑，包括选股模型、退出策略和仓位管理。

---

## 实现范围

### 1. 选股模型实现（P0）
**文件路径**: `strategies/trends_up/optimize_03/stock_selection.py`

**核心功能**:
- [ ] 实现周线评分函数 `calculate_weekly_score()`（30 分）
  - 周线价格 > 周线 MA20
  - 周线 MA20 > 周线 MA60
  - 周线 RPS > 70
  - 周线成交量 > 周线 MA_VOL_20 * 0.8
  
- [ ] 实现日线评分函数 `calculate_daily_score()`（70 分）
  - 价格突破（25 分）
  - 成交量确认（20 分）
  - 动量指标（15 分）
  - 资金流向（10 分）

- [ ] 实现综合评分函数 `calculate_total_score()`
  - 权重：周线 30% + 日线 70%
  - 评分门槛：≥ 55 分

- [ ] 实现选股函数 `select_stocks()`
  - 返回评分最高的 15 只股票
  - 按评分降序排序

---

### 2. 退出策略实现（P0）
**文件路径**: `strategies/trends_up/optimize_03/exit_strategy.py`

**核心功能**:
- [ ] 实现 ATR 止损函数 `check_atr_stop_loss()`
  - ATR 周期：20 日
  - 止损倍数：2.5 倍（基础）
  - 动态调整：持仓>10 天 → 3.0 倍

- [ ] 实现分级止盈函数 `check_take_profit()`
  - 第 1 档：涨幅 ≥ 20% → 卖出 20%
  - 第 2 档：涨幅 ≥ 40% → 卖出 30%
  - 第 3 档：涨幅 ≥ 60% → 卖出 50%

- [ ] 实现移动止盈函数 `check_trailing_stop()`
  - 启用条件：盈利 > 25%
  - 回撤阈值：12%

- [ ] 实现时间止损函数 `check_time_stop()`
  - 时间门槛：25 天
  - 盈利门槛：< 8%

- [ ] 实现统一退出检查函数 `check_exit_conditions()`
  - 整合所有退出条件
  - 优先级：止损 > 止盈 > 时间止损

---

### 3. 仓位管理实现（P1）
**文件路径**: `strategies/trends_up/optimize_03/position_management.py`

**核心功能**:
- [ ] 实现市场状态识别函数 `identify_market_regime()`
  - 使用沪深 300 指数判断
  - 返回：'trend' / 'volatile' / 'bear'

- [ ] 实现动态仓位函数 `calculate_position_size()`
  - 基础仓位：10%
  - 根据评分调整：
    - score ≥ 85: 15% 仓位
    - score ≥ 75: 13% 仓位
    - score ≥ 65: 11% 仓位
    - score ≥ 55: 10% 仓位
  - 市场状态调整：
    - 震荡市：* 0.7
    - 熊市：* 0.5

- [ ] 实现仓位调整函数 `rebalance_portfolio()`
  - 总仓位上限：90%
  - 最大持股数：15 只
  - 行业集中度：≤ 30%

---

### 4. 主策略文件（P0）
**文件路径**: `strategies/trends_up/optimize_03/strategy.py`

**核心功能**:
- [ ] 实现 `initialize(context)` 函数
  - 初始化所有参数
  - 设置数据缓存

- [ ] 实现 `handle_data(context, data)` 函数
  - 更新市场状态
  - 执行退出检查
  - 计算选股评分（每 5 天）
  - 选股并调整仓位

---

## 技术要求

### 1. 代码规范
- 遵循 PEP8 编码规范
- 所有函数必须有 docstring
- 关键逻辑必须有注释
- 使用类型注解（Type Hints）

### 2. 单元测试
**文件路径**: `strategies/trends_up/optimize_03/tests/`

**测试覆盖**:
- [ ] 选股评分计算测试
- [ ] 退出条件触发测试
- [ ] 仓位计算测试
- [ ] 边界条件测试

### 3. 依赖管理
**文件路径**: `strategies/trends_up/optimize_03/requirements.txt`

```
pandas>=1.3.0
numpy>=1.20.0
ta-lib>=0.4.0  # 技术指标库
```

---

## 验收标准

### 1. 功能验收
- [ ] 选股数量：≥ 12 只/期（平均）
- [ ] 评分计算：与 Excel 手工计算结果一致（误差 < 1%）
- [ ] 退出触发：止损/止盈逻辑正确
- [ ] 仓位计算：符合设计文档公式

### 2. 性能验收
- [ ] 单次 `handle_data()` 执行时间 < 2 秒
- [ ] 内存占用 < 500MB
- [ ] 支持至少 3 年历史数据回测

### 3. 代码质量
- [ ] 单元测试覆盖率 ≥ 80%
- [ ] 无严重代码异味（Code Smell）
- [ ] 通过 @Strategy-QA 代码审查

---

## 交付物

### 1. 代码文件
```
strategies/trends_up/optimize_03/
├── __init__.py
├── strategy.py              # 主策略文件
├── stock_selection.py       # 选股模型
├── exit_strategy.py         # 退出策略
├── position_management.py   # 仓位管理
├── utils.py                 # 工具函数
├── config.py                # 参数配置
├── requirements.txt         # 依赖包
└── tests/
    ├── __init__.py
    ├── test_stock_selection.py
    ├── test_exit_strategy.py
    └── test_position_management.py
```

### 2. 文档文件
- [ ] 代码注释完整
- [ ] README.md（使用说明）
- [ ] CHANGELOG.md（变更日志）

### 3. 测试报告
- [ ] 单元测试结果
- [ ] 代码覆盖率报告
- [ ] 性能测试结果

---

## 时间节点

| 阶段 | 内容 | 截止日期 |
|------|------|----------|
| D+1 | 完成选股模型 + 退出策略 | 2026-03-29 |
| D+2 | 完成仓位管理 + 主策略 | 2026-03-30 |
| D+3 | 完成单元测试 + 自测 | 2026-03-31 |
| D+4 | 提交 @Strategy-QA 审查 | 2026-04-01 |

---

## 风险提示

### 1. 技术风险
- ATR 计算依赖 ta-lib 库，需确保环境已安装
- 周线数据需要特殊处理（日线 → 周线转换）

### 2. 数据风险
- 主力净流入数据可能需要特殊数据源
- 历史数据复权处理需一致

### 3. 性能风险
- 全市场选股可能较慢，需优化计算逻辑
- 建议使用缓存机制减少重复计算

---

## 参考文档

1. [v4.4 优化设计文档](file:///c:/Users/Admin/SynologyDrive/PtradeProjects/SimTradeLab/strategies/trends_up/optimize_03/v44_optimization_design.md)
2. [v4.3 诊断报告](file:///c:/Users/Admin/SynologyDrive/PtradeProjects/SimTradeLab/strategies/trends_up/optimize_03/v43_diagnosis_report.md)
3. [SimTradeLab API 文档](file:///c:/Users/Admin/SynologyDrive/PtradeProjects/SimTradeLab/docs/api_reference.md)

---

## 备注

1. 实现过程中如有疑问，请及时与 Strategy-Arch 沟通
2. 参数调整需在设计文档允许范围内（±5% 浮动）
3. 如需修改核心逻辑，需先更新设计文档并重新评审
4. 提交代码前请确保通过所有单元测试

---

**任务创建人**: Strategy-Arch  
**创建日期**: 2026-03-28  
**最后更新**: 2026-03-28  
**任务状态**: 待执行 → 进行中 → 待验收 → 已完成

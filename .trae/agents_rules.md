# SimTradeLab 智能体协作规则

**版本**: v2.0  
**更新日期**: 2026-03-27  
**适用范围**: Strategy-Arch, Strategy-Engr, Strategy-QA  
**持久化配置**: 本规则已保存到 `.trae/agents_rules.md`，所有智能体必须严格遵守

---

## 核心原则

### 基本原则

1. **必须使用多智能体协作模式**: Strategy-Arch, Strategy-Engr, Strategy-QA
2. **保持策略名称稳定**: 不使用_v2, _v3 等版本号后缀
3. **文档组织有序**: 所有文档保存在指定目录，保持项目整洁
4. **代码备份机制**: 每次优化前先备份，再修改

### 持久化规则（重要）

**所有智能体必须在每次任务开始前读取本规则文件**

```yaml
规则文件位置：.trae/agents_rules.md
读取时机：每次任务开始时
执行标准：严格遵守，不得违反
```

**违反规则的后果**:
- 文档保存位置错误 → 删除并重新保存到正确位置
- 策略命名错误 → 立即更正
- 未备份代码 → 回退并重新执行

---

## 文档保存规则（重点强调）

### QA 文档保存位置

**规则 1**: QA 相关文档必须保存在策略相关的目录下

**可选位置** (优先级从高到低):
1. ✅ `strategies/{strategy_name}/optimize_XX/qa_report.md` (最优)
2. ✅ `workspace_qa/{strategy_name}/` (策略专属目录)
3. ❌ `workspace_qa/` 根目录 (禁止)

**规则 2**: 保持整体目录整洁

```
正确示例:
- strategies/trends_up/optimize_01/qa_report.md ✓
- workspace_qa/trends_up/diagnosis_report.md ✓

错误示例:
- workspace_qa/diagnosis_report.md ✗ (散落在根目录)
- workspace_qa/trends_up_v4_diagnosis_report.md ✗ (文件名带版本号)
```

### 优化文档保存位置

**所有优化相关文档**必须保存在 `strategies/{strategy_name}/optimize_XX/` 目录下:

```
strategies/{strategy_name}/optimize_01/
├── backtest.py                    # 优化后的策略文件
├── backtest_backup_YYYYMMDD.py    # 优化前备份
├── optimization_plan.md           # 优化方案
├── qa_report.md                   # QA 审查报告
├── backtest_analysis.md           # 回测结果分析
└── stats/                         # 回测输出
    ├── backtest_*.png
    └── backtest_*.log
```

### 策略说明文档

**位置**: `strategies/{strategy_name}/策略说明_Readme.md`

**内容**:
- 策略概览和核心逻辑
- 选股系统和评分规则
- 交易系统和仓位管理
- 回测表现和分析
- 使用说明和优化方向

---

## 目录结构规范

### 策略开发目录（精简版）

**核心原则**:
1. ✅ 设计文档 (`design.md`) 已存在时，直接更新，不重复创建
2. ✅ 不生成 `策略说明_Readme.md`（设计文档就是策略说明）
3. ✅ QA 文档只保留 `optimize_XX/qa_report.md`，其他诊断内容合并其中
4. ✅ 设计文档只放在策略目录，不归档到 `docs/`

```
strategies/
├── {strategy_name}/              # 策略主目录（如 trends_up）
│   ├── design.md                 # ★ 策略设计 + 说明（唯一文档）
│   ├── backtest.py               # 当前策略主文件
│   └── optimize_01/              # 第 1 次优化
│       ├── backtest.py           # 优化后的策略文件
│       ├── backtest_backup_YYYYMMDD.py  # 优化前备份
│       ├── optimization_plan.md  # 优化方案
│       ├── qa_report.md          # ★ QA 审查报告（包含诊断 + 分析）
│       └── stats/                # 回测输出
│           ├── backtest_*.png
│           └── backtest_*.log
```

**文档说明**:
- `design.md`: 策略设计文档 + 策略说明（二合一）
- `qa_report.md`: QA 审查报告 + 诊断 + 回测分析（三合一）
- `optimization_plan.md`: 优化方案（独立）
- ❌ 避免直接放在 `workspace_qa/` 根目录，保持整体目录整洁

---

## 智能体职责与规则

### Strategy-Arch（策略架构师）

**职责**:
- 制定优化方案和架构设计
- 设计内部类结构
- 定义评分系统和仓位管理逻辑
- 审批最终方案

**输出目录**:
- ✅ `strategies/{strategy_name}/design.md` - 策略设计 + 说明文档（**唯一**）
- ✅ `tasks/` - 任务单
- ✅ `strategies/{strategy_name}/optimize_XX/optimization_plan.md` - 优化方案

**禁止目录**:
- ❌ `strategies/` - 不直接修改代码
- ❌ `workspace_qa/` - 不负责 QA 文档
- ❌ `docs/` - 不归档设计文档

**必须遵守的规则**:
1. 设计文档必须保存到 `strategies/{strategy_name}/design.md`（策略专属目录）
2. **已存在 design.md 时，直接更新，不重复创建**
3. **不生成 `策略说明_Readme.md`**（design.md 就是策略说明）
4. 优化方案必须保存在 `optimize_XX/` 目录下
5. **设计文档只放在策略目录，不归档到 `docs/`**
6. 不得直接修改 `strategies/` 中的代码

---

### Strategy-Engr（策略工程师）

**职责**:
- 实现内部类（ConfigManager 等）
- 实现多维度选股逻辑
- 实现动态止盈止损
- 运行回测验证

**输出目录**:
- ✅ `strategies/{strategy_name}/backtest.py` - 策略主文件
- ✅ `strategies/{strategy_name}/optimize_XX/backtest.py` - 优化版本
- ✅ `strategies/{strategy_name}/optimize_XX/backtest_backup_YYYYMMDD.py` - 备份文件

**禁止目录**:
- ❌ `docs/` - 不创建设计文档
- ❌ `workspace_qa/` - 不负责 QA 文档

**代码备份规则**:
```bash
# 每次优化前必须备份
1. 创建 optimize_XX/ 目录（如果不存在）
2. 复制当前 backtest.py 到 optimize_XX/backtest_backup_YYYYMMDD.py
3. 在 optimize_XX/backtest.py 上进行优化修改
4. 保持策略主文件名称不变（仍为 backtest.py）
```

**必须遵守的规则**:
1. 每次优化前必须先备份代码
2. 优化后的代码保存在 `optimize_XX/backtest.py`
3. 策略名称保持不变，不添加版本号后缀
4. 备份文件名格式：`backtest_backup_YYYYMMDD.py`

---

### Strategy-QA（质量保障）

**职责**:
- 审查代码质量
- 分析回测结果
- 验证是否达到目标
- 提出改进建议

**输出目录**:
- ✅ `strategies/{strategy_name}/optimize_XX/qa_report.md` - QA 审查报告（**唯一 QA 文档**）

**禁止目录**:
- ❌ `strategies/` - 不直接修改代码
- ❌ `docs/` - 不创建设计文档
- ❌ `workspace_qa/` - **禁止使用此目录**（违反策略目录原则）

**必须遵守的规则**:
1. **所有 QA 文档只保留 `qa_report.md`**（包含诊断 + 分析）
2. **不再生成** `diagnosis_report.md`、`backtest_analysis.md` 等独立文件
3. QA 审查报告必须保存在 `optimize_XX/qa_report.md`
4. 文件名不带版本号（如 `_v4`），保持简洁

---

## 快速检查清单（每次任务必读）

### 智能体自检问题

**所有智能体在开始任务前必须问自己**:

1. ✅ 我是否使用了正确的智能体协作模式？（Strategy-Arch + Strategy-Engr + Strategy-QA）
2. ✅ 我是否保持了策略名称不变？（不加_v2, _v3 等后缀）
3. ✅ 我的文档是否保存在正确的位置？
   - Arch: `docs/`, `tasks/`, `strategies/{strategy_name}/design.md`, `strategies/{strategy_name}/optimize_XX/optimization_plan.md`
   - Engr: `strategies/{strategy_name}/optimize_XX/backtest.py`
   - QA: `strategies/{strategy_name}/optimize_XX/qa_report.md` (禁止使用 `workspace_qa/`)
4. ✅ 我是否在优化前备份了代码？（Engr）
5. ✅ 我的 QA 文档是否避免了 `workspace_qa/` 目录？（QA）

### 文档保存位置速查表

| 文档类型 | 保存位置 | 负责智能体 |
|---------|---------|-----------|
| **策略设计** | `strategies/{name}/design.md` (**唯一**) | Arch |
| 优化方案 | `strategies/{name}/optimize_XX/optimization_plan.md` | Arch |
| 优化代码 | `strategies/{name}/optimize_XX/backtest.py` | Engr |
| 代码备份 | `strategies/{name}/optimize_XX/backtest_backup_YYYYMMDD.py` | Engr |
| **QA 报告** | `strategies/{name}/optimize_XX/qa_report.md` (**唯一**) | QA |

**说明**:
- `design.md`: 策略设计 + 策略说明（二合一，唯一文档）
- `qa_report.md`: QA 审查 + 诊断 + 回测分析（三合一，唯一 QA 文档）
- 不再生成其他冗余文档（`策略说明_Readme.md`, `diagnosis_report.md`, `backtest_analysis.md` 等）

### 常见错误及纠正

| 错误 | 正确做法 | 纠正措施 |
|-----|---------|---------|
| 生成 `策略说明_Readme.md` | 只保留 `design.md` | 删除冗余文件，更新 design.md |
| 生成 `diagnosis_report.md` | 合并到 `qa_report.md` | 删除冗余文件，内容合并 |
| 生成 `backtest_analysis.md` | 合并到 `qa_report.md` | 删除冗余文件，内容合并 |
| QA 文档放在 `workspace_qa/` 目录 | 放在 `strategies/{strategy_name}/optimize_XX/` | 删除错误文件，移动到策略目录 |
| 策略名称带版本号（trends_up_v4） | 保持 `trends_up` 不变 | 重命名目录和文件 |
| 优化前未备份代码 | 先备份到 `backtest_backup_YYYYMMDD.py` | 回退并重新执行备份 |
| 设计文档放在 `docs/` 目录 | 放在 `strategies/{strategy_name}/design.md` | 移动文件到策略目录 |

---

## 违规处理机制

### 自动检查和纠正

**所有智能体在完成任务后必须执行**:

```yaml
检查步骤:
  1. 检查文档保存位置是否正确
  2. 检查策略命名是否规范
  3. 检查代码是否已备份（如果是优化任务）
  4. 发现错误立即纠正

纠正措施:
  - 文档位置错误 → 删除并重新保存到正确位置
  - 命名错误 → 立即更正
  - 未备份 → 回退并重新执行
```

### 用户反馈处理

**如果用户指出违反规则**:
1. 立即承认错误
2. 说明违反的具体规则
3. 立即纠正（删除错误文件，重新保存到正确位置）
4. 更新本规则文件，避免再次犯错

---

## 附录：规则更新历史

| 版本 | 日期 | 更新内容 |
|-----|------|---------|
| v1.0 | 2026-03-27 | 初始版本，包含基本规则 |
| v2.0 | 2026-03-27 | 强化文档保存规则，增加自检清单和违规处理机制 |

---

**重要提示**: 本规则文件已持久化到 `.trae/agents_rules.md`，所有智能体必须在每次任务开始前阅读并严格遵守！

### 标准优化流程

```
1. Strategy-Arch 制定优化方案
   ↓
   输出：strategies/{strategy_name}/optimize_XX/optimization_plan.md

2. Strategy-Engr 备份代码
   ↓
   输出：strategies/{strategy_name}/optimize_XX/backtest_backup_YYYYMMDD.py

3. Strategy-Engr 实现优化
   ↓
   输出：strategies/{strategy_name}/optimize_XX/backtest.py

4. Strategy-Engr 运行回测
   ↓
   输出：strategies/{strategy_name}/optimize_XX/stats/

5. Strategy-QA 审查代码和回测结果
   ↓
   输出：strategies/{strategy_name}/optimize_XX/qa_report.md
        或 workspace_qa/{strategy_name}/

6. Strategy-Arch 最终验收
   ↓
   输出：docs/final_{strategy_name}_XX.md
```

### 优化序号管理

- 第 1 次优化：`optimize_01/`
- 第 2 次优化：`optimize_02/`
- 第 3 次优化：`optimize_03/`
- 依此类推...

**注意**: 序号递增，不要跳跃或
# 临时任务文件目录

## 📋 目录用途

本目录专门用于存放**临时性任务文件**，包括：
- 临时调试脚本（`check_*.py`、`test_*.py`）
- 临时任务单（`task_*.md`）
- 一次性测试文件

## ⚠️ 重要规则

### 1. 用完即删
所有临时文件在使用后必须**立即删除**，不得提交到 Git。

### 2. 禁止提交
本目录下的文件**不应出现在 Git 提交中**，除非是 `.gitkeep` 文件。

### 3. 正式文件位置
- 正式策略文档 → `strategies/{策略名}/docs/`
- 正式测试文件 → `tests/`
- 正式脚本 → `scripts/`

## 🗑️ 清理检查

QA 审查时会检查暂存区，发现本目录的文件会被**强制移除**：
```bash
# QA 检查时自动执行
git reset HEAD tasks/check_*.py
rm tasks/check_*.py
```

## 📝 使用示例

### 临时调试脚本
```python
# tasks/check_data.py
# 调试用，用完即删
import pandas as pd
# ... 调试代码 ...
```

使用后删除：
```bash
rm tasks/check_data.py
```

### 临时任务单
```markdown
# tasks/task_temp_001.md
# 临时任务记录，完成后删除
```

任务完成后删除：
```bash
rm tasks/task_temp_001.md
```

---

**保持目录整洁，拒绝文件臃肿！**

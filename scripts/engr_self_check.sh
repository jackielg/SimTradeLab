#!/bin/bash

# engr 自检脚本 v2.0
# 用法：engr_self_check.sh {策略名}

STRATEGY=$1

if [ -z "$STRATEGY" ]; then
    echo "❌ 用法：engr_self_check.sh {策略名}"
    echo "示例：engr_self_check.sh dual_ma"
    exit 1
fi

BACKTEST_FILE="strategies/${STRATEGY}/backtest.py"

echo "========================================"
echo "🔍 engr 提交前自检"
echo "========================================"
echo "策略：$STRATEGY"
echo "文件：$BACKTEST_FILE"
echo "时间：$(date)"
echo "========================================"
echo ""

# 检查文件是否存在
if [ ! -f "$BACKTEST_FILE" ]; then
    echo "❌ 文件不存在：$BACKTEST_FILE"
    exit 1
fi

ERRORS=0

# ========================================
# 1. 语法检查（必须通过）
# ========================================
echo "1️⃣  语法检查..."
python -m py_compile "$BACKTEST_FILE" 2>&1
if [ $? -ne 0 ]; then
    echo "❌ 语法检查失败！"
    echo ""
    echo "请修复语法错误后再提交"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ 语法检查通过"
fi
echo ""

# ========================================
# 2. PEP8 检查（必须通过）
# ========================================
echo "2️⃣  PEP8 代码规范检查..."
if command -v pycodestyle &> /dev/null; then
    PEP8_OUTPUT=$(python -m pycodestyle --max-line-length=120 "$BACKTEST_FILE" 2>&1)
    PEP8_EXIT=$?
    
    if [ $PEP8_EXIT -ne 0 ]; then
        echo "❌ PEP8 检查失败！"
        echo ""
        echo "错误详情："
        echo "$PEP8_OUTPUT" | head -20
        echo ""
        echo "请修复格式问题后再提交"
        ERRORS=$((ERRORS + 1))
    else
        echo "✅ PEP8 检查通过"
    fi
else
    echo "⚠️  pycodestyle 未安装，跳过检查"
    echo "📝 安装方法：pip install pycodestyle"
fi
echo ""

# ========================================
# 3. 行尾空格检查（必须通过）
# ========================================
echo "3️⃣  行尾空格检查..."
TRAILING_SPACES=$(grep -n "[[:space:]]$" "$BACKTEST_FILE" | head -5)
if [ -n "$TRAILING_SPACES" ]; then
    echo "❌ 发现行尾空格！"
    echo ""
    echo "错误详情："
    echo "$TRAILING_SPACES"
    echo ""
    echo "请移除行尾空格后再提交"
    echo "💡 提示：IDE 通常有自动清理功能"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ 行尾空格检查通过"
fi
echo ""

# ========================================
# 4. IDE 诊断确认（必须通过）
# ========================================
echo "4️⃣  IDE 诊断确认..."
echo ""
echo "请在 IDE 中打开文件，确认："
echo "  ✅ 无红色波浪线（语法错误）"
echo "  ✅ 无黄色波浪线（警告）"
echo ""
read -p "确认？(y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ IDE 诊断确认失败"
    echo ""
    echo "请在 IDE 中修复提示的问题后再提交"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ IDE 诊断确认通过"
fi
echo ""

# ========================================
# 总结
# ========================================
echo "========================================"
echo "📊 自检总结"
echo "========================================"
echo ""

if [ $ERRORS -gt 0 ]; then
    echo "❌ 自检失败！"
    echo ""
    echo "发现 $ERRORS 个问题，必须修复后才能提交给 qa。"
    echo "修复后请重新运行：engr_self_check.sh $STRATEGY"
    echo "========================================"
    exit 1
else
    echo "🎉 自检全部通过！"
    echo ""
    echo "✅ 可以提交给 qa 审查"
    echo ""
    echo "下一步："
    echo "1. 创建自检报告：strategies/${STRATEGY}/docs/self_check.md"
    echo "2. 提交 qa 审查：qa_check.sh $STRATEGY"
fi
echo "========================================"

#!/bin/bash

# QA 自动化检查脚本 v2.0
# 用法：qa_check.sh {策略名}

STRATEGY=$1

if [ -z "$STRATEGY" ]; then
    echo "❌ 用法：qa_check.sh {策略名}"
    echo "示例：qa_check.sh dual_ma"
    exit 1
fi

BACKTEST_FILE="strategies/${STRATEGY}/backtest.py"

echo "========================================"
echo "🔍 开始 QA 自动化检查"
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
WARNINGS=0

# ========================================
# 0. 检查暂存区无价值文件（新增！）
# ========================================
echo "0️⃣  检查 GitHub 暂存区无价值文件..."
echo ""

# 获取暂存区文件列表
STAGED_FILES=$(git diff --cached --name-only 2>/dev/null)

if [ -n "$STAGED_FILES" ]; then
    echo "📋 暂存区文件列表："
    echo "$STAGED_FILES"
    echo ""
    
    # 检查临时调试脚本
    TEMP_SCRIPTS=$(echo "$STAGED_FILES" | grep -E "^check_.*\.py$|^test_.*\.py$" | grep -v "^tests/")
    if [ -n "$TEMP_SCRIPTS" ]; then
        echo "⚠️  发现临时调试脚本（建议从暂存区移除）："
        echo "$TEMP_SCRIPTS"
        echo ""
        echo "💡 处理方法："
        echo "   git reset HEAD {文件路径}"
        echo "   rm {文件路径}"
        echo ""
        WARNINGS=$((WARNINGS + 1))
    fi
    
    # 检查空文件
    for FILE in $STAGED_FILES; do
        if [ -f "$FILE" ]; then
            LINE_COUNT=$(wc -l < "$FILE" | tr -d ' ')
            if [ "$LINE_COUNT" -eq 0 ]; then
                echo "⚠️  发现空文件：$FILE"
                WARNINGS=$((WARNINGS + 1))
            fi
        fi
    done
    
    # 检查路径不规范（大小写问题）
    PATH_ISSUES=$(echo "$STAGED_FILES" | grep -i "^simtradelab/" | grep -v "^SimTradeLab/")
    if [ -n "$PATH_ISSUES" ]; then
        echo "⚠️  发现路径大小写不规范（应使用 SimTradeLab/）："
        echo "$PATH_ISSUES"
        echo ""
        WARNINGS=$((WARNINGS + 1))
    fi
    
    echo ""
else
    echo "✅ 暂存区为空，跳过检查"
fi
echo ""
echo "1️⃣  语法检查..."
python -m py_compile "$BACKTEST_FILE" 2>&1
if [ $? -ne 0 ]; then
    echo "❌ 语法检查失败！"
    echo ""
    echo "错误详情："
    python -m py_compile "$BACKTEST_FILE" 2>&1 | head -20
    ERRORS=$((ERRORS + 1))
    echo ""
    echo "📝 建议：检查语法错误，然后重新运行检查"
else
    echo "✅ 语法检查通过"
fi
echo ""

# ========================================
# 2. PEP8 检查（强制）
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
        ERRORS=$((ERRORS + 1))
        echo ""
        echo "📝 建议：修复格式问题，然后重新运行检查"
    else
        echo "✅ PEP8 检查通过"
    fi
else
    echo "⚠️  pycodestyle 未安装，跳过 PEP8 检查"
    echo "📝 安装方法：pip install pycodestyle"
    WARNINGS=$((WARNINGS + 1))
fi
echo ""

# ========================================
# 3. 行尾空格检查（强制）
# ========================================
echo "3️⃣  行尾空格检查..."
TRAILING_SPACES=$(grep -n "[[:space:]]$" "$BACKTEST_FILE" | head -10)
if [ -n "$TRAILING_SPACES" ]; then
    echo "❌ 发现行尾空格！"
    echo ""
    echo "错误详情："
    echo "$TRAILING_SPACES"
    ERRORS=$((ERRORS + 1))
    echo ""
    echo "📝 建议：移除行尾空格（IDE 通常有自动清理功能）"
else
    echo "✅ 行尾空格检查通过"
fi
echo ""

# ========================================
# 4. 空行检查（建议）
# ========================================
echo "4️⃣  空行检查..."
EMPTY_LINES_WITH_SPACES=$(grep -n "^[[:space:]]*$" "$BACKTEST_FILE" | grep "[[:space:]]" | head -10)
if [ -n "$EMPTY_LINES_WITH_SPACES" ]; then
    echo "⚠️  发现空行包含空格！"
    echo ""
    echo "详情："
    echo "$EMPTY_LINES_WITH_SPACES"
    WARNINGS=$((WARNINGS + 1))
    echo ""
    echo "📝 建议：使用纯空行（不包含空格）"
else
    echo "✅ 空行检查通过"
fi
echo ""

# ========================================
# 5. IDE 诊断提示（人工确认）
# ========================================
echo "5️⃣  IDE 诊断检查..."
echo ""
echo "请在 IDE 中打开文件：$BACKTEST_FILE"
echo "确认以下项目："
echo "  ✅ 无红色波浪线（语法错误）"
echo "  ✅ 无黄色波浪线（警告）"
echo "  ✅ 无绿色波浪线（代码风格提示）"
echo ""
read -p "确认以上项目全部通过？(y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ IDE 诊断检查失败"
    echo ""
    echo "📝 建议：在 IDE 中查看并修复提示的问题"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ IDE 诊断检查通过"
fi
echo ""

# ========================================
# 总结
# ========================================
echo "========================================"
echo "📊 检查总结"
echo "========================================"
echo "错误数：$ERRORS"
echo "警告数：$WARNINGS"
echo ""

if [ $ERRORS -gt 0 ]; then
    echo "❌ QA 检查失败！"
    echo ""
    echo "发现 $ERRORS 个错误，必须修复后才能提交。"
    echo "请修复问题后，重新运行：qa_check.sh $STRATEGY"
    echo "========================================"
    exit 1
elif [ $WARNINGS -gt 0 ]; then
    echo "⚠️  QA 检查通过（有警告）"
    echo ""
    echo "发现 $WARNINGS 个警告，建议修复但不是必须。"
    echo "是否继续提交？"
    read -p "继续？(y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ 提交已取消"
        exit 1
    fi
else
    echo "🎉 QA 检查全部通过！"
fi

echo "========================================"
echo ""
echo "✅ 可以提交给 arch 验收"

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
# 0. 检查暂存区无价值文件（强制清理！）
# ========================================
echo "0️⃣  检查 GitHub 暂存区无价值文件..."
echo ""

# 获取暂存区文件列表
STAGED_FILES=$(git diff --cached --name-only 2>/dev/null)

if [ -n "$STAGED_FILES" ]; then
    echo "📋 暂存区文件列表："
    echo "$STAGED_FILES"
    echo ""
    
    # 检查临时调试脚本（强制清理）
    TEMP_SCRIPTS=$(echo "$STAGED_FILES" | grep -E "^check_.*\.py$|^test_.*\.py$" | grep -v "^tests/")
    if [ -n "$TEMP_SCRIPTS" ]; then
        echo "❌ 发现临时调试脚本（必须从暂存区移除并删除）："
        echo "$TEMP_SCRIPTS"
        echo ""
        echo "💡 临时脚本应放在 SimTradeLab/tasks/ 目录，用完即删"
        echo ""
        
        # 自动从暂存区移除
        for FILE in $TEMP_SCRIPTS; do
            git reset HEAD "$FILE" 2>/dev/null
            echo "✅ 已从暂存区移除：$FILE"
        done
        
        ERRORS=$((ERRORS + 1))
    fi
    
    # 检查空文件（强制清理）
    EMPTY_FILES=""
    for FILE in $STAGED_FILES; do
        if [ -f "$FILE" ]; then
            LINE_COUNT=$(wc -l < "$FILE" | tr -d ' ')
            if [ "$LINE_COUNT" -eq 0 ]; then
                EMPTY_FILES="$EMPTY_FILES $FILE"
                echo "❌ 发现空文件：$FILE"
            fi
        fi
    done
    
    if [ -n "$EMPTY_FILES" ]; then
        echo ""
        echo "💡 空文件必须删除"
        for FILE in $EMPTY_FILES; do
            git reset HEAD "$FILE" 2>/dev/null
            rm -f "$FILE"
            echo "✅ 已删除：$FILE"
        done
        ERRORS=$((ERRORS + 1))
    fi
    
    # 检查路径不规范（强制清理）
    PATH_ISSUES=$(echo "$STAGED_FILES" | grep -i "^simtradelab/" | grep -v "^SimTradeLab/")
    if [ -n "$PATH_ISSUES" ]; then
        echo ""
        echo "❌ 发现路径大小写不规范（必须从暂存区移除）："
        echo "$PATH_ISSUES"
        echo ""
        
        for FILE in $PATH_ISSUES; do
            git reset HEAD "$FILE" 2>/dev/null
            echo "✅ 已从暂存区移除：$FILE"
        done
        
        ERRORS=$((ERRORS + 1))
    fi
    
    # 检查一次性 MD 文档（强制清理）
    ONE_TIME_DOCS=$(echo "$STAGED_FILES" | grep -E "cleanup_.*\.md$|fix_report_.*\.md$|improvement_.*\.md$" | grep -v "^strategies/.*/docs/")
    if [ -n "$ONE_TIME_DOCS" ]; then
        echo ""
        echo "❌ 发现一次性文档（必须从暂存区移除）："
        echo "$ONE_TIME_DOCS"
        echo ""
        echo "💡 文档应保存在 strategies/{策略名}/docs/ 目录"
        echo ""
        
        for FILE in $ONE_TIME_DOCS; do
            git reset HEAD "$FILE" 2>/dev/null
            echo "✅ 已从暂存区移除：$FILE"
        done
        
        ERRORS=$((ERRORS + 1))
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

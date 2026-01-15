#!/bin/bash
# 手动测试脚本：在其他项目中使用工作流框架

set -e

echo "=========================================="
echo "测试在其他项目中使用工作流框架"
echo "=========================================="
echo ""

# 创建临时测试项目
TEST_PROJECT_DIR=$(mktemp -d -t work_by_roles_test_XXXXXX)
echo "📁 创建测试项目目录: $TEST_PROJECT_DIR"
cd "$TEST_PROJECT_DIR"

# 创建模拟项目文件
echo "📝 创建模拟项目文件..."
mkdir -p src
echo "# Test Project" > README.md
echo "print('Hello World')" > main.py
echo "pytest>=7.0" > requirements.txt
echo "def main(): pass" > src/app.py

echo ""
echo "=========================================="
echo "步骤 1: 安装工作流框架"
echo "=========================================="
echo ""

# 检查是否已安装
if command -v workflow &> /dev/null; then
    echo "✅ workflow 命令已可用"
    workflow --version 2>/dev/null || echo "ℹ️  版本信息不可用"
else
    echo "⚠️  workflow 命令不可用，请先运行: pip install -e ."
    echo "   在框架项目目录中运行安装命令"
    exit 1
fi

echo ""
echo "=========================================="
echo "步骤 2: 运行 workflow setup"
echo "=========================================="
echo ""

workflow setup

echo ""
echo "=========================================="
echo "步骤 3: 验证配置文件"
echo "=========================================="
echo ""

if [ -d ".workflow" ]; then
    echo "✅ .workflow 目录已创建"
else
    echo "❌ .workflow 目录未创建"
    exit 1
fi

if [ -f ".workflow/role_schema.yaml" ]; then
    echo "✅ role_schema.yaml 已创建"
else
    echo "❌ role_schema.yaml 未创建"
    exit 1
fi

if [ -d ".workflow/skills" ]; then
    SKILL_COUNT=$(find .workflow/skills -name "Skill.md" | wc -l | tr -d ' ')
    echo "✅ skills 目录已创建 (包含 $SKILL_COUNT 个技能)"
else
    echo "❌ skills 目录未创建"
    exit 1
fi

if [ -f ".workflow/project_context.yaml" ]; then
    echo "✅ project_context.yaml 已创建"
else
    echo "❌ project_context.yaml 未创建"
    exit 1
fi

if [ -f ".workflow/USAGE.md" ]; then
    echo "✅ USAGE.md 已创建"
else
    echo "❌ USAGE.md 未创建"
    exit 1
fi

echo ""
echo "=========================================="
echo "步骤 4: 测试基本命令"
echo "=========================================="
echo ""

echo "📋 测试 list-roles 命令:"
workflow list-roles | head -5
echo ""

echo "📋 测试 list-skills 命令:"
workflow list-skills | head -5
echo ""

echo "📋 测试 status 命令:"
workflow status
echo ""

echo ""
echo "=========================================="
echo "✅ 所有测试通过！"
echo "=========================================="
echo ""
echo "测试项目目录: $TEST_PROJECT_DIR"
echo "你可以查看该目录来检查生成的文件"
echo ""
echo "清理测试目录？(y/n)"
read -r response
if [[ "$response" =~ ^[Yy]$ ]]; then
    rm -rf "$TEST_PROJECT_DIR"
    echo "✅ 已清理测试目录"
else
    echo "ℹ️  测试目录保留在: $TEST_PROJECT_DIR"
fi


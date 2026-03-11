#!/bin/bash
#===============================================================================
# KangaBase One Click Go 🦘
# 一键安装、初始化、运行Demo、跑测试
#===============================================================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

# 打印分隔线
print_separator() {
    echo "==============================================================================="
}

# 打印标题
print_title() {
    echo ""
    print_separator
    echo -e "${GREEN}$1${NC}"
    print_separator
}

#===============================================================================
# 1. 检查 Python 版本
#===============================================================================
check_python() {
    print_title "🐍 检查 Python 版本"

    # 检查 python 命令
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        print_error "未找到 Python，请先安装 Python 3.9+"
        exit 1
    fi

    # 检查版本
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
        print_error "Python 版本过低: $PYTHON_VERSION，需要 3.9+"
        exit 1
    fi

    print_success "Python 版本: $PYTHON_VERSION"
}

#===============================================================================
# 2. 检查 pip
#===============================================================================
check_pip() {
    print_title "📦 检查 pip"

    if ! $PYTHON_CMD -m pip --version &> /dev/null; then
        print_warning "pip 未安装，尝试安装..."
        $PYTHON_CMD -m ensurepip --default-pip 2>/dev/null || {
            print_error "pip 安装失败，请手动安装"
            exit 1
        }
    fi

    print_success "pip 可用"
}

#===============================================================================
# 3. 检查/创建虚拟环境（可选）
#===============================================================================
setup_venv() {
    print_title "🏠 虚拟环境设置"

    if [ "$1" == "true" ] || [ "$1" == "--no-venv" ]; then
        print_info "跳过虚拟环境创建（--no-venv）"
        return
    fi

    # 检查是否已有虚拟环境
    if [ -d "venv" ]; then
        print_info "发现已有虚拟环境: venv/"
        USE_VENV="y"
    else
        echo ""
        read -p "是否创建虚拟环境？(Y/n): " USE_VENV
        USE_VENV=${USE_VENV:-y}
    fi

    if [ "$USE_VENV" == "y" ] || [ "$USE_VENV" == "Y" ]; then
        if [ ! -d "venv" ]; then
            print_info "创建虚拟环境..."
            $PYTHON_CMD -m venv venv
            print_success "虚拟环境创建完成"
        fi

        print_info "激活虚拟环境..."
        source venv/bin/activate
        print_success "虚拟环境已激活"
    else
        print_info "使用系统 Python 环境"
    fi
}

#===============================================================================
# 4. 安装 KangaBase
#===============================================================================
install_kangabase() {
    print_title "📥 安装 KangaBase"

    # 检查是否已是开发模式安装
    if [ -f "setup.py" ] || [ -f "pyproject.toml" ]; then
        print_info "检测到项目目录，开发模式安装..."
        $PYTHON_CMD -m pip install -e . --quiet
    else
        print_info "从 PyPI 安装稳定版..."
        $PYTHON_CMD -m pip install kangabase --quiet
    fi

    # 验证安装（开发模式下添加父目录到 PYTHONPATH）
    PARENT_DIR=$(dirname "$(pwd)")
    if PYTHONPATH="$PARENT_DIR:$PYTHONPATH" $PYTHON_CMD -c "import kangabase" 2>/dev/null; then
        VERSION=$(PYTHONPATH="$PARENT_DIR:$PYTHONPATH" $PYTHON_CMD -c "import kangabase; print(getattr(kangabase, '__version__', '0.1.0'))" 2>/dev/null || echo "0.1.0")
        print_success "KangaBase 安装成功 (版本: $VERSION)"
    else
        # 尝试直接导入（可能在 src-layout 中）
        if $PYTHON_CMD -c "from core.database import Database" 2>/dev/null; then
            print_success "KangaBase 安装成功（开发模式）"
        else
            print_error "KangaBase 安装失败"
            exit 1
        fi
    fi
}

#===============================================================================
# 5. 运行示例 Demo
#===============================================================================
run_demo() {
    print_title "🎮 运行示例 Demo"

    # 检查示例目录
    if [ ! -d "examples/coupon" ]; then
        print_warning "示例目录不存在，跳过 Demo"
        return
    fi

    # 非交互模式（管道/CI）直接运行
    if [ -t 0 ]; then
        echo ""
        read -p "是否运行优惠券 Demo？(Y/n): " RUN_DEMO
        RUN_DEMO=${RUN_DEMO:-y}
    else
        RUN_DEMO="y"
    fi

    if [ "$RUN_DEMO" == "y" ] || [ "$RUN_DEMO" == "Y" ]; then
        print_info "运行 examples/coupon/demo.py ..."

        # 检查 demo 文件
        if [ ! -f "examples/coupon/demo.py" ]; then
            print_warning "demo.py 不存在，跳过"
            return
        fi

        PARENT_DIR=$(dirname "$(pwd)")
        PYTHONPATH="$PARENT_DIR:$PYTHONPATH" $PYTHON_CMD examples/coupon/demo.py

        print_success "Demo 运行完成"
    else
        print_info "跳过 Demo"
    fi
}

#===============================================================================
# 6. 运行测试
#===============================================================================
run_tests() {
    print_title "🧪 运行测试"

    # 检查测试目录
    if [ ! -d "tests" ]; then
        print_warning "测试目录不存在，跳过测试"
        return
    fi

    echo ""
    read -p "是否运行测试套件？(Y/n): " RUN_TESTS
    RUN_TESTS=${RUN_TESTS:-y}

    if [ "$RUN_TESTS" == "y" ] || [ "$RUN_TESTS" == "Y" ]; then
        print_info "安装测试依赖..."
        $PYTHON_CMD -m pip install pytest pytest-cov --quiet 2>/dev/null || true

        print_info "运行测试..."
        echo ""

        # 运行测试
        if $PYTHON_CMD -m pytest tests/ -v --tb=short; then
            print_success "所有测试通过 🎉"
        else
            print_warning "部分测试失败，请检查"
        fi
    else
        print_info "跳过测试"
    fi
}

#===============================================================================
# 7. 显示成功信息和下一步
#===============================================================================
show_next_steps() {
    print_title "🚀 下一步"

    echo -e "${GREEN}KangaBase 已就绪！${NC}"
    echo ""
    echo "📚 文档:"
    echo "   • README:       cat README.md"
    echo "   • 设计理念:     cat docs/DESIGN.md"
    echo "   • 使用指南:    cat docs/GUIDE.md"
    echo ""
    echo "🔨 快速开始:"
    echo "   • 初始化项目:  kangabase init my-project"
    echo "   • 查看帮助:     kangabase --help"
    echo ""
    echo "💡 示例:"
    echo "   • 优惠券 Demo: cd examples/coupon && python demo.py"
    echo ""
    echo "🛠️  开发:"
    echo "   • 开发模式安装: $PYTHON_CMD -m pip install -e ."
    echo "   • 运行测试:     pytest tests/"
    echo ""

    print_success "祝您使用愉快！🦘"
    echo ""
}

#===============================================================================
# 主流程
#===============================================================================
main() {
    echo ""
    echo "╔═══════════════════════════════════════════════════════════════════╗"
    echo "║                                                                   ║"
    echo "║              🦘 KangaBase One Click Go 🦘                        ║"
    echo "║                                                                   ║"
    echo "║         轻如 SQLite · 易如 Supabase · 为 Agent 而生              ║"
    echo "║                                                                   ║"
    echo "╚═══════════════════════════════════════════════════════════════════╝"
    echo ""

    # 检查是否在项目目录
    if [ -f "setup.py" ] || [ -f "pyproject.toml" ]; then
        print_info "检测到 KangaBase 项目目录"
        cd "$(dirname "$0")"
    fi

    # 解析参数
    NO_VENV=false
    SKIP_DEMO=false
    SKIP_TESTS=false

    for arg in "$@"; do
        case $arg in
            --no-venv)
                NO_VENV=true
                ;;
            --skip-demo)
                SKIP_DEMO=true
                ;;
            --skip-tests)
                SKIP_TESTS=true
                ;;
            --help|-h)
                echo "用法: $0 [选项]"
                echo ""
                echo "选项:"
                echo "  --no-venv     不创建虚拟环境"
                echo "  --skip-demo   跳过 Demo 运行"
                echo "  --skip-tests  跳过测试"
                echo "  --help, -h    显示帮助"
                exit 0
                ;;
        esac
    done

    # 执行步骤
    check_python
    check_pip
    setup_venv $NO_VENV
    install_kangabase

    if [ "$SKIP_DEMO" != true ]; then
        run_demo
    fi

    if [ "$SKIP_TESTS" != true ]; then
        run_tests
    fi

    show_next_steps
}

# 运行主流程
main "$@"

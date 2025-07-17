@echo off
echo ========================================
echo FITS文件背景抽取工具
echo ========================================
echo.

echo 检查Python环境...
python --version
if %errorlevel% neq 0 (
    echo 错误: 未找到Python，请确保Python已安装并添加到PATH
    pause
    exit /b 1
)

echo.
echo 选择运行模式:
echo 1. 完整版 (需要photutils库)
echo 2. 简化版 (只需要astropy和matplotlib)
echo.
set /p choice="请输入选择 (1 或 2): "

if "%choice%"=="1" (
    echo.
    echo 运行完整版背景抽取工具...
    echo 检查依赖库...
    python -c "import astropy, photutils, matplotlib, numpy; print('所有依赖库已安装')"
    if %errorlevel% neq 0 (
        echo.
        echo 警告: 缺少必要的依赖库
        echo 正在尝试安装依赖...
        pip install -r requirements.txt
        if %errorlevel% neq 0 (
            echo 依赖安装失败，将使用简化版
            goto simple_version
        )
    )
    echo.
    echo 开始处理FITS文件...
    python extract_background.py
) else if "%choice%"=="2" (
    :simple_version
    echo.
    echo 运行简化版背景抽取工具...
    echo 检查基本依赖库...
    python -c "import astropy, matplotlib, numpy; print('基本依赖库已安装')"
    if %errorlevel% neq 0 (
        echo.
        echo 错误: 缺少基本依赖库
        echo 请运行: pip install astropy matplotlib numpy
        pause
        exit /b 1
    )
    echo.
    echo 开始处理FITS文件...
    python simple_background_extractor.py
) else (
    echo 无效选择，请重新运行脚本
    pause
    exit /b 1
)

echo.
echo ========================================
echo 处理完成！
echo 请检查输出目录中的结果文件
echo ========================================
pause

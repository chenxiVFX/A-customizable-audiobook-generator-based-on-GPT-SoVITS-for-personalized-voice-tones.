@echo off
chcp 65001
title 有声小说生成器

echo ============================================
echo           有声小说生成器启动程序
echo ============================================
echo.

:: 检查 Python 是否已安装
echo [1/5] 正在检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Python未安装或未添加到系统环境变量！
    echo 请先安装Python 3.8或更高版本。
    echo 您可以从 https://www.python.org/downloads/ 下载Python。
    echo 安装时请勾选"Add Python to PATH"选项。
    pause
    exit /b 1
)
echo [成功] Python环境检查通过
echo.

:: 检查虚拟环境
echo [2/5] 正在检查虚拟环境...
if not exist "venv" (
    echo 虚拟环境不存在，正在创建...
    python -m venv venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败！
        echo 请确保Python安装正确且具有管理员权限。
        pause
        exit /b 1
    )
    echo [成功] 虚拟环境创建完成
) else (
    echo [信息] 虚拟环境已存在
)
echo.

:: 激活虚拟环境
echo [3/5] 正在激活虚拟环境...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [错误] 激活虚拟环境失败！
    echo 请尝试删除venv文件夹后重新运行此脚本。
    pause
    exit /b 1
)
echo [成功] 虚拟环境激活成功
echo.

:: 安装依赖
echo [4/5] 正在检查并安装依赖...
echo 这可能需要几分钟时间，请耐心等待...
pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 安装依赖失败！
    echo 请检查网络连接或尝试手动运行：pip install -r requirements.txt
    pause
    exit /b 1
)
echo [成功] 依赖安装完成
echo.

:: 启动程序
echo [5/5] 正在启动程序...
echo 如果程序启动失败，请查看上方是否有错误信息。
echo.
python gui.py
if errorlevel 1 (
    echo [错误] 程序启动失败！
    echo 请检查：
    echo 1. 是否所有依赖都已正确安装
    echo 2. 是否有足够的系统权限
    echo 3. 是否所有必要的文件都存在
    pause
    exit /b 1
)

:: 退出虚拟环境
call venv\Scripts\deactivate.bat
echo.
echo 程序已退出
pause 
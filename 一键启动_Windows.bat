@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Research Toolbox - 科研数据分析
if exist ".venv\Scripts\python.exe" goto START

echo ====================================================
echo Research Toolbox：首次初始化本地 Python 环境
echo 首次运行需要 Windows 10/11、Python 3.11/3.12、网络。
echo 不会改动实验原始数据。以后只需双击此 BAT 启动。
echo ====================================================
where py >nul 2>&1
if not errorlevel 1 (
 py -3.12 -m venv ".venv" >nul 2>&1
 if not exist ".venv\Scripts\python.exe" py -3.11 -m venv ".venv" >nul 2>&1
)
if not exist ".venv\Scripts\python.exe" (
 where python >nul 2>&1
 if not errorlevel 1 (
  python -c "import sys;sys.exit(0 if sys.version_info[:2] in [(3,11),(3,12)] else 1)" >nul 2>&1
  if not errorlevel 1 python -m venv ".venv"
 )
)
if not exist ".venv\Scripts\python.exe" (
 echo 未检测到可用 Python 3.11/3.12。请先安装 64 位 Python，并勾选 PATH。
 pause
 exit /b 1
)
echo 正在安装所需依赖，首次可能需要数分钟……
".venv\Scripts\python.exe" -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
if errorlevel 1 (
 echo 依赖安装失败。请确认网络后重新双击 BAT。
 pause
 exit /b 1
)
:START
".venv\Scripts\python.exe" desktop.py
if errorlevel 1 (
 echo 启动失败。请保留此窗口中的错误信息并检查数据格式。
 pause
 exit /b 1
)
endlocal

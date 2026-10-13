@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 goto BAD_FOLDER
title Research Toolbox - Windows Launcher

set "ENV_PY=%CD%\.venv\Scripts\python.exe"
set "START_LOG=%CD%\startup.log"
>"%START_LOG%" echo Research Toolbox - launcher log

if not exist "desktop.py" goto MISSING_FILES
if not exist "requirements.txt" goto MISSING_FILES

if exist "%ENV_PY%" goto CHECK_DEPS

echo [1/3] Creating the local Python environment...
where py >nul 2>&1
if errorlevel 1 goto TRY_PYTHON
py -3.12 -m venv ".venv" >>"%START_LOG%" 2>&1
if exist "%ENV_PY%" goto CHECK_DEPS
py -3.11 -m venv ".venv" >>"%START_LOG%" 2>&1
if exist "%ENV_PY%" goto CHECK_DEPS

:TRY_PYTHON
where python >nul 2>&1
if errorlevel 1 goto PYTHON_MISSING
python -c "import sys;sys.exit(0 if sys.version_info[:2] in [(3,11),(3,12)] and sys.maxsize>2**32 else 1)" >>"%START_LOG%" 2>&1
if errorlevel 1 goto PYTHON_MISSING
python -m venv ".venv" >>"%START_LOG%" 2>&1
if not exist "%ENV_PY%" goto PYTHON_MISSING

:CHECK_DEPS
echo [2/3] Checking the scientific Python packages...
"%ENV_PY%" -c "import numpy,scipy,pandas,matplotlib,sklearn,cv2,PIL,openpyxl,docx,statsmodels" >>"%START_LOG%" 2>&1
if not errorlevel 1 goto START_UI

echo Installing dependencies from the Tsinghua PyPI mirror...
"%ENV_PY%" -m pip install --disable-pip-version-check --no-cache-dir --timeout 120 --retries 5 -i https://pypi.tuna.tsinghua.edu.cn/simple -r "requirements.txt" >>"%START_LOG%" 2>&1
if not errorlevel 1 goto VERIFY_DEPS

echo Tsinghua download failed; trying the official PyPI source...
"%ENV_PY%" -m pip install --disable-pip-version-check --no-cache-dir --timeout 120 --retries 5 -i https://pypi.org/simple -r "requirements.txt" >>"%START_LOG%" 2>&1
if errorlevel 1 goto INSTALL_FAILED

:VERIFY_DEPS
"%ENV_PY%" -c "import numpy,scipy,pandas,matplotlib,sklearn,cv2,PIL,openpyxl,docx,statsmodels" >>"%START_LOG%" 2>&1
if errorlevel 1 goto INSTALL_FAILED

:START_UI
echo [3/3] Starting Research Toolbox...
"%ENV_PY%" -u "desktop.py" >>"%START_LOG%" 2>&1
if errorlevel 1 goto APP_FAILED
exit /b 0

:MISSING_FILES
echo.
echo [ERROR] desktop.py or requirements.txt was not found.
echo Please extract the WHOLE GitHub ZIP before running this BAT.
pause
exit /b 1

:PYTHON_MISSING
echo.
echo [ERROR] 64-bit Python 3.11 or 3.12 was not found.
echo Install Python, enable Add Python to PATH, then rerun this BAT.
echo Detailed output: "%START_LOG%"
pause
exit /b 1

:INSTALL_FAILED
echo.
echo [ERROR] Python packages could not be installed or imported.
echo Open "%START_LOG%" to see the detailed error.
type "%START_LOG%"
pause
exit /b 1

:APP_FAILED
echo.
echo [ERROR] Research Toolbox exited with an error.
echo Open "%START_LOG%" to see the traceback.
type "%START_LOG%"
pause
exit /b 1

:BAD_FOLDER
echo [ERROR] Could not enter the folder containing the launcher.
pause
exit /b 1

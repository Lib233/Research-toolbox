@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
pushd "%~dp0"
if errorlevel 1 goto BAD_FOLDER
title Research Toolbox - Windows Launcher

set "ENV_PY=%CD%\.venv\Scripts\python.exe"
set "START_LOG=%CD%\startup.log"
set "BASE_CMD="
set "LOCAL_BAD=0"
set "LOCAL_GOOD=0"
set "MODULE_CHECK=import numpy, scipy, pandas, matplotlib, sklearn, cv2, PIL, openpyxl, docx, statsmodels"
>"%START_LOG%" echo Research Toolbox - launcher log
>>"%START_LOG%" echo Launcher started

if not exist "desktop.py" goto MISSING_FILES
if not exist "requirements.txt" goto MISSING_FILES

echo [1/3] Checking available Python environments...
if not exist "%ENV_PY%" goto FIND_SYSTEM
"%ENV_PY%" -c "import sys;sys.exit(0 if sys.version_info[:2] in [(3,11),(3,12)] and sys.maxsize>2**32 else 1)" >>"%START_LOG%" 2>&1
if errorlevel 1 goto LOCAL_INVALID
set "LOCAL_GOOD=1"
"%ENV_PY%" -c "%MODULE_CHECK%" >>"%START_LOG%" 2>&1
if not errorlevel 1 goto USE_LOCAL
goto FIND_SYSTEM

:LOCAL_INVALID
set "LOCAL_BAD=1"
>>"%START_LOG%" echo Existing .venv does not run a supported 64-bit Python.

:FIND_SYSTEM
where python >nul 2>&1
if errorlevel 1 goto TRY_PY_312
python -c "import sys;sys.exit(0 if sys.version_info[:2] in [(3,11),(3,12)] and sys.maxsize>2**32 else 1)" >nul 2>&1
if errorlevel 1 goto TRY_PY_312
set "BASE_CMD=python"
python -c "%MODULE_CHECK%" >nul 2>&1
if not errorlevel 1 goto USE_BASE

:TRY_PY_312
where py >nul 2>&1
if errorlevel 1 goto READY_TO_INSTALL
py -3.12 -c "import sys;sys.exit(0 if sys.maxsize>2**32 else 1)" >nul 2>&1
if errorlevel 1 goto TRY_PY_311
if not defined BASE_CMD set "BASE_CMD=py -3.12"
py -3.12 -c "%MODULE_CHECK%" >nul 2>&1
if not errorlevel 1 goto USE_PY_312

:TRY_PY_311
py -3.11 -c "import sys;sys.exit(0 if sys.maxsize>2**32 else 1)" >nul 2>&1
if errorlevel 1 goto READY_TO_INSTALL
if not defined BASE_CMD set "BASE_CMD=py -3.11"
py -3.11 -c "%MODULE_CHECK%" >nul 2>&1
if not errorlevel 1 goto USE_PY_311

:READY_TO_INSTALL
if "%LOCAL_BAD%"=="1" goto BROKEN_ENV
if "%LOCAL_GOOD%"=="1" goto INSTALL_DEPS
if not defined BASE_CMD goto PYTHON_MISSING

echo Creating the project .venv with a supported Python...
%BASE_CMD% -m venv ".venv" >>"%START_LOG%" 2>&1
if errorlevel 1 goto VENV_FAILED
if not exist "%ENV_PY%" goto VENV_FAILED
"%ENV_PY%" -c "import sys;sys.exit(0 if sys.version_info[:2] in [(3,11),(3,12)] and sys.maxsize>2**32 else 1)" >>"%START_LOG%" 2>&1
if errorlevel 1 goto VENV_FAILED

:INSTALL_DEPS
echo [2/3] Installing the required scientific packages...
"%ENV_PY%" -m pip --version >>"%START_LOG%" 2>&1
if not errorlevel 1 goto INSTALL_TUNA
"%ENV_PY%" -m ensurepip --upgrade >>"%START_LOG%" 2>&1
if errorlevel 1 goto INSTALL_FAILED

:INSTALL_TUNA
echo Trying the Tsinghua PyPI mirror...
"%ENV_PY%" -m pip install --disable-pip-version-check --no-cache-dir --timeout 40 --retries 2 -i https://pypi.tuna.tsinghua.edu.cn/simple -r "requirements.txt" >>"%START_LOG%" 2>&1
if not errorlevel 1 goto VERIFY_DEPS

echo Trying the official PyPI index...
"%ENV_PY%" -m pip install --disable-pip-version-check --no-cache-dir --timeout 40 --retries 2 -i https://pypi.org/simple -r "requirements.txt" >>"%START_LOG%" 2>&1
if errorlevel 1 goto INSTALL_FAILED

:VERIFY_DEPS
"%ENV_PY%" -c "%MODULE_CHECK%" >>"%START_LOG%" 2>&1
if errorlevel 1 goto INSTALL_FAILED

:USE_LOCAL
set "RUN_MODE=LOCAL"
goto START_UI

:USE_BASE
set "RUN_MODE=BASE"
set "RUN_CMD=%BASE_CMD%"
goto START_UI

:USE_PY_312
set "RUN_MODE=BASE"
set "RUN_CMD=py -3.12"
goto START_UI

:USE_PY_311
set "RUN_MODE=BASE"
set "RUN_CMD=py -3.11"
goto START_UI

:START_UI
echo [3/3] Starting Research Toolbox...
if "%RUN_MODE%"=="LOCAL" goto LAUNCH_LOCAL
>>"%START_LOG%" echo Launching with an installed Python interpreter.
%RUN_CMD% -u "desktop.py" >>"%START_LOG%" 2>&1
if errorlevel 1 goto APP_FAILED
popd
exit /b 0

:LAUNCH_LOCAL
>>"%START_LOG%" echo Launching with the project .venv.
"%ENV_PY%" -u "desktop.py" >>"%START_LOG%" 2>&1
if errorlevel 1 goto APP_FAILED
popd
exit /b 0

:MISSING_FILES
echo.
echo [ERROR] desktop.py or requirements.txt is missing.
echo Extract the complete GitHub ZIP before launching.
goto STOP_ERROR

:PYTHON_MISSING
echo.
echo [ERROR] No usable 64-bit Python 3.11 or 3.12 was found.
echo Install Python 3.11/3.12, then try again.
py -0p >>"%START_LOG%" 2>&1
goto STOP_ERROR

:BROKEN_ENV
echo.
echo [ERROR] The existing .venv Python is broken or unsupported.
echo Rename the .venv folder, then rerun this launcher.
echo Do not delete your samples or analysis results.
goto STOP_ERROR

:VENV_FAILED
echo.
echo [ERROR] Could not create a working Python virtual environment.
goto STOP_ERROR

:INSTALL_FAILED
echo.
echo [ERROR] Dependencies are still missing.
findstr /I /C:"getaddrinfo failed" /C:"Name or service not known" /C:"Failed to establish a new connection" "%START_LOG%" >nul 2>&1
if errorlevel 1 goto INSTALL_OTHER_ERROR
echo Network or DNS lookup failed. This is not a NumPy version conflict.
echo Check internet access and whether both pypi.org and pypi.tuna.tsinghua.edu.cn resolve.
echo If this PC has no internet, install from a local Windows wheel collection.
goto STOP_ERROR

:INSTALL_OTHER_ERROR
echo See startup.log for the exact pip error.
goto STOP_ERROR

:APP_FAILED
echo.
echo [ERROR] The application exited with an error.
echo See startup.log for the Python traceback.
goto STOP_ERROR

:BAD_FOLDER
echo [ERROR] Could not enter the folder containing this launcher.
pause
exit /b 1

:STOP_ERROR
echo.
echo Detailed log: "%START_LOG%"
echo Press any key to keep this window open until you have read the error.
pause
popd
exit /b 1

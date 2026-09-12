# setup_and_run.bat
# Windows launcher for Let-It-Die TODO Tracker
# Usage:
#   setup_and_run.bat                    :: normal GUI launch
#   setup_and_run.bat --offscreen        :: headless (no window, for SSH/etc)
#   setup_and_run.bat --save "C:\Savedata\76561198140783693.sav"

@echo off
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%.venv"
set "REQS=%SCRIPT_DIR%requirements.txt"
set "LAUNCHER=%SCRIPT_DIR%start_todo_tracker.py"

set "OFFSCREEN=0"
set "SAVE_ARG="

:parse_args
if "%~1"=="" goto :done_args
if /i "%~1"=="--offscreen" (
    set "OFFSCREEN=1"
    shift
    goto :parse_args
)
if /i "%~1"=="--save" (
    if "%~2"=="" (
        echo ERROR: --save requires a path argument.
        goto :error
    )
    set "SAVE_ARG=--save "%~2""
    shift
    shift
    goto :parse_args
)
echo Unknown option: %~1
echo Usage: %~nx0 [--offscreen] [--save "path\to\save.sav"]
goto :error

:done_args
echo.

:: --- create venv if missing ---
if not exist "%VENV_DIR%" (
    echo >> Creating virtual environment in %VENV_DIR% ...
    python -m venv "%VENV_DIR%"
) else (
    echo >> Virtual environment already exists at %VENV_DIR%
)

:: --- activate (call batch, then return) ---
call "%VENV_DIR%\Scripts\activate.bat"

:: --- upgrade pip (quiet) ---
echo >> Ensuring pip is up to date ...
pip install --quiet --upgrade pip

:: --- install requirements ---
if exist "%REQS%" (
    echo >> Installing requirements from %REQS% ...
    pip install --quiet -r "%REQS%"
) else (
    echo WARNING: %REQS% not found - installing PySide6 only.
    pip install --quiet "PySide6>=6.5.0"
)

:: --- verify launcher ---
if not exist "%LAUNCHER%" (
    echo ERROR: Launcher not found: %LAUNCHER%
    goto :error
)

:: --- launch ---
echo.
echo >> Launching TODO Tracker ...
if %OFFSCREEN%==1 (
    set "QT_QPA_PLATFORM=offscreen"
    echo     (offscreen / headless mode)
)

if defined SAVE_ARG (
    python "%LAUNCHER%" %SAVE_ARG%
) else (
    python "%LAUNCHER%"
)

goto :eof

:error
echo.
echo Setup or launch failed.
pause
exit /b 1

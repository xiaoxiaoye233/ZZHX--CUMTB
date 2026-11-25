@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist "..\project\venv\Scripts\python.exe" (
    "..\project\venv\Scripts\python.exe" stm32_auto_print.py %*
) else if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" stm32_auto_print.py %*
) else (
    python stm32_auto_print.py %*
)
pause

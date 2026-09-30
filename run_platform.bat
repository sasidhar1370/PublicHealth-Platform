@echo off
setlocal enabledelayedexpansion

title Public Health Competency Assessment Platform

:: Free port 8000 if previously occupied
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do taskkill /f /pid %%a >nul 2>&1

echo ===============================================================================
echo     PUBLIC HEALTH COMPETENCY ASSESSMENT AND LEARNING PLATFORM
echo     Institutional CEPH / CPH Standardized Examination Console
echo ===============================================================================
echo.

:: 1. Verify Python
echo [1/3] Verifying Python runtime...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not added to your PATH.
    pause
    exit /b 1
)

:: 2. Dependencies
echo [2/3] Verifying dependencies...
pip install python-multipart >nul 2>&1

:: 3. Launch Backend
echo [3/3] Starting backend server on http://127.0.0.1:8000 ...
start /b uvicorn backend.main:app --host 127.0.0.1 --port 8000

timeout /t 3 /nobreak >nul

echo.
echo ===============================================================================
echo  Platform is LIVE:
echo  - Portal URL: http://127.0.0.1:8000/
echo  - Swagger Docs: http://127.0.0.1:8000/docs
echo ===============================================================================
echo.
echo Opening portal in browser...
start http://127.0.0.1:8000/

pause

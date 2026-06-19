@echo off
REM WandaTools Backend - Setup Script for Windows

echo.
echo ^>^>^> WandaTools Backend - Setup Script
echo ^>^>^> ==================================
echo.

REM Check Python version
echo ^>^>^> Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo OK: Python %PYTHON_VERSION% found
echo.

REM Create virtual environment
echo ^>^>^> Creating virtual environment...
if not exist "venv" (
    python -m venv venv
    echo OK: Virtual environment created
) else (
    echo OK: Virtual environment already exists
)
echo.

REM Activate virtual environment
echo ^>^>^> Activating virtual environment...
call venv\Scripts\activate.bat
echo OK: Virtual environment activated
echo.

REM Upgrade pip
echo ^>^>^> Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1
echo OK: pip upgraded
echo.

REM Install dependencies
echo ^>^>^> Installing dependencies from requirements.txt...
pip install -r requirements.txt
echo OK: Dependencies installed
echo.

REM Create .env file if it doesn't exist
if not exist ".env" (
    echo ^>^>^> Creating .env file...
    copy .env.example .env >nul
    echo OK: .env file created from template
    echo WARNING: Please edit .env with your configuration:
    echo    - DATABASE_URL: Update with your PostgreSQL connection string
    echo    - SECRET_KEY: Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    echo.
) else (
    echo OK: .env file already exists
)
echo.

REM Display next steps
echo OK: Setup complete!
echo.
echo Next steps:
echo 1. Edit .env file with your configuration
echo 2. Ensure PostgreSQL is running
echo 3. Create database: psql -c "CREATE DATABASE wandatools_db;"
echo 4. Start server: uvicorn main:app --reload
echo 5. Open http://localhost:8000/api/docs
echo.
echo Enjoy developing!
pause

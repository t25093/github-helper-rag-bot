@echo off
REM ============================================================
REM  Org knowledge bot - one-click start (Windows)
REM  Double-click this file, or run:  run.bat
REM ============================================================
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

REM --- 1. Find Python 3.12 (falls back to any "python") ---
set "PY=py -3.12"
%PY% --version >nul 2>&1
if errorlevel 1 (
    set "PY=python"
    python --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python 3.12 was not found.
        echo         Install it from https://www.python.org/downloads/
        echo         and check "Add python.exe to PATH" during setup.
        goto :fail
    )
)
echo [OK] Using: %PY%

REM --- 2. Check the .env file with the API key ---
if not exist ".env" (
    echo [ERROR] The .env file is missing.
    echo         Copy .env.example to .env and put your GOOGLE_API_KEY in it.
    goto :fail
)

REM --- 3. Install libraries on first run ---
%PY% -c "import chromadb, chainlit, llama_index.core, rank_bm25" >nul 2>&1
if errorlevel 1 (
    echo [..] Installing libraries - this can take a few minutes...
    %PY% -m pip install -r requirements.txt --no-warn-script-location
    if errorlevel 1 (
        echo [ERROR] Library installation failed. See the messages above.
        goto :fail
    )
)
echo [OK] Libraries installed

REM --- 4. Build the index if it does not exist, otherwise offer to rebuild ---
if not exist "storage\chroma" (
    echo [..] No index found - building it from the files in the data folder...
    %PY% ingest.py
    if errorlevel 1 goto :fail
) else (
    echo.
    echo Rebuild the index? Needed only after changing files in the data folder.
    choice /C YN /T 10 /D N /M "Y = rebuild, N = start the bot (auto N in 10 seconds)"
    if errorlevel 2 (
        echo [OK] Using the existing index
    ) else (
        %PY% ingest.py
        if errorlevel 1 goto :fail
    )
)

REM --- 5. Start the bot (opens http://localhost:8000) ---
echo.
echo [..] Starting the bot. To stop it: press Ctrl+C in this window.
%PY% -m chainlit run app.py
goto :end

:fail
echo.
echo The bot did not start. Fix the problem above and run this file again.
pause
exit /b 1

:end
endlocal

@echo off
cd /d "%~dp0"
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\pythonw.exe"
    "C:\Python313\pythonw.exe"
    "C:\Python312\pythonw.exe"
    "C:\Python311\pythonw.exe"
) do (
    if exist %%P (
        start "" %%P "%~dp0project_tracker.py"
        exit /b
    )
)
where pythonw >nul 2>&1 && (start "" pythonw "%~dp0project_tracker.py" & exit /b)
where python  >nul 2>&1 && (start "" python  "%~dp0project_tracker.py" & exit /b)
msg * "Python not found. Install from python.org and tick 'Add to PATH'."

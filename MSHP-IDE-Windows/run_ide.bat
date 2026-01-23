@echo off
setlocal
set "ROOT=%~dp0"
set "PY=%ROOT%python\python.exe"

if exist "%PY%" goto :run

for /f "delims=" %%P in ('dir /b /s "%ROOT%python\python.exe" 2^>nul') do (
  set "PY=%%P"
  goto :run
)

echo Portable Python not found in:
 echo   %ROOT%python
 echo.
 echo Press any key to exit.
 pause >nul
exit /b 1

:run
set "PYTHON_PORTABLE=%PY%"
"%PY%" "%ROOT%app\ide.py"

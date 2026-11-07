@echo off
rem COHIWizard setup for Windows
rem Finds Python 3.10 - 3.13 (installs Python 3.10.11 for the current user if
rem none is found), fetches the current cohi_setup.py from GitHub and
rem starts it. Arguments are passed on to cohi_setup.py.
setlocal
set "HERE=%~dp0"
set "SETUP=%HERE%cohi_setup.py"
set "PYEXE="

for %%V in (3.10 3.11 3.12 3.13) do (
    if not defined PYEXE (
        py -%%V -c "import sys" >nul 2>&1 && set "PYEXE=py -%%V"
    )
)
if not defined PYEXE (
    python -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,13) else 1)" >nul 2>&1 && set "PYEXE=python"
)
if not defined PYEXE (
    echo No suitable Python found, installing Python 3.10.11 for the current user ...
    powershell -NoProfile -Command "Invoke-WebRequest -UseBasicParsing https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe -OutFile '%TEMP%\python-3.10.11-amd64.exe'"
    if errorlevel 1 goto :fail
    "%TEMP%\python-3.10.11-amd64.exe" /passive InstallAllUsers=0 Include_launcher=1 PrependPath=0 Include_test=0
    if errorlevel 1 goto :fail
    set PYEXE="%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
)

rem Always fetch the current cohi_setup.py so that a stale copy next to this
rem file is never used. Exception: inside a git checkout (developer tree) the
rem local file is kept. Without internet an existing copy is used.
if exist "%HERE%..\.git" if exist "%SETUP%" goto :run
echo Downloading cohi_setup.py ...
powershell -NoProfile -Command "Invoke-WebRequest -UseBasicParsing https://raw.githubusercontent.com/hermy-sf/COHIWizard/cohiwizard_v2.3/sources/cohi_setup.py -OutFile '%SETUP%.new'"
if errorlevel 1 goto :nodownload
move /y "%SETUP%.new" "%SETUP%" >nul
goto :run

:nodownload
if exist "%SETUP%.new" del "%SETUP%.new"
if not exist "%SETUP%" goto :fail
echo Download failed, using the existing cohi_setup.py

:run

%PYEXE% "%SETUP%" %*
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo COHIWizard setup failed, see the messages above.
pause
exit /b 1

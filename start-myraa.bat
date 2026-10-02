@echo off
chcp 65001 >nul
title MYRAA Launcher
color 0B

set "PYTHON_EXE=python"
set "PROJECT_DIR=%~dp0"
rem UTF-8 process encoding: Gemini Live voice and Hindi text require UTF-8;
rem cp1252 default would break Hindi/Devanagari. Keep PYTHONUTF8=1.
set "PYTHONUTF8=1"

echo ============================================================
echo                 MYRAA ALL-IN-ONE LAUNCHER
echo ============================================================
echo.

echo [1/4] Cleaning stale instances...
powershell -NoProfile -ExecutionPolicy Bypass -Command "foreach($p in @(3000,8765)){ $conns=Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue; if($conns){ $owners=$conns | Select-Object -ExpandProperty OwningProcess -Unique; foreach($procId in $owners){ if($procId -and $procId -ne 0){ Write-Host ('    Killing stale process on port ' + $p + ' (PID ' + $procId + ')'); Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue } } } }"
ping -n 3 127.0.0.1 >nul
echo     Done.
echo.

echo [2/4] Starting Desktop Control Agent...
start "MYRAA Desktop Agent" /D "%PROJECT_DIR%" cmd /k %PYTHON_EXE% -m uvicorn desktop_agent.main:app --host 127.0.0.1 --port 8765
echo     Launching in background window...
echo.

echo [3/4] Waiting for Desktop Agent...
rem Readiness contract: GET /health/live == 200 means process alive.
rem Deliberately NOT /health - that is the detailed subsystem report,
rem which may show degraded subsystems while the process is fine.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$u='http://127.0.0.1:8765/health/live'; $max=15; $code=0; for($i=1;$i -le $max;$i++){ try{ $r=Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 2; $code=[int]$r.StatusCode }catch{ if($_.Exception.Response){ $code=[int]$_.Exception.Response.StatusCode }else{ $code=0 } }; if($code -eq 200){ Write-Host '    Desktop Agent READY'; exit 0 }; Write-Host ('    ...waiting {0}/{1}' -f $i,$max); Start-Sleep -Seconds 1 }; Write-Host ''; Write-Host '    [ERROR] Desktop Agent failed to become ready.'; Write-Host '    Check startup log.'; Write-Host ('    Endpoint checked : {0}' -f $u); Write-Host ('    Last HTTP status : {0}   (0 = no connection / not listening)' -f $code); exit 1"
if errorlevel 1 (
    echo.
    echo [ERROR] MYRAA Server not started because Desktop Agent is not ready.
    goto :cleanup_fail
)
echo.

echo [4/4] Starting MYRAA Server...
echo ============================================================
echo   Desktop Agent : http://127.0.0.1:8765
echo   MYRAA UI      : http://localhost:3000
echo ============================================================
echo.
echo   Close this window to stop MYRAA.
echo.

start "" /b powershell -NoProfile -ExecutionPolicy Bypass -Command "$ok=$false; foreach($i in 1..30){ try{ $r=Invoke-WebRequest -Uri 'http://127.0.0.1:3000' -UseBasicParsing -TimeoutSec 2; if($r.StatusCode -eq 200){ $ok=$true; break } }catch{}; Start-Sleep -Seconds 1 }; if($ok){ Write-Host '    MYRAA UI is up: http://localhost:3000' }else{ Write-Host '    [ERROR] MYRAA Server failed to start.' }"

cd /d "%PROJECT_DIR%"
npm run dev
if errorlevel 1 (
    echo.
    echo [ERROR] MYRAA Server failed to start.
)

echo.
echo MYRAA has stopped. Cleaning up Desktop Agent...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$conns=Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue; if($conns){ $conns | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } }"
pause
exit /b 0

:cleanup_fail
powershell -NoProfile -ExecutionPolicy Bypass -Command "$conns=Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue; if($conns){ $conns | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } }"
pause
exit /b 1

@echo off
cd /d "%~dp0"
python tests\test_performance_integration.py
pause
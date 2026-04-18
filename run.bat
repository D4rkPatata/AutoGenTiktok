@echo off
cd /d "%~dp0"
.conda\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app --reload-dir frontend

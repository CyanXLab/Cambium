@echo off
chcp 65001 >nul 2>&1
title Cambium
cd /d "%~dp0"
python -m uvicorn app.main:app --host 0.0.0.0 --port 3000 --log-level info

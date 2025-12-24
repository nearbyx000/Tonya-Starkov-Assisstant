@echo off
title Tonya Voice Server Automation
cd /d "%~dp0"

:: --- CONFIGURATION ---
:: Replace with the EXACT name of the model you downloaded in LM Studio
set MODEL_KEY="TheBloke/mistrall-7b-instruct-v0.1"
:: ---------------------

echo [1/3] Starting LM Studio Server...
call lms server start --cors=true

echo [2/3] Loading Model (%MODEL_KEY%)...
:: This forces the model to load immediately
call lms load %MODEL_KEY% --gpu=max

echo [3/3] Starting Python Voice Server...
python server.py

pause
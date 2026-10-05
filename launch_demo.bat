@echo off
title TCP Multi-Client Chat Demo Launcher
echo ========================================================
echo   Launching TCP Multi-Client Chat Application Demo
echo   1. TCP Chat Server (CLI Terminal)
echo   2. Client Instance 1 (Alice)
echo   3. Client Instance 2 (Bob)
echo ========================================================

start "TCP Chat Server" cmd /k "python run_server.py"
timeout /t 2 /nobreak > nul

start "TCP Client 1" cmd /k "python run_client.py"
timeout /t 1 /nobreak > nul

start "TCP Client 2" cmd /k "python run_client.py"

echo Demo launched successfully! Check the opened windows.

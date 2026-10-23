@echo off
chcp 65001 >nul
title Instalando o Editor Viral
echo Instalando o Editor Viral. Pode levar de 10 a 25 minutos...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"
echo.
pause

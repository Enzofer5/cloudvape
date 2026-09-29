@echo off
chcp 65001 >nul
title CloudVape - Tienda demo
cd /d "%~dp0"

echo ============================================
echo    CloudVape - iniciando la tienda...
echo ============================================

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] No se encontro Python.
    echo Instalalo desde https://www.python.org/downloads/
    echo IMPORTANTE: tilda la opcion "Add python.exe to PATH" al instalar.
    echo.
    pause
    exit /b 1
)

if not exist venv (
    echo Creando entorno virtual la primera vez...
    python -m venv venv
    if errorlevel 1 ( echo [ERROR] No se pudo crear el entorno virtual. & pause & exit /b 1 )
)

call venv\Scripts\activate.bat

if not exist venv\.instalado (
    echo Instalando dependencias, puede tardar un par de minutos...
    python -m pip install --upgrade pip >nul
    pip install -r requirements.txt
    if errorlevel 1 ( echo [ERROR] Fallo la instalacion de dependencias. & pause & exit /b 1 )
    echo ok> venv\.instalado
)

python iniciar_demo.py
pause

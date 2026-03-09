@echo off
title Anonymiseur PDF

set "ROOT=%~dp0"
set "VENV=%ROOT%venv"
set "PY=%VENV%\Scripts\python.exe"
set "PIP=%VENV%\Scripts\pip.exe"
set "FLAG=%VENV%\.installed"

echo === Anonymiseur PDF ===
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR : Python introuvable.
    echo Installez Python 3.10+ depuis https://www.python.org/downloads/
    echo Cochez "Add Python to PATH"
    pause
    exit /b 1
)

if not exist "%VENV%\Scripts\activate.bat" (
    echo Creation du venv...
    python -m venv "%VENV%"
    if errorlevel 1 ( echo ERREUR venv & pause & exit /b 1 )
)

if not exist "%PY%" (
    echo ERREUR : %PY% introuvable
    echo Supprimez le dossier venv et relancez.
    pause
    exit /b 1
)

if not exist "%FLAG%" (
    echo Installation des dependances...
    "%PIP%" install --upgrade pip
    "%PIP%" install -r "%ROOT%requirements.txt"
    if errorlevel 1 ( echo ERREUR installation & pause & exit /b 1 )

    echo Telechargement modele spaCy...
    "%PY%" -m spacy download fr_core_news_lg
    if errorlevel 1 ( echo ERREUR spacy & pause & exit /b 1 )

    echo ok > "%FLAG%"
)

:: --- Verifier et corriger Tesseract + fra.traineddata ---
set "TESS_DIR="
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" set "TESS_DIR=C:\Program Files\Tesseract-OCR"
if exist "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe" set "TESS_DIR=C:\Program Files (x86)\Tesseract-OCR"

if "%TESS_DIR%"=="" (
    echo ERREUR : Tesseract introuvable.
    echo Telechargez-le depuis : https://github.com/UB-Mannheim/tesseract/wiki
    pause
    exit /b 1
)

set "TESSDATA=%TESS_DIR%\tessdata"
set "FRA_FILE=%TESSDATA%\fra.traineddata"

if not exist "%FRA_FILE%" (
    echo Telechargement des donnees de langue francaise pour Tesseract...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/tesseract-ocr/tessdata/raw/main/fra.traineddata' -OutFile '%FRA_FILE%'"
    if errorlevel 1 (
        echo ERREUR : Impossible de telecharger fra.traineddata
        echo Telechargez manuellement fra.traineddata depuis GitHub/tesseract-ocr/tessdata
        echo et placez-le dans : %TESSDATA%
        pause
        exit /b 1
    )
    echo fra.traineddata installe avec succes.
)

:: Definir les variables pour Tesseract
set "TESSDATA_PREFIX=%TESSDATA%"
set "PATH=%TESS_DIR%;%PATH%"

echo Lancement...
cd /d "%ROOT%"
"%PY%" main.py
echo.
echo Code de sortie : %errorlevel%
pause

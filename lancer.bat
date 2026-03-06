@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Anonymiseur PDF

:: ─── Chemins ────────────────────────────────────────────────────────────────
set "ROOT=%~dp0"
set "VENV=%ROOT%venv"
set "PY=%VENV%\Scripts\python.exe"
set "PIP=%VENV%\Scripts\pip.exe"
set "FLAG=%VENV%\.installed"

:: ─── Python disponible ? ─────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python est introuvable.
    echo Installez Python 3.10+ depuis https://www.python.org/downloads/
    echo Cochez "Add Python to PATH" lors de l'installation.
    pause
    exit /b 1
)

:: ─── Créer le venv si besoin ──────────────────────────────────────────────────
if not exist "%VENV%\Scripts\activate.bat" (
    echo [1/4] Creation de l'environnement virtuel...
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo [ERREUR] Impossible de creer le venv.
        pause
        exit /b 1
    )
)

:: ─── Vérifier que python.exe du venv existe ──────────────────────────────────
if not exist "%PY%" (
    echo [ERREUR] python.exe introuvable dans le venv : %PY%
    echo Supprimez le dossier "venv" et relancez ce fichier.
    pause
    exit /b 1
)

:: ─── Installer les dépendances une seule fois ─────────────────────────────────
if not exist "%FLAG%" (
    echo [2/4] Installation des dependances (premiere fois, ~5 min)...
    "%PIP%" install --upgrade pip --quiet
    "%PIP%" install -r "%ROOT%requirements.txt"
    if errorlevel 1 (
        echo [ERREUR] L'installation des dependances a echoue.
        pause
        exit /b 1
    )

    echo [3/4] Telechargement du modele spaCy (fr_core_news_lg)...
    "%PY%" -m spacy download fr_core_news_lg
    if errorlevel 1 (
        echo [ATTENTION] Le modele spaCy n'a pas pu etre telecharge.
        echo Verifiez votre connexion internet et relancez ce fichier.
        pause
        exit /b 1
    )

    echo ok > "%FLAG%"
    echo [4/4] Installation terminee.
)

:: ─── Vérifier Tesseract ───────────────────────────────────────────────────────
tesseract --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ATTENTION] Tesseract OCR n'est pas installe ou absent du PATH.
    echo Telechargez-le ici : https://github.com/UB-Mannheim/tesseract/wiki
    echo.
    echo Appuyez sur une touche pour continuer sans OCR...
    pause >nul
)

:: ─── Lancer l'application ────────────────────────────────────────────────────
echo Lancement de l'Anonymiseur PDF...
echo Python : %PY%
cd /d "%ROOT%"
"%PY%" main.py > "%ROOT%erreur.log" 2>&1
set EXITCODE=%errorlevel%
echo.
echo Code de sortie : %EXITCODE%
if %EXITCODE% neq 0 (
    echo.
    echo [ERREUR] L'application s'est terminee avec une erreur :
    echo --------------------------------------------------------
    type "%ROOT%erreur.log"
    echo --------------------------------------------------------
    echo Le detail est sauvegarde dans erreur.log
) else (
    if exist "%ROOT%erreur.log" (
        for %%A in ("%ROOT%erreur.log") do if %%~zA gtr 0 (
            echo [INFO] Sortie capturee dans erreur.log :
            type "%ROOT%erreur.log"
        )
    )
)
pause
endlocal

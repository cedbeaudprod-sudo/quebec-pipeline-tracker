@echo off
echo ========================================
echo   Quebec Pipeline Tracker - Setup
echo ========================================
echo.

cd /d "%~dp0"

echo Installation des dependances...
py -m pip install -r requirements.txt

echo.
echo Lancement de l'application...
echo (Le navigateur va s'ouvrir automatiquement)
echo.
py -m streamlit run app.py

pause

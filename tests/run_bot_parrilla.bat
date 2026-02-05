@echo off
echo 📅 Enviando Partidos de Hoy
echo ===========================
cd /d "%~dp0"
python src/bot_parrilla.py hoy
echo.
echo ✅ Partidos enviados
pause

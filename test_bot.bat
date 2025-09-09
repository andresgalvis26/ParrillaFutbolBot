@echo off
echo 🔍 Probando Bot - Partidos de Hoy
echo =================================
cd /d "%~dp0"
python src/bot_parrilla.py test hoy
echo.
echo ✅ Prueba completada
pause

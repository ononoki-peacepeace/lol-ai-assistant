@echo off
chcp 65001 > nul
cd /d %~dp0

title LOL AI Assistant - Candidate Review

echo ================================
echo LOL AI Assistant - Candidate Review
echo ================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] 未找到 .venv\Scripts\python.exe
    pause
    exit /b 1
)

echo [启动] Streamlit Review App
echo 浏览器一般会自动打开。
echo 如果没有打开，请访问 http://localhost:8501
echo.

.venv\Scripts\python.exe -m streamlit run tools\knowledge\review_app.py

echo.
echo Review App 已退出。
pause
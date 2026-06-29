@echo off
chcp 65001 > nul
cd /d %~dp0

title LOL AI Assistant - Async RAG Worker

echo ================================
echo LOL AI Assistant - Async RAG Worker
echo ================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] 未找到 .venv\Scripts\python.exe
    pause
    exit /b 1
)

echo 请先运行 setup_keys.bat 配置 DEEPSEEK_API_KEY 和 TAVILY_API_KEY。

echo.
echo [启动] 后台监听 knowledge\search\bp_search_jobs.json
echo 每轮最多执行 1 个任务，避免一次性烧太多 API。
echo.

.venv\Scripts\python.exe tools\knowledge\run_search_jobs.py --config knowledge\search\bp_search_jobs.json --loop --limit 1 --idle-sleep 10

echo.
echo RAG Worker 已退出。
pause
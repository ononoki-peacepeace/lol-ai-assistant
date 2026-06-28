@echo off
chcp 65001 > nul
cd /d %~dp0

title LOL AI Assistant - Merge Approved Knowledge

echo ================================
echo LOL AI Assistant - Merge Approved
echo ================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] 未找到 .venv\Scripts\python.exe
    pause
    exit /b 1
)

echo 这个脚本会把 review_status=approved 的候选知识合并到：
echo - knowledge\bp\counters.json
echo - knowledge\bp\champion_strength.json
echo - knowledge\bp\team_combos.json
echo.

set /p CONFIRM=确认合并吗？输入 y 继续: 
if /I not "%CONFIRM%"=="y" (
    echo 已取消。
    pause
    exit /b 0
)

echo.
echo [DRY RUN] 先预览合并结果：
.venv\Scripts\python.exe tools\knowledge\merge_approved_proposals.py --dry-run

echo.
set /p CONFIRM2=确认正式写入吗？输入 y 继续: 
if /I not "%CONFIRM2%"=="y" (
    echo 已取消正式写入。
    pause
    exit /b 0
)

echo.
echo [MERGE] 正式合并：
.venv\Scripts\python.exe tools\knowledge\merge_approved_proposals.py

echo.
echo 合并完成。
pause
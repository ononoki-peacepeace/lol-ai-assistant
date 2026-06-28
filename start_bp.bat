@echo off
chcp 65001 > nul
cd /d %~dp0

title LOL AI Assistant - BP Assistant

echo ================================
echo LOL AI Assistant - BP Assistant
echo ================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] 未找到 .venv\Scripts\python.exe
    echo 请先创建虚拟环境并安装依赖。
    pause
    exit /b 1
)

set SIDE=blue
set ROLE=top


echo 默认位置: top
echo.


set /p ROLE_INPUT=请输入位置 role，top/jungle/mid/adc/support，直接回车默认 top: 
if not "%ROLE_INPUT%"=="" set ROLE=%ROLE_INPUT%

echo.
echo [启动] side=%SIDE% role=%ROLE%
echo.

.venv\Scripts\python.exe main.py watch-bp  --role %ROLE% --ai

echo.
echo BP Assistant 已退出。
pause
@echo off
chcp 65001 > nul
cd /d %~dp0

title LOL AI Assistant - Setup API Keys

echo ================================
echo LOL AI Assistant - Setup API Keys
echo ================================
echo.

echo 这个脚本会在项目根目录生成 .env 文件。
echo .env 里保存 API Key，不要提交到 GitHub。
echo.

set /p DEEPSEEK_KEY=请输入 DEEPSEEK_API_KEY，直接回车跳过: 
set /p TAVILY_KEY=请输入 TAVILY_API_KEY，直接回车跳过: 

echo. > .env

if not "%DEEPSEEK_KEY%"=="" (
    echo DEEPSEEK_API_KEY=%DEEPSEEK_KEY%>> .env
)

if not "%TAVILY_KEY%"=="" (
    echo TAVILY_API_KEY=%TAVILY_KEY%>> .env
)

echo.
echo 已生成 .env 文件。
echo.

type .env

echo.
pause
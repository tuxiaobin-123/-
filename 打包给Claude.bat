@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
set "PACKAGE=%ROOT%..\flood-twin-system-claude-source.zip"

echo 正在打包源码给 Claude...
where git >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$root=(Resolve-Path '%ROOT%').Path; $out=(Resolve-Path '%ROOT%\..').Path + '\flood-twin-system-claude-source.zip'; if(Test-Path $out){Remove-Item $out -Force}; $exclude='\\.git\\|\\.venv|backend\\venv|frontend\\node_modules|frontend\\dist|runtime-logs|\\tmp\\|\\outputs\\'; $files=Get-ChildItem $root -Recurse -File | Where-Object { $_.FullName -notmatch $exclude }; Compress-Archive -Path $files.FullName -DestinationPath $out -Force"
) else (
  cd /d "%ROOT%"
  git archive --format=zip --output="%PACKAGE%" HEAD
)

echo.
echo 已生成:
echo %PACKAGE%
pause

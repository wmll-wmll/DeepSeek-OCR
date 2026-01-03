# DeepSeek-OCR Web App 启动脚本

# 设置错误时停止
$ErrorActionPreference = "Stop"

# 获取脚本所在目录
$ScriptDir = $PSScriptRoot

# 检查虚拟环境
if (Test-Path "$ScriptDir\.venv\Scripts\Activate.ps1") {
    Write-Host "正在激活虚拟环境..."
    & "$ScriptDir\.venv\Scripts\Activate.ps1"
} else {
    Write-Host "警告: 未找到虚拟环境 (.venv)，尝试直接运行..."
}

# 设置环境变量 (如果需要)
$env:PYTHONPATH = "$ScriptDir;$env:PYTHONPATH"

# 运行 Web 应用
Write-Host "正在启动 Web 应用..."
Write-Host "访问 http://localhost:8000 使用 OCR 服务"
python -m uvicorn web_app.main:app --host 0.0.0.0 --port 8000 --reload


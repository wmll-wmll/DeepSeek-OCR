# DeepSeek-OCR Web App 启动脚本 (Vue 3 + FastAPI)

# 设置错误时停止
$ErrorActionPreference = "Stop"

# 获取脚本所在目录
$ScriptDir = $PSScriptRoot

# 1. 检查并准备前端
$FrontendDir = "$ScriptDir\web_app\frontend"
$DistDir = "$FrontendDir\dist"

Write-Host "正在检查前端状态..."

if (-not (Test-Path $DistDir)) {
    Write-Host "前端构建产物未找到 (dist)，正在尝试构建..."
    
    # 检查 npm.ps1 是否可用
    if (Get-Command npm.ps1 -ErrorAction SilentlyContinue) {
        try {
            Push-Location $FrontendDir
            
            Write-Host "正在安装前端依赖 (这可能需要几分钟)..."
            npm.ps1 install
            
            Write-Host "正在构建前端应用..."
            npm.ps1 run build
            
            Write-Host "前端构建完成！"
        } catch {
            Write-Host "前端构建失败: $_"
            Write-Host "将尝试仅以 API 模式启动后端..."
        } finally {
            Pop-Location
        }
    } else {
        Write-Host "警告: 未找到 npm.ps1，无法自动构建前端。Web 界面可能无法访问。"
        Write-Host "请确保已安装 Node.js 并配置了 npm.ps1，或者手动在 web_app/frontend 目录下运行构建。"
    }
} else {
    Write-Host "前端已构建。"
}

# 2. 启动后端
# 检查虚拟环境
if (Test-Path "$ScriptDir\.venv\Scripts\Activate.ps1") {
    Write-Host "正在激活虚拟环境..."
    & "$ScriptDir\.venv\Scripts\Activate.ps1"
} else {
    Write-Host "警告: 未找到虚拟环境 (.venv)，尝试直接运行..."
}

# 设置环境变量
$env:PYTHONPATH = "$ScriptDir;$env:PYTHONPATH"
$env:DEEPSEEK_OCR_MODEL_PATH = "$ScriptDir\model"

# 运行 Web 应用
Write-Host "`n==============================================="
Write-Host "正在启动 DeepSeek-OCR Web 服务..."
Write-Host "访问地址: http://localhost:8000"
Write-Host "==============================================="

python -m uvicorn web_app.backend.main:app --host 0.0.0.0 --port 8000

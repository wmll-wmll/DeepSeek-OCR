param (
    [Parameter(Mandatory=$true)]
    [string]$Image,

    [string]$Mode = "markdown",

    [string]$Output = ""
)

# 设置错误时停止
$ErrorActionPreference = "Stop"

# 获取脚本所在目录
$ScriptDir = $PSScriptRoot

# 检查图片路径
if (-not (Test-Path $Image)) {
    Write-Error "找不到图片文件: $Image"
    exit 1
}

# 转换为绝对路径
$Image = Resolve-Path $Image

# 激活虚拟环境
Write-Host "正在激活虚拟环境..."
& "$ScriptDir\.venv\Scripts\Activate.ps1"

# 构建参数
$ArgsList = @("--image", $Image, "--mode", $Mode)
if ($Output) {
    $ArgsList += "--output"
    $ArgsList += $Output
}

# 进入代码目录
cd "$ScriptDir\DeepSeek-OCR-master\DeepSeek-OCR-hf"

# 运行推理脚本
Write-Host "正在运行 OCR (模式: $Mode)..."
python easy_ocr.py @ArgsList

Write-Host "运行完成！"

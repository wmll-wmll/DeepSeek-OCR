# DeepSeek-OCR Windows 运行脚本

# 设置错误时停止
$ErrorActionPreference = "Stop"

# 获取脚本所在目录
$ScriptDir = $PSScriptRoot

# 激活虚拟环境
Write-Host "正在激活虚拟环境..."
& "$ScriptDir\.venv\Scripts\Activate.ps1"

# 进入代码目录
cd "$ScriptDir\DeepSeek-OCR-master\DeepSeek-OCR-hf"

# 运行推理脚本
Write-Host "正在运行 OCR 推理..."
python run_dpsk_ocr.py

Write-Host "运行完成！结果保存在 output 目录。"

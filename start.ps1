# ── 一键启动脚本 ──────────────────────────────────────────
# 1. 在 LightRAG 目录启动 RAG server（后台）
# 2. 等待 RAG server 就绪
# 3. 启动学习系统主程序（前台）
# ─────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"

$scriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ragDir      = Join-Path $scriptDir "LightRAG"
$studyDir    = Join-Path $scriptDir "agentic-study-system"
$ragPort     = 9621
$ragUrl      = "http://127.0.0.1:$ragPort/health"

Write-Host "▶ 启动 LightRAG server（端口 $ragPort）..." -ForegroundColor Cyan

# 在 LightRAG 目录启动 server，独立窗口运行
$ragProcess = Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$ragDir'; lightrag-server 2>&1 | Tee-Object -FilePath '$ragDir\lightrag.log'"
) -PassThru -WindowStyle Normal

Write-Host "  LightRAG PID: $($ragProcess.Id)"

# 等待健康检查通过（最多 60 秒）
Write-Host "⏳ 等待 LightRAG 就绪..." -ForegroundColor Yellow
$deadline = (Get-Date).AddSeconds(60)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $resp = Invoke-WebRequest -Uri $ragUrl -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
    Start-Sleep -Seconds 2
    Write-Host "  ..." -NoNewline
}

if (-not $ready) {
    Write-Warning "LightRAG 60 秒内未响应，仍将启动主程序（将使用本地检索回退）。"
} else {
    Write-Host "`n✅ LightRAG 已就绪！" -ForegroundColor Green
}

# 启动学习系统
Write-Host "▶ 启动 Agentic Study System..." -ForegroundColor Cyan
Set-Location $studyDir
python main.py serve

# 启动内嵌 LightRAG Server（云雾AI + 本地 Ollama embedding）
# 依赖：pip install -r requirements.txt  &&  ollama pull nomic-embed-text

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$lightRagRoot = Join-Path $projectRoot "LightRAG"
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pythonExe = if (Test-Path $venvPython) { $venvPython } else { "python" }

if (-not (Test-Path $lightRagRoot)) {
    throw "LightRAG source not found: $lightRagRoot"
}

$env:PYTHONIOENCODING       = "utf-8"
$env:PYTHONPATH             = "$lightRagRoot;$env:PYTHONPATH"
$env:LLM_BINDING            = "openai"
$env:LLM_MODEL              = if ($env:LIGHTRAG_LLM_MODEL) { $env:LIGHTRAG_LLM_MODEL } else { "gpt-5.4-mini" }
$env:LLM_BINDING_HOST       = if ($env:LIGHTRAG_LLM_BASE_URL) { $env:LIGHTRAG_LLM_BASE_URL } elseif ($env:OPENAI_BASE_URL) { $env:OPENAI_BASE_URL } else { "https://api.openai.com/v1" }
$env:EMBEDDING_BINDING      = "ollama"
$env:EMBEDDING_MODEL        = "nomic-embed-text"
$env:EMBEDDING_BINDING_HOST = "http://localhost:11434"
$env:EMBEDDING_DIM          = "768"   # nomic-embed-text 输出维度，必须与模型一致

# 从 .env 读取 LightRAG LLM 配置（不硬编码 key 到脚本里）
if (Test-Path (Join-Path $PSScriptRoot "..\.env")) {
    Get-Content (Join-Path $PSScriptRoot "..\.env") | ForEach-Object {
        if ($_ -match "^LIGHTRAG_LLM_API_KEY=(.+)$") {
            $env:LLM_BINDING_API_KEY = $Matches[1]
        }
        if ($_ -match "^LIGHTRAG_LLM_BASE_URL=(.+)$") {
            $env:LLM_BINDING_HOST = $Matches[1]
        }
        if ($_ -match "^LIGHTRAG_LLM_MODEL=(.+)$") {
            $env:LLM_MODEL = $Matches[1]
        }
    }
}

$workDir = Join-Path $projectRoot "lightrag-data"
New-Item -ItemType Directory -Force $workDir | Out-Null

Write-Host "Starting LightRAG Server on http://127.0.0.1:9621 ..."
Write-Host "Source: $lightRagRoot"
Write-Host "Log: $workDir\server.log"
Write-Host "Press Ctrl+C to stop."

& $pythonExe -m lightrag.api.lightrag_server `
    --host 127.0.0.1 --port 9621 `
    --working-dir $workDir `
    *>> "$workDir\server.log"

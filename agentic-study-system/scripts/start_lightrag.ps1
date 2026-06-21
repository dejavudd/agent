# 启动 LightRAG Server（云雾AI + 本地 Ollama embedding）
# 依赖：pip install lightrag-hku[api]  &&  ollama pull nomic-embed-text

$env:PYTHONIOENCODING       = "utf-8"
$env:LLM_BINDING            = "openai"
$env:LLM_MODEL              = "gpt-5.4-mini"
$env:LLM_BINDING_HOST       = "https://yunwu.ai/v1"
$env:EMBEDDING_BINDING      = "ollama"
$env:EMBEDDING_MODEL        = "nomic-embed-text"
$env:EMBEDDING_BINDING_HOST = "http://localhost:11434"
$env:EMBEDDING_DIM          = "768"   # nomic-embed-text 输出维度，必须与模型一致

# 从 .env 读取 API key（不硬编码到脚本里）
if (Test-Path (Join-Path $PSScriptRoot "..\.env")) {
    Get-Content (Join-Path $PSScriptRoot "..\.env") | ForEach-Object {
        if ($_ -match "^LIGHTRAG_LLM_API_KEY=(.+)$") {
            $env:LLM_BINDING_API_KEY = $Matches[1]
        }
    }
}

$workDir = "D:\lightrag-data"
New-Item -ItemType Directory -Force $workDir | Out-Null

Write-Host "Starting LightRAG Server on http://127.0.0.1:9621 ..."
Write-Host "Log: $workDir\server.log"
Write-Host "Press Ctrl+C to stop."

& "D:\Conda\envs\agent\python.exe" -m lightrag.api.lightrag_server `
    --host 127.0.0.1 --port 9621 `
    --working-dir $workDir `
    *>> "$workDir\server.log"

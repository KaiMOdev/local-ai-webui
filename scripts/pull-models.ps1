<#
.SYNOPSIS
  Pullt de aanbevolen Ollama-modellen voor deze stack.

.DESCRIPTION
  Kiest een chat-model op basis van je VRAM (of gebruik -Model om te overschrijven)
  en pullt altijd het embedding-model 'nomic-embed-text' voor RAG.

.PARAMETER Tier
  16gb | 8gb | cpu  -> bepaalt het standaard chat-model. Standaard: 8gb.

.PARAMETER Model
  Overschrijf het chat-model expliciet, bv. -Model "llama3.1:8b".

.EXAMPLE
  .\scripts\pull-models.ps1 -Tier 16gb
  .\scripts\pull-models.ps1 -Model "qwen2.5:14b-instruct"
#>
param(
  [ValidateSet("16gb", "8gb", "cpu")]
  [string]$Tier = "8gb",
  [string]$Model = ""
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  Write-Host "Ollama is niet gevonden. Installeer het via https://ollama.com/download" -ForegroundColor Red
  exit 1
}

if (-not $Model) {
  $Model = switch ($Tier) {
    "16gb" { "qwen2.5:14b-instruct" }
    "8gb"  { "qwen2.5:7b-instruct" }
    "cpu"  { "qwen2.5:3b-instruct" }
  }
}

$embed = "nomic-embed-text"

Write-Host "Chat-model     : $Model"     -ForegroundColor Cyan
Write-Host "Embedding-model: $embed"      -ForegroundColor Cyan
Write-Host ""

foreach ($m in @($Model, $embed)) {
  Write-Host "==> ollama pull $m" -ForegroundColor Yellow
  ollama pull $m
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Pull mislukt voor $m" -ForegroundColor Red
    exit 1
  }
}

Write-Host ""
Write-Host "Klaar. Zet in Open WebUI het chat-model op '$Model' en bij Admin > Settings >" -ForegroundColor Green
Write-Host "Documents het embedding-model op '$embed' (engine: Ollama)." -ForegroundColor Green

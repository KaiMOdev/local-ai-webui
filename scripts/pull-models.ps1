<#
.SYNOPSIS
  Pullt de aanbevolen Ollama-modellen voor deze stack.

.DESCRIPTION
  Kiest een chat-model op basis van je VRAM (of gebruik -Model om te overschrijven)
  en pullt altijd het embedding-model 'nomic-embed-text' voor RAG.

.PARAMETER Tier
  auto | 16gb | 8gb | cpu  -> bepaalt het chat-model. Standaard 'auto':
  detecteert de NVIDIA-GPU (via nvidia-smi) en kiest het tier op VRAM
  (>=15 GB -> 16gb, >=7.5 GB -> 8gb, anders cpu); geen NVIDIA-GPU -> cpu.
  Geef expliciet een tier om de detectie over te slaan.

.PARAMETER Model
  Overschrijf het chat-model expliciet, bv. -Model "llama3.1:8b".

.EXAMPLE
  .\scripts\pull-models.ps1 -Tier 16gb
  .\scripts\pull-models.ps1 -Model "qwen2.5:14b-instruct"
#>
param(
  [ValidateSet("auto", "16gb", "8gb", "cpu")]
  [string]$Tier = "auto",
  [string]$Model = ""
)

$ErrorActionPreference = "Stop"

function Get-TierForVramMiB {
  param([int]$VramMiB)
  if ($VramMiB -ge 15360) { return "16gb" }  # >= 15 GB
  if ($VramMiB -ge 7680)  { return "8gb" }   # >= 7.5 GB
  return "cpu"
}

function Get-NvidiaVram {
  # Geeft @{ MiB = <int>; Name = <string> } voor de grootste NVIDIA-GPU,
  # of $null als nvidia-smi ontbreekt of niets bruikbaars teruggeeft.
  if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) { return $null }
  try {
    $lines = & nvidia-smi --query-gpu=memory.total,name --format=csv,noheader,nounits 2>$null
  } catch {
    return $null
  }
  if ($LASTEXITCODE -ne 0 -or -not $lines) { return $null }

  $best = $null
  foreach ($line in $lines) {
    $parts = $line -split ",", 2
    if ($parts.Count -lt 2) { continue }
    $mib = 0
    if (-not [int]::TryParse($parts[0].Trim(), [ref]$mib)) { continue }
    if (-not $best -or $mib -gt $best.MiB) {
      $best = @{ MiB = $mib; Name = $parts[1].Trim() }
    }
  }
  return $best
}

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  Write-Host "Ollama is niet gevonden. Installeer het via https://ollama.com/download" -ForegroundColor Red
  exit 1
}

if (-not $Model) {
  if ($Tier -eq "auto") {
    $gpu = Get-NvidiaVram
    if ($gpu) {
      $Tier = Get-TierForVramMiB -VramMiB $gpu.MiB
      $vramGb = [math]::Round($gpu.MiB / 1024)
      Write-Host ("Gedetecteerde GPU: {0} ({1} GB) -> tier {2}" -f $gpu.Name, $vramGb, $Tier) -ForegroundColor Cyan
    } else {
      $Tier = "cpu"
      Write-Host "Geen NVIDIA-GPU gevonden -> tier cpu" -ForegroundColor Yellow
    }
  }
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

<#
.SYNOPSIS
  Controleert of alle onderdelen van de stack draaien.

.DESCRIPTION
  Checkt: Ollama (native host), Open WebUI (Docker) en SearXNG (Docker, via JSON-zoekopdracht).

.EXAMPLE
  .\scripts\healthcheck.ps1
#>
param(
  [int]$WebUiPort = 3000,
  [string]$OllamaUrl = "http://localhost:11434"
)

function Test-Endpoint {
  param([string]$Name, [string]$Url, [scriptblock]$Check)
  try {
    $result = & $Check
    if ($result) {
      Write-Host ("[OK]   {0,-12} {1}" -f $Name, $Url) -ForegroundColor Green
    } else {
      Write-Host ("[FAIL] {0,-12} {1}" -f $Name, $Url) -ForegroundColor Red
    }
  } catch {
    Write-Host ("[FAIL] {0,-12} {1}  ({2})" -f $Name, $Url, $_.Exception.Message) -ForegroundColor Red
  }
}

Write-Host "Stack health check" -ForegroundColor Cyan
Write-Host "==================" -ForegroundColor Cyan

# 1) Ollama (native op de host)
Test-Endpoint -Name "Ollama" -Url "$OllamaUrl/api/tags" -Check {
  $r = Invoke-RestMethod -Uri "$OllamaUrl/api/tags" -TimeoutSec 5
  $models = ($r.models | ForEach-Object { $_.name }) -join ", "
  Write-Host "       modellen: $models" -ForegroundColor DarkGray
  $true
}

# 2) Open WebUI (Docker)
Test-Endpoint -Name "Open WebUI" -Url "http://localhost:$WebUiPort/health" -Check {
  $r = Invoke-WebRequest -Uri "http://localhost:$WebUiPort/health" -TimeoutSec 5 -UseBasicParsing
  $r.StatusCode -eq 200
}

# 3) SearXNG (via Open WebUI's container-netwerk testen we hier vanaf de host;
#    standaard is searxng niet naar de host geëxposeerd. We checken daarom of de
#    container draait. Exposeer poort 8888 in docker-compose.yml om dit direct te testen.)
Test-Endpoint -Name "SearXNG" -Url "docker ps" -Check {
  $running = docker ps --filter "name=searxng" --filter "status=running" --format "{{.Names}}"
  if ($running) { Write-Host "       container: $running" -ForegroundColor DarkGray; $true } else { $false }
}

Write-Host ""
Write-Host "Tip: open http://localhost:$WebUiPort in je browser voor de UI." -ForegroundColor DarkGray

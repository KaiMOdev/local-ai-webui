# CLAUDE.md — local-ai-webui

Projectgids voor Claude Code. Kort houden; alleen wat niet uit de code zelf blijkt.

## Wat dit is
Een lokale AI-assistent **bovenop [Open WebUI](https://openwebui.com)** met **Ollama**
als inference-engine, plus **RAG, tool calling, skills/agents en web search** (SearXNG).
Dit is geen from-scratch app: we leveren een Docker-stack + **Python-extensies** die je
in Open WebUI importeert.

## Architectuur (in één blik)
- **Ollama** draait *native* op de Windows-host (beste GPU-support) — niet in Docker.
- **Open WebUI** + **SearXNG** draaien in Docker (`docker-compose.yml`).
- Onze uitbreidingen staan in `extensions/` en zijn de **bron-van-waarheid** in git;
  Open WebUI bewaart geïmporteerde kopieën in zijn eigen DB (volume `open-webui`).

## Mapindeling
- `extensions/tools/` — Open WebUI **Tools** (`Tools`-class, getypte methodes → function calling).
- `extensions/functions/` — **Functions**: `Pipe` (skill/agent), `Filter` (pre/post-processing).
- `searxng/` — SearXNG-config (JSON-output aan, limiter uit).
- `scripts/` — PowerShell-helpers (`pull-models.ps1`, `healthcheck.ps1`).
- `tests/` — offline unit-tests (alleen netwerkloze logica, bv. de calculator).

## Conventies voor extensies
- **Tool** = class `Tools` met `Valves`/`UserValves` (pydantic) voor config; elke
  publieke methode heeft type-hints + een duidelijke docstring (die wordt aan het model gegeven).
- **Function** = class `Pipe`, `Filter` of `Action`; eerste match bepaalt het type.
- Bovenaan elk bestand een docstring-header met `title/author/version/license/requirements`.
- Externe pip-packages: zet ze in de `requirements:`-regel van de header (Open WebUI installeert ze).
- **Security**: valideer externe input. Voorbeeld: `web_fetch.py` gebruikt `_is_public_url()`
  als SSRF-guard; de calculator gebruikt een AST-evaluator (nooit `eval()`).
- Bewerk je een extensie in de Open WebUI-UI? Kopieer de wijziging terug naar `extensions/`
  zodat git de bron-van-waarheid blijft.

## Belangrijk bij gebruik
- Tools worden pas aangeroepen als het model op **Function Calling = Native** staat
  (Workspace → Models → Advanced) én een tool-capable model gebruikt (bv. `qwen2.5:*`).

## Checks vóór commit
```bash
ruff check .
python -m py_compile extensions/tools/*.py extensions/functions/*.py
pytest
docker compose config --quiet
```
CI (`.github/workflows/ci.yml`) draait deze ook; CodeQL scant wekelijks op security.

## Herkomst
Tooling (ruff/CI/CodeQL/dependabot-patroon) en de security-aanpak zijn overgenomen uit
het MIT-gelicentieerde **LocalChat**-project. De architecturen verschillen (LocalChat is
een eigen FastAPI-app), dus we hebben patronen overgenomen, geen modules.

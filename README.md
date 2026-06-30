# Lokale AI WebUI — Open WebUI + Ollama

Een zelf-gehoste, privacy-vriendelijke AI-assistent die volledig lokaal draait.
Gebouwd op **[Open WebUI](https://openwebui.com)** met **[Ollama](https://ollama.com)**
als inference-engine, plus **RAG (documenten)**, **tool calling**, **skills/agents**
en **web search** via SearXNG.

```
Browser ─▶ Open WebUI (Docker) ─▶ Ollama (native, GPU)   ← chat + embeddings
                     └──────────▶ SearXNG (Docker)        ← web search
```

## Onderdelen

| Onderdeel | Waar | Taak |
|---|---|---|
| **Ollama** | native Windows-app | Draait de modellen (chat + embeddings). Beste GPU-support. |
| **Open WebUI** | Docker (`:3000`) | UI, chat, RAG/Knowledge, tool-loop, Functions/Pipes. |
| **SearXNG** | Docker (intern) | Privacy-vriendelijke web search, geen API-keys. |
| **`extensions/`** | git | Eigen Tools, een Pipe-skill en een Filter (zie `extensions/README.md`). |

---

## 1. Vereisten

- **Docker Desktop** (met WSL 2 backend) — https://www.docker.com/products/docker-desktop
- **Ollama** voor Windows — https://ollama.com/download
  (installeer en laat draaien; een NVIDIA-GPU wordt automatisch gebruikt)

## 2. Setup

```powershell
# 1. Config klaarzetten
Copy-Item .env.example .env
# open .env en zet een eigen WEBUI_SECRET_KEY (en evt. searxng secret in searxng/settings.yml)

# 2. Modellen pullen (detecteert je NVIDIA-GPU automatisch; override met -Tier of -Model)
.\scripts\pull-models.ps1
# of forceer een tier: .\scripts\pull-models.ps1 -Tier 16gb | 8gb | cpu

# 3. Stack starten
docker compose up -d

# 4. Health check
.\scripts\healthcheck.ps1
```

Open daarna **http://localhost:3000** en maak het eerste account aan (dat wordt admin).

### Modelkeuze (kies op je VRAM)

| Hardware | Chat-model (sterke tool-calling) | Embeddings |
|---|---|---|
| GPU 16 GB+ | `qwen2.5:14b-instruct` | `nomic-embed-text` |
| GPU 8–12 GB | `qwen2.5:7b-instruct` (of `llama3.1:8b`) | `nomic-embed-text` |
| CPU / zwakke GPU | `qwen2.5:3b-instruct` (of `llama3.2:3b`) | `nomic-embed-text` |

> `qwen2.5` is gekozen om sterke, betrouwbare **function calling**. Het script kiest
> standaard automatisch een tier op basis van je NVIDIA-VRAM (geen GPU -> `cpu`).
> Overschrijf desgewenst met `-Tier 16gb|8gb|cpu` of `-Model "..."`.  

---

## 3. Features configureren

### RAG (documenten)
1. **Admin Panel → Settings → Documents**: Embedding Engine = **Ollama**, model = `nomic-embed-text`.
   Zet **Hybrid Search** aan en (optioneel) Reranking-model `BAAI/bge-reranker-v2-m3`.
2. **Workspace → Knowledge → +**: maak een collectie en upload documenten/PDF's.
3. In de chat: typ `#` en kies je collectie, of koppel de collectie aan een model.
   Antwoorden bevatten dan bronverwijzingen.

### Web search (SearXNG)
- Staat al aangezet via `docker-compose.yml` (`ENABLE_RAG_WEB_SEARCH`, `SEARXNG_QUERY_URL`).
- Controleer in **Admin → Settings → Web Search** dat engine = `searxng`.
- In de chat: gebruik de **Web Search**-toggle (wereldbol-icoon) bij het invoerveld.

### Tools & Skills
Zie **[`extensions/README.md`](extensions/README.md)** — daar staat hoe je de meegeleverde
Tools (rekenmachine, datum/tijd, web fetch, Wikipedia), de **Research Agent** (Pipe) en de
**Prompt Enhancer** (Filter) importeert. Belangrijk: zet bij een model
**Advanced Params → Function Calling = Native** zodat tools daadwerkelijk worden aangeroepen.

---

## 4. Verificatie (end-to-end)

| Test | Verwacht |
|---|---|
| `docker compose ps` + `.\scripts\healthcheck.ps1` | Ollama, Open WebUI en SearXNG draaien |
| Chat: een gewone vraag | Streaming antwoord van het lokale model |
| RAG: vraag die alleen uit je document te beantwoorden is | Antwoord **met bron** |
| Web search aan: vraag over actueel nieuws | Antwoord **citeert URL's** |
| Tools (Native aan): "Hoeveel is 17,3% van 4230 en hoe laat is het in Tokyo?" | Tool-calls zichtbaar, correct antwoord |
| Model "Research Agent" kiezen + onderzoeksvraag | Meerstaps-antwoord met bronnenlijst |

---

## 5. Beheer

```powershell
docker compose logs -f open-webui     # logs volgen
docker compose pull; docker compose up -d   # Open WebUI / SearXNG updaten
docker compose down                   # stoppen (data blijft in 'open-webui' volume)
docker compose down -v                # ALLES wissen incl. data-volume
```

## Alternatief: alles in Docker (Ollama als container)

De standaard draait Ollama native voor de beste GPU-betrouwbaarheid op Windows.
Wil je Ollama tóch containeriseren, voeg dan een service toe en wijs Open WebUI ernaar:

```yaml
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    volumes: ["ollama:/root/.ollama"]
    # GPU (vereist NVIDIA Container Toolkit in WSL2):
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: ["gpu"]
    restart: unless-stopped
# en in volumes: ollama:
```

Zet dan in `.env`: `OLLAMA_BASE_URL=http://ollama:11434`.

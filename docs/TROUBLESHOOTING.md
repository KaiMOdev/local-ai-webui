# Troubleshooting

Veelvoorkomende problemen bij deze stack (Open WebUI + SearXNG in Docker, Ollama
native op de Windows-host). Per item: **Symptoom → Check → Oplossing**.

---

### "No models found" in Workspace → Models

**Symptoom:** `http://localhost:3000/workspace/models` toont geen modellen, terwijl
je modellen hebt gepulld.

**Check:**
```powershell
docker exec open-webui sh -c "curl -s -m 5 http://host.docker.internal:11434/api/tags"
```

**Oplossing:**
1. **Workspace → Models** toont alleen je *eigen custom model-presets* — niet de
   ruwe Ollama-modellen. Dat het leeg is, is normaal tot je er zelf één maakt (＋).
2. Je gepullde modellen verschijnen in de **model-dropdown bovenaan een nieuwe chat**
   en in **Admin Panel → Settings → Models**. Kijk daar.
3. Geeft de check hierboven wél de modellen terug maar de chat-dropdown niet? Herlaad
   de pagina; check anders **Admin → Settings → Connections** (Ollama-verbinding).

---

### Open WebUI kan Ollama niet bereiken

**Symptoom:** geen enkel model zichtbaar, of fouten bij chatten/embeddings.

**Check:**
```powershell
docker exec open-webui sh -c "curl -s -m 5 http://host.docker.internal:11434/api/tags || echo UNREACHABLE"
```

**Oplossing:**
1. `docker-compose.yml` moet `extra_hosts: ["host.docker.internal:host-gateway"]`
   hebben en `OLLAMA_BASE_URL=http://host.docker.internal:11434` (standaard al zo).
2. Bereikt de container Ollama niet, maar de host wel (`Invoke-RestMethod
   http://localhost:11434/api/tags`)? Laat Ollama op alle interfaces luisteren:
   zet systeemvariabele `OLLAMA_HOST=0.0.0.0` en herstart Ollama.
3. Controleer dat Ollama draait: `.\scripts\healthcheck.ps1`.

---

### SearXNG geeft geen zoekresultaten

**Symptoom:** Web Search aan, maar antwoorden citeren geen URL's / "no results".

**Check:**
```powershell
docker compose ps searxng
```

**Oplossing:**
1. SearXNG moet JSON-output aanhebben (`searxng/settings.yml`: `formats` bevat `json`)
   en de limiter uit. Zie `searxng/`.
2. In Open WebUI: **Admin → Settings → Web Search** → engine = `searxng`,
   query-URL `http://searxng:8080/search?q=<query>&format=json`.
3. Herstart na configwijziging: `docker compose restart searxng`.

---

### Tools/functies worden niet aangeroepen

**Symptoom:** het model negeert je tools (geen tool-calls zichtbaar).

**Check:** staat het model op native tool-calling?

**Oplossing:**
1. **Workspace → Models → [model] → Advanced Params → Function Calling = Native**.
2. Gebruik een tool-capable model (bv. `qwen2.5:*` of `llama3.1`). Modellen zonder
   tool-ondersteuning roepen nooit tools aan.

---

### 500: Internal Error bij openen van de UI

**Symptoom:** browser toont "500: Internal Error" op `http://localhost:3000`.

**Check:**
```powershell
docker compose logs --tail=50 open-webui
```

**Oplossing:**
1. Meestal is de container nog aan het opstarten — **herlaad de pagina** na een paar
   seconden. `docker compose ps` moet `Up (healthy)` tonen.
2. Blijft het: check de logs op een traceback en herstart met
   `docker compose restart open-webui`.

---

### Waarschuwing: InsecureKeyLengthWarning (HMAC key < 32 bytes)

**Symptoom:** in de logs: `InsecureKeyLengthWarning: The HMAC key is N bytes long`.

**Oplossing:** zet in `.env` een `WEBUI_SECRET_KEY` van **minstens 32 bytes** en
herstart: `docker compose up -d`. Onschuldig voor lokaal gebruik, maar netjes om op te lossen.

---

### Een extensie laadt niet in Open WebUI

**Symptoom:** een geïmporteerde Tool/Function verschijnt niet of geeft een fout.

**Check:** `docker compose logs --tail=80 open-webui` op een import-/`ModuleNotFoundError`.

**Oplossing:**
1. Externe pip-packages moeten in de `requirements:`-regel van de docstring-header
   staan (Open WebUI installeert die bij import).
2. Controleer de class-naam: een Tool is class `Tools`; een Function is `Pipe`,
   `Filter` of `Action`. De eerste match bepaalt het type.
3. Lokaal syntaxcheck: `python -m py_compile extensions/tools/<bestand>.py`.

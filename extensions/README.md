# Extensions — Tools, Skills & Filters

Deze map bevat de **broncode** van onze Open WebUI-uitbreidingen, in git als
bron-van-waarheid. Open WebUI bewaart geïmporteerde extensies in zijn eigen
database (binnen het `open-webui` Docker-volume), dus we beheren de `.py`-bestanden
hier en **importeren** ze via de Workspace-UI.

## Wat zit erin?

### `tools/` — Open WebUI **Tools** (function calling)
Elke methode met type-hints + docstring wordt een functie die het model kan aanroepen.

| Bestand | Functies | Doel |
|---|---|---|
| `utilities.py` | `calculator`, `current_datetime`, `convert_units` | Veilig rekenen, tijdzone-bewuste tijd, eenheden-conversie (geen externe deps). |
| `web_fetch.py` | `fetch_url` | Eén concrete URL ophalen en als leesbare tekst teruggeven. |
| `wikipedia.py` | `search_wikipedia`, `get_summary` | Wikipedia doorzoeken en samenvattingen ophalen. |

### `functions/` — Open WebUI **Functions**
| Bestand | Type | Doel |
|---|---|---|
| `research_agent.py` | **Pipe** | Verschijnt als eigen "model" *Research Agent*: web search → bronnen verzamelen → onderbouwd antwoord met `[n]`-verwijzingen. |
| `prompt_enhancer.py` | **Filter** | Injecteert huidige datum/tijd als context (lost "model kent de datum niet" op) + lichte normalisatie. Heeft een per-chat toggle. |

## Importeren in Open WebUI

> Je moet ingelogd zijn als **admin** (het eerste account).

### Tools
1. **Workspace → Tools → `+` (Create New Tool)**.
2. Open het `.py`-bestand uit `tools/`, kopieer de **volledige inhoud** in de editor.
3. Naam/beschrijving worden uit de docstring-header gehaald. Klik **Save**.
4. Herhaal voor elk bestand in `tools/`.

### Functions (Pipe & Filter)
1. **Workspace → Functions → `+` (Create New Function)**.
2. Plak de inhoud van `research_agent.py` → **Save**. Er verschijnt nu een model
   **Research Agent** in de modelkiezer.
3. Plak de inhoud van `prompt_enhancer.py` → **Save**, en **enable** de filter.
   (Een Filter werkt globaal of per model; zet hem aan waar je hem wilt.)

## Tools koppelen aan een model + Native calling aanzetten

Tools worden pas aangeroepen als (a) ze aan het model/de chat hangen en (b) het model
in **Native** function-calling-modus staat:

1. **Workspace → Models** → kies/maak een model op basis van je Ollama-chatmodel.
2. Onder **Tools**: vink `utilities`, `web_fetch`, `wikipedia` aan.
3. **Advanced Params → Function Calling → `Native`** (Default werkt minder betrouwbaar).
4. Gebruik een model dat function calling goed ondersteunt (bv. `qwen2.5:*`, `llama3.1:8b`).

## Aanpassen / uitbreiden

- **Valves** (admin-instelbaar) en **UserValves** (per gebruiker) verschijnen als velden in
  de UI — handig voor API-keys, taal, time-outs. Zie de `Valves`-classes in de bestanden.
- Een nieuwe tool toevoegen = nieuw bestand in `tools/` met een `Tools`-class en getypte,
  gedocumenteerde methodes; daarna importeren zoals hierboven.
- Houd na het bewerken in de UI de wijziging in sync met dit bestand (kopieer terug naar
  git), zodat de repo de bron-van-waarheid blijft.

## Referenties
- Tools: https://docs.openwebui.com/features/extensibility/plugin/tools/
- Functions: https://docs.openwebui.com/features/extensibility/plugin/functions/
- Pipe: https://docs.openwebui.com/features/extensibility/plugin/functions/pipe/
- Filter: https://docs.openwebui.com/features/extensibility/plugin/functions/filter/

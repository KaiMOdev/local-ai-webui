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
| `web_fetch.py` | `fetch_url` | Eén concrete URL ophalen en als leesbare tekst teruggeven (met SSRF-guard). |
| `wikipedia.py` | `search_wikipedia`, `get_summary` | Wikipedia doorzoeken en samenvattingen ophalen. |
| `onedrive.py` | `search_files`, `list_recent_files`, `read_file` | Cloud-connector: OneDrive doorzoeken/lezen via Microsoft Graph (zie hieronder). |

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

## Cloud-connectors (OneDrive — Microsoft Graph)

`onedrive.py` is een cloud-connector die **on-demand** in je OneDrive zoekt en bestanden
leest (geen achtergrond-sync). Het model roept `search_files` → `read_file` aan; je krijgt
de inhoud live in de chat — effectief RAG over je cloudopslag.

### Eenmalige Azure AD-setup (admin)
1. **Azure Portal → App registrations → New registration**. Kies *single tenant* (alleen
   je organisatie) of *common* (ook persoonlijke accounts). Voeg een redirect-URI toe, bv.
   `http://localhost:53682/` (voor het token-script hieronder).
2. **API permissions → Microsoft Graph → Delegated**: `Files.Read.All`, `Sites.Read.All`,
   `offline_access`. Verleen admin-consent indien vereist.
3. **Certificates & secrets → New client secret** → noteer de waarde.
4. Importeer `onedrive.py` als Tool en vul in de **Valves** (admin): `tenant_id`,
   `client_id`, `client_secret`.

### Per gebruiker: refresh_token ophalen
Elke gebruiker koppelt zijn eigen account door eenmalig een **refresh token** te halen en in
zijn **UserValves** te zetten. Snelste manier — een kort lokaal scriptje met de auth-code flow:

```python
# get_ms_refresh_token.py  — eenmalig draaien:  python get_ms_refresh_token.py
import http.server, urllib.parse, webbrowser, requests

TENANT = "common"          # of je tenant-id
CLIENT_ID = "<client_id>"
CLIENT_SECRET = "<client_secret>"
REDIRECT = "http://localhost:53682/"
SCOPE = "Files.Read.All Sites.Read.All offline_access"
AUTH = f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/authorize"
TOKEN = f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token"

webbrowser.open(f"{AUTH}?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT}"
                f"&response_mode=query&scope={urllib.parse.quote(SCOPE)}")

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        code = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("code", [None])[0]
        r = requests.post(TOKEN, data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT, "scope": SCOPE})
        print("\nREFRESH TOKEN:\n", r.json().get("refresh_token"))
        self.send_response(200); self.end_headers(); self.wfile.write(b"Klaar - terug naar de terminal.")
http.server.HTTPServer(("localhost", 53682), H).handle_request()
```

Plak de geprinte `refresh_token` in **Workspace → Tools → onedrive → (jouw) UserValves**.
Koppel de tool aan een model met **Function Calling = Native** en vraag bv.
*"zoek mijn offerte in OneDrive en vat hem samen"*.

### Andere connectors toevoegen (zelfde patroon)
`onedrive.py` is bewust het **basis-patroon**: `Valves` (gedeelde app-registratie) +
`UserValves` (per-gebruiker token) + de helpers `_get_access_token` / `_graph_get` /
`_extract_text`. Voor **SharePoint** wijzig je de endpoints naar `/sites/{site-id}/drive/...`
(of gebruik client-credentials i.p.v. een refresh token voor org-brede toegang); voor
**Google Drive** vervang je token-URL/scope en endpoints door de Drive API v3 (met
`export` voor Google Docs/Sheets). De rest van de structuur blijft gelijk.

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

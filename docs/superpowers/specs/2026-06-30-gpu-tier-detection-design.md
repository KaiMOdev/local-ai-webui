# GPU-tier auto-detectie in `pull-models.ps1`

**Datum:** 2026-06-30
**Status:** Goedgekeurd ontwerp (klaar voor implementatieplan)

## Probleem

`scripts/pull-models.ps1` vereist dat de gebruiker zelf de juiste `-Tier`
(`16gb` | `8gb` | `cpu`) kiest op basis van hun VRAM. Wie hun VRAM niet kent,
moet gokken of de README-tabel raadplegen. We willen dat het script de NVIDIA-GPU
detecteert en automatisch het best passende model kiest.

## Doel

- Bij uitvoeren **zonder** `-Tier` detecteert het script de VRAM van de
  (grootste) NVIDIA-GPU en kiest het bijbehorende model-tier automatisch.
- Volledig backward-compatible: bestaande aanroepen met expliciete `-Tier` of
  `-Model` blijven ongewijzigd werken.

## Niet-doelen (YAGNI)

- Geen los `scripts/gpu-check.ps1`; detectie leeft in `pull-models.ps1`.
- Geen AMD/Intel VRAM-detectie (op Windows onbetrouwbaar; project is NVIDIA-first).
- Geen `-DryRun`/preview-vlag.
- Embedding-model blijft vast `nomic-embed-text`.

## Ontwerp

### 1. Trigger & precedence (backward-compatible)

`-Tier` krijgt een extra waarde `auto`, die de nieuwe standaard wordt:

```powershell
param(
  [ValidateSet("auto", "16gb", "8gb", "cpu")]
  [string]$Tier = "auto",
  [string]$Model = ""
)
```

Voorrangsvolgorde voor de modelkeuze:

1. `-Model "..."` expliciet → wint altijd (detectie wordt overgeslagen voor de
   modelkeuze; de gedetecteerde VRAM mag wel ter info getoond worden).
2. `-Tier 16gb|8gb|cpu` expliciet → forceert dat tier.
3. `-Tier auto` (standaard) → `Get-RecommendedTier` bepaalt het tier.

### 2. Detectiefunctie `Get-RecommendedTier`

In-script functie die een tier-string (`16gb` | `8gb` | `cpu`) teruggeeft.

- Roept aan: `nvidia-smi --query-gpu=memory.total,name --format=csv,noheader,nounits`.
- `memory.total` is in **MiB**; pak per regel de waarde, neem de **grootste**
  GPU (Ollama laadt een model op één device).
- Faalt `nvidia-smi` (niet gevonden, non-zero exit, of lege/onparseerbare
  output) → tier = `cpu` (geen exception laten ontsnappen).
- Geeft naast het tier ook genoeg info terug voor de UX-regel (GPU-naam +
  VRAM in GB), bv. via een klein object of out-params.

### 3. VRAM → tier drempels

Tolerant voor gerapporteerd-vs-nominaal (een "16 GB"-kaart rapporteert ~16376 MiB,
een "8 GB"-kaart vaak < 8192 MiB door reservering). Reken in GB = `MiB / 1024`:

| Grootste GPU VRAM | Tier  | Model                  |
|-------------------|-------|------------------------|
| ≥ 15 GB           | `16gb`| `qwen2.5:14b-instruct` |
| ≥ 7.5 GB          | `8gb` | `qwen2.5:7b-instruct`  |
| < 7.5 GB of geen NVIDIA-GPU | `cpu` | `qwen2.5:3b-instruct` |

### 4. UX (Nederlands, in lijn met bestaande output)

Eén informatieve regel vóór het pullen:

- Met GPU:
  `Gedetecteerde GPU: NVIDIA GeForce RTX 4080 (16 GB) -> tier 16gb -> qwen2.5:14b-instruct`
- Fallback:
  `Geen NVIDIA-GPU gevonden -> tier cpu (qwen2.5:3b-instruct).`
- Bij expliciete `-Tier`/`-Model` wordt detectie overgeslagen en blijft de
  huidige output gelden (geen detectie-regel, of alleen ter info).

Kleur/stijl volgt de bestaande `Write-Host`-conventies in het script.

### 5. Documentatie

`README.md` (sectie 2 "Setup", modelkeuze-tabel/tekst): noteren dat
`pull-models.ps1` zonder `-Tier` het tier nu **automatisch** detecteert; `-Tier`
en `-Model` blijven beschikbaar als override. De script-header (`.PARAMETER Tier`)
wordt bijgewerkt met de `auto`-waarde.

## Edge cases

- **Meerdere GPU's**: kies de grootste VRAM-waarde.
- **`nvidia-smi` aanwezig maar GPU in vreemde staat** (lege/`[N/A]`-output):
  behandel als niet-parseerbaar → `cpu`-fallback.
- **`-Model` zonder geldig `-Tier`**: `-Model` wint; geen detectie nodig voor keuze.
- **Laptop met dGPU uit / alleen iGPU**: `nvidia-smi` ontbreekt of faalt → `cpu`.
- Detectie mag het script **nooit** laten crashen; elke fout valt terug op `cpu`.

## Verificatie

PowerShell-scripts vallen buiten de `pytest`-suite, dus verificatie is handmatig:

1. Machine met NVIDIA-GPU: `./scripts/pull-models.ps1` (geen args) toont de juiste
   gedetecteerde GPU/tier/model-regel.
2. Geen-GPU-pad simuleren (bv. `nvidia-smi` tijdelijk niet op PATH) → `cpu`-fallback.
3. Override-paden: `-Tier 16gb` en `-Model "..."` gedragen zich als voorheen.

Geen nieuwe PowerShell-testharnas toevoegen.

## Out of scope

Los GPU-check-commando, niet-NVIDIA-detectie, preview-vlag, wijzigingen aan het
embedding-model of aan `healthcheck.ps1`.

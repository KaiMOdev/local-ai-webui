# GPU-tier Auto-Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `scripts/pull-models.ps1` auto-detect NVIDIA VRAM and pick the best `qwen2.5` model tier when run without `-Tier`, while keeping explicit `-Tier`/`-Model` overrides working.

**Architecture:** Add a `auto` value to `-Tier` (new default). Two small in-script helpers do the work: `Get-TierForVramMiB` (pure VRAM→tier mapping) and `Get-NvidiaVram` (I/O: read VRAM via `nvidia-smi`). The model-selection block calls them only when `-Model` is empty and `-Tier` is `auto`; any failure falls back to the `cpu` tier.

**Tech Stack:** Windows PowerShell 5.1 / PowerShell 7, `nvidia-smi`, Ollama.

## Global Constraints

- Language of all user-facing strings and comments: **Dutch** (match existing script/codebase).
- **Backward-compatible:** existing `-Tier 16gb|8gb|cpu` and `-Model "..."` calls must behave exactly as before.
- NVIDIA-only detection via `nvidia-smi`. No AMD/Intel reading. No separate `gpu-check.ps1`. No `-DryRun`. Embedding model stays `nomic-embed-text`.
- Detection must **never** throw out of the script; every failure path returns the `cpu` tier.
- VRAM→tier thresholds (compute GB as `MiB / 1024`): **≥ 15 GB → `16gb`**, **≥ 7.5 GB → `8gb`**, **otherwise → `cpu`**. As MiB: `≥ 15360 → 16gb`, `≥ 7680 → 8gb`, else `cpu`.
- Model map (unchanged): `16gb → qwen2.5:14b-instruct`, `8gb → qwen2.5:7b-instruct`, `cpu → qwen2.5:3b-instruct`.
- **No new automated test harness** (no Pester). Verification is the deterministic mapping check + manual runs shown in each task.

---

### Task 1: GPU detection + auto-tier selection in `pull-models.ps1`

**Files:**
- Modify: `scripts/pull-models.ps1` (header `.PARAMETER Tier` at 9-10; `param` block at 19-23; model-selection block at 32-38; add two functions after line 30)

**Interfaces:**
- Produces (in-script functions):
  - `Get-TierForVramMiB([int]$VramMiB) -> [string]` returning `"16gb"`, `"8gb"`, or `"cpu"`.
  - `Get-NvidiaVram() -> [hashtable] @{ MiB = [int]; Name = [string] }` for the largest GPU, or `$null` when no NVIDIA GPU / `nvidia-smi` is unavailable.
- Consumes: nothing from other tasks.

- [ ] **Step 1: Record the target VRAM→tier mapping (the spec you code against)**

Write `Get-TierForVramMiB` in Step 3 to satisfy exactly this table; Step 5 verifies it deterministically:

```
16376 MiB -> 16gb     (16 GB card, reports just under 16384)
12288 MiB -> 8gb      (12 GB card)
 8192 MiB -> 8gb      (8 GB card)
 7000 MiB -> cpu      (~6.8 GB card, below the 7.5 GB floor)
    0 MiB -> cpu      (no GPU / detection failed)
```

- [ ] **Step 2: Update the `param` block and header docs**

Replace the `param(...)` block (lines 19-23) with:

```powershell
param(
  [ValidateSet("auto", "16gb", "8gb", "cpu")]
  [string]$Tier = "auto",
  [string]$Model = ""
)
```

Replace the `.PARAMETER Tier` lines (9-10) with:

```
.PARAMETER Tier
  auto | 16gb | 8gb | cpu  -> bepaalt het chat-model. Standaard 'auto':
  detecteert de NVIDIA-GPU (via nvidia-smi) en kiest het tier op VRAM
  (>=15 GB -> 16gb, >=7.5 GB -> 8gb, anders cpu); geen NVIDIA-GPU -> cpu.
  Geef expliciet een tier om de detectie over te slaan.
```

- [ ] **Step 3: Add the two helper functions**

Insert immediately after the `$ErrorActionPreference = "Stop"` line (currently line 25), before the `ollama` presence check:

```powershell
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
```

- [ ] **Step 4: Wire detection into the model-selection block**

Replace the existing block (lines 32-38):

```powershell
if (-not $Model) {
  $Model = switch ($Tier) {
    "16gb" { "qwen2.5:14b-instruct" }
    "8gb"  { "qwen2.5:7b-instruct" }
    "cpu"  { "qwen2.5:3b-instruct" }
  }
}
```

with:

```powershell
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
```

- [ ] **Step 5: Verify the pure mapping deterministically (no GPU needed)**

Run:

```powershell
pwsh -NoProfile -Command ". { $(Get-Content -Raw ./scripts/pull-models.ps1) } 2>$null; foreach($v in 16376,12288,8192,7000,0){ '{0,6} -> {1}' -f $v, (Get-TierForVramMiB -VramMiB $v) }"
```

If dot-sourcing tries to execute the body (it will, and may hit the `ollama` check or a pull), use this self-contained fallback that mirrors the committed function exactly:

```powershell
pwsh -NoProfile -Command "function Get-TierForVramMiB { param([int]`$VramMiB) if (`$VramMiB -ge 15360){return '16gb'} if (`$VramMiB -ge 7680){return '8gb'} return 'cpu' }; foreach(`$v in 16376,12288,8192,7000,0){ '{0,6} -> {1}' -f `$v, (Get-TierForVramMiB -VramMiB `$v) }"
```

Expected output:

```
 16376 -> 16gb
 12288 -> 8gb
  8192 -> 8gb
  7000 -> cpu
     0 -> cpu
```

- [ ] **Step 6: Manual run on the NVIDIA machine**

Run (Ctrl-C once the pull starts if you don't want to (re)download — the detection/selection line prints first):

```powershell
pwsh -File ./scripts/pull-models.ps1
```

Expected: a Cyan line `Gedetecteerde GPU: <naam> (<N> GB) -> tier <t>` followed by `Chat-model     : qwen2.5:...` matching the table. Then confirm overrides still work:

```powershell
pwsh -File ./scripts/pull-models.ps1 -Tier 16gb   # no detection line; Chat-model: qwen2.5:14b-instruct
pwsh -File ./scripts/pull-models.ps1 -Model "llama3.1:8b"  # no detection line; Chat-model: llama3.1:8b
```

Note (honest limitation): the no-GPU `cpu` fallback path is covered by the `Get-Command nvidia-smi` guard and code review; cleanly simulating it on a machine that has both `nvidia-smi` and `ollama` on PATH is impractical, so it is verified by reasoning rather than a runtime command.

- [ ] **Step 7: Commit**

```powershell
git add scripts/pull-models.ps1
git commit -m "feat: auto-detect NVIDIA VRAM and pick model tier in pull-models.ps1"
```

---

### Task 2: Document auto-detection in `README.md`

**Files:**
- Modify: `README.md` (setup step 2 at lines 37-38; model-choice note at lines 57-58)

**Interfaces:**
- Consumes: the `auto` default behaviour from Task 1.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Update setup step 2**

Replace lines 37-38:

```
# 2. Modellen pullen (kies tier op je VRAM: 16gb | 8gb | cpu)
.\scripts\pull-models.ps1 -Tier 8gb
```

with:

```
# 2. Modellen pullen (detecteert je NVIDIA-GPU automatisch; override met -Tier of -Model)
.\scripts\pull-models.ps1
# of forceer een tier: .\scripts\pull-models.ps1 -Tier 16gb | 8gb | cpu
```

- [ ] **Step 2: Update the model-choice note**

Replace lines 57-58:

```
> `qwen2.5` is gekozen om sterke, betrouwbare **function calling**. Weet je je VRAM niet?
> Start met `-Tier 8gb`; werkt het traag, ga naar `cpu`; heb je een dikke GPU, naar `16gb`.
```

with:

```
> `qwen2.5` is gekozen om sterke, betrouwbare **function calling**. Het script kiest
> standaard automatisch een tier op basis van je NVIDIA-VRAM (geen GPU -> `cpu`).
> Overschrijf desgewenst met `-Tier 16gb|8gb|cpu` of `-Model "..."`.
```

- [ ] **Step 3: Verify the docs render and are consistent**

Run:

```powershell
Select-String -Path README.md -Pattern "pull-models.ps1|automatisch|-Tier" | Select-Object LineNumber, Line
```

Expected: the setup command shows the no-arg invocation, the note mentions automatic tier selection, and no stale "Start met `-Tier 8gb`" guidance remains.

- [ ] **Step 4: Commit**

```powershell
git add README.md
git commit -m "docs: document automatic GPU-tier detection in pull-models.ps1"
```

---

## Self-Review

**1. Spec coverage:**
- Trigger & precedence (auto default, -Model > -Tier > auto) → Task 1 Steps 2, 4. ✓
- `Get-RecommendedTier` detection (renamed to `Get-NvidiaVram` + `Get-TierForVramMiB`, split I/O from pure mapping for testability) → Task 1 Step 3. ✓
- Thresholds (≥15 / ≥7.5 GB) → Global Constraints + Task 1 Step 3/5. ✓
- UX Dutch line + fallback → Task 1 Step 4. ✓
- Largest-GPU / non-parseable / no-smi edge cases → `Get-NvidiaVram` loop + guards (Task 1 Step 3). ✓
- README + header docs → Task 2 + Task 1 Step 2. ✓
- Manual verification, no new harness → Task 1 Steps 5-6, Task 2 Step 3. ✓

**2. Placeholder scan:** No TBD/TODO; every code step shows complete code; verification steps give exact expected output. (Task 1 Step 1 is an intentional record-the-expected-table step, not a placeholder.) ✓

**3. Type consistency:** `Get-TierForVramMiB([int]$VramMiB)->string` and `Get-NvidiaVram()->@{MiB;Name}` are used with identical names/shape in Steps 3-5. The `$gpu.MiB` / `$gpu.Name` accesses match the hashtable keys produced. ✓

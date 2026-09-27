# Brief hackathon · Externo 1 (A): datos sintéticos y chequeo de privacidad

> Pegale esto al agente externo 1. Worktree `C:\Users\HP\Documents\n-de-1\n-de-1-frente-a`, rama `frente-a`.
> **Antes de empezar: `git merge main`**. Entrega en **menos de 5 h**; `synth.py` primero, porque desbloquea la demo.

## Contexto
Josué presenta Consejo N-de-1 hoy en una hackathon. Un experimento real tarda semanas, así que la demo muestra 5
semanas **simuladas con el código real** y reloj acelerado (`core.simulate`, lo hace Claude). Para eso hacen falta
tramos de actividad sintéticos creíbles, y vos conocés `ActivitySpan` y `outcome@1` mejor que nadie. Además, el repo
se hace público esta noche: hay que garantizar que no lleve nada privado.

## 1. `tools/capture/synth.py` (prioridad 1)
Implementá exactamente la interfaz `core.interfaces.SynthDay`:
```python
def synth_day(day: date, blocks: list[Block], profile: str, rng: random.Random,
              latency_scale: dict[str, float] | None = None) -> list[ActivitySpan]
```
- **Perfil `"tdah_mananas"`** (el único obligatorio). Por bloque, con P = `planned_start_ms`:
  - **Latencia de arranque:** lognormal con mediana de ~25 min en la mañana (antes de las 12:00) y ~8 min en la
    tarde, σ_log ≈ 0.6. Se multiplica por `latency_scale.get(block_id, 1.0)`.
    - Mañanas: ~10% de bloques sin arranque en 90 min (censurados).
    - ~5% de bloques con la compu apagada toda la ventana (`device_off`: sin tramos).
  - **Antes de arrancar:** en la mañana, ~80% de las veces la primera ventana es distracción (`WhatsApp.exe` "WhatsApp",
    o `chrome.exe` "YouTube - Google Chrome"); el resto, `explorer.exe` u otra app genérica. Alternar 1 a 4 cambios de
    ventana.
  - **Trabajo:** un tramo de ≥ 16 min que **coincida con los `work_matchers` del bloque**. Si hay un matcher de
    proceso, usar ese proceso; si es de título, un título que contenga el patrón.
  - Fuera de los bloques, actividad genérica e inactividad. De vez en cuando, una pausa (`__paused__`, título vacío,
    `idle=true`).
- **Invariantes:** en orden, sin solapes, dentro del día local, títulos genéricos (**nunca datos reales**), y la misma
  semilla da los mismos tramos.
- **Tests (`tests/sensing/test_synth.py`):**
  - determinismo;
  - sin solapes;
  - `evaluate_block` (el real) sobre esos tramos da latencias coherentes: mediana de mañana > tarde, hay censurados y
    hay `device_off`;
  - `latency_scale=0.5` reduce la mediana de forma visible;
  - los matchers del bloque cuentan como `work` con `categorize`.

## 2. `scripts/check_private.py` (prioridad 2)
Recorre los archivos versionados (`git ls-files`) y el historial (`git log -p`, opcional con `--history`). Termina
con exit 1 si encuentra:
- emails, salvo `noreply@anthropic.com` y los del autor en los metadatos de git;
- rutas `C:\Users\<usuario>\` dentro de fixtures o datos (en `docs/` se permiten, avisando);
- archivos `*.raw.jsonl`, `*.sqlite*`, `journal.jsonl`, `.env` o `data/*.lock` versionados;
- en `tests/fixtures/traces/*.jsonl`, títulos no vacíos que no estén en una lista de títulos genéricos permitidos;
- patrones de token o clave (`sk-`, `ghp_`, `token=`).

Allowlist en `scripts/check_private_allow.txt`. Correrlo sobre `main` y reportar en tu `frente-a.md`.

## Reglas
- Solo `tools/capture/`, `tests/sensing/`, `scripts/` y tu `frente-a.md`.
- No toques contratos. Si `SynthDay` no te alcanza, pedilo en `frente-a.md` y seguí.
- Commits `feat(a): ...` en `frente-a`. Avisá en `frente-a.md` apenas `synth.py` esté listo, así Claude lo mergea
  enseguida.

# Coordinación: Claude y 2 agentes externos en paralelo

| Frente | Agente | Worktree / rama | Carpetas propias (solo escribe acá) |
|---|---|---|---|
| **0: Columna** | Claude (sesión principal) | `n-de-1` / `main` | `contracts/`, `docs/` (salvo `frente-{a,b,d}.md`), `core/app.py`, `core/__main__.py`, `core/contracts.py`, `core/interfaces.py`, `core/journal/`, `core/llm/`, `core/_stub.py`, `tools/export_contracts.py`, `pyproject.toml`, `tests/integration/` |
| **C: Consejo y estadística** | Claude (sesión principal) | `n-de-1` / `main` | `core/council/`, `core/stats/`, `tests/council/`, `tests/stats/`, `data/cassettes/` |
| **A: Sensor y resultado** | Externo 1 | `n-de-1/n-de-1-frente-a` / `frente-a` | `core/sensing/`, `tools/capture/`, `tests/sensing/`, `tests/fixtures/traces/`, y en la Fase 3 solo `packaging/sidecar.spec` |
| **B1: Bloques y sorteo** | Externo 2 (ver `brief-b1.md`) | `n-de-1/n-de-1-frente-b` / `frente-b` | `core/runtime/`, `tests/runtime/` |
| **B2: Scheduler e intervenciones** | Claude (hecho, 2026-09-27) | `n-de-1` / `main` | `core/runtime/`, `tests/runtime/` |
| **D: App Electron** | Claude | `n-de-1/n-de-1-frente-d` / `frente-d` | `app/`, `packaging/` (salvo `sidecar.spec`) |

## Cambio de reparto (2026-09-26)
Quedan dos agentes externos. El externo 2 hace solo la Fase 1 de B (`brief-b1.md`): bloques, rutas y sorteo.
Claude toma D en `n-de-1-frente-d` y, después del merge de B1, el resto de B (scheduler, intervenciones,
overlay y recuperación). `brief-b.md` y `brief-d.md` quedan como especificación completa de cada frente.

## Aviso (2026-09-27): B2 ya está en `main`; la rama `frente-b2` quedó reemplazada
Dos sesiones de Claude hicieron B2 en paralelo sin saberlo. La versión de `main` (Frente 0) está completa e integrada: scheduler, rutas, recuperación y tests con ventanas reales.

De `frente-b2` se **portaron** a `main`:
- el filtro de ventanas reales (sin dueño, sin estilo de herramienta, no *cloaked*);
- la restauración verificada por PID, por el reciclaje de hwnd;
- los procesos protegidos (la propia app, el núcleo y `explorer.exe`);
- la persistencia antes de minimizar.

**No mergear `frente-b2`:** sus `interventions.py` y `overlay.py` chocan con los de `main`. Si esa sesión tiene algo más, que lo anote en `frente-d.md` y el Frente 0 lo porta. Antes de empezar un frente nuevo, confirmar en esta tabla quién lo tiene.

## Reglas
1. **Solo escribís en tus carpetas.** Si necesitás algo fuera, lo pedís en tu `frente-X.md`.
2. **Los contratos están congelados:** `core/contracts.py`, `core/interfaces.py`, las firmas de `routes.py`,
   `contracts/`, `docs/outcome-rules.md` y `docs/journal-events.md`. Para cambiar algo, anotá un pedido de contrato
   en tu `frente-X.md`. Solo el Frente 0 los aplica.
3. **Tus rutas HTTP** viven en `core/<tu_paquete>/routes.py`, con los paths, métodos y modelos ya declarados. Las
   implementás; no agregás, quitás ni renombrás. Solo `core/app.py` las monta.
4. **Otros frentes:** no importás internals de otro frente. Solo `core.contracts`, `core.interfaces`, `core.journal` y
   `core.llm`.
5. **Journal:** escribís solo con `core.journal.append_typed`, y solo los `kind` que la tabla de
   `docs/journal-events.md` te asigna.
6. **Privacidad:** los títulos de ventana, rutas y textos del usuario nunca van al journal, a logs compartidos ni a
   fixtures commiteados sin sanitizar.
7. **Sin mocks:** los tests usan fixtures reales (trazas sanitizadas, ejemplos de `contracts/examples/`, respuestas
   de LLM grabadas). Un `ActivitySource` en memoria alimentado con trazas reales es un fixture y está permitido; un
   `Mock()` que inventa comportamiento, no.
8. **Antes de escribir, volvé a listar el árbol** y hacé `git pull`/merge de `main` en tu rama: otros agentes pueden
   haber cambiado algo hace minutos.
9. **Tu `frente-X.md`** se actualiza al terminar cada tarea: estado, bloqueos, pedidos y cómo probar lo que
   entregaste.
10. **Git:** commiteás en tu rama con mensajes `feat(a): ...`, `test(b): ...`, etc. No mergeás a `main`: lo hace el
    Frente 0 en cada hito.

## Fases e hitos
| Fase | A | B | C (Claude) | D |
|---|---|---|---|---|
| 1 (unos 3 días) | Sensor, SQLite, `categorize`, `evaluate_block` con trazas reales | Store de bloques, rutas `/blocks`, sorteo y compromiso de semilla, `block_confirmed` y `assignment` | Stats (permutación, potencia, α), simulación, ledger | Electron, sidecar, bandeja, planificador |
| **Hito 1** | | | Frente 0 integra: **empieza la línea base real** | |
| 2 (unos 4 días) | Features completas, `device_off`, borrado automático, `/outcomes`, pausa | Scheduler, 4 intervenciones, recuperación ante caídas, overlay, abort, emergencia | Snapshot, Scout y Red Team en Ollama, Allocator, preregistro, `after_outcome` | Overlays, vista de hoy, vista del experimento |
| **Hito 2** | | | Primer experimento preregistrado y corriendo | |
| 3 (unos 3 días) | `packaging/sidecar.spec` (PyInstaller) | Integración en Windows (Notepad real, kill a mitad de camino) | Resolución, veto regret, `/report` | Resultados, reporte, ajustes, electron-builder |
| **Hito 3** | | | Integración final y E2E | |

## Comandos comunes (en tu worktree)
```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest -q
.venv\Scripts\python tools/export_contracts.py --check
.venv\Scripts\python -m core --port 0 --data-dir data   # núcleo a mano (imprime NDE1_READY y el token por stderr)
```

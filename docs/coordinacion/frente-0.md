# Frente 0: Claude · Columna

> Solo el dueño del frente escribe este archivo. Actualizalo al terminar cada tarea.

## Estado
- Fase actual: 0 cerrada (2026-09-26)

## Hecho

## En curso

## Bloqueos

## Pedidos de contrato
<!-- Formato: fecha · qué cambiar exactamente · por qué. El Frente 0 responde acá abajo de cada pedido. -->

## Cómo probar lo entregado
- `.venv\Scripts\python -m pytest -q`: 55 tests (contratos, app, arranque, journal, cliente LLM).
- `.venv\Scripts\python tools/export_contracts.py --check`

## Fase 0 entregada (2026-09-26)
- Contratos congelados: `core/contracts.py`, `core/interfaces.py`, `contracts/` (36 schemas, `openapi.json`, 22 ejemplos).
- Normativos: `docs/outcome-rules.md`, `docs/journal-events.md`, `contracts/README.md` (protocolo de arranque).
- Copiado de Night Council con atribución: `core/journal/` (cadena de hashes, lock del sistema), `core/llm/` (cliente para Ollama con respuestas grabadas).
- `core/app.py`: composición, token local, `/health`, `/journal/verify`, `/settings`. Stubs 501 en las rutas de A, B y C.
- Briefs: `brief-a.md`, `brief-b.md`, `brief-d.md`.

## Hito 1 (2026-09-27): parcial
- Mergeados A (`c1bc408`) y D (`merge frente-d`). Los 4 pedidos de contrato de A están aplicados (`fbb52b2`).
- Verificado en `main`:
  - suite Python completa en verde y `export_contracts --check` ok;
  - app: typecheck, 46 tests de Vitest y tipos del contrato al día;
  - smoke del núcleo lanzado como lo hace Electron: `/health`, `/activity/today` (el sensor graba en SQLite), `/experiments/current`, `/ledger` y `/journal/verify` responden 200.
- **Falta B1** (`/blocks` y sorteo): sin eso no se pueden planear ni confirmar bloques, y la línea base real no puede empezar. La rama `frente-b` sigue en el commit de la Fase 0, sin cambios.

## B2: scheduler e intervenciones (Claude, en `main`, 2026-09-27)
Adelantado mientras B1 trabaja. Todo va en archivos que el brief de B1 le prohíbe crear, así que no se pisan:
- `core/runtime/scheduler.py`: ciclo de vida del bloque.
  - Intervención activa única.
  - `block_start` / `device_wake`; relevo entre bloques.
  - Evaluación con `evaluate_block` de A, que es final → revertir → `outcome` → `after_outcome`.
  - Recuperación, abort (con intención de tratar) y emergencia.
  - Vistas `overlay()` y `status()`.
  - Del store de B1 usa solo el protocolo `BlockRepo`: `pending`, `get`, `arm`, `set_status`, `set_aborted`.
- `core/runtime/interventions.py`: Win32 (minimizar/restaurar, nunca ocultar ni cerrar), selección con `categorize` de A y lista blanca, `open_target`.
- `core/runtime/intervention_state.py`: SQLite propio (`interventions.sqlite`) con fase por bloque, `hwnd` minimizados y banderas.
- `core/runtime/overlay.py`: cuenta regresiva desde P − 3 min y primer paso. Se oculta con 60 s seguidos de trabajo.
- Tests: `tests/runtime/test_b2_scheduler.py` (13) y `tests/runtime/test_b2_windows.py` (2, con una ventana Tk real, incluida una caída).
- **Pendiente para el merge de B1:** adaptar `BlockRepo` al store real, conectar en `routes.py` las 4 rutas de Claude (`abort`, `overlay`, `status`, `emergency_release`) y armar el scheduler en `build(ctx)`.

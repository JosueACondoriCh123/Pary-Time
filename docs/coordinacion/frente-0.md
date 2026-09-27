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

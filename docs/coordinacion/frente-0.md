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

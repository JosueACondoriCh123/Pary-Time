# Frente B: Externo 2 · Runtime e intervenciones

> Solo el dueño del frente escribe este archivo. Actualizalo al terminar cada tarea.

## Estado
- Fase actual: 1 entregada (2026-09-27). Scheduler, intervenciones, overlay y recuperación quedan para Claude (B2).

## Hecho
- `core/runtime/store.py`: SQLite en `data_dir/runtime.sqlite` con el bloque completo (campos LOCAL incluidos) y la asignación (`arm`, `experiment_id`, `draw_index`, `assigned_ms`). Una conexión con lock; los textos no salen de esta base.
- Rutas `GET/POST/PATCH/DELETE /blocks`, `POST /blocks/confirm` y `POST /blocks/{id}/first_step`. `block_id = blk_` + 12 hex. Editar o cancelar solo en `planned` (si no, 409); cancelar deja `cancelled`.
- Al confirmar, cada bloque `planned` del día (orden `planned_start_ms`) pasa a `confirmed`, escribe `block_confirmed` y enseguida `assignment`. Con experimento elegible, el brazo sale de `permuted_arm` y `draw_index` es la cantidad de `assignment` ya sellados de ese experimento. Sin experimento, o si el bloque no es elegible: `control`, `experiment_id` y `draw_index` en null, sin consumir índice.
- `arm_revealed` queda en null hasta `planned_start_ms`. `primer_paso` se revela al confirmar y `needs_first_step` es true hasta `POST /blocks/{id}/first_step`. El reloj es el `clock` que recibe `build(ctx, clock)`; por defecto `time.time_ns()`.
- `abort`, `/runtime/overlay`, `/runtime/status` y `/runtime/emergency_release` siguen en 501.

## En curso

## Bloqueos
- `pytest -q` del repo falla en `tests/integration/test_app.py::test_front_stubs_answer_501_until_implemented[get-/activity/today]`: el Frente A ya responde 200 y el test de la columna sigue esperando 501. No es código de B (`/runtime/status` sigue en 501). Lo tiene que actualizar el Frente 0.

## Pedidos de contrato
<!-- Formato: fecha · qué cambiar exactamente · por qué. El Frente 0 responde acá abajo de cada pedido. -->

## Cómo probar lo entregado
```powershell
..\.venv\Scripts\python -m pytest tests/runtime -q
..\.venv\Scripts\python tools/export_contracts.py --check
```
`tests/runtime`: 8 tests. Cubren CRUD y 409/404, sorteo contra `permuted_arm`, `draw_index` entre dos días, línea base y bloques no elegibles, el par `block_confirmed` + `assignment`, privacidad del journal, revelación con reloj manual y `first_step`.

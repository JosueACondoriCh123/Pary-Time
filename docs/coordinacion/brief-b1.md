# Brief · Frente B1: bloques y sorteo

> Pegale este archivo entero al agente externo 2 como primer mensaje. Su worktree es
> `C:\Users\HP\Documents\n-de-1\n-de-1-frente-b` (rama `frente-b`).
>
> Este brief **reemplaza a `brief-b.md` para el agente externo 2.** Es solo la Fase 1 de B: Python puro, SQLite y
> FastAPI. No hay Win32, hilos ni relojes. El resto de B (scheduler, intervenciones, overlay y recuperación) lo hace
> Claude cuando esto esté mergeado.

## Contexto en 5 líneas
Consejo N-de-1 es una app de escritorio para Windows que hace experimentos aleatorizados sobre cómo arranca a
trabajar una persona con TDAH. La persona declara **bloques** de trabajo para mañana y los confirma. Al confirmar, se
sortea para cada bloque si recibe una intervención o nada (control), y el sorteo queda sellado en un journal con
cadena de hashes. Vos construís **el guardado de bloques, sus rutas HTTP y el sorteo**. La app Electron (Frente D)
consume tus rutas para el planificador.

## Leé antes de escribir una línea (en este orden)
1. `docs/coordinacion/README.md`: reglas, carpetas e hitos. **Obligatorio.**
2. `core/contracts.py`, solo estas partes: `Arm`, `TaskKind`, `BlockStatus`, `Target`, `WorkMatcher`, `BlockCreate`,
   `BlockUpdate`, `Block`, `BlockView`, `ConfirmDay`, `FirstStep`, `permuted_arm`, `Assignment` y `BlockConfirmed`.
3. `core/interfaces.py`: `AppContext`, `ExperimentProvider` y `ActiveExperiment` (sobre todo `eligible` y `seed_hex`).
4. `docs/journal-events.md`: vos escribís solo `block_confirmed` y `assignment`.
5. `core/runtime/__init__.py` y `core/runtime/routes.py`: tu esqueleto. Las firmas de las rutas son contrato.
6. `core/app.py`, solo para ver cómo se arma el `AppContext` y cómo llegan `app.state.ctx` y el token.
7. `contracts/README.md`, la sección "Semántica que el schema no expresa".

## Tus carpetas (solo escribís acá)
`core/runtime/` y `tests/runtime/`. Más tu `docs/coordinacion/frente-b.md`.

## Qué entregás

### 1. `core/runtime/store.py`
- SQLite en `ctx.data_dir / "runtime.sqlite"`.
- Guarda todos los campos de `Block`, incluidos los LOCAL (`task_label`, `target`, `work_matchers`, `first_step`), y
  la asignación de cada bloque (`arm`, `experiment_id`, `draw_index`, `assigned_ms`).
- Los títulos, etiquetas y rutas se quedan acá. **Nunca van al journal.**
- Una conexión por operación o un lock: FastAPI puede llamarte desde varios hilos.

### 2. Rutas de bloques en `core/runtime/routes.py`
Implementá estas seis. **No cambies paths, métodos ni modelos.**

| Ruta | Regla |
|---|---|
| `GET /blocks?date=YYYY-MM-DD` | Bloques de ese `local_date`, ordenados por `planned_start_ms`, incluidos los `cancelled` |
| `POST /blocks` | `block_id = "blk_" + 12 hex` (`secrets.token_hex(6)`), `status = planned`, `created_ms = ahora` → 201 |
| `PATCH /blocks/{id}` | Solo si `status == planned`; si no, 409. 404 si no existe. Solo cambia los campos no nulos |
| `DELETE /blocks/{id}` | Solo si `status == planned`; si no, 409. Deja `status = cancelled` (no borra la fila) |
| `POST /blocks/confirm` | El sorteo, ver abajo |
| `POST /blocks/{id}/first_step` | Guarda `first_step`. 409 si al bloque no le tocó `primer_paso` |

Las otras cuatro rutas (`abort`, `/runtime/overlay`, `/runtime/status` y `/runtime/emergency_release`) **se quedan
en `not_implemented("B")`**. Son de Claude.

Para llegar al contexto desde una ruta, usá `request.app.state.ctx` (mirá cómo lo hace `core/app.py`). `build(ctx)`
sigue devolviendo un objeto con `.router`, `.start()` y `.stop()`. `start` y `stop` pueden no hacer nada.

### 3. Sorteo al confirmar (`POST /blocks/confirm`)
Para cada bloque `planned` de ese `local_date`, **en orden de `planned_start_ms`**:
1. Poné `status = confirmed` y escribí `append_typed(journal, "block_confirmed", BlockConfirmed(...))`.
2. Buscá el experimento activo: `exp = ctx.experiments.active() if ctx.experiments else None`.
   - **Con experimento y `exp.eligible(block)`:**
     - `draw_index` = cantidad de eventos `assignment` que ya hay en el journal con ese `experiment_id`
       (recorré `ctx.journal.events()`);
     - `arm = permuted_arm(exp.seed_hex, exp.experiment_id, draw_index, exp.treatment)`.
   - **Sin experimento, o con un bloque no elegible:** `arm = control`, `experiment_id = None` y
     `draw_index = None`. Es la línea base. **No consume índice.**
3. Escribí `append_typed(journal, "assignment", Assignment(...))` inmediatamente después.
4. Devolvé la lista de `BlockView` de ese día.

Confirmar un día sin bloques `planned` devuelve la lista tal cual, sin escribir nada.

**Nunca uses otro RNG.** `permuted_arm` es la referencia normativa y el consejo la reverifica con la semilla revelada.

### 4. Revelación en `BlockView`
- `arm_revealed` es `None` mientras `ahora < planned_start_ms`.
- **Excepción:** si el brazo es `primer_paso`, se revela apenas se confirma, y `needs_first_step = first_step is None`.
- `experiment_id` sí se muestra desde el sorteo.
- `ahora` sale de una función `now_ms()` de tu módulo que los tests puedan reemplazar pasándola como parámetro (sin
  `Mock`). Por ejemplo, un `Clock` con `now_ms()` que `build` recibe con valor por defecto `time.time() * 1000`.

## Tests (`tests/runtime/`)
Construí un `AppContext` real con un `Journal` en `tmp_path` y usá `fastapi.testclient.TestClient` sobre la app
completa de `core.app` o sobre tu router. Para el experimento activo, escribí una clase chica que implemente
`ExperimentProvider` / `ActiveExperiment` con una semilla fija. Eso es un fixture, no un mock: implementa la
interfaz real.

Tienen que cubrir:
1. CRUD: crear, listar, editar y cancelar, con el formato de `block_id`.
2. 409 al editar o cancelar un bloque confirmado, y 404 con un id inexistente.
3. Sorteo reproducible: los brazos coinciden con `permuted_arm` calculado a mano en el test.
4. `draw_index` consecutivo entre dos días confirmados por separado.
5. Los bloques no elegibles y la línea base (sin experimento) no consumen índices.
6. En el journal, cada `assignment` va justo después de su `block_confirmed`.
7. **Privacidad:** ningún evento del journal contiene `task_label`, `target.value`, los `pattern` de los matchers ni
   `first_step`. Usá textos únicos en el test y buscalos en el archivo del journal.
8. Revelación: `arm_revealed` es `None` antes de la hora y aparece después, moviendo el reloj del test. `primer_paso`
   se revela al confirmar.
9. `first_step`: 409 si no le tocó `primer_paso`, y `needs_first_step` pasa a `false` al escribirlo.

## Definición de terminado
- Antes de empezar: `git merge main` en tu rama.
- `.venv\Scripts\python -m pytest -q` y `.venv\Scripts\python tools/export_contracts.py --check` pasan.
- `git diff --stat main...` solo muestra `core/runtime/`, `tests/runtime/` y `docs/coordinacion/frente-b.md`.
- `docs/coordinacion/frente-b.md` está actualizado: qué hiciste y cómo probarlo.
- Commits en `frente-b` con mensajes `feat(b): ...` y `test(b): ...`. **No mergeás a `main`.**

## Prohibido
- Editar `core/contracts.py`, `core/interfaces.py`, `core/app.py` o las firmas de `routes.py`. Si algo falta, pedilo
  en tu `frente-b.md` y seguí con otra cosa.
- Tocar las cuatro rutas que son de Claude, o crear `scheduler.py` o `interventions.py`.
- Usar un sorteo distinto de `permuted_arm`, o mostrar el brazo antes de tiempo.
- Usar `Mock()` o `patch` para inventar comportamiento.

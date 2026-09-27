# Brief · Frente B: runtime e intervenciones

> Pegale este archivo entero al agente externo 2 como primer mensaje. Su worktree es
> `C:\Users\HP\Documents\n-de-1\n-de-1-frente-b` (rama `frente-b`).

## Contexto en 5 líneas
Consejo N-de-1 es una app de escritorio para Windows que hace experimentos aleatorizados sobre cómo arranca a
trabajar una persona con TDAH. La persona declara **bloques** de trabajo. Al confirmarlos, se sortea para cada bloque
si recibe una intervención o nada (control). A la hora del bloque, la compu aplica la intervención y mide cuánto tarda
en arrancar. Vos construís el **runtime**: bloques, sorteo, aplicación y reversión de las 4 intervenciones, overlay y
recuperación ante caídas. Hay otros 3 agentes trabajando en paralelo en otras carpetas.

## Leé antes de escribir una línea (en este orden)
1. `docs/coordinacion/README.md`: reglas, carpetas e hitos. **Obligatorio.**
2. `core/contracts.py`: `Block*`, `Arm`, `Assignment`, `InterventionEvent`, `OverlayState`, `RuntimeStatus`,
   `BlockConfirmed`, `BlockAbort`, `Settings`, y sobre todo `permuted_arm` y `seed_commitment`.
3. `core/interfaces.py`: `ActivitySource`, `EvaluateBlock`, `Categorize` (del Frente A), `ExperimentProvider` y
   `ActiveExperiment` (del Frente C), `AppContext` y `moderator_matches`.
4. `docs/journal-events.md`: los `kind` que te tocan escribir y cuándo.
5. `docs/outcome-rules.md`: la métrica que calcula el Frente A. Vos la consumís.
6. `core/runtime/__init__.py` y `core/runtime/routes.py`: tu esqueleto. Las firmas de las rutas son contrato.
7. `docs/superpowers/specs/2026-09-26-consejo-n-de-1-design.md`: el diseño completo.

## Tus carpetas (solo escribís acá)
`core/runtime/`, `tests/runtime/`.

## Dependencias de otros frentes (pueden estar en `None` en tu rama)
En tu rama, `ctx.activity`, `ctx.evaluate_block`, `ctx.categorize` y `ctx.experiments` pueden ser `None` hasta el
merge. Tu código tiene que:
- **Si `ctx.experiments` es `None` o `active()` devuelve `None`:** asignar `control` con `experiment_id=None`. Es la
  línea base.
- **Si `ctx.activity` / `ctx.evaluate_block` son `None`:** no evaluar outcomes. Se loguea una vez, sin romper.
- **En los tests:** construir un `AppContext` real con un `Journal` en `tmp_path` y fuentes de actividad en memoria
  alimentadas con trazas reales (`contracts/examples/ActivitySpan.list.json` y, cuando existan,
  `tests/fixtures/traces/*.jsonl`). Para `evaluate_block`, hasta que A mergee, testeá tu scheduler con una función
  que implemente una versión mínima documentada en el test, y reemplazala por la real en el Hito 1.

## Qué entregás

### Fase 1 (hacia el Hito 1)
1. **`core/runtime/store.py`:** SQLite en `ctx.data_dir / "runtime.sqlite"` con los bloques (todos los campos de
   `Block`, incluidos los LOCAL), las asignaciones y el estado de intervenciones (`hwnd`, proceso, `applied_ms`,
   `reverted_ms`). Los títulos y rutas se quedan acá, nunca en el journal.
2. **Rutas de bloques:** `GET/POST/PATCH/DELETE /blocks`, `POST /blocks/confirm` y `POST /blocks/{id}/first_step`,
   con estas reglas:
   - `block_id = "blk_" + 12 hex`.
   - `PATCH` y `DELETE` solo con `status == planned`; si no, 409.
   - `DELETE` deja `cancelled`.
3. **Sorteo al confirmar** (`POST /blocks/confirm`), para cada bloque `planned` del día, en orden de
   `planned_start_ms`:
   1. `status = confirmed` y `append_typed(journal, "block_confirmed", BlockConfirmed(...))`.
   2. `exp = ctx.experiments.active()`. Si hay experimento y `exp.eligible(block)`:
      - `draw_index` = cantidad de eventos `assignment` en el journal con ese `experiment_id`;
      - `arm = permuted_arm(exp.seed_hex, exp.experiment_id, draw_index, exp.treatment)`.
      Si no hay experimento o el bloque no es elegible: `arm = control`, `experiment_id = None` y
      `draw_index = None`.
   3. `append_typed(journal, "assignment", Assignment(...))`.
   - **Nunca uses otro RNG.** `permuted_arm` es la referencia normativa y el consejo la reverifica con la semilla
     revelada.
4. **Revelación:** `BlockView.arm_revealed` queda en `None` hasta `planned_start_ms`, salvo `primer_paso`, que se
   revela al confirmar con `needs_first_step = first_step is None`.
5. **Tests:** sorteo reproducible y verificable contra `permuted_arm`, `draw_index` consecutivo entre días, bloques
   no elegibles que no consumen índices, reglas 409, y que ningún evento del journal lleve textos del usuario.

### Fase 2 (hacia el Hito 2)
1. **`core/runtime/scheduler.py`:** un hilo con tick de unos 2 s y **reloj inyectable** (un `Clock` con `now_ms()`,
   para tests deterministas). Por bloque confirmado:
   - En `planned_start_ms`, o en el primer tick después si la compu despertó dentro de
     `[P, P + censor_s)`: `status = running` y se aplica la intervención del brazo. Journal
     `intervention: applied`, con `reason = block_start` o `device_wake`.
   - En cada tick de un bloque `running`:
     `outcome = ctx.evaluate_block(block, ctx.activity.spans(P, now), now, settings)`. Si el `status` es final:
     1. revertir (`work_run_reached` / `censor`);
     2. actualizar `status`;
     3. `append_typed(journal, "outcome", outcome)`;
     4. `ctx.experiments.after_outcome(outcome)`.
   - Los bloques que nunca llegaron a correr porque la compu estuvo apagada toda la ventana también se evalúan (dan
     `device_off`) y escriben su `outcome`.
2. **`core/runtime/interventions.py`:** cada intervención con `apply(block) -> state` y `revert(state)`. Aplicar dos
   veces deja el mismo estado. **La salida de emergencia siempre gana.**
   - `abrir_trabajo`: `os.startfile(target.value)` para `file`, `url` y `app`. Con `target.kind == "none"` o un error:
     journal `intervention: failed` (el bloque sigue en su brazo, por intención de tratar). Revertir no hace nada:
     nunca cierra el trabajo.
   - `retrasar_distracciones`:
     - Recorre las ventanas top-level visibles con `EnumWindows`. **Minimiza** con `ShowWindow(SW_MINIMIZE)`, nunca
       oculta, las que cumplen alguna de estas condiciones:
       - su proceso está en `distraction_processes`;
       - es un navegador cuyo título contiene un patrón de distracción, según `ctx.categorize(span, None, settings)
         == distraction`.
     - Nunca toca `whitelist_processes`.
     - Guarda los `hwnd` en `runtime.sqlite`.
     - En cada tick vuelve a minimizar las que reaparecieron (`reapplied`), salvo después de una salida de emergencia.
     - Revertir restaura con `ShowWindow(SW_RESTORE)` **solo** las ventanas que minimizó y siguen existiendo e
       iconificadas.
   - `primer_paso` y `cuenta_regresiva`: solo `OverlayState`.
     - `cuenta_regresiva`: en `P − 3 min` muestra "`<label>` · arrancás en m:ss". Después de `P`, "llevás m min".
     - `primer_paso`: muestra el texto escrito.
     - Ambas se esconden cuando la ventana activa es trabajo por 60 s seguidos
       (`ctx.categorize(span, block, settings) == work`) o al llegar a un `outcome` final.
3. **Recuperación ante caídas (`start()`):** antes de nada, restaura toda ventana con estado aplicado y sin revertir
   en `runtime.sqlite`, y escribe `intervention: reverted, reason: recovery`. Después, si el bloque sigue en
   ventana, el scheduler reaplica normalmente (`reapplied`).
4. **Rutas:**
   - `POST /blocks/{id}/abort`: revierte, escribe `block_abort` e `intervention: reverted, reason: abort`, y marca
     `aborted = True`. **El bloque se sigue evaluando** para su `outcome`, por intención de tratar.
   - `GET /runtime/overlay` y `GET /runtime/status`.
   - `POST /runtime/emergency_release`: restaura todo y no vuelve a minimizar en ese bloque.
5. **Constitución en tiempo de ejecución** (verificá en código y en test):
   - nunca se interviene fuera de un bloque confirmado y en ventana;
   - la lista blanca nunca se toca;
   - una sola intervención activa a la vez.

### Fase 3
- **Tests de integración en Windows** (`@pytest.mark.windows`):
  - abrir `notepad.exe` real con `settings.distraction_processes=["notepad.exe"]`, aplicar
    `retrasar_distracciones` y verificar `IsIconic`, luego revertir y verificar que se restauró;
  - lanzar el núcleo como subproceso, aplicar, **matarlo** con `TerminateProcess`, relanzarlo y verificar que
    Notepad se restauró y que el journal tiene `reason: recovery`.
- Endurecer: suspensión en medio de un bloque, un bloque que empieza mientras otro sigue `running` (el anterior se
  cierra por censura antes), cambio de fecha a medianoche.

## Definición de terminado (cada fase)
- Pasan `.venv\Scripts\python -m pytest -q` y `tools/export_contracts.py --check`.
- `git diff --stat main...` solo muestra tus carpetas.
- `docs/coordinacion/frente-b.md` está actualizado.
- Ningún evento del journal lleva títulos, rutas ni textos del usuario.

## Prohibido
- Editar contratos, interfaces, `core/app.py` o las firmas de `routes.py`. Si algo falta, pedilo en tu
  `frente-b.md`.
- Ocultar ventanas (`SW_HIDE`), cerrar procesos o intervenir fuera de un bloque.
- Usar un sorteo distinto de `permuted_arm`, o mostrar el brazo antes de tiempo en la API.

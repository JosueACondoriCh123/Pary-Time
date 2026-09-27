# Brief · Frente A: sensor y resultado

> Pegale este archivo entero al agente externo 1 como primer mensaje. Su worktree es
> `C:\Users\HP\Documents\n-de-1\n-de-1-frente-a` (rama `frente-a`).

## Contexto en 5 líneas
Consejo N-de-1 es una app de escritorio para Windows que hace experimentos aleatorizados sobre cómo arranca a
trabajar una persona con TDAH. La métrica primaria es la **latencia de arranque**: cuánto tarda desde la hora
planeada de un bloque hasta un tramo de 15 min de trabajo real. Vos construís el **sensor**, que registra qué ventana
está activa, y la **función que calcula esa métrica**. Todo es local; nada sale de la compu. Hay otros 3 agentes
trabajando en paralelo en otras carpetas.

## Leé antes de escribir una línea (en este orden)
1. `docs/coordinacion/README.md`: reglas, carpetas e hitos. **Obligatorio.**
2. `docs/outcome-rules.md`: **la especificación normativa de tu función principal.** Implementala exactamente.
3. `core/contracts.py`: `ActivitySpan`, `BlockOutcome`, `OutcomeFeatures`, `OutcomeRules`, `Category`,
   `ActivitySummary`, `Settings`, `Block`, `WorkMatcher`.
4. `core/interfaces.py`: `ActivitySource`, `EvaluateBlock`, `Categorize`, `AppContext`.
5. `core/sensing/__init__.py` y `core/sensing/routes.py`: tu esqueleto. Las firmas de las rutas son contrato.
6. `docs/superpowers/specs/2026-09-26-consejo-n-de-1-design.md`: el diseño completo, por contexto.

## Tus carpetas (solo escribís acá)
`core/sensing/`, `tools/capture/`, `tests/sensing/`, `tests/fixtures/traces/`, y en la Fase 3 solo el archivo
`packaging/sidecar.spec`.

## Qué entregás

### Fase 1 (hacia el Hito 1)
1. **`core/sensing/sampler.py`:** un hilo que muestrea a 1 Hz.
   - Proceso de la ventana en primer plano: `win32gui.GetForegroundWindow` y `win32process.GetWindowThreadProcessId`.
     El nombre del ejecutable se obtiene con `QueryFullProcessImageNameW` vía ctypes o con
     `win32process.GetModuleFileNameEx` (quedarse con el basename, por ejemplo `WINWORD.EXE`).
   - Título de la ventana.
   - Inactividad: `win32api.GetLastInputInfo()` contra `GetTickCount()`. `idle = true` si pasaron más de
     `OUTCOME_RULES.idle_max_s`.
   - Pantalla bloqueada (`locked`): `LockApp.exe` en primer plano o falla de `OpenInputDesktop`.
   - Comprime en `ActivitySpan`: extiende el tramo actual mientras `(process, title, idle, locked)` no cambie.
   - **Si entre dos muestras pasan más de 5 s** (suspensión, apagado), cierra el tramo y deja el hueco: los huecos
     significan compu apagada.
   - Falla suave: si una llamada win32 falla, esa muestra se saltea y se loguea; nunca tira el hilo.
2. **`core/sensing/store.py`, `SpanStore`:** implementa `ActivitySource` sobre SQLite en
   `ctx.data_dir / "activity.sqlite"`, en modo WAL. Tabla
   `spans(start_ms, end_ms, process, title, idle, locked)` con índice por `start_ms`. `spans(a, b)` devuelve los
   tramos que se solapan con `[a, b)`, en orden, recortados al rango. Tiene que ser seguro con hilos: el sampler
   escribe y el runtime lee.
3. **`core/sensing/categorize.py`, `categorize(span, block, settings) -> Category`:** función pura.
   - `work`: hay un `block` y algún `WorkMatcher` coincide (subcadena sin distinguir mayúsculas sobre `process` o
     `title`).
   - `distraction`: `process` está en `settings.distraction_processes`, o está en `settings.browser_processes` y el
     título contiene algún `settings.distraction_title_patterns`. Si coincide con `whitelist_processes`, nunca es
     `distraction`.
   - `other`: el resto. `__paused__` es `other`.
   - Con `block=None` nunca devuelve `work`.
4. **`core/sensing/outcome.py`, `evaluate_block(block, spans, now_ms, settings) -> BlockOutcome`:** función
   **pura** que implementa `docs/outcome-rules.md` al pie de la letra, incluidas las features.
5. **`core/sensing/__init__.py`:** `build(ctx)` devuelve el servicio real con `router`, `start()` (arranca el
   sampler), `stop()` (lo frena y cierra el tramo abierto), `activity` (tu `SpanStore`), `evaluate_block` y
   `categorize`.
6. **Rutas:** `GET /activity/today` y `POST /activity/pause` / `POST /activity/resume`.
   - `minutes_by_category` usa las claves `distraction`, `other`, `idle` y `paused`.
   - Durante la pausa se escriben tramos `process="__paused__", title="", idle=true` (ver outcome-rules).
7. **`tools/capture/`:**
   - `record.py`: corre el sampler solo y escribe tramos a `tests/fixtures/traces/<nombre>.raw.jsonl`. Esos archivos
     están en .gitignore y **nunca se commitean**.
   - `sanitize.py`: produce `<nombre>.jsonl` commiteable. Mantiene `process`. En `title` deja solo una subcadena de
     una keep-list (`--keep cap3 --keep tesis`) o el patrón de distracción que coincidió (por ejemplo `youtube`); el
     resto queda en `""`.
   - Josué va a correr la captura 2–3 días reales. Mientras tanto, construí fixtures chicos a mano en el mismo
     formato, **marcados como `synthetic` en el nombre**.
8. **Tests (`tests/sensing/`):** cada regla de outcome-rules con al menos un caso:
   - arranque normal;
   - hueco de 59 s que no corta y de 61 s que sí;
   - inactividad > 120 s en la app de trabajo;
   - `started_early`;
   - censura a 90 min;
   - tramo abierto al momento de la censura (sigue `pending`);
   - `device_off`;
   - compu que se prende tarde dentro de la ventana (cuenta como latencia);
   - pausa;
   - features.

   Además, `SpanStore` con SQLite real en `tmp_path`, y la compresión del sampler probada sobre muestras grabadas
   (separá la lógica de compresión de las llamadas win32 para poder probarla).

### Fase 2 (hacia el Hito 2)
- Borrado automático: una vez por día y al arrancar, borra tramos más viejos que `settings.raw_retention_days`.
- `GET /outcomes?from_date&to_date`: lee del journal los eventos `outcome` y los cruza con `block_confirmed` para
  sacar `local_date`. **No los escribís vos:** los escribe el runtime (Frente B).
- Endurecer: reloj del sistema que salta (usá `time.monotonic()` para medir intervalos y wall clock para los
  timestamps), múltiples monitores, ventanas sin título, procesos elevados sin permiso de lectura (quedan como
  `process = "?"`).
- Correr `evaluate_block` sobre las trazas reales sanitizadas de Josué y dejar esos casos como tests de regresión.

### Fase 3
- `packaging/sidecar.spec` (PyInstaller, one-folder) que empaquete `python -m core` como `nde1-core.exe`. Es la
  **única** excepción fuera de tus carpetas; el Frente D lo consume desde electron-builder. Coordiná el nombre y la
  ruta de salida en tu `frente-a.md`.

## Definición de terminado (cada fase)
- Pasan `.venv\Scripts\python -m pytest -q` y `tools/export_contracts.py --check`.
- No tocaste nada fuera de tus carpetas: `git diff --stat main...` lo muestra.
- `docs/coordinacion/frente-a.md` está actualizado con qué hiciste, cómo probarlo y los pedidos pendientes.
- Ningún fixture commiteado contiene títulos sin sanitizar.

## Prohibido
- Editar `core/contracts.py`, `core/interfaces.py`, `core/app.py`, `docs/outcome-rules.md` o las firmas de
  `routes.py`. Si una regla te parece mal, **pedí el cambio**; no la "arregles" en el código.
- Escribir al journal (vos no tenés `kind` asignado).
- Mandar datos por red, usar `print` con títulos o loguear títulos a archivos fuera del SQLite.

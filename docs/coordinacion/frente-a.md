# Frente A: Externo 1 · Sensor y resultado

> Solo el dueño del frente escribe este archivo. Actualizalo al terminar cada tarea.

## Estado
- 2026-09-27: Fase 2 reforzada con recuperación del sensor, regresión real breve y replay de trazas.
  Sigue pendiente la validación con 2–3 días reales de Josué; no se da por cumplida con la captura breve.
- La entrega inicial `a060e33` ya fue integrada por el Frente 0 (Hito 1).
- Fase 3: sidecar reconstruido con las correcciones de Fase 2 y verificado en Windows.
- Worktree real: `C:\Users\HP\Documents\n-de-1\n-de-1-frente-a`, rama `frente-a`.
- Base de esta continuación: `main@121b372`, con A, C, D y las cuatro respuestas del Frente 0 incorporadas.

## Hecho
- Sensor a 1 Hz con Win32, cierre de handles, nombres de proceso mediante acceso limitado, títulos acotados,
  bloqueo e inactividad; errores sin títulos ni mensajes privados. Sin dependencias de runtime nuevas.
- Compresor puro separado de Win32. Huecos >5 s y saltos del reloj no inventan trabajo continuo.
- `SpanStore`: SQLite WAL, exclusión mutua entre lectores/escritor, recorte `[a,b)`, muestras persistidas,
  borrado al arrancar, diario y al cambiar retención; `secure_delete` y truncado de WAL tras purgar.
- `categorize` y `evaluate_block` conforme a `outcome@1`: latencia, censura, tramo abierto, device_off,
  arranque temprano, pausas y features. No hay escrituras al journal desde el frente A.
- Servicio conectado por `build(ctx)`; routers independientes por instancia; resumen diario, pausa/resume
  y consulta de outcomes cruzados con la fecha local de `block_confirmed`.
- Pausa sin consultar títulos; se conserva su vencimiento en SQLite para sobrevivir al reinicio del núcleo.
- Herramientas `record.py` y `sanitize.py`, captura recuperable desde SQLite y guía `tools/capture/README.md`.
- Pruebas con contratos ilustrativos, SQLite real, replay sintético y llamadas reales de Windows.
- Spec PyInstaller one-folder: `packaging/sidecar.spec`. Frente D debe consumir
  `dist/nde1-core/nde1-core.exe` junto con TODO `dist/nde1-core/`, incluido `_internal/`.
  `console=True` mantiene stdout para `NDE1_READY`; Electron lo debe lanzar con `windowsHide: true`.
  También se incluyen los prompts Markdown de C; sin esos recursos el consejo empaquetado no podría leerlos.

## Refuerzos de la Fase 2 (2026-09-27)
- Al reiniciar, el compresor recupera el último fin persistido desde SQLite. Si el reloj retrocedió,
  espera a alcanzar ese límite: no inserta filas solapadas ni sustituye trabajo ya observado.
- SQLite acepta extensiones de un tramo manteniendo su estado; rechaza acortarlo o reclasificarlo.
- La lectura de inactividad obtiene primero `GetLastInputInfo` y después `GetTickCount`, para que un
  input entre ambas llamadas no se interprete como un desbordamiento del contador DWORD.
- Se verifica el borrado al arrancar también sobre los bytes del SQLite, usando un título sintético.
- `tools/capture/replay.py` evalúa un bloque local contra una traza y emite únicamente `BlockOutcome`.
  Usa el fin observado como `now_ms` por defecto; permite comparar con un resultado revisado usando `--expect`.
- Sanitización y replay comparten validación cronológica: rechazan tramos invertidos, desordenados o
  solapados sin publicar el contenido privado ni dejar un fixture parcial.
- Captura real de Windows de 20 segundos, sanitizada sin keep-list: `phase2-windows-20260927.jsonl`.
  Contiene inactividad, no arranque de trabajo. Su resultado revisado es `pending` para un bloque de prueba.
  La procedencia y el alcance se documentan en `tests/fixtures/traces/README.md`.

## En curso
- Ninguna captura prolongada en ejecución. Siguiente hito: trazas reales y revisión del Frente 0.

## Bloqueos
- Faltan las trazas de 2–3 días de Josué. Los fixtures sintéticos no sustituyen esa validación.

## Pedidos de contrato
<!-- Formato: fecha · qué cambiar exactamente · por qué. El Frente 0 responde acá abajo de cada pedido. -->
- 2026-09-26 · Frente 0: quitar `/activity/today` del test de stubs 501 y verificar `ActivitySummary`/200.
  La primera corrida completa terminó con ese único fallo; no se ocultó ni saltó el test.
- 2026-09-26 · Frente 0: corregir `BlockOutcome.started.json` y las copias del ejemplo en otros contratos
  si corresponde: para `ActivitySpan.list.json`, `pre_start_switches` antes del arranque es 2, no 3.
  La regla escrita mide `[P,E)`: chrome → WhatsApp → explorer; el salto a WINWORD en E queda afuera.
- 2026-09-26 · Frente 0: corregir la descripción OpenAPI de pausa (hoy dice «no registra nada»).
  Se registran spans `__paused__` sin títulos, tal como manda `outcome@1`. A conserva el texto congelado.
- 2026-09-26 · Frente 0: declarar PyInstaller como herramienta de empaquetado opcional de desarrollo;
  el entorno compartido no lo trae. A no modifica `pyproject.toml` ni las dependencias compartidas.

- **Respuesta del Frente 0 (2026-09-27), los 4 aplicados en `main` junto con el merge de A (Hito 1):**
  1. El test de stubs ya no incluye `/activity/today`; se agregó `test_sensing_routes_are_live`, que exige 200 y `ActivitySummary`.
  2. `BlockOutcome.started.json`: `pre_start_switches` = 2. Correcto: WINWORD está en E, fuera de `[P, E)`.
  3. La descripción OpenAPI de la pausa ahora dice que se graban tramos `__paused__` sin títulos. `openapi.json` quedó regenerado.
  4. `pyproject.toml`: extra opcional `packaging = ["pyinstaller>=6"]`, que se instala con `pip install -e ".[packaging]"`.

## Precisiones para B y C
- Pasar a `evaluate_block` todo el intervalo normativo, incluido margen posterior a los 90 minutos;
  no cerrar un bloque mientras el resultado sea `pending`.
- Se recorta además a `now_ms`: una traza pregrabada no permite observar el futuro.
- Los cambios de proceso se cuentan solo entre spans anteriores al arranque; segundos de distracción
  y minutos del resumen se truncan después de sumar, porque los campos del contrato son enteros.
- `first_category` usa la primera observación desde P, incluso en arranque temprano; cobertura de un
  intervalo vacío = 1. `started_early` solo es verdadero si el tramo que califica comienza en P y lo cubre.
- No se confunde pausa con equipo apagado. El contrato sí hace indistinguibles la falta de sensor y el
  equipo apagado: no se agregó un estado fuera de contrato.

## Cómo probar lo entregado
- Suite general de esta continuación: **175 passed, 2 skipped**, sin fallos.
  Los skips son la prueba live de Ollama y el smoke del ejecutable, que se habilitan explícitamente.
- `tools/export_contracts.py --check`: correcto. No se editaron contratos desde A.
- Frente A en fuentes: **76 passed, 1 skipped**. La regresión real breve está incluida.
  Smoke del sidecar final: **1 passed**, con arranque HTTP, journal, interrupción/reinicio, pausa y prompts,
  sobre una carpeta temporal, sin dejar procesos activos. Se inspeccionó además el bytecode empaquetado
  para confirmar que contiene el último orden de lectura de inactividad.
- Desde esta subcarpeta: `..\.venv\Scripts\python.exe -m pytest -q tests/sensing`.
- Contratos: `..\.venv\Scripts\python.exe tools/export_contracts.py --check`.
- Suite completa: `..\.venv\Scripts\python.exe -m pytest -q`.
- Captura y sanitización: ver `tools/capture/README.md`. No se deja captura de días ejecutándose sin supervisión.
- Empaquetado: `python -m PyInstaller --noconfirm packaging/sidecar.spec` en un entorno con PyInstaller.
- En este worktree se instaló PyInstaller 6.22.3 solo bajo `.venv/Lib/site-packages` (ignorado), sin tocar
  el entorno compartido. Para repetir la construcción local en una consola nueva:

```powershell
$env:PYTHONPATH = (Resolve-Path .venv/Lib/site-packages).Path
..\.venv\Scripts\python.exe -m PyInstaller --noconfirm --workpath build/phase2-final packaging/sidecar.spec
$env:NDE1_SIDECAR_EXE = (Resolve-Path dist/nde1-core/nde1-core.exe).Path
..\.venv\Scripts\python.exe -m pytest tests/sensing/test_sidecar.py -o addopts='' -q
```

- Recompilar el sidecar cuando se integren nuevas entregas de B/C. Los binarios, SQLite y trazas raw no se commitean.

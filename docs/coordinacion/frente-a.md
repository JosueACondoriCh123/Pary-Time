# Frente A: Externo 1 · Sensor y resultado

> Solo el dueño del frente escribe este archivo. Actualizalo al terminar cada tarea.

## Estado
- 2026-09-26: implementación de Fases 1 y 2 disponible; validación con trazas largas reales pendiente.
- Fase 3: sidecar construido y probado en Windows después de integrar C. Listo para revisión/merge del Frente 0.
- Worktree real: `C:\Users\HP\Documents\n-de-1\n-de-1-frente-a`, rama `frente-a`.
- Integrado `main` hasta `4f6ab9d`, incluida la entrega de C; reparada la referencia Git que seguía apuntando a la carpeta hermana.

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

## En curso
- Ninguna captura prolongada en ejecución. Siguiente hito: trazas reales y revisión del Frente 0.

## Bloqueos
- Faltan las trazas de 2–3 días de Josué. Los fixtures sintéticos no sustituyen esa validación.
- La suite general tiene una expectativa de Fase 0 obsoleta: `tests/integration/test_app.py` parametriza
  `/activity/today` como stub 501; A ya responde 200. Se deja intacta por pertenecer al Frente 0.

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
- Resultados sobre `main@4f6ab9d` + A: **158 passed, 3 skipped, 1 failed**, por el stub obsoleto descrito arriba.
  Los skips son dos pruebas de Ollama optativas y el smoke del ejecutable, que se habilita por variable de entorno.
- `tools/export_contracts.py --check`: correcto. No se editaron contratos desde A.
- Frente A: **62 pruebas aprobadas**, contando el smoke del ejecutable habilitado explícitamente.
  El sidecar reconstruido con C pasó arranque HTTP, verificación del journal, interrupción/reinicio,
  conservación de pausa y presencia de los prompts. La prueba usa una carpeta temporal y no deja procesos activos.
- Desde esta subcarpeta: `..\.venv\Scripts\python.exe -m pytest -q tests/sensing`.
- Contratos: `..\.venv\Scripts\python.exe tools/export_contracts.py --check`.
- Suite completa: `..\.venv\Scripts\python.exe -m pytest -q` (ver expectativa 501 pendiente arriba).
- Captura y sanitización: ver `tools/capture/README.md`. No se deja captura de días ejecutándose sin supervisión.
- Empaquetado: `python -m PyInstaller --noconfirm packaging/sidecar.spec` en un entorno con PyInstaller.
- En este worktree se instaló PyInstaller 6.22.3 solo bajo `.venv/Lib/site-packages` (ignorado), sin tocar
  el entorno compartido. Para repetir la construcción local en una consola nueva:

```powershell
$env:PYTHONPATH = (Resolve-Path .venv/Lib/site-packages).Path
..\.venv\Scripts\python.exe -m PyInstaller --noconfirm packaging/sidecar.spec
$env:NDE1_SIDECAR_EXE = (Resolve-Path dist/nde1-core/nde1-core.exe).Path
..\.venv\Scripts\python.exe -m pytest tests/sensing/test_sidecar.py -o addopts='' -q
```

- Recompilar el sidecar cuando se integren nuevas entregas de B/C. Los binarios, SQLite y trazas raw no se commitean.

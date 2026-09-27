# Captura local del Frente A

## Demo de hackathon: datos sintéticos

`tools.capture.synth.synth_day` implementa `core.interfaces.SynthDay` sin leer el sensor,
reloj actual, archivos ni journal. Solo debe recibir bloques creados para la demo,
con matchers genéricos: el matcher elegido se incorpora a la ventana de trabajo.
Las etiquetas, destinos y primeros pasos no se copian. Se rechazan matchers con
rutas o emails; esto no reemplaza la responsabilidad del llamador de usar datos sintéticos.

```python
from datetime import date
from random import Random
from tools.capture.synth import synth_day

spans = synth_day(date(2026, 9, 27), demo_blocks, "tdah_mananas", Random(7),
                  latency_scale={demo_blocks[0].block_id: 0.5})
```

Las latencias de base son lognormales (sigma 0.6), con medianas de 25 minutos por
la mañana y 8 por la tarde/noche. Hay 5% de apagados por bloque; las mañanas añaden
10% de demoras largas. Los parámetros son inventados para la demostración, sin
significado clínico. El factor multiplica la demora latente antes de evaluarla:
`0.5` la reduce a la mitad y puede convertir una demora censurada en un arranque.
Los apagados se conservan. El evaluador real sigue decidiendo todos los resultados.

Los tramos de trabajo duran al menos 16 minutos; hay entre 1 y 4 cambios de ventana
antes del trabajo. Fuera de las ventanas se añade actividad genérica de 08:00 a 22:00,
inactividad y algunas pausas `__paused__` con `idle=true` y título vacío. Los períodos
apagados quedan sin observaciones, también en el margen posterior a los 90 minutos.

Reservar **106 minutos desde el inicio de cada bloque**, sin solapamientos ni cruces
de medianoche. Todos los bloques deben pertenecer al día local pedido y tener IDs
distintos. Mismo día, bloques, perfil, semilla, factores y zona horaria producen los
mismos tramos; cambiar un factor no altera las extracciones aleatorias de los otros
bloques. Los factores deben ser finitos y no negativos. Perfil disponible: `tdah_mananas`.
El simulador de C debe marcar su directorio con `DATA_LABEL=sintetico` y mostrar
**DATOS SINTÉTICOS**. Este generador no escribe ni marca directorios por sí mismo.

## Capturar uso real (fuera de la entrega de hackathon)

Desde `n-de-1/n-de-1-frente-a`, usando el Python 3.11 del proyecto padre:

```powershell
..\.venv\Scripts\python.exe tools/capture/record.py dia1 --hours 48
```

Dejá esta consola abierta mientras trabajás. `Ctrl+C` termina y exporta. No se instala
una tarea automática ni queda un proceso en segundo plano. Los datos se guardan cada
segundo en `data/capture-dia1.sqlite`; al terminar se exportan a
`tests/fixtures/traces/dia1.raw.jsonl`. Ambos quedan excluidos de Git por las reglas
existentes. La captura aplica `raw_retention_days` (14 por defecto); el archivo raw
exportado debe eliminarse manualmente cuando deje de ser necesario.

Si la consola o el equipo se cierran antes de exportar, recuperá la captura:

```powershell
..\.venv\Scripts\python.exe tools/capture/record.py dia1 --export-only
```

Sanitizá antes de compartir cualquier traza:

```powershell
..\.venv\Scripts\python.exe tools/capture/sanitize.py tests/fixtures/traces/dia1.raw.jsonl --keep cap3 --keep tesis
```

El resultado `dia1.jsonl` conserva proceso, tiempos, inactividad y bloqueo. En el título
solo quedan los tokens explícitamente permitidos y los patrones de distracción de
navegadores. La lista `--keep` debe contener fragmentos genéricos necesarios para los
matchers, nunca nombres, rutas ni textos personales. `--settings ruta/settings.json`
permite usar los patrones personalizados del usuario. El sanitizador no sobrescribe
archivos existentes ni imprime títulos, incluso si una línea tiene errores.

## Reproducir un resultado de bloque

Con la traza sanitizada y el bloque real en formato `Block` (incluidos sus matchers):

```powershell
..\.venv\Scripts\python.exe tools/capture/replay.py tests/fixtures/traces/dia1.jsonl --block data/runtime/bloque.json --output data/runtime/resultado.json
```

La salida es un `BlockOutcome`: no incluye títulos, matchers ni etiquetas de tarea.
Por defecto, `now_ms` es el fin observado de la traza. Una captura corta queda
`pending`; no se adelanta el reloj para fabricar una censura. Para reproducir una
evaluación realizada en un instante conocido, agregá `--now-ms <epoch_en_ms>`.
Usá `--settings ruta/settings.json` si el bloque empleó ajustes personalizados.

Después de revisar el resultado, `--expect ruta/resultado.json` compara exactamente
el resultado y devuelve código 1 si cambia. Esto permite convertir las futuras
trazas reales de 2–3 días en regresiones reproducibles. El bloque local contiene
textos privados: guardalo bajo `data/runtime/` (ignorado), no entre los fixtures.
La sanitización y el replay rechazan tramos invertidos, desordenados o solapados
antes de crear la salida; los huecos por suspensión sí son válidos.

Para una prueba breve usá un nombre nuevo y `--seconds 5`. No confundas esa prueba
con la captura de 2–3 días que requiere la validación del proyecto.

## Formatos y límites

- Una línea JSON por `ActivitySpan`, conforme a `contracts/schemas/ActivitySpan.schema.json`.
- Los fixtures hechos a mano contienen `synthetic` en el nombre. No representan uso real.
- El primer muestreo establece un punto; el siguiente establece duración. Al cerrar o
  detectar un hueco se extrapola como máximo un segundo desde la última observación.
- Huecos de más de 5 segundos o saltos entre reloj monotónico y reloj civil no se
  convierten en trabajo continuo. Tras un salto hacia atrás se omiten observaciones
  hasta alcanzar el último timestamp guardado, incluso si se reinicia el proceso.
  Los tramos persistidos solo pueden extenderse conservando su estado: no se pueden
  acortar ni reclasificar por accidente.
- No se manipulan ventanas, teclado ni mouse. La captura observa la ventana activa
  en cualquier monitor. Un proceso inaccesible se registra como `?`.
- Los errores de muestreo se omiten y se informa solo su clase. Bajo `outcome@1`, los
  huecos por errores del sensor son indistinguibles de equipo apagado: la cobertura
  derivada permite detectarlos, pero haría falta un contrato nuevo para distinguirlos.

La implementación de las llamadas nativas sigue la documentación de Microsoft de
[QueryFullProcessImageNameW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew),
[OpenInputDesktop](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-openinputdesktop)
y [GetTickCount](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-gettickcount).
El empaquetado usa el formato documentado de
[specs de PyInstaller](https://pyinstaller.org/en/stable/spec-files.html).

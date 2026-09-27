# Captura local del Frente A

## Fase 5: estabilidad con datos sintéticos

`soak.py` ejercita `Sampler._ingest`, compresión, retención y SQLite reales con
observaciones sintéticas a 1 Hz lógico. No inicia `WindowsReader`, no lee ventanas
y no escribe al journal. Cada ejecución exige una carpeta **nueva** y la marca
`DATA_LABEL=sintetico`. Usar `build/` mantiene los resultados fuera de Git.

```powershell
# Volumen de 48 h; corre a la velocidad que permiten SQLite y el disco.
..\.venv\Scripts\python.exe tools/capture/soak.py --out build/soak-accelerated --hours 48

# 48 horas transcurridas, con una muestra por segundo y la misma carga sintética.
..\.venv\Scripts\python.exe tools/capture/soak.py --out build/soak-realtime --mode realtime --hours 48
```

No cambiar las opciones de durabilidad de SQLite para acelerar la prueba. La corrida
acelerada puede tardar decenas de minutos: hace las mismas escrituras por muestra.
Un smoke usa `--seconds 5`. El escenario alterna trabajo, distracción, inactividad,
bloqueo y pausa cada 30 s; introduce huecos de 10 s por hora, saltos del reloj civil
y retrocesos, y reabre la base y el compresor cada 6 h sin vaciar el estado en memoria.
Estas reaperturas prueban recuperación de estado persistido, no simulan un corte eléctrico.
La retención se fija en un día para ejercitar purgas durante las 48 h; al arrancar
también se inserta y purga un registro sintético vencido.

`status.json` se reemplaza atómicamente y contiene estado, PID, tiempo lógico,
tiempo transcurrido, conteos, integridad y problemas. `metrics.jsonl` agrega una
medición por minuto real en modo realtime, o por hora lógica en modo acelerado.
Se comprueban duración positiva, ausencia de solapamientos, retención y estados
permitidos, además de `PRAGMA quick_check`. No se exportan títulos, procesos,
rutas, tokens ni mensajes de excepciones. El SQLite contiene solo las etiquetas
sintéticas fijas del escenario.

Se miden heap de Python con `tracemalloc` y handles del propio proceso en Windows
mediante [GetProcessHandleCount](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesshandlecount).
Un aumento superior a 16 MiB de heap o 64 handles respecto de la primera medición
reportada produce fallo; son umbrales de regresión para esta carga acotada. No son
una medición de todo el RSS ni una prueba de ausencia de cualquier fuga nativa.
El reporte conserva hallazgos intermedios aunque una medición posterior se recupere.
Los saltos del planificador real se cuentan sin rellenar muestras perdidas; más
de 1% de ticks perdidos o un hueco mayor de 5 s invalida la corrida.

Consultar el avance y detener una corrida, incluso lanzada con ventana oculta:

```powershell
Get-Content build/soak-realtime/status.json
New-Item -ItemType File -Path build/soak-realtime/stop.request
```

La detención se revisa cada segundo y deja `status=interrupted`, cierra SQLite y
no marca aprobación. `Ctrl+C` tiene el mismo efecto en primer plano. Un cierre
forzado del proceso puede dejar `running` como último estado: comprobar también
el PID y la fecha de actualización; ese archivo por sí solo no acredita que siga vivo.
Una ejecución no se reanuda; repetir requiere otra carpeta. No se crea un servicio
ni una tarea de inicio de Windows.

Exit 0 exige `checks_passed=true`; 1 indica fallo de la corrida, 2 error de preparación
y 130 interrupción. `wall_48h_completed` solo puede ser verdadero en modo realtime
tras al menos 172.800 s transcurridos y no reemplaza `checks_passed`.
**48 h lógicas aceleradas no son un soak de 48 h reales.** Esta herramienta tampoco
valida 48 h de Win32, Electron, NSIS o intervenciones: esas pruebas corresponden a
una integración posterior. Las pruebas breves existentes de Win32 y del sidecar
se informan por separado.

Los avisos del sensor se limitan a uno por 60 s de reloj monotónico. Incluyen el
número de errores desde el último aviso y la clase del último error, nunca su
mensaje ni traceback. El primer error se informa enseguida; si después cesan los
fallos puede quedar un conteo pendiente sin otro aviso. La señal `sensor_running`
sigue dependiendo de la antigüedad de la última muestra válida, no del log.

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

### Fase 4: comprobar los datos antes del experimento real

Cerrá normalmente la app para que SQLite complete su checkpoint y ejecutá desde A:

```powershell
..\.venv\Scripts\python.exe tools/capture/preflight.py --data-dir ../data
```

Elegí la carpeta de datos reales usada por tu app: `../data` es solo un ejemplo. Electron
usa `NDE1_DATA_DIR` si está definido; en otro caso, `data` dentro de su carpeta `userData`.
La herramienta no crea esa carpeta,
no arranca el sensor y no modifica datos. Lee el journal con su verificador de hashes
y la base propia de A mediante SQLite inmutable. Si hay un WAL, rehúsa leerlo para no
ignorar observaciones pendientes; cerrá el núcleo y repetí. No elimina el WAL ni repara
un journal truncado. Detecta cambios de archivos durante la lectura.

La salida JSON contiene únicamente conteos, límites temporales agregados y códigos de
problema. **No contiene títulos, procesos, rutas, efectos por brazo, p-valores ni semillas.**
No se recalculan resultados ni se escribe al journal. Comprueba:

- etiqueta `DATA_LABEL`: `sintetico` nunca puede aprobar como datos reales;
- al menos siete días calendario entre la primera y última fecha local con resultados
  de línea base, contando ambas fechas, antes del primer preregistro; se informa además
  cuántas fechas tuvieron observaciones, sin exigir trabajo todos los días;
- los `device_off` y los controles de un experimento no completan esa semana;
- integridad del journal, duplicados, referencias básicas y resultados finales coherentes;
- reglas de medición preregistradas iguales a `outcome@1`, y cambios de configuración
  que afectaron la clasificación de distracciones durante un experimento;
- actividad persistida no vacía, ordenada, sin solapamientos y base SQLite legible.

Exit **0** significa que esas comprobaciones de medición pasaron; **1**, que hay
problemas reportados; **2**, que no pudo completarse la comprobación. Los siete días
provienen de la semana de línea base del plan: **no son un criterio de potencia** ni
una autorización del consejo para iniciar el experimento. Sin marcador se conserva
el valor `real` del contrato Health, pero se advierte que no se verificó la procedencia.
Una etiqueta, por sí sola, no prueba que las observaciones sean reales.

Límites: no contrasta cada outcome contra las trazas originales, que pueden haberse
purgado por retención; no reconstruye ajustes históricos ni detecta cambios manuales
de `settings.json` que no dejaron evento. `withdraw`, la restauración de ventanas y
la decisión de continuar capturando requieren los contratos y servicios de 0/B/C/D.

### Registrar y reproducir trazas

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

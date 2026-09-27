# Frente A: Externo 1 · Sensor y resultado

> Solo el dueño del frente escribe este archivo. Actualizalo al terminar cada tarea.

## Fase 6 · comprobación local, CI y candidato de A (2026-09-27)
- Continuación solicitada por Josué. Integrada la base `main@4f5beb8` mediante
  `33af5a8`, incluidas las correcciones de C y las excepciones de privacidad
  aprobadas por el Frente 0. El soak realtime de F5 sigue activo; no se reinició
  ni se reemplazó por la corrida acelerada.
- `tools/capture/release_check.py`: comprobación local de solo lectura para A.
  Reutiliza el preflight, exige etiqueta explícita real, resolución registrada
  con N completo y reporte realtime aprobado de 48 h. Comprueba compromiso,
  asignaciones, índices, conteos y coherencia con el preregistro, sin recalcular
  estadísticas de C ni revelar datos en la salida. No genera la resolución.
  Los casos de prueba son inventados, aunque uno use la etiqueta `real` para
  probar esa condición; no constituyen el primer experimento real de Josué.
- `scripts/ci_a.py`: comando ejecutable para CI/local, desde un commit limpio.
  Verifica contratos, privacidad, todos los tests de A y un smoke sintético;
  opcionalmente reconstruye y prueba el EXE, crea ZIP completo, manifiesto de
  archivos con SHA-256 y checksum del ZIP. Relee el ZIP y verifica cada archivo.
  Falla ante chequeos rechazados, cambio de fuentes o archivos privados/enlaces
  en el bundle. Logs y bases de prueba quedan ignorados; no se publican.
- La opción `--history` audita las referencias Git disponibles. Dependencias
  mantienen los rangos existentes; se registra Python/PyInstaller y el commit,
  sin prometer reproducibilidad del binario byte por byte entre instalaciones.
- **Integración pendiente de 0:** `scripts/ci-frente-a.yml` está lista para copiar
  a `.github/workflows/frente-a.yml`. A entrega la plantilla en su carpeta y no
  edita la infraestructura global fuera de su reparto. Usa Ubuntu/Windows y
  Python 3.11; sube exclusivamente recibo, manifiesto, checksum y ZIP exitosos.
  No hay remoto Git configurado en esta copia; no se ejecutó GitHub Actions.
- **C/D/0:** producir la primera resolución real, integrar y validar el instalador
  NSIS y decidir tag/firma/publicación. Un CI de A verde conserva
  `release_approved=false`; los datos reales y la comprobación de 48 h son locales.
- Datos revisados: faltan `journal.jsonl` y `activity.sqlite` bajo `../data`;
  tampoco se encontró journal en las dos ubicaciones habituales de Electron
  revisadas en F4, ni está configurado `NDE1_DATA_DIR`. Se solicitó la ubicación
  si existe otra carpeta real. No se recorrió el perfil del usuario.
- Uso y límites: `scripts/README.md` y `tools/capture/README.md`.

### Evidencia y pendientes de la entrega F6
- Implementación: `e928e268ddf16340db08baf2c7e29143596a04c6`. La ejecución local
  de `scripts/ci_a.py --out build/phase6-candidate-20260927 --build-sidecar --history`
  terminó con exit 0 desde ese commit limpio: contratos, privacidad, tests de A,
  smoke sintético, compilación nueva y smoke del EXE aprobados. Recibo:
  `build/phase6-candidate-20260927/ci-report.json`, con `checks_passed=true` y
  **`release_approved=false`**. Python 3.11.9; PyInstaller 6.22.3; Windows x64.
- Tests de A: **182 passed, 1 skipped** (63.42 s); el skip corresponde al EXE
  opt-in, probado por separado sobre el binario recién compilado. Las **39 pruebas
  nuevas** también pasaron juntas. La plantilla YAML fue parseada y comprobada
  localmente; esto no equivale a ejecutar GitHub Actions ni su job de Linux.
- Scanner de privacidad, incluido historial: **265 archivos, cero errores y
  36 avisos**. Las excepciones proceden de la base aprobada por 0; A no amplió
  la allowlist. Los avisos documentales/históricos y las cinco imágenes siguen
  requiriendo revisión manual antes de publicación; el scanner no hace OCR.
- Candidato para D: `build/phase6-candidate-20260927/nde1-core-windows-x64.zip`.
  Contiene el bundle completo de **140 archivos**, más su manifiesto; tamaño
  **32.715.016 bytes**. SHA-256 del ZIP:
  `3246c313661a444ab53c6ad0f06ef20bfbb6ca065e45e6065414158fdc6f98fb`.
  En la misma carpeta están `bundle-manifest.json` y `SHA256SUMS.txt`.
  El bundle sin comprimir está en `dist/nde1-core/` dentro de esa salida:
  consumir la carpeta completa, incluido `_internal/`. Se verificaron CRC y
  hashes de todos los archivos del ZIP. Artefactos locales ignorados por Git;
  no hay tag, firma, push ni publicación. Recompilar si cambia la base integrada.
- Suite integrada: **333 passed, 2 skipped, 1 failed** (221.05 s), registrada en
  `build/phase6-full-suite.log`. Falló B:
  `tests/runtime/test_b2_windows.py::test_delay_distractions_minimizes_only_our_window_and_restores_it`,
  porque esperaba una ventana minimizada y obtuvo dos. La repetición aislada
  pasó (1 test, 5.19 s), pero **no elimina el defecto de aislamiento observado**.
  La regla productiva de WhatsApp también selecciona una ventana ajena al Tk del
  fixture, y la aserción fallida evita llegar a la restauración del test.
- Se reparó únicamente el efecto de esa prueba: su registro SQLite se leyó sin
  modificarlo y se verificaron HWND, PID y estado minimizado antes de restaurar.
  De dos ventanas registradas, el Tk ya estaba cerrado y se restauró la restante;
  ninguna quedó minimizada y no se leyeron títulos. Recibo agregado:
  `build/phase6-runtime-window-cleanup.json`. **Para B/0:** limitar el fixture
  Win32 a los PID de sus propias ventanas y garantizar restauración con
  `try/finally`, incluso ante aserciones fallidas. A no modificó código de B.
- Comprobación local de release: `build/phase6-local-check.json` rechaza la
  carpeta real incompleta por ausencia de SQLite/journal, línea base, etiqueta
  explícita y resolución; las 48 h también siguen pendientes. La demo sintética
  pasó la coherencia de una resolución con 44 asignaciones verificadas, pero
  **no pasó el requisito de datos reales** (`build/phase6-demo-check.json`).
- Soak F5 al registrar esta evidencia: `status=running`, PID 57732, unos
  **68 minutos**, 4.069 muestras, diez ticks sin observación previstos, un tick
  perdido por el planificador y cero problemas reportados; integridad correcta,
  crecimiento de handles cero. Sigue usando muestras sintéticas, sin captura
  nativa. `wall_48h_completed=false` y `checks_passed=false`: no se declara
  aprobado hasta finalizar y revisar el reporte completo.
- **F6 global pendiente:** datos y primera resolución reales; finalización del
  soak de 48 h; corrección/verificación del aislamiento de B; activación de CI
  por 0 y sus ejecuciones remotas; instalación/desinstalación NSIS por D;
  revisión final de privacidad y decisión de firma/tag/publicación por 0.

## Fase 5 · estabilidad, sidecar y logs (2026-09-27)
- Continuación solicitada por Josué; eligió **muestras sintéticas** para el soak.
  Se integró `main@6905b88` en `frente-a` mediante `0012efa`. El instalador NSIS
  sigue siendo responsabilidad de D; A entrega el sidecar y evidencia del sensor.
- `tools/capture/soak.py` ejecuta muestras sintéticas sobre el compresor, Sampler y
  SQLite reales, con durabilidad normal de producción. Comprueba integridad,
  solapamientos, retención, estados permitidos y crecimiento de heap/handles.
  Ejercita huecos, saltos y retrocesos de reloj y reaperturas cada seis horas.
  No inicia Win32, no escribe al journal, no toca datos de la aplicación y no
  representa actividad real de Josué. Uso, límites y parada: `tools/capture/README.md`.
- Refuerzos productivos: avisos de muestreo limitados a uno por minuto con conteo
  y clase del error; mensajes y tracebacks privados siguen excluidos. Si SQLite
  falla durante inicialización, su conexión se cierra antes de propagar el error,
  permitiendo reintentar sin acumular handles. Sin cambios en `outcome@1` o contratos.
- **Soak real de 48 h iniciado**, con ventana oculta: 2026-09-27 13:43:53 Bolivia
  (17:43:53 UTC). Fin previsto: 2026-09-29 13:43:53 Bolivia, si el equipo permanece
  activo. PID de trabajo inicial **57732** (el launcher fue 60500).
  Estado local: `build/phase5-realtime-20260927/status.json`;
  métricas: `build/phase5-realtime-20260927/metrics.jsonl`.
  Sigue **pendiente** hasta observar `status=completed`, `checks_passed=true` y
  `wall_48h_completed=true`. El estado inicial fue verificado junto con el proceso vivo.
  Para detener: crear `build/phase5-realtime-20260927/stop.request`.
- Carga acelerada de 48 h lógicas: `build/phase5-accelerated-20260927/status.json`.
  **Completada y aprobada**, exit 0: 172.800 segundos lógicos, **172.320 muestras**,
  480 ticks sin observación previstos y siete reaperturas. Duración real **1660.672 s**
  (27 min 41 s), fin 2026-09-27 18:03:40 UTC. Integridad correcta; cero tramos
  inválidos, solapados, anteriores al último corte de retención o con estados ajenos
  al escenario. 49 reportes: aumento máximo de heap 203.478 bytes, de handles **0**;
  SQLite/WAL/SHM alcanzaron 4.492.792 bytes y quedaron en 368.640 bytes al cerrar.
  El SQLite final contiene 3.576 tramos. No equivale a 48 h transcurridas:
  `checks_passed=true`, **`wall_48h_completed=false`**.
  Una suspensión o cierre forzado no se convierte en aprobación ni se rellena con
  observaciones inventadas. Los directorios de ensayo y binarios están ignorados.
- Última comprobación de la corrida realtime al cerrar esta entrega: proceso vivo,
  1.200 muestras, unos 20 minutos transcurridos, cero ticks perdidos, cero problemas
  reportados y stderr vacío. Sigue pendiente; no se instaló monitor ni tarea de inicio.
  Consultar el estado vivo antes de declarar F5 aprobada; una fecha prevista no es evidencia.
- Sidecar reconstruido desde un workpath nuevo `build/phase5-sidecar-20260927`:
  consumir **TODO `dist/nde1-core/`**, incluido `_internal/`. Smoke sobre el EXE:
  **1 passed** (25.03 s), con HTTP real, rutas de A rechazando solicitudes sin token,
  pausa persistida y reinicio. También se inspeccionó el bytecode del EXE: contiene
  `_report_error` y el cierre de la conexión ante fallo de inicialización.
  SHA-256 del EXE: `ff89cf0bc41aa82617ed5502a8614ff65ba2155910ed0257109b74370eb14fe4`.
  Manifiesto local de fuentes/EXE: `build/phase5-artifacts.json`.
  Recompilar al integrar cambios posteriores de 0/B/C; esta evidencia corresponde
  exactamente a la base indicada más los cambios de A.
- Validación: **143 passed, 1 skipped** en `tests/sensing` (58.92 s; el skip es el
  EXE opt-in, que pasó por separado). Exportación de contratos correcta. La suite
  general dio **283 passed, 2 skipped, 1 failed** (256.96 s), sin omitir el fallo:
  `tests/council/test_council_lifecycle.py::test_full_lifecycle_resolves_at_n_and_reveals_the_committed_seed`
  falló con `KeyError` al buscar una resolución ausente. No se alteró C desde A.
  Para C: el test suministra exactamente `2*n` outcomes; la asignación por bloques
  de cuatro no garantiza n por brazo cuando n es impar. Revisar los conteos y el
  criterio de término del fixture antes de asumir una resolución inmediata.
- Ensayo Win32 acotado, sin leer ventanas: 5.000 consultas del propio proceso y
  5.000 de un PID inválido, **201 handles antes y después**. Evidencia local:
  `build/phase5-native-handles.json`. No sustituye un soak nativo prolongado.
- Scanner con los archivos finales preparados y `--history`: **256 archivos,
  7 errores y 34 avisos**, exit 1; sin hallazgos nuevos en los cambios de F5 de A.
  El email de `app/package-lock.json:4158` aparece en la copia actual y dos commits;
  quedan dos emails en el historial de `scripts/check_private_allow.txt` (`4f5beb8`)
  y rutas de usuario históricas en `tests/runtime/test_soak.py:11` (`20637ab`,
  `455cba3`). No se imprimen los valores ni se amplía la allowlist para ocultarlos.
  El scanner lee todas las referencias Git, también entregas de otros frentes
  aún no integradas en A. Los avisos incluyen rutas documentales y cinco imágenes
  cuya información visual no fue auditada por el scanner. Revisión pendiente de 0.
  La comprobación adicional de la copia actual, sin historial, dio **256 archivos,
  1 error y 15 avisos**: el único error es el email del lockfile ya indicado.

### Revisión de seguridad del ámbito de A
- Revisión manual de `core/sensing`, herramientas de captura y frontera HTTP del
  sidecar. No se ejecutó el comando `/security-review`, que no está disponible
  en esta sesión; no se presenta esto como una auditoría completa de la aplicación.
- Corregidos: crecimiento de stderr ante errores sostenidos/intermitentes y
  conexiones SQLite sin cierre explícito tras una inicialización fallida.
  Regresiones verificadas con errores que contienen un canario privado, SQLite
  inválido real y recuperación posterior; sin mocks de disco ni del sistema operativo.
- Las cuatro rutas de A requieren autenticación en la aplicación compuesta y en
  el EXE. Las solicitudes sin token o con token incorrecto se rechazan antes de
  leer/escribir el almacén. Resúmenes y reportes no exportan títulos ni procesos.
  SQL parametrizado; títulos locales acotados; pausa omite lectura de ventanas;
  eliminación por retención mantiene `secure_delete` y checkpoint del WAL.
- Límites: este soak mide Python/SQLite; el smoke Win32 y el EXE son breves.
  Faltan soak del escritorio completo e instalación/desinstalación NSIS por D.
  No se certifica cifrado local, borrado forense ni ausencia absoluta de fugas.
- Para 0/D, antes de compartir logs generales: `core/__main__.py` imprime el token
  temporal en stderr si falta `NDE1_TOKEN`; Electron sí lo suministra. Los errores
  generales de arranque/HTTP también pueden incluir rutas en traceback. A no
  cambió la composición ni el protocolo de inicio congelados; definir y probar
  la política de redacción/exportación de logs en esos componentes.

## Fase 4 · primer experimento real (2026-09-27)
- Continuación solicitada por Josué. Se interpreta como **F4 del plan posterior a la
  hackathon** (primer experimento real y `withdraw`), manteniendo A en sensor/medición.
- Entrega de A: `tools/capture/preflight.py --data-dir <carpeta>` y documentación en
  `tools/capture/README.md`. Audita en solo lectura la etiqueta, semana de línea base,
  integridad del journal, referencias/duplicados, coherencia de outcomes y SQLite de A.
  Comprueba reglas preregistradas y cambios de clasificación durante experimentos.
  No escribe eventos, no inicia captura ni experimento, no revela semillas ni efectos.
- Requiere cerrar normalmente el núcleo para leer SQLite sin WAL; no repara ni elimina
  archivos. La salida solo trae agregados y códigos de problema. Los tests verifican
  que tanto los bytes como la lista de archivos queden iguales antes y después.
  La semana se mide como intervalo calendario entre fechas con outcomes de línea base,
  incluyendo ambas; se reporta por separado cuántos días tuvieron observaciones. No
  exige siete días trabajados ni sustituye el mínimo de muestra o potencia del consejo.
- Comprobación local: `../data` carece de `journal.jsonl` y `activity.sqlite`; falta
  la semana de línea base. `../demo-data` está marcado **sintetico** y se rechaza para
  un experimento real (también tenía WAL durante la lectura). No se confunde la demo
  ni la captura breve de 20 s con datos reales de una semana.
  Tampoco existen datos bajo las ubicaciones revisadas `%APPDATA%/nde1-app/data` y
  `%APPDATA%/Consejo N-de-1/data`. Si se usa `NDE1_DATA_DIR`, hay que comprobar esa
  ubicación explícita; no se hizo una búsqueda indiscriminada por el perfil del usuario.
- La captura prolongada y el primer experimento real siguen pendientes de datos reales.
  No se implementó una retirada usando `block_abort`, ni se alteró `outcome@1`.
- Validación final de A: **21 pruebas nuevas de preflight aprobadas**;
  `export_contracts.py --check` correcto. La corrida de suite completa terminó con **265 passed,
  2 skipped y 1 fallo** en `test_a_true_effect_is_found_with_the_preregistered_stratified_test`:
  el simulador devolvió `not_supported` donde el test exige `supported`. No se cambió
  código productivo del sensor, reglas, simulador, consejo ni estadísticas en esta entrega.
- Diagnóstico para C: `core/simulate/engine.py` siembra las trazas e IDs del consejo,
  pero `Council.run()` genera la semilla del experimento con `secrets.token_hex(32)`;
  los IDs de bloques también usan `secrets`. `--seed 7` no fija el sorteo completo.
  Corregir la inyección de aleatoriedad **solo en simulación**, conservando la semilla
  segura en uso real y la verificación del sorteo. No elegir otra traza/semilla a mano
  para ocultar este fallo ni relajar la prueba desde A.
- El test de integración pasó al repetirlo aisladamente **sin cambios**. Se conserva
  el fallo anterior como incidencia intermitente; no se presenta la suite completa como verde.
- Scanner de la copia de A con los archivos nuevos preparados: sin hallazgos nuevos;
  permanece el email del lockfile ya reportado (exit 1) y avisos de rutas en docs.

### Pedidos de contrato a 0/B/C/D para completar F4
1. Definir el evento y estado `withdraw` a nivel experimento, su ruta autenticada y
   semántica de semilla/resolución. Hoy `JournalKind`, `ExperimentProgress` y
   `ExperimentProvider` no contienen retirada. Conservar los outcomes históricos;
   distinguir retirada de "Hoy no" de un bloque y de la salida de emergencia.
2. B/C: definir qué sucede con asignaciones ya confirmadas y bloques pendientes;
   restaurar intervenciones y evitar nuevas aplicaciones/sorteos del experimento
   retirado. A no escribe ni filtra retrospectivamente outcomes por esa condición.
3. 0/B/C: congelar la configuración experimental pertinente. Actualmente `PUT
   /settings` permite modificar listas de distracción, navegadores y whitelist durante
   un experimento; B consulta ajustes actuales. Eso cambia features/intervenciones,
   aunque el matcher de trabajo y las constantes de `outcome@1` se mantengan iguales.
   A detecta cambios journalizados, pero no puede impedirlos desde su interfaz actual.
4. D/0: definir si retirar el experimento conserva la captura ordinaria o también la
   pausa por decisión del usuario. La pausa de A sigue siendo temporal (1–480 min);
   no usarla como una retirada permanente implícita.

Estos pedidos corresponden a la siguiente integración; no son requisitos para usar
el preflight. Una salida 0 del preflight no sustituye el verificador/potencia del consejo.

## Hackathon · entrega prioritaria (2026-09-27)
- **`synth.py` LISTO para integrar en C**, basado en `main@15b4f50` y el brief definitivo.
  Implementa la firma `SynthDay` con `latency_scale` opcional. Importar
  `from tools.capture.synth import synth_day`; pasar `date`, bloques sintéticos,
  `"tdah_mananas"`, `random.Random(seed)` y factores por ID si corresponden.
- Distribución lognormal, medianas 25/8 min, sigma 0.6; 5% apagados, componente de
  demoras largas matinales, 80% de primeras ventanas matinales en distracción,
  1–4 cambios, trabajo ≥16 min y actividad/pausas fuera de bloques.
- Solo trazas: el resultado sigue saliendo del `evaluate_block` real. No se modificó
  `outcome@1`, contratos, sorteo ni journal. Todo es sintético, sin estimaciones clínicas.
- **Integración C:** dejar ≥106 minutos entre inicios y hasta medianoche; las ventanas
  de observación incluyen margen para completar trabajo después de los 90 min.
  Solo matchers genéricos de demo: se usa el primer matcher de proceso, o el de título.
  No pasar bloques reales. `DATA_LABEL` es responsabilidad del simulador.
- Pruebas específicas: **12 passed**, con determinismo, clasificación real, distribución,
  censura, apagados, escala, privacidad básica de entradas y ventanas inválidas.
  Comando: `python -m pytest -q tests/sensing/test_synth.py`.
- **Scanner listo:** `scripts/check_private.py`, allowlist explícita y guía en
  `scripts/README.md`. Revisa archivos versionados, y con `--history` líneas añadidas
  y eliminadas de todas las referencias, incluidos merges. No imprime coincidencias
  privadas. Las pruebas usan repositorios Git temporales reales, sin mocks.
- **Resultado sobre `main@76b9d88`:** 240 archivos; con `--history`, exit **1**,
  **3 errores correspondientes a un único email** (copia actual y dos apariciones
  históricas), y **25 avisos de rutas en docs** entre copia actual e historial.
  Comando desde A: `python scripts/check_private.py --root .. --history`.
- **Pendiente para 0/D antes de publicar:** el lockfile `app/package-lock.json`, en
  `node_modules/glob.deprecated` (línea 4158 en la base T0), contiene un email público
  del mantenedor. El brief solo exceptúa `noreply@anthropic.com`: el scanner lo marca
  como error y no lo agregué a la allowlist. Decidir cómo retirar esa dirección del
  archivo y tratar su presencia previa en el historial antes de publicar.
  Las rutas locales bajo `docs/` se informan como avisos, tal como permite el brief.
  No se modifica ni reescribe el historial desde A.
- Las dos herramientas de esta entrega tienen **30 tests aprobados**: 12 de synth y
  18 de privacidad. Incluyen secretos borrados, otras ramas, secretos añadidos en un
  merge, nombres de archivo sensibles, UTF-16 y redacción de salida.
- La integración `main@bbb356c` ya contiene el generador de A y las entregas de B/C/D;
  esta rama se actualizó a esa base para la validación final. El cambio posterior
  `76b9d88` solo elimina duplicados de `.gitignore`.
- Validación final sobre esa integración: **246 passed, 2 skipped** (144.64 s),
  incluyendo `tests/integration/test_full_cycle.py` con las trazas de A y resolución
  con semilla verificada. Los skips son Ollama live y el ejecutable empaquetado opt-in.
  `python tools/export_contracts.py --check` terminó correctamente.
- El escaneo debe repetirse después de añadir los archivos finales a Git y antes
  del push. No audita archivos sin versionar ni el contenido visual de imágenes/video.
- La captura de días, instalador y soak del plan anterior quedan fuera de esta entrega.

## Estado previo a la hackathon
- 2026-09-27: Fase 2 reforzada con recuperación del sensor, regresión real breve y replay de trazas.
  Sigue pendiente la validación con 2–3 días reales de Josué; no se da por cumplida con la captura breve.
- La entrega inicial `a060e33` ya fue integrada por el Frente 0 (Hito 1).
- Fase 3: sidecar reconstruido con las correcciones de Fase 2 y verificado en Windows.
- Worktree: `n-de-1-frente-a` dentro del proyecto, rama `frente-a`.
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

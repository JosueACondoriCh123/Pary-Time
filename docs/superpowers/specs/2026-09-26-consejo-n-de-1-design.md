# Consejo N-de-1: diseño

Fecha: 2026-09-26 · Autor: Josué Condori (con Claude) · Estado: aprobado para la Fase 0

## Qué es

Una app de escritorio para Windows que hace **experimentos aleatorizados sobre tu forma de arrancar a trabajar**.
Está pensada para personas con TDAH, donde una misma estrategia le sirve a unos y a otros no: lo que le funciona a
otro no te dice nada sobre vos.

Los agentes no dan consejos:
1. Proponen una hipótesis falsable sobre tus propios datos.
2. Un Red Team de otra familia de modelo la ataca con estadística determinista.
3. Se preregistra en un journal con cadena de hashes.
4. La compu sortea y aplica la intervención en tus bloques de trabajo.
5. Al llegar al N preregistrado, un test de permutación dice si en vos funciona.

Encuadre fijo: **ajustes de flujo de trabajo medidos sobre una sola persona. No es tratamiento ni consejo médico.**

## Por qué es nuevo

Búsqueda del 2026-09-26, sin pretensión de exhaustividad:
- QuantifyMe (MIT, 2018) hace N-de-1 en el celular, para salud, con hipótesis manuales y sin LLM.
- `ErikBjare/quantifiedme` son dashboards sobre ActivityWatch, sin experimentos.
- `oci-agent` hace inferencia causal observacional genérica.

No se encontró nada que combine hipótesis generadas por agentes, un Red Team estadístico, aleatorización ejecutada por
la propia compu y preregistro con cadena de hashes.

La arquitectura del consejo viene de Night Council, del mismo autor.

## Decisiones cerradas

| Tema | Decisión |
|---|---|
| Usuario | Personas con TDAH; herramienta personal, 100% local |
| Métrica primaria | Latencia de arranque (reglas en `docs/outcome-rules.md`) |
| Unidad aleatorizada | Bloque programado por la persona |
| Intervenciones | Abrir el trabajo solo · Primer paso mínimo · Retrasar distracciones · Cuenta regresiva |
| LLM | Local con Ollama (RTX 4050, 6 GB): un modelo a la vez; Scout y Red Team de familias distintas |
| Interfaz | Electron + React/Vite |
| Núcleo | Proceso Python 3.11 aparte (FastAPI en 127.0.0.1 con token local) |
| Plazo | MVP en 2–4 semanas, con 4 agentes en paralelo (`docs/coordinacion/`) |

## Arquitectura

```
Electron (app/) ──HTTP 127.0.0.1 + X-NDE1-Token──▶ núcleo Python (core/)
                                                   ├─ sensing (A): sensor win32 → SQLite local; outcome; categorize
                                                   ├─ runtime (B): bloques, sorteo, intervenciones, overlay
                                                   ├─ council (C): snapshot → Scout → verificador → Red Team → Allocator
                                                   │               → constitución → preregistro; análisis; ledger
                                                   └─ journal (0): cadena de hashes, fuente de verdad compartida
```

Las interfaces entre frentes están en `core/interfaces.py`, y los modelos de datos en `core/contracts.py`. Ambos
quedaron congelados al cerrar la Fase 0.

### Flujo de un día
1. A la noche se planean los bloques de mañana y se confirman (`POST /blocks/confirm`). El runtime sortea la condición
   de cada bloque elegible y la sella en el journal (`block_confirmed`, `assignment`). La condición se revela recién a
   la hora del bloque. La única excepción es `primer_paso`, que pide escribir el paso de antemano; queda anotado como
   limitación.
2. A la hora del bloque, el runtime aplica la intervención (`intervention: applied`). Si la compu se prende tarde pero
   dentro de la ventana, la aplica al despertar (`device_wake`).
3. En cada tick, el runtime pide los tramos del sensor y llama a `evaluate_block`. Cuando el resultado es final,
   revierte, escribe el `outcome` y avisa al consejo (`after_outcome`).
4. Una vez por semana, o a mano, se reúne el consejo:
   1. Arma el snapshot agregado, sin títulos.
   2. El Scout propone una hipótesis.
   3. El verificador chequea citas y cifras.
   4. El Red Team corre sus herramientas con poder de veto: potencia, confusores y comparaciones múltiples. Además
      escribe un pre-mortem, que no tiene veto.
   5. El Allocator elige por información esperada por unidad de fricción, ponderada por el ledger.
   6. La constitución aplica sus reglas.
   7. Se escribe el `preregistration`, con el hash de la semilla, antes del primer sorteo.
5. Al llegar al N preregistrado en ambos brazos, el consejo corre el test preregistrado y escribe la `resolution`,
   donde revela la semilla. El panel nunca muestra el efecto antes del N.

### Estadística
- **Línea base:** la primera semana corre sin intervenciones. Sirve para estimar la varianza de log-latencia.
- **Sorteo:** bloques permutados de 4 (`core.contracts.permuted_arm`), deterministas desde la semilla.
- **Test:** permutación, a una cola, sobre la diferencia de medianas de latencia. Los censurados cuentan como 90 min,
  lo que por rangos es conservador. El análisis es por intención de tratar: los bloques abortados cuentan en su brazo
  y los `device_off` se excluyen. Se valida contra `scipy.stats.permutation_test` y con simulación de efecto conocido.
- **Potencia:** el Red Team veta si el N necesario para el efecto propuesto no entra en unas 3 semanas de bloques.
- **Comparaciones múltiples:** el α se ajusta por el número de hipótesis ya probadas en el ledger (alpha-spending
  sobre `family_alpha`).
- **Ledger:** posterior Beta(1 + apoyados, 1 + no apoyados) por intervención.
- **Veto regret:** el 10% del presupuesto (`exploration_fraction`) prueba hipótesis vetadas por evidencia débil,
  nunca las vetadas por la constitución, y mide cuántas replican.
- **Si el LLM falla:** el Allocator elige directo entre las 4 intervenciones (`source: allocator_fallback`).

### Constitución
- Un solo experimento activo a la vez.
- Nunca se interviene fuera de los bloques declarados.
- Hay un tope de bloques con intervención de alta fricción (`high_friction_max_fraction`).
- La lista blanca nunca se minimiza.
- Abortar ("hoy no") siempre es posible y queda como dato.
- La salida de emergencia restaura todo.

### Privacidad
- Los títulos de ventana crudos solo existen en el SQLite local y se borran a los `raw_retention_days` (14 por defecto).
- El journal nunca lleva títulos ni textos del usuario: lo impiden `append_typed` y `_FORBIDDEN`, y lo cubre un test.
  Por eso el reporte se puede compartir con un profesional.
- El LLM corre local y solo ve el snapshot agregado.

### Manejo de errores
- **El proceso Python se cae:** Electron lo reinicia. Al arrancar, el runtime restaura las ventanas que quedaron
  minimizadas sin revertir (`intervention: reverted, reason: recovery`).
- **Dos núcleos sobre el mismo `data_dir`:** el `LoopLock` del sistema operativo lo impide.
- **Ollama no disponible:** el consejo usa el respaldo del Allocator.
- **Journal con la última línea rota:** se recupera sin perder la cadena (comportamiento heredado de Night Council).

## Verificación
- Sin mocks. Los fixtures son trazas reales del sensor, sanitizadas, y respuestas de Ollama grabadas.
- `outcome`: censura, interrupciones de menos de 60 s, `device_off` y `started_early`.
- Sorteo: determinismo, balance y verificación del compromiso de la semilla.
- Análisis: contraste con scipy; simulación marcada como sintética.
- Intervenciones: integración en Windows con Notepad real, incluido matar el núcleo a mitad de camino.
- De punta a punta: una semana de línea base real y `GET /journal/verify` en ok.

## Fuera de alcance del MVP
- Agregar datos de varias personas (plataforma para investigadores de HCI).
- macOS y Linux.
- Métricas de sostener el foco o cortar el hiperfoco.
- Notificaciones del sistema.

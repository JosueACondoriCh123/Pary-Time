# Reglas de la métrica primaria: `outcome@1`

Documento **normativo**. `core.sensing.outcome.evaluate_block` (Frente A) lo implementa y el análisis (Frente C)
depende de él. Cambiar una regla es un contrato nuevo (`outcome@2`), nunca una edición silenciosa, porque cada
`outcome` y cada `preregistration` citan la versión.

Constantes (`core.contracts.OUTCOME_RULES`):

| Constante | Valor | Significado |
|---|---|---|
| `work_run_s` | 900 | Un arranque válido es un tramo de trabajo de 15 min |
| `gap_tolerance_s` | 60 | Los huecos más cortos que esto no cortan el tramo |
| `idle_max_s` | 120 | Sin teclado ni mouse hasta 2 min en la app de trabajo sigue contando (leer). Lo marca el sensor en `ActivitySpan.idle` |
| `censor_s` | 5400 | A los 90 min sin haber empezado un tramo, el bloque queda censurado |

## Definiciones

Sea `P = block.planned_start_ms`.

1. **Recorte:** solo cuentan los tramos del sensor dentro de `[P, P + censor_s + work_run_s + gap_tolerance_s)`. Lo
   anterior a `P` no cuenta, salvo por la regla 5.
2. **Segmento de trabajo:** un `ActivitySpan` con `categorize(span, block, settings) == work`, `idle == false` y
   `locked == false`.
3. **Hueco:** tiempo entre dos segmentos de trabajo consecutivos. Puede estar ocupado por otra app, por inactividad,
   por la compu bloqueada o por la **ausencia de tramos** (compu apagada o suspendida).
4. **Tramo de trabajo:** una secuencia maximal de segmentos de trabajo donde cada hueco dura menos de
   `gap_tolerance_s`. Su **inicio** es el inicio de su primer segmento. Su **largo** va desde ese inicio hasta el fin
   del último segmento, huecos incluidos.
5. **Arranque temprano:** si en `P` ya hay un segmento de trabajo en curso (un tramo lo cubre), el inicio del tramo
   se toma como `P`. Latencia 0 y `started_early = true`.
6. **Tramo que califica:** el primero cuyo inicio es anterior a `P + censor_s` y cuyo largo llega a `work_run_s`.
   Puede completarse después de `P + censor_s`.

## Resultado

- **`started`:** existe un tramo que califica. `latency_s = (inicio − P) / 1000`, siempre ≥ 0, y
  `work_run_start_ms = inicio`. Es final apenas el largo llega a `work_run_s`.
- **`device_off`:** ningún tramo del sensor se solapa con `[P, P + censor_s)`. Solo se decide cuando
  `now_ms ≥ P + censor_s`. Se excluye del análisis; no es lo mismo que no arrancar.
- **`censored`:** `now_ms ≥ P + censor_s`, no hay tramo que califique, no es `device_off` y ningún tramo iniciado
  antes de `P + censor_s` sigue abierto. Abierto significa que su último segmento terminó hace menos de
  `gap_tolerance_s` respecto de `now_ms`, o sigue en curso. `latency_s = null` y `censored = true`. El análisis lo
  toma como 90 min.
- **`pending`:** cualquier otro caso.

## Variables derivadas (`OutcomeFeatures`)

Se calculan sobre `[P, E)`, con `E` = inicio del tramo que califica si `started`, o `P + censor_s` si no:

- `pre_start_switches`: cantidad de cambios de `process` entre tramos consecutivos del sensor en `[P, E)`.
- `first_category`: categoría del primer tramo que cubre o empieza después de `P`. `none` si no hay ninguno.
- `distraction_s_before_start`: segundos en tramos `distraction` dentro de `[P, E)`.
- `sensor_coverage`: fracción de `[P, E)` cubierta por tramos del sensor. Si `E = P` (arranque temprano), vale 1.
- `started_early`: la regla 5.

`evaluate_block` es una **función pura**: el mismo input da el mismo output, y el reloj entra como `now_ms`.

## Pausa de privacidad

Durante `POST /activity/pause`, el sensor no graba títulos pero **sí** escribe tramos `process = "__paused__"`,
`title = ""`, `idle = true`. Así una pausa cuenta como "no trabajo" y no se confunde con compu apagada.

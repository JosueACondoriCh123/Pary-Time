# Frente C: Claude · Consejo y estadística

> Solo el dueño del frente escribe este archivo. Actualizalo al terminar cada tarea.

## Estado
- Fase 1 terminada (2026-09-26).
- Fase 2 terminada (2026-09-26). Corrida real grabada: `data/cassettes/`, respuestas de Qwen y Granite sobre el snapshot SINTÉTICO.

## Hecho
### Fase 1: estadística (`core/stats/`)
- `permutation.py`: test preregistrado `permutation_median_diff_one_sided@1`. Exacto hasta 200k particiones (vectorizado) y Monte Carlo con semilla fija por encima. Coincide con `scipy.stats.permutation_test` en los casos exactos.
- `power.py`:
  - N por brazo sobre log(latencia + 60 s) con la eficiencia de la mediana (2/π), y factibilidad en semanas. La simulación confirma la potencia prometida.
  - `mde_ratio`: el efecto mínimo detectable con un N dado.
- `multiplicity.py`: alpha-investing (Foster y Stine). El primer α con `family_alpha` = 0.05 es 0.02375.
- `ledger.py`: Beta(1 + apoyados, 1 + no apoyados) por intervención.
- `simulation.py`: experimentos SINTÉTICOS. Tasa de falsos positivos ≤ α.
- `analysis.py`: análisis por intención de tratar hacia los números de la `resolution`.

### Fase 2: consejo (`core/council/`)
- `journal_view.py`: lectura tipada del journal, que es la única fuente del consejo.
- `snapshot.py`:
  - Filas por bloque control con outcome final y `facts` por franja, tipo de tarea, día y primera categoría. Sin títulos. Se congela con sha256.
  - Lo que ve el LLM es una tabla compacta con las últimas 30 filas.
- `verifier.py`: cada cifra de la justificación tiene que estar en el snapshot o en la propia hipótesis, y cada `block_id` citado tiene que existir.
- `red_team.py`: herramientas con veto.
  - `power`: N inflado por la fracción censurada; tope de 3 semanas.
  - `confounders`: ≥70% de los bloques en un mismo día o tipo de tarea.
  - `multiplicity`, `constitution`.
  - El pre-mortem del LLM no tiene veto.
- `llm_roles.py`: Scout `qwen3.5:4b` y pre-mortem `granite4.2:8b`. Los prompts están en `prompts/`, versionados por hash.
- `allocator.py`: elige por ganancia × prior / (fricción × semanas).
  - **Respaldo sin LLM:** preregistra el efecto mínimo detectable dentro del tope.
  - **Exploración:** usa el 10% del presupuesto en hipótesis vetadas solo por potencia o confusores.
- `council.py`: reunión completa y preregistro con compromiso de la semilla. La semilla queda en `data_dir/council/seeds/`.
- `experiments.py`:
  - `ExperimentProvider` para el Frente B.
  - Resolución al llegar al N, con semilla revelada y verificación del sorteo contra `permuted_arm`.
  - Progreso sin efecto, ledger, veto regret y `/report`.
- Rutas de C implementadas y reunión semanal automática (cada 30 min chequea si pasó una semana).

## Hallazgos que afectan a todos
1. **Potencia real de un N-de-1:** con σ_log ≈ 0.65 y 2 bloques por día, en 3 semanas solo se detectan efectos grandes (ratio ≈ 0.5). Una hipótesis con moderador ("solo mañanas") deja 1 bloque por día y pide más de 4 semanas. El Red Team la veta por potencia, lo que cuenta como evidencia débil y la vuelve explorable. **Más bloques por día = experimentos más cortos.** Frente D: vale la pena que el planificador lo diga.
2. **La mediana con muchos empates es gruesa:** con 15 valores idénticos por brazo, p ≈ 0.5. Por eso `power` infla N por la fracción censurada.
3. **Ollama + qwen3.5:** con el razonamiento activo, el modelo gasta el presupuesto pensando y devuelve el contenido vacío. `for_ollama` manda `reasoning_effort: "none"` por defecto.
4. **Contexto de 4096 tokens:** el prompt del Scout quedó con un techo de unos 2240 tokens (medido) para cualquier duración de la línea base.
5. **Bug heredado:** el validador de JSON de Night Council no soporta `"null"`. Corregido acá; en Night Council sigue igual.

## Corrida real (qwen3.5:4b + granite4.2:8b, 2026-09-26)
- **Sin restricción:** el Scout propuso ratios de 0.65–0.7 (realistas) y el Red Team vetó las 3 por potencia (12–18 semanas). En la primera también detectó un confusor real del fixture ("escritura" = "mañana" en el 100% de los bloques).
- **Cambios de diseño a partir de eso:**
  1. El Scout recibe como restricción el efecto mínimo detectable.
  2. Si todo lo del Scout se veta, entra el respaldo.
  3. El pre-mortem se escribe solo para lo elegido (1 llamada en vez de 8).
- **Con restricción:** `retrasar_distracciones` con ratio 0.38 pasó todas las herramientas; las otras dos quedaron apenas por encima (3.7 y 5.4 semanas).
- **Latencias:** Scout 37 s, pre-mortem 39 s.

## Limitación conocida
El verificador comprueba que cada cifra EXISTA en el snapshot, pero no que diga lo que el modelo afirma. En la corrida real, Qwen escribió "50% de escritura censurados" cuando es 4%; el 50 existe en otro lado del snapshot. No cambia la decisión (las herramientas usan los datos, no el texto), pero la justificación que ve la persona puede estar mal. Mejora posible: atar cada porcentaje a un `pct_*` del bucket citado.

## En curso

## Para el Frente B (ExperimentProvider)
- `ctx.experiments.active()` devuelve `None` si no hay experimento o si la semilla local falta o no coincide con el compromiso. En ese caso se asigna control.
- Después de escribir cada `outcome` final, llamar `ctx.experiments.after_outcome(outcome)`, que puede escribir la `resolution`.

## Bloqueos
Ninguno.

## Pedidos de contrato
<!-- Formato: fecha · qué cambiar exactamente · por qué. El Frente 0 responde acá abajo de cada pedido. -->

## Cómo probar lo entregado
- `.venv\Scripts\python -m pytest -q tests/stats tests/council`
- Con Ollama y los modelos bajados: `$env:NDE1_LIVE_TESTS=1; .venv\Scripts\python -m pytest -q -s tests/council/test_ollama_council.py`

# Frente C: Claude · Consejo y estadística

> Solo el dueño del frente escribe este archivo. Actualizalo al terminar cada tarea.

## Estado
- Fase actual: 1 terminada (2026-09-26) · sigue la Fase 2 (consejo con Ollama)

## Hecho
- `core/stats/permutation.py`: test preregistrado `permutation_median_diff_one_sided@1`. Exacto hasta 200k particiones (vectorizado) y Monte Carlo con semilla fija por encima. Coincide con `scipy.stats.permutation_test` en los casos exactos.
- `core/stats/power.py`: N por brazo sobre log(latencia + 60 s) con la eficiencia de la mediana (2/π), y factibilidad en semanas. La simulación confirma la potencia prometida.
- `core/stats/multiplicity.py`: alpha-investing (Foster y Stine). El primer α con `family_alpha` = 0.05 es 0.02375.
- `core/stats/ledger.py`: Beta(1 + apoyados, 1 + no apoyados) por intervención.
- `core/stats/simulation.py`: experimentos SINTÉTICOS. Tasa de falsos positivos ≤ α.
- `core/stats/analysis.py`: análisis por intención de tratar hacia los números de la `resolution`.

## Nota para todos
La diferencia de medianas es un estadístico grueso cuando hay muchos empates (por ejemplo, muchos censurados a 90 min). Con 15 valores idénticos por brazo, p ≈ 0.5. La herramienta de potencia del Red Team va a tener que descontar la fracción censurada de la línea base (Fase 2).

## En curso

## Bloqueos

## Pedidos de contrato
<!-- Formato: fecha · qué cambiar exactamente · por qué. El Frente 0 responde acá abajo de cada pedido. -->

## Cómo probar lo entregado
- `.venv\Scripts\python -m pytest -q tests/stats`

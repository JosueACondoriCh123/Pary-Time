# Texto para la entrega (Devpost o formulario)

**Nombre:** Consejo N-de-1

**En una línea:** tu compu hace experimentos aleatorizados sobre cómo arrancás a trabajar. Un consejo de agentes
locales propone, la estadística veta y la compu ejecuta.

## Qué problema resuelve
En TDAH, las estrategias para arrancar a trabajar le funcionan a unos y a otros no. Los consejos genéricos y las
apps de productividad no pueden decirte qué te funciona **a vos**. La herramienta correcta para eso es un ensayo
N-de-1 (una sola persona, aleatorizado), pero nadie lo hace a mano durante semanas.

## Qué hace
1. Mide, sin que anotes nada, cuánto tardás en arrancar cada bloque de trabajo que declarás (sensor local de
   ventanas).
2. Un consejo de agentes locales delibera:
   - **Scout** (qwen3.5:4b): propone una hipótesis falsable con citas a tus bloques.
   - **Verificador:** rechaza cifras que no estén en tus datos.
   - **Red Team** (granite4.2:8b, otra familia): herramientas estadísticas con poder de veto (potencia, confusores,
     alpha-investing, constitución) y un pre-mortem sin veto.
3. El experimento se **preregistra**, con el hash de la semilla, en un journal con cadena de hashes, antes del primer
   sorteo.
4. La compu **sortea y aplica** la intervención en tus bloques: abrir el trabajo solo, primer paso mínimo,
   minimizar distracciones o cuenta regresiva. Siempre hay salida de emergencia.
5. Al llegar al N, un test de permutación estratificado da el veredicto y **revela la semilla**, para que cualquiera
   verifique que el sorteo no se tocó.

## Cómo lo construimos
- Python (FastAPI, numpy/scipy, pywin32) para el núcleo y Electron + React + TypeScript para la app.
- Ollama local en una RTX 4050 de 6 GB.
- 4 agentes en paralelo (dos sesiones de Claude Code y dos agentes externos), cada uno en su git worktree, con
  contratos congelados (JSON Schema + OpenAPI generados) y coordinación por archivos.
- Más de 200 tests, incluido un ciclo completo acelerado y tests con ventanas reales de Windows.

## Desafíos y aprendizajes
- **El simulador encontró un error nuestro:** la mediana agrupada perdía el efecto cuando se mezclan mañanas y
  tardes (un efecto de ×0.5 se medía como 0.88). Lo reemplazamos por un test estratificado: ahora recupera ~0.5,
  lo detecta en 9 de 10 semillas y no da falsos positivos sin efecto.
- **LLM chico y local:** Qwen con razonamiento activado devolvía respuestas vacías, el prompt no entraba en 4096
  tokens y el modelo inventó porcentajes ("47% de censura" cuando era 0%). Por eso el veto es determinista y el verificador ata cada cifra a su unidad y
  tema.
- **Un N-de-1 tiene poca potencia:** con 2 bloques por día, en 3 semanas solo se detectan efectos grandes. El Scout
  recibe ese límite como restricción.

## Honestidad
- El proyecto empezó el **2026-09-26** (historial de git).
- Los resultados de la demo vienen de **datos sintéticos** generados por el código real. El primer experimento real
  todavía no terminó.
- No es tratamiento ni consejo médico.

## Links
- Repo: `<URL del repo público>`
- Video: `<URL del video>`

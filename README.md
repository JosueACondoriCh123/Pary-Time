# Consejo N-de-1

**Tu compu hace ciencia sobre cómo arrancás a trabajar.** Para personas con TDAH, donde el consejo genérico falla,
porque lo que le sirve a otro no te dice nada sobre vos.

Declarás tus bloques de trabajo. Un consejo de agentes **locales** hace el resto:
1. **Scout** (`qwen3.5:4b`) lee tu línea base y propone una hipótesis falsable: "abrir el documento solo a la hora
   del bloque reduce tu latencia de arranque a la mitad".
2. **Verificador:** rechaza cualquier cifra que no esté en tus datos, atada a su unidad y a su tema.
3. **Red Team** (`granite4.2:8b`, otra familia de modelo) la ataca con **estadística determinista con poder de
   veto**: potencia, confusores, comparaciones múltiples y constitución. El modelo escribe un pre-mortem, **sin
   veto**.
4. **Preregistro:** hipótesis, test, N, α y el **hash de la semilla** quedan sellados en un journal con cadena de
   hashes **antes** del primer sorteo.
5. **La compu ejecuta el experimento:** cada bloque se sortea (bloques permutados de 4) y, si le toca, se aplica la
   intervención. Puede ser abrir el trabajo solo, mostrar tu primer paso mínimo, **minimizar WhatsApp y YouTube**
   hasta que arranques, o una cuenta regresiva visible.
6. **Resolución:** al llegar al N preregistrado, un test de permutación estratificado da el veredicto, y la semilla
   se revela para que cualquiera verifique que el sorteo no se tocó.

> Ajustes de flujo de trabajo medidos sobre una sola persona. **No es tratamiento ni consejo médico.**

**Todo es local:** el sensor de ventanas, los modelos (Ollama), la estadística y los datos. Los títulos de ventana
nunca salen de un SQLite local y se borran a los 14 días. El journal no guarda títulos ni textos, así que el reporte
se puede compartir con un profesional.

<!-- capturas: docs/hackathon/img/ (las genera `npm run shots` en app/) -->

## Qué lo hace distinto
Búsqueda del 2026-09-26, sin pretensión de exhaustividad:
- Existen plataformas N-de-1 (QuantifyMe, MIT 2018; StudyU), pero son de celular, de salud y con hipótesis escritas
  a mano.
- Existen dashboards de tiempo en la compu (ActivityWatch, quantifiedme), pero **observan, no experimentan**.
- Existen agentes con motor de reglas y auditoría (triage de SOC), pero en otro dominio.

No encontramos nada que combine **hipótesis propuestas por agentes, un Red Team estadístico con veto, aleatorización
ejecutada por la propia compu y preregistro con cadena de hashes** sobre el flujo de trabajo de una persona.

## Resultado del simulador (datos sintéticos)
Un experimento real tarda semanas. `python -m core.simulate` corre **el código real** con reloj acelerado: 5 semanas
de bloques con tramos de actividad sintéticos y un **efecto verdadero conocido** (con la intervención se arranca en la
mitad de tiempo).

| | Resultado |
|---|---|
| Línea base | 14 bloques de control; el consejo se reúne |
| Preregistro | `abrir_trabajo`, N = 20 por brazo, α = 0.024 (alpha-investing), semilla comprometida |
| Resolución | latencia mediana **18.7 → 5.4 min**, ratio geométrico **0.50** (el efecto verdadero era 0.5), **p = 0.005 < α** |
| Sin efecto (control del simulador) | **no apoyado**: no hay falso descubrimiento |
| Journal | 268 eventos, `verify` ok; cada asignación coincide con la semilla revelada |

**El simulador encontró un error nuestro.** El primer test preregistrado comparaba medianas agrupadas. Con mañanas
lentas y tardes rápidas la latencia es bimodal, y la mediana caía en el hueco entre los dos grupos: un efecto
verdadero de ×0.5 se medía como 0.88 (p = 0.27). Lo reemplazamos por un test que permuta **dentro de cada franja
horaria** y compara la media de log-latencia (`permutation_meanlog_diff_stratified@2`). Mejor que te lo diga un
simulador y no tu primer experimento real.

## Corrida real del consejo (Ollama local, RTX 4050 6 GB)
- Qwen propuso 3 hipótesis en 37 s y Granite escribió el pre-mortem en 39 s. Las respuestas quedaron grabadas en
  `data/cassettes/` y se reproducen en los tests.
- **Sin restricción:** el Scout pidió efectos realistas (−30%), y el Red Team las vetó por potencia (12–18 semanas).
  Ahora el Scout recibe el **efecto mínimo detectable** como restricción.
- **El verificador atrapó a Qwen inventando** "50% de bloques censurados" (era 4%): la cifra existía, pero como
  porcentaje de otra cosa.

## Probarlo
Requisitos: Windows 10/11, Python 3.11, Node 20 o superior, [Ollama](https://ollama.com) (opcional; sin él, el
consejo usa un respaldo determinista).

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
ollama pull qwen3.5:4b; ollama pull granite4.2:8b          # opcional

# 5 semanas simuladas (DATOS SINTÉTICOS) y la app encima
.venv\Scripts\python -m core.simulate --out demo-data --weeks 5 --seed 7
cd app; npm install; npm run demo

# demo en vivo: un bloque que empieza en 2 minutos con WhatsApp/YouTube minimizados
.venv\Scripts\python tools/demo_live.py --data-dir demo-live --in 2m --arm retrasar_distracciones
cd app; npm run demo:live

# tests
.venv\Scripts\python -m pytest -q
```

Para usarlo con datos reales: `cd app; npm run dev`. Planificá tus bloques y confirmá el día. La primera semana es
línea base: solo se mide.

## Arquitectura
```
Electron (app/) ──HTTP 127.0.0.1 + token──▶ núcleo Python (core/)
                                            ├─ sensing   sensor Win32 → SQLite local · outcome@1 · categorize
                                            ├─ runtime   bloques · sorteo sellado · scheduler · intervenciones · overlay
                                            ├─ council   snapshot → Scout → verificador → Red Team → Allocator → preregistro
                                            ├─ stats     permutación estratificada · potencia · alpha-investing · ledger Beta
                                            ├─ simulate  ciclo completo acelerado (demo y prueba)
                                            └─ journal   cadena de hashes, fuente de verdad compartida
```
Detalle: [diseño](docs/superpowers/specs/2026-09-26-consejo-n-de-1-design.md) ·
[reglas de la métrica](docs/outcome-rules.md) · [eventos del journal](docs/journal-events.md) ·
[contratos](contracts/README.md).

## Límites, con honestidad
- **Una sola persona:** el resultado no generaliza, y ese es justamente el punto.
- **Sin ciego:** la persona ve la intervención.
- **Poca potencia:** con 2 bloques por día, en 3 semanas solo se detectan efectos grandes (reducir la latencia a la
  mitad, más o menos).
- **Verificador léxico:** ata cifras a unidad y tema, pero no entiende todas las afirmaciones.
- **Solo Windows.**
- **Sin validar en uso real prolongado:** el primer experimento real todavía no terminó. Los resultados de arriba
  son del simulador.

## Cómo se construyó
Proyecto empezado el **2026-09-26** (ver el historial de git). Lo construyeron 4 agentes en paralelo, cada uno en su
worktree y con contratos congelados: dos sesiones de Claude Code y dos agentes externos. La coordinación está en
[`docs/coordinacion/`](docs/coordinacion/README.md). El journal, el lock de proceso y el cliente LLM vienen de Night
Council, del mismo autor.

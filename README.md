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

| El consejo delibera | El sorteo se verifica |
|---|---|
| ![Consejo](docs/hackathon/img/consejo.png) | ![Resultados](docs/hackathon/img/resultados.png) |

*Capturas sobre datos SINTÉTICOS (`npm run shots`). A la izquierda, el Scout propone 3 hipótesis, las 5
herramientas del Red Team las revisan y se preregistra la elegida (N = 21 aunque el modelo prometa un efecto que
pediría menos). A la derecha, la semilla revelada coincide con el hash publicado antes del primer sorteo.*

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

**Corrida de la demo** (`--seed 11 --llm cache`, consejo real con Qwen y Granite):

| | Resultado |
|---|---|
| Línea base | 1 semana de bloques de control |
| Consejo | el Scout propone `primer_paso` (ratio 0.45), pasa el verificador y el Red Team, y se preregistra |
| Preregistro | N = 21 por brazo (todo el presupuesto de 3 semanas), α = 0.024 (alpha-investing), hash de la semilla |
| Resolución | latencia mediana **13.8 → 11.0 min**, ratio dentro de franja **0.68**, **p = 0.021 < α = 0.024**: apoyado |
| Segunda reunión | 3 hipótesis nuevas del Scout; se elige `cuenta_regresiva` y queda en curso |
| Journal | 268 eventos, `verify` ok; cada asignación coincide con la semilla revelada |

**Estudio de potencia** (`--llm off`, semillas 1 a 10, el mismo código):

| Efecto verdadero | Apoyado |
|---|---|
| ×0.5 (con la intervención, la mitad de tiempo) | **8 de 10** (se diseñó para 80%) |
| ×1.0 (sin efecto) | **0 de 5** (ningún falso descubrimiento) |

Las semillas 1 y 7 son los 2 de 10 que fallan con efecto real: la latencia baja, pero el test preregistrado con
su α no alcanza y el veredicto dice "no apoyado". Es la potencia prometida, no un error: el sistema no se autoengaña
para darte una buena noticia.

**El simulador encontró tres errores nuestros**, antes de que le pasen a una persona real:
1. **Medianas agrupadas:** el primer test comparaba medianas de todos los bloques juntos. Con mañanas lentas y tardes
   rápidas la latencia es bimodal, y la mediana caía en el hueco entre los dos grupos: un ×0.5 verdadero se medía
   como 0.88 (p = 0.27).
2. **Desbalance por franja:** los bloques alternan mañana y tarde, y el sorteo en bloques de 4 puede cargar el
   tratamiento de mañanas lentas. La media agrupada mezclaba franja con efecto (ratio 0.92 con un ×0.5 real). El test
   actual (`permutation_meanlog_diff_stratified@2`) permuta **dentro de cada franja** y promedia las diferencias
   **dentro de franja**, con pesos tipo Mantel-Haenszel.
3. **Sorteo no reproducible:** la semilla del consejo salía de `secrets`, que es correcto en uso real pero hacía
   irreproducible la simulación. Ahora es inyectable, y en la simulación está sembrada.

## Corrida real del consejo (Ollama local, RTX 4050 6 GB)
- Qwen propuso 3 hipótesis en 37 s y Granite escribió el pre-mortem en 39 s. Las respuestas quedaron grabadas en
  `data/cassettes/` y se reproducen en los tests.
- **Sin restricción:** el Scout pidió efectos realistas (−30%), y el Red Team las vetó por potencia (12–18 semanas).
  Ahora el Scout recibe el **efecto mínimo detectable** como restricción.
- **El verificador atrapó a Qwen inventando:** "50% de bloques censurados" (era 4%) y "47% de censura en lectura"
  (era 0%). La cifra a veces existía, pero como porcentaje de otra cosa: por eso cada cifra se ata a su unidad y
  a su tema.
- **Otro error nuestro:** el Red Team dimensionaba N con el efecto que prometía el Scout. Con un 0.45 optimista salió
  N = 6 y un efecto real no llegó a p < α. Ahora el efecto propuesto solo decide si la hipótesis es testeable, y N usa
  todo el presupuesto de semanas: el tamaño no sale de la confianza del modelo.

## Probarlo
Requisitos: Windows 10/11, Python 3.11, Node 20 o superior, [Ollama](https://ollama.com) (opcional; sin él, el
consejo usa un respaldo determinista).

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
ollama pull qwen3.5:4b; ollama pull granite4.2:8b          # opcional

# 5 semanas simuladas (DATOS SINTÉTICOS) y la app encima. Con Ollama, el consejo es real (--llm cache);
# sin Ollama usá --llm off (respaldo determinista, otros resultados)
.venv\Scripts\python -m core.simulate --out demo-data --weeks 5 --seed 11 --llm cache
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

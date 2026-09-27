# "Mi tiempo": historial de uso de la compu

Fecha: 2026-09-27 · Estado: implementado para la entrega de la hackathon.

## Qué es
Una pantalla nueva en la app, "Mi tiempo", que muestra todo el tiempo en la compu de los últimos 14 días, clasificado
y ordenado:
- **indicadores:** tiempo activo, % de trabajo en bloques, % de distracción, foco más largo y cambios de app por hora;
- **gráficos:** barras apiladas por día, dona del reparto, ranking de apps y barras por hora del día;
- **sitios de distracción.**

El selector va entre Hoy, 7 días y 14 días.

## Decisiones
- **Clasificación:** las categorías que ya existen más el ranking de apps.
  - `work`: dentro de la ventana de un bloque declarado `[P, P + planned_minutes)` y coincide con sus reglas.
  - `distraction`: según `categorize` de A.
  - `idle`: sin input o pantalla bloqueada.
  - `paused`: pausa de privacidad.
  - `other`: el resto.
- **Privacidad:** el núcleo devuelve solo agregados (`ActivityHistory`, `contracts@1.2`). Apps por nombre de
  ejecutable y sitios solo por el patrón de distracción que coincidió. **Nunca títulos de ventana ni textos de
  bloques**; lo verifica `tests/insights/test_history.py`.
- **Rango:** hasta 31 días por pedido. El dato real llega hasta `raw_retention_days` (14), porque los tramos crudos se
  borran después. Guardar historial largo con un resumen diario sin títulos queda para después de la hackathon.
- **Sin dependencias nuevas:** los gráficos son SVG propios (`app/src/views/History.tsx`, `app/src/lib/usage.ts`).
  Evita el riesgo de build y de CSP el día de la entrega.
- **Sin tocar lo de otros frentes:**
  - `core/insights/` es nuevo;
  - `ctx.blocks_on` se arma en `core/app.py` desde el store del runtime, sin editar `core/runtime/`;
  - la ruta es `GET /activity/history?from_date&to_date`.

## Riesgo anotado
Ver el tiempo de distracción es feedback, y puede cambiar cómo trabaja la persona. Afecta a los dos brazos por igual,
así que la aleatorización sigue siendo válida. Aun así, la comparación con la línea base (antes de la pantalla) ya no
es exactamente igual. Si importa, se puede ocultar durante la semana de línea base.

## Verificación
- `tests/insights/test_history.py`: categorías, trabajo solo dentro de bloques, horas, apps, sitios, foco, cambios
  por hora, recorte al ahora, privacidad, validación de rango y token.
- `app/tests/usage.test.ts`: formato, rangos, geometría de la dona y coherencia del ejemplo del contrato.
- Renderizado verificado en el navegador integrado en modo ejemplos. La captura `mi-tiempo.png` se agrega con
  `npm run shots` cuando la app instalada esté cerrada (instancia única).

# Frente D: Claude · App Electron

> Solo el dueño del frente escribe este archivo. Actualizalo al terminar cada tarea.
> Desde el 2026-09-26, D lo hace Claude (ver "Cambio de reparto" en `README.md`).

## Estado
- Fases 1, 2 y 3 hechas del lado de la app (2026-09-26).
- 2026-09-27: el sidecar de A (`a060e33`) quedó integrado en la app empaquetada y verificado de punta a punta.
- Lo que falta depende de B1 y B2 (rutas de bloques y runtime).

## Hecho

### Fase 1
- **Stack:** Electron 44, Vite 8, React 19 y TypeScript 6.0. El proceso principal y el preload se empaquetan con
  esbuild a CJS en `dist-electron/`.
- **Tipos del contrato:** `npm run contracts` genera `app/src/contracts/index.ts` desde `contracts/schemas`.
  - Junta los `$defs` de todos los schemas en un solo archivo, así `Arm` y los demás existen una sola vez.
  - Saca los `title` de los campos, así no aparecen alias como `BlockId1` o `BlockId2`.
  - `--check` falla si hay diferencias.
- **Sidecar (`electron/sidecar.ts` y `electron/sidecar-logic.ts`):**
  - Token con `randomBytes(32)`, solo en memoria.
  - Lanza `python -m core --port 0 --data-dir <userData>/data` y lee `NDE1_READY` con un timeout de 20 s.
  - Relanza con backoff de 1, 2, 5 y 10 s. Con más de 5 caídas en 5 min muestra el stderr y un botón "Reintentar".
  - En desarrollo usa `<repo>/.venv` y, si no existe, el `.venv` del repo padre (los worktrees anidados no tienen
    venv propio). Empaquetado usa `resources/nde1-core/nde1-core.exe`.
  - Variables para forzar rutas: `NDE1_PYTHON`, `NDE1_REPO` y `NDE1_DATA_DIR`.
- **Ventana y bandeja:**
  - Instancia única, porque dos núcleos no pueden compartir el `data-dir`.
  - Cerrar la ventana la esconde.
  - Menú de la bandeja: "Abrir", "Planificar mañana", "Pausar sensor 30/60 min", "Salida de emergencia" y "Salir".
    Avisa con un globo y mensajes humanos para 409 y 501.
  - Arranque con Windows activado por defecto (`prefs.json` en `userData`, con `--hidden`). Solo se registra
    empaquetado.
- **Seguridad:**
  - `contextIsolation`, `sandbox` y sin `nodeIntegration`.
  - El preload expone solo `window.nde1` (ver `src/bridge.ts`).
  - CSP en el build y navegación bloqueada.
  - El token viaja solo en el header `X-NDE1-Token`.
- **Cliente API (`src/api.ts`):** tipado con los contratos. Muestra mensajes humanos para 0, 401, 404, 409, 422 y 501
  ("Todavía no disponible en esta versión.").
- **Planificador:**
  - Mañana y hoy.
  - Crear, editar y quitar bloques mientras están `planned`.
  - Chips de duración y de `TaskKind`.
  - Objetivo con selector nativo de archivo, app o web.
  - Matchers autocompletados y editables (`.docx` → `WINWORD.EXE` + nombre del archivo).
  - Botón grande "Confirmar mañana".
  - Pide el primer paso en los bloques con `needs_first_step`.
  - **El brazo se muestra solo si `arm_revealed` no es null** (`visibleArm`, con test).
- **Modo ejemplos:**
  - `npm run dev:fixtures` usa `contracts/examples/*.json` con la franja fija "DATOS DE EJEMPLO".
  - `vite build` se niega con `VITE_FIXTURES=1`, y el código de ejemplos no entra al bundle.

### Fase 2
- **Overlay:**
  - Ventana transparente, `alwaysOnTop` con nivel `screen-saver`, `focusable: false` y `showInactive`.
  - Clics que pasan de largo; esquina superior derecha.
  - Consulta `GET /runtime/overlay` cada 1 s. Si recibe 501 o un error, se esconde.
- **Hoy:**
  - Bloque activo con la condición revelada y su explicación, más el primer paso si lo hay.
  - "Siguiente en X".
  - "Hoy no" con confirmación de un clic: el primer toque arma el botón por 4 s.
  - "Salida de emergencia", el sensor (pausar o reanudar) y la lista del día.
- **Experimento:**
  - Intervención, moderador y barras `n_*_done` / `n_per_arm`, con el texto fijo contra espiar. Sin efectos
    parciales.
  - "Reunir al consejo ahora", con el resumen del `CouncilRun`: modelos o respaldo, propuestas, veredicto del Red
    Team herramienta por herramienta, pre-mortem y si eligió un experimento.

### Fase 3
- **Resultados:**
  - Por experimento: hipótesis, veredicto, medianas, ratio, p y α, censurados, excluidos y "hoy no".
  - **Semilla verificada en el renderer con WebCrypto:** sha256 de los *bytes* de la semilla hex, igual que
    `core.contracts.seed_commitment`.
  - Ledger como curvas de la posterior Beta, y el veto regret.
- **Reporte:**
  - `/report` y `/journal/verify`.
  - "Guardar como" HTML autocontenido (sin scripts, con CSP `default-src 'none'` y todo escapado) o JSON.
  - Disclaimer siempre visible.
- **Ajustes:**
  - Listas de distracción, navegadores y lista blanca.
  - Retención y modelos de Ollama.
  - α, exploración y tope de fricción se muestran fijos.
  - Arranque con Windows y pausa del sensor.
- **Empaquetado:**
  - `packaging/electron-builder.yml`: NSIS por usuario, `asInvoker`, sin elevación.
  - `extraResources` toma el sidecar de A.
  - `npm run dist` genera el instalador.

### Integración con el sidecar de A (2026-09-27)
- Se construyó la app empaquetada con `dist/nde1-core/` de A copiado en `<repo>/dist/` (ignorado por git).
- Resultado del e2e `e2e/packaged.spec.ts`, sobre `release/win-unpacked` y sin Python:
  - `isPackaged` da true y el núcleo congelado arranca en unos 7 s.
  - `/health` responde, `/activity/today` da 200 con el sensor real y `/journal/verify` sale ok.
  - La vista "Hoy" muestra "Sensor: midiendo".
- Al cerrar la app no quedan procesos `nde1-core` huérfanos: el modo onedir no tiene proceso hijo.
- `NDE1_NO_LOGIN_ITEM=1` evita que el test registre el `.exe` de `release/` en el inicio de Windows.

## En curso
- Nada. Sigo con B2 (scheduler e intervenciones) cuando se mergee B1.

## Bloqueos
- `/blocks` y `/runtime/*` responden 501 hasta el merge de B1 y B2. La app lo muestra con el mensaje de 501.

## Coordinación con A (sidecar)
`packaging/sidecar.spec` tiene que producir un PyInstaller **onedir** en `<repo>/dist/nde1-core/`, con el ejecutable
`nde1-core.exe` adentro. Tiene que aceptar los mismos argumentos que `python -m core` (`--port 0 --data-dir <dir>`),
leer `NDE1_TOKEN` del entorno e imprimir `NDE1_READY {...}` por stdout. electron-builder lo copia a
`resources/nde1-core/`.

## Pedidos de contrato
<!-- Formato: fecha · qué cambiar exactamente · por qué. El Frente 0 responde acá abajo de cada pedido. -->
Ninguno.

## Cómo probar lo entregado
En `app/`, la primera vez:

```powershell
npm install
```

Después, según qué quieras probar:

| Comando | Qué hace |
|---|---|
| `npm run typecheck`, `npm run lint`, `npm test` | Chequeos estáticos y 46 tests de Vitest (READY, backoff, tiempos, matchers, brazo oculto, cliente HTTP contra un servidor real, semilla, Beta y reporte HTML) |
| `npm run contracts -- --check` | Verifica que los tipos estén al día con el contrato |
| `npm run test:e2e` | Build más Playwright for Electron contra el núcleo real: `/health`, 401 sin token, renderer aislado, token no guardado, **matar el núcleo y verificar que se relanza**, y el planificador |
| `npm run dev` | App contra el núcleo real, con HMR |
| `npm run dev:fixtures` | App con los datos de ejemplo |
| `npm run dist` | Instalador NSIS en `app/release/` (antes, copiá o construí `dist/nde1-core/` en la raíz del repo) |
| `npm run dist:dir` y después `npx playwright test e2e/packaged.spec.ts` | App empaquetada con el núcleo congelado (se saltea si falta el sidecar) |

## Hackathon (2026-09-27) · `brief-d-hackathon.md`

### Hecho
- **Franja "DATOS SINTÉTICOS":** fija en todas las vistas cuando `GET /health` → `data_label == "sintetico"`. Se vuelve
  a leer si el núcleo se reinicia. Es violeta y distinta de "DATOS DE EJEMPLO", que es naranja y solo aparece en
  desarrollo.
- **Scripts:**
  - `npm run demo`: la app sobre `<repo>/demo-data`.
  - `npm run demo:live`: la app sobre `<repo>/demo-live`.
  - Ninguno de los dos corre si el data-dir no tiene `DATA_LABEL = sintetico`, así la demo nunca toca los datos
    reales. Si falta, muestran el comando exacto para generarlo.
- **Consejo para el jurado** (`src/views/Council.tsx`):
  - Cada propuesta es una tarjeta: hipótesis en una línea, justificación del Scout (o "Respaldo").
  - Después vienen el verificador y las 4 herramientas del Red Team, con ✅ o ❌ y su detalle, y el veredicto.
  - El pre-mortem va aparte, con la etiqueta "sin poder de veto".
  - El preregistro muestra el test (con nombre humano, incluido `permutation_meanlog_diff_stratified@2`) y el hash
    de la semilla abreviado, con el tooltip "la semilla se revela al terminar".
- **Resultados:**
  - Frase humana: "Con “X” arrancaste en la mitad de tiempo (p = 0.010 < α = 0.024): en vos, funciona."
  - Barras de medianas.
  - Caja "¿Se tocó el sorteo?" en 3 pasos: hash preregistrado, semilla revelada y sha256 recalculado en la compu,
    con "✅ El sorteo no se tocó" en grande.
- **`npm run shots`:**
  - Genera 5 PNG en `docs/hackathon/img/` con el orden `planificador`, `hoy`, `reporte`, `consejo` y `resultados`.
  - Trabaja sobre una copia descartable de `demo-data`.
  - Variables `NDE1_SHOTS_DATA` y `NDE1_SHOTS_OUT` para elegir datos y salida.
- **Tests:** 52 de Vitest (con la frase del resultado y la elección de la propuesta) y 4 e2e, que ahora aceptan
  `contracts@1.x`.

### Probado con `core.simulate` (WIP de `main`, sin commitear)
Generé `demo-data` en una carpeta temporal (`--weeks 5 --seed 7`) y saqué capturas con el núcleo de `main`. Todo se ve
bien. Hay tres avisos para el Frente 0:

1. **El consejo del `demo-data` corrió con respaldo.** Dice "Scout no disponible: sin cassette 9c0092a8b9ab". Para el
   guion, el paso "el verificador atrapa una cifra inventada" necesita la cassette de Qwen para ese snapshot
   (`NDE1_LLM_MODE=record`). Si no, la vista muestra 4 respaldos sin vetos.
2. **Contrato en movimiento.** Con el código commiteado, `Preregistration.test = permutation_meanlog_diff_stratified@2`
   da 500 en `/experiments`, `/council/runs`, `/ledger` y `/report`. Cuando se commitee, regenero los tipos con
   `npm run contracts`.
3. **Privacidad de `demo-data`.** Mientras la app corre sobre un data-dir de demo, el sensor de A graba las ventanas
   reales de Josué en su `activity.sqlite`. **No publiquen `demo-data/*.sqlite` después de abrir la app.** Una opción
   es no arrancar el sensor cuando `data_label == sintetico`, o que `check_private.py` lo cubra.

### Falta
- Capturas finales sobre el `demo-data` definitivo, y el GIF del overlay y de la re-minimización con `demo-live`
  (necesita `tools/demo_live.py` de B).
- Ensayo del guion dos veces, con las fricciones anotadas acá.

### Cierre de la hackathon (fase 4 de D)
- **Capturas finales** en `docs/hackathon/img/`, sobre el `demo-data` definitivo de `main`. El consejo ya muestra la
  corrida real de Qwen: el verificador veta 3 hipótesis por "cifras fuera del snapshot: 47%, 58%".
- **Resultados:** sello "✅ el sorteo no se tocó" junto al veredicto, visible sin scroll (casilla del checklist del
  guion). La frase del efecto aclara que el ratio es del test preregistrado estratificado, y las barras se rotulan
  como medianas crudas. Antes decía "la mitad de tiempo" al lado de 14 → 9 min, y se leía como una contradicción.
- **Capturas de página completa:** la barra lateral ahora llega hasta abajo.
- **`npm run gif`:**
  1. Arma `demo-live` con `tools/demo_live.py` (bloque a 45 s con `retrasar_distracciones`).
  2. Graba el escritorio con ffmpeg.
  3. Reabre las ventanas minimizadas, espera que se re-minimicen y toca "Salida de emergencia".
  4. Deja el GIF en `docs/hackathon/img/demo-live.gif`.
  - **Mueve ventanas reales y graba el escritorio completo:** hay que dejar en pantalla solo lo que se puede
    publicar.
- **Para el Frente 0:** el guion (`docs/hackathon/demo.md`, paso 4) dice "18.7 → 5.4 min", pero el `demo-data` actual
  da medianas de 14 → 9 min, ratio 0.50 y p = 0.002. Conviene ajustar el guion o citar los números de la pantalla.

### Mejoras del frontend (2026-09-27)
- **Consejo compacto:**
  - Arriba, el flujo de la reunión: ideas del Scout → vetadas → respaldo → preregistrada.
  - Una fila desplegable por idea, con un chip de veredicto (el motivo del veto se lee con el verificador primero).
  - Los respaldos del Allocator van agrupados en una sola fila.
  - La elegida aparece completa, con herramientas, pre-mortem y preregistro. El detalle técnico del respaldo queda
    plegado.
- **"Hoy" con línea de tiempo:**
  - Etapas: sellado → hora → intervención → arranque. Emergencia y "hoy no" se marcan como aviso.
  - Cuenta regresiva grande antes de la hora.
  - El bloque en foco es el activo o, si no hay, el próximo cuando falta menos de 30 min.
  - `blockTimeline` es pura y está testeada, incluida la regla de nunca nombrar el brazo si `arm_revealed` es null.
- **Ledger en barras:** "funcionó n de m · %" y "sin probar todavía" en lugar de curvas planas.
- **Modo proyector:** botón al pie de la barra lateral y `Ctrl+Shift+P`. Letra de 19 px y más contraste; se recuerda
  por pantalla.
- **Variable `NDE1_USER_DATA`:** los tests, las capturas y el GIF usan su propia carpeta de usuario. Así conviven con
  la app instalada abierta (antes el candado de instancia única los cerraba) y no tocan sus preferencias.
- 61 tests de Vitest y 4 e2e pasan. Capturas regeneradas en `docs/hackathon/img/`.

### Pedido de contrato (2026-09-27)
- `RuntimeStatus`: agregar `n_windows_minimized: int` y `n_reapplied: int` para el bloque activo, sin títulos.
- **Por qué:** la línea de tiempo de "Hoy" podría decir "2 ventanas minimizadas · re-minimizadas 1 vez", que es lo que
  el público no ve en la demo. Hoy esos números solo están en los eventos `intervention` del journal.
- **Opcional:** no bloquea la demo.

### Para el Frente 0
- El `demo-data` actual ya no tiene vetos del verificador, después del arreglo de falsos positivos. El guion
  (`docs/hackathon/demo.md`, paso 3) ya prevé contarlo con la corrida real del README si no aparece un ❌.


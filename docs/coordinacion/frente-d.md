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

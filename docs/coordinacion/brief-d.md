# Brief · Frente D: app Electron

> Pegale este archivo entero al agente externo 3 como primer mensaje. Su worktree es
> `C:\Users\HP\Documents\n-de-1-frente-d` (rama `frente-d`).

## Contexto en 5 líneas
Consejo N-de-1 es una app de escritorio para Windows que hace experimentos aleatorizados sobre cómo arranca a
trabajar una persona con TDAH. El núcleo es un proceso Python local que expone una API HTTP en `127.0.0.1`. Vos
construís **toda la app Electron**: lanza y vigila ese proceso, muestra el ícono en la bandeja, el planificador de
bloques, los overlays y las vistas de experimento y resultados. **El usuario tiene TDAH: cada clic de más es fricción
real.** Hay otros 3 agentes trabajando en paralelo en otras carpetas.

## Leé antes de escribir una línea (en este orden)
1. `docs/coordinacion/README.md`: reglas, carpetas e hitos. **Obligatorio.**
2. `contracts/README.md`: **protocolo de arranque**, generación de tipos y semántica que el schema no expresa.
3. `contracts/openapi.json`: la API completa. Es tu contrato; no hay otra.
4. `contracts/examples/*.json`: datos de ejemplo válidos para desarrollar la UI.
5. `docs/superpowers/specs/2026-09-26-consejo-n-de-1-design.md`: el diseño completo.

## Tus carpetas (solo escribís acá)
`app/` completa y `packaging/`, salvo `packaging/sidecar.spec`, que es del Frente A.

## Stack
- Electron (última estable), Vite, React 19 y **TypeScript**. Node 26 está instalado.
- Tipos desde `contracts/schemas` con `json-schema-to-typescript`, en el script `npm run contracts` que escribe
  `app/src/contracts/`. **Nunca escribas tipos del contrato a mano.**
- Sin framework de estado: `fetch` + hooks alcanzan.
- Seguridad de Electron: `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`. Un `preload` expone solo
  `window.nde1 = { baseUrl, token, ... }` vía `contextBridge`.
- **El token nunca va al `localStorage` ni a la URL.**

## Qué entregás

### Fase 1 (hacia el Hito 1)
1. **Proceso principal (`app/electron/main.ts`):**
   - **Sidecar:**
     - Genera un token con `crypto.randomBytes(32)` y lanza el núcleo.
       - Desarrollo: `<repo>/.venv/Scripts/python.exe -m core --port 0 --data-dir <app.getPath("userData")>/data`, con
         `cwd = <repo>` y el env `NDE1_TOKEN`.
       - Producción: `resources/nde1-core/nde1-core.exe` con los mismos argumentos.
     - Lee stdout hasta la línea `NDE1_READY {...}` (timeout de 20 s) y le pasa `baseUrl` y el token al renderer por
       el preload.
     - Si el proceso muere, lo relanza con backoff (1, 2, 5, 10 s). Si muere más de 5 veces en 5 min, muestra un error
       claro con el stderr y un botón "reintentar".
     - Al salir, mata el proceso. El núcleo restaura las ventanas al volver a arrancar, así que no hace falta un cierre
       elegante.
   - **Bandeja:** ícono con menú "Abrir", "Planificar mañana", "Pausar sensor 30 min / 60 min", "Salida de emergencia"
     y "Salir". Cerrar la ventana la esconde; no sale de la app.
   - **Arranque con Windows:** opción `app.setLoginItemSettings`, activada por defecto y desactivable en Ajustes.
     Sin esto no se miden las mañanas.
2. **Cliente API (`app/src/api.ts`):** tipado con los contratos, con el header `X-NDE1-Token` en todo salvo `/health`.
   Los errores 409 y 501 se muestran con un mensaje humano. Un 501 dice "todavía no disponible en esta versión".
3. **Planificador (vista principal de la noche):**
   - Lista de bloques de mañana. Crear un bloque pide:
     - hora y duración;
     - tipo de tarea (chips de `TaskKind`);
     - etiqueta;
     - objetivo, con selector de archivo nativo (`dialog.showOpenDialog`), app o URL;
     - matchers de trabajo, **autocompletados** con el nombre del archivo y el proceso probable (`.docx` →
       `WINWORD.EXE`) y editables.
   - Botón grande **"Confirmar mañana"**, que llama a `POST /blocks/confirm`.
   - Después de confirmar, los bloques con `needs_first_step` piden su primer paso ("¿Cuál es el primer paso
     ridículamente chico?").
   - **La UI nunca muestra `arm_revealed` si es null, ni lo infiere.**
4. **Modo ejemplos:** con `VITE_FIXTURES=1`, la UI lee `contracts/examples/*.json` en lugar de la API y muestra
   una franja fija **"DATOS DE EJEMPLO"**. Sirve para avanzar antes de que B y C estén mergeados; nunca queda activo
   en producción.

### Fase 2 (hacia el Hito 2)
1. **Overlay:**
   - `BrowserWindow` sin marco, transparente y `alwaysOnTop` con nivel `screen-saver`.
   - `setIgnoreMouseEvents(true, { forward: true })`, para que los clics pasen.
   - Esquina superior derecha, no roba el foco (`focusable: false`, `showInactive`).
   - Consulta `GET /runtime/overlay` cada 1 s y se esconde si `visible` es false.
   - Tipografía grande y legible, que no tape el trabajo.
2. **Vista "Hoy":** el bloque activo con la condición revelada, cuánto falta para el siguiente y dos botones:
   - **"Hoy no"** (`POST /blocks/{id}/abort`), con confirmación de un clic;
   - **"Salida de emergencia"**.
3. **Vista "Experimento":**
   - Usa `GET /experiments/current`: intervención, moderador y una barra de progreso `n_control_done` /
     `n_treatment_done` contra `n_per_arm`.
   - Texto fijo: *"El resultado se muestra al completar el experimento, para que no te engañes espiando."*
   - **Nunca calcules ni muestres efectos parciales.**
   - Botón "Reunir al consejo ahora" (`POST /council/run`) con el resumen de `CouncilRun`: propuestas, vetos con su
     motivo y lo elegido.

### Fase 3
1. **Resultados** (`GET /experiments`, `/ledger`, `/veto_regret`):
   - por experimento: hipótesis, veredicto, medianas, ratio, p y α, los censurados y la verificación de la semilla
     (`sha256(seed_revealed) == seed_commitment`, calculada en el renderer con WebCrypto);
   - el ledger como barras de la posterior Beta, y el veto regret.
2. **Reporte:** `GET /report` y `GET /journal/verify`. Exporta HTML autocontenido o JSON con "Guardar como", listo
   para compartir con un profesional. Muestra siempre el `disclaimer`.
3. **Ajustes:** `GET/PUT /settings` (listas de distracción, lista blanca, retención, modelos de Ollama, arranque con
   Windows) y pausa del sensor.
4. **Empaquetado:** electron-builder con destino NSIS. Incluye como `extraResources` la salida de
   `packaging/sidecar.spec`, que construye el Frente A. Coordiná la ruta en tu `frente-d.md`.

## Copy y tono
- Español rioplatense con voseo ("arrancás", "confirmá").
- Frases cortas; nada de culpa ni gamificación punitiva.
- Siempre visible en Resultados y Reporte: *"Ajustes de flujo de trabajo medidos sobre vos. No es tratamiento ni
  consejo médico."*

## Tests
- Vitest para la lógica del renderer: formateo de tiempos, parser de la línea READY, backoff del sidecar, verificación
  de la semilla y la regla de no mostrar el brazo oculto.
- Smoke de Electron (Playwright for Electron) que lance la app contra el núcleo real
  (`.venv\Scripts\python -m core`) y verifique `/health` y el render del planificador.
- `npm run build`, `npm run typecheck` y `npm run lint` en verde.

## Definición de terminado (cada fase)
- `npm run typecheck && npm run lint && npm test` pasan en `app/`.
- `npm run contracts` no deja diffs: los tipos están al día con el contrato.
- `git diff --stat main...` solo muestra `app/` y `packaging/`.
- `docs/coordinacion/frente-d.md` está actualizado, con capturas de pantalla si ayudan.

## Prohibido
- Tocar `core/`, `contracts/` o `tests/`. Si la API no te alcanza, pedilo en tu `frente-d.md`.
- Mostrar efectos parciales o el brazo antes de tiempo, o guardar el token fuera de la memoria del proceso.
- Pedir permisos de administrador.

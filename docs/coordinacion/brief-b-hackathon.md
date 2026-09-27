# Brief hackathon · Externo 2 (B): runtime confiable en la demo en vivo

> Pegale esto al agente externo 2. Worktree `C:\Users\HP\Documents\n-de-1\n-de-1-frente-b`, rama `frente-b`.
> **Antes de empezar: `git merge main`**, porque B2 (scheduler, intervenciones, overlay) ya está ahí. Entrega en
> **menos de 5 h**.

## Contexto
Josué presenta hoy en una hackathon. En la demo en vivo:
1. Crea un bloque que empieza en 2 minutos con la condición `retrasar_distracciones`.
2. Aparece el overlay con la cuenta regresiva.
3. A la hora del bloque, WhatsApp y YouTube se minimizan solos.
4. Los vuelve a abrir y se re-minimizan.
5. "Salida de emergencia" los restaura.

Todo eso ya existe en `core/runtime/`. Tu trabajo es que **no falle frente al jurado**. Desde esta noche,
`core/runtime/` completo es tuyo, incluido lo de B2: `scheduler.py`, `interventions.py`, `overlay.py` e
`intervention_state.py`.

## 1. `tools/demo_live.py` (prioridad 1)
```powershell
.venv\Scripts\python tools/demo_live.py --data-dir demo-live --in 2m --arm retrasar_distracciones --label "Tesis cap. 3"
```
- Crea `demo-live/` con el marcador `DATA_LABEL` que contenga `sintetico`. Así la app muestra "DATOS SINTÉTICOS"
  (`Health.data_label`).
- Inserta con el `BlockStore` real un bloque `confirmed` que empieza en `ahora + --in`.
  - Condición **forzada** `--arm`, con `experiment_id=None`.
  - Escribe `block_confirmed` y `assignment` con `append_typed`.
  - **Solo en un data dir de demo:** si el directorio no tiene el marcador, se niega a correr.
- Imprime cómo abrir la app sobre ese data dir: `NDE1_DATA_DIR`. El Frente D arma `npm run demo:live`.
- `--arm cuenta_regresiva` y `--arm primer_paso --first-step "..."` también tienen que funcionar.

## 2. Ensayo con apps reales en la compu de Josué (prioridad 2)
Probá la secuencia completa y arreglá lo que falle, **sin cambiar el sorteo ni `outcome@1`**:
- **WhatsApp de escritorio (UWP):** la ventana es de `ApplicationFrameHost.exe` con título "WhatsApp". `main` ya
  agregó ese proceso a `browser_processes` y `whatsapp` a los patrones. Verificá que se minimice y se restaure, y que
  el filtro *cloaked* no la descarte cuando está visible.
- YouTube en Chrome y en Edge.
- Una app en pantalla completa: el overlay tiene que verse o, como mínimo, no romper nada.
- Que "Salida de emergencia" y "Hoy no" desde la app restauren todo.
- Que matar el núcleo a mitad del bloque y relanzarlo (lo hace Electron) restaure las ventanas.

Todo lo que encuentres va a `frente-b.md` como "checklist de ensayo" con ✅ o ❌ y el arreglo.

## 3. Test de caída real (si queda tiempo)
- Núcleo como subproceso, `TerminateProcess` con la ventana Tk propia minimizada.
- Relanzar y verificar `reason: recovery`.
- Mismo patrón que `tests/runtime/test_b2_windows.py`: nunca tocar ventanas de la persona.

## Reglas
- Solo `core/runtime/`, `tests/runtime/`, `tools/demo_live.py` y tu `frente-b.md`.
- La suite corre con `NDE1_NO_DESKTOP=1` (`tests/conftest.py`). Los tests con ventanas reales usan su propia
  ventana.
- Commits `feat(b): ...` y `fix(b): ...` en `frente-b`. Avisá en `frente-b.md` cuando `demo_live.py` esté listo.

# Frente B: Externo 2 · Runtime e intervenciones

> Solo el dueño del frente escribe este archivo. Actualizalo al terminar cada tarea.

## Estado
- Fase actual: 3 del brief (caída real), 2026-09-27. El plan de después de la hackathon llama "F4" al retiro de experimentos; eso no tiene evento ni ruta en el contrato, así que no lo inventé.

## Hecho
- `tools/demo_live.py` acepta `--label` y `--first-step` (solo con `primer_paso`). El brazo sigue forzado, sin `permuted_arm`, y el texto no entra al journal.
- Caída real: un test lanza el núcleo, minimiza una ventana Tk propia, lo mata con `TerminateProcess` y lo relanza. El journal queda con `intervention` `reason: recovery` y `n_windows >= 1`. No toca ventanas de la persona.
- Un hueco de ticks (suspensión) no vuelve a aplicar la intervención. Al cruzar la medianoche sigue habiendo una sola intervención activa: el bloque anterior se revierte con `block_start` y el nuevo arranca.
- `tools/demo_live.py --data-dir demo-live --in 2m --arm retrasar_distracciones` crea un bloque confirmado con el brazo **forzado**. No llama a `permuted_arm`. Escribe `DATA_LABEL=sintetico` y se niega a usar `data/` del repo, la carpeta de la app instalada, un journal sin marcador, o un directorio cuyo núcleo sigue abierto.
- En un directorio sintético, `retrasar_distracciones` muestra la cuenta regresiva (`arrancás en m:ss`) desde 3 min antes. Sin el marcador, ese brazo no muestra overlay.
- WhatsApp de escritorio en esta compu es `WhatsApp.Root.exe` (no `WhatsApp.exe`) y puede estar cloaked. También entra `ApplicationFrameHost.exe` si el título dice WhatsApp, y un Chrome/Edge cloaked cuyo título ya es YouTube. La lista blanca de `whatsapp.exe` cubre esa familia. outcome@1 y el sorteo no se tocaron.
- El overlay de Electron vuelve a pedir `screen-saver` al mostrarse y cada 1 s, para quedar arriba de un video a pantalla completa. La ventana sigue siendo de D; el cambio está en `app/electron/main.ts`.

## En curso

## Bloqueos
- Al ensayar, WhatsApp estaba en la bandeja (ninguna ventana visible). No lo abrí: volver a esconderlo sería `SW_HIDE`, y eso está prohibido. Con la ventana abierta, el filtro nuevo la toma.
- YouTube no estaba abierto en Chrome ni en Edge. El caso cloaked + título `YouTube` queda cubierto por test, no por una ventana real.

## Pedidos de contrato
<!-- Formato: fecha · qué cambiar exactamente · por qué. El Frente 0 responde acá abajo de cada pedido. -->
- 2026-09-27 · `Settings.distraction_processes` incluye `WhatsApp.exe` y no `WhatsApp.Root.exe`. Lo resolví solo en la selección de ventanas de la intervención, sin cambiar el contrato ni `categorize`, para no mover outcome@1. Si el Frente 0 quiere el nombre nuevo en el default, es un pedido aparte.
- 2026-09-27 · Hace falta un evento de journal (y su ruta) para retirar un experimento. Sin eso el runtime no puede dejar de sortear un experimento en curso: `active()` sigue el preregistro abierto.

## Cómo probar lo entregado
```powershell
..\.venv\Scripts\python -m pytest tests/runtime -q
..\.venv\Scripts\python tools/demo_live.py --data-dir demo-live --in 2m --arm retrasar_distracciones --label "Tesis cap. 3"
..\.venv\Scripts\python -m pytest tests/runtime/test_b2_windows.py -q
```
Después, la app con `NDE1_DATA_DIR` en ese `demo-live`. El overlay aparece enseguida; a los 2 min se minimizan WhatsApp (ventana abierta) y YouTube en Chrome o Edge. "Salida de emergencia" los restaura.

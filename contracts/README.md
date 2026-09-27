# Contratos (`contracts@1`), congelados al cerrar la Fase 0

| Archivo | Qué es | Fuente |
|---|---|---|
| `schemas/*.schema.json` | JSON Schema de cada modelo | **Generado** desde `core/contracts.py` |
| `openapi.json` | La API REST completa (paths, métodos, modelos) | **Generado** desde las rutas de cada frente |
| `examples/*.json` | Un ejemplo válido por modelo | Ilustrativos: **no son datos reales**. Validados por test |

Otras piezas congeladas:
- `core/interfaces.py`: las interfaces Python entre frentes.
- `docs/outcome-rules.md`: las reglas normativas de la métrica.
- `docs/journal-events.md`: los eventos del journal.

## Cambiar un contrato
Nadie edita `core/contracts.py`, `core/interfaces.py`, las rutas declaradas ni este directorio, salvo el Frente 0. Si
necesitás un cambio, anotá un **pedido de contrato** en tu `docs/coordinacion/frente-X.md` con el motivo y el cambio
exacto. El Frente 0 lo aplica, regenera y avisa.

```powershell
.venv\Scripts\python tools/export_contracts.py          # solo Frente 0: regenera
.venv\Scripts\python tools/export_contracts.py --check  # todos: exit 1 si está desincronizado
```

## Tipos TypeScript (Frente D)
Se generan, nunca se escriben a mano:
```powershell
cd app
npx json-schema-to-typescript -i ../contracts/schemas -o src/contracts --cwd ../contracts/schemas
```

## Protocolo de arranque (Electron ↔ núcleo)
1. Electron genera un token aleatorio (32 bytes o más) y lanza
   `python -m core --port 0 --data-dir <userData>/data` con la variable de entorno `NDE1_TOKEN=<token>`.
   En producción lanza el ejecutable del sidecar con los mismos argumentos.
2. El núcleo escucha **solo** en `127.0.0.1` e imprime por stdout una única línea:
   `NDE1_READY {"port": 51234, "version": "n-de-1@0.1.0", "contracts": "contracts@1"}`.
3. Todas las rutas salvo `GET /health` exigen el header `X-NDE1-Token: <token>`. Sin él, responden 401.
4. Si el núcleo muere, Electron lo relanza con backoff. Al arrancar, el runtime restaura las ventanas que quedaron
   minimizadas.
5. Dos núcleos sobre el mismo `--data-dir` no pueden convivir: el segundo falla al arrancar por el `LoopLock`.

## Semántica que el schema no expresa
- `BlockView.arm_revealed` es `null` hasta `planned_start_ms`. La excepción es `primer_paso`, que se revela al
  confirmar para poder escribir el paso.
- `GET /experiments/current` **nunca** incluye el efecto ni las medianas antes de la `resolution`.
- Tiempos en epoch ms UTC. `local_date` y las franjas horarias usan el reloj local de la compu
  (`core.interfaces.time_of_day`).

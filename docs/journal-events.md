# Eventos del journal (`contracts@1`)

`data/journal.jsonl`: una línea por evento con `seq`, `ts`, `kind`, `agent_version`, `payload`, `prev` y `hash`.
`hash` es el sha256 del evento canónico sin el campo `hash`. `verify()` falla si una línea se altera, se borra o se
reordena. El mecanismo está heredado de Night Council.

**Reglas:**
- Se escribe **solo** con `core.journal.append_typed(journal, kind, payload)`, que valida el payload contra
  `core.contracts.JOURNAL_PAYLOADS`.
- Ningún payload lleva títulos de ventana, rutas ni textos del usuario. Lo impiden el modelo y `_FORBIDDEN`, y lo
  cubre un test.
- Nunca se edita a mano: un byte cambiado rompe todos los hashes siguientes.
- Un solo proceso escribe (`LoopLock` sobre `data/core.lock`).

| `kind` | Escribe | Payload (`core.contracts`) | Cuándo |
|---|---|---|---|
| `app_start` | 0 | `{version, contracts}` | Cada arranque del núcleo |
| `settings_changed` | 0 | `{keys: [...]}`, solo nombres | `PUT /settings` con cambios |
| `block_confirmed` | B | `BlockConfirmed` | Al confirmar el día, uno por bloque |
| `assignment` | B | `Assignment` | Inmediatamente después de su `block_confirmed` |
| `intervention` | B | `InterventionEvent` | Aplicar, reaplicar, revertir o fallar una intervención |
| `block_abort` | B | `BlockAbort` | "Hoy no" |
| `outcome` | B (calcula A) | `BlockOutcome` con `status` final | Cuando `evaluate_block` devuelve `started`, `censored` o `device_off` |
| `council_run` | C | `CouncilRun` | Cada reunión del consejo, incluidos los vetos |
| `preregistration` | C | `Preregistration` | Antes del primer `assignment` del experimento |
| `resolution` | C | `Resolution` | Al alcanzar el N preregistrado. Revela la semilla |

## Invariantes que el consejo verifica al leer
- Cada `assignment` con `experiment_id` tiene un `preregistration` anterior con ese id.
- La secuencia de `arm` de un experimento, ordenada por `draw_index`, coincide con
  `permuted_arm(seed, experiment_id, i, treatment)` una vez revelada la semilla, y `sha256(seed) == seed_commitment`.
- Hay como máximo un `outcome` final por `block_id`.
- Hay como máximo un experimento sin `resolution` a la vez.

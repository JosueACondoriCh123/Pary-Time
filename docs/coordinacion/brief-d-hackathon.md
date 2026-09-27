# Brief hackathon · Claude, sesión D: la app lista para el jurado

> Para la sesión de Claude del Frente D. Worktree `C:\Users\HP\Documents\n-de-1\n-de-1-frente-d`, rama `frente-d`.
> **Antes de empezar: `git merge main`**, porque trae `contracts@1.1` con `Health.data_label`. Regenerá los tipos con
> `npm run contracts`. Entrega en **menos de 5 h**.
>
> **Aviso:** B2 ya está en `main` (ver el aviso en `docs/coordinacion/README.md`). La rama `frente-b2` quedó
> reemplazada: no la mergees ni la sigas.

## Contexto
Josué presenta hoy en una hackathon: demo en vivo, video de 2–3 min y repo público. El guion está en
`C:\Users\HP\.claude\plans\quiero-basarme-en-la-validated-cloud.md`, sección "Guion de la demo". En resumen:
1. Runtime en vivo con `demo-live`, que genera `tools/demo_live.py` del externo 2.
2. "Reunir al consejo" en vivo.
3. Resultados de 5 semanas simuladas en `demo-data`, que genera `python -m core.simulate` de Claude.
4. Privacidad y límites.

## Entregas
1. **Franja "DATOS SINTÉTICOS"** fija y visible en todas las vistas cuando `GET /health` → `data_label ==
   "sintetico"`. Tiene que ser una sola, clara, sin tapar contenido.
2. **Scripts:**
   - `npm run demo`: la app con `NDE1_DATA_DIR=<repo>/demo-data`. Si no existe, mensaje claro: correr
     `.venv\Scripts\python -m core.simulate --out demo-data --weeks 5 --seed 7`.
   - `npm run demo:live`: la app sobre `<repo>/demo-live`.
3. **Consejo legible para el jurado** (vista Experimento → "Reunir al consejo" y detalle del `CouncilRun`):
   - Cada propuesta como tarjeta: intervención, ratio esperado, justificación y las **5 herramientas** con ✅ o ❌ y su
     detalle.
   - El verificador rechazando una cifra inventada se tiene que entender sin explicación.
   - El pre-mortem aparte, con la etiqueta "sin poder de veto".
   - El preregistro con `seed_commitment` abreviado y el tooltip "la semilla se revela al terminar".
4. **Resultados:** la verificación de la semilla (`sha256(seed_revealed) == seed_commitment`, que ya calculás con
   WebCrypto) **grande y visible**: "✅ el sorteo no se tocó". Medianas, ratio y p contra α en una frase humana:
   "con la intervención arrancaste en la mitad de tiempo (p = 0.01 < α = 0.024)".
5. **Capturas:** `npm run shots` (Playwright contra `demo-data`) genera PNG de Planificador, Hoy, Consejo, Resultados
   y Reporte en `docs/hackathon/img/`. Un GIF corto del overlay y de la re-minimización si llegás (opcional).
6. **Ensayo:** correr el guion completo dos veces y anotar fricciones en `frente-d.md`.

## Reglas
- Solo `app/`, `packaging/` y tu `frente-d.md`. En `docs/hackathon/img/` solo las capturas.
- **Congelado:** no cambies cómo se oculta el brazo (`visibleArm`) ni muestres efectos parciales.
- Commits `feat(d): ...` en `frente-d`. Avisá en `frente-d.md`.

# Consejo N-de-1

Experimentos aleatorizados sobre **cómo arrancás a trabajar**, ejecutados por tu propia compu. Pensado para personas
con TDAH, donde una misma estrategia le sirve a unos y a otros no.

Declarás tus bloques de trabajo. Un consejo de agentes locales hace el resto:
1. propone una hipótesis sobre tus datos;
2. un Red Team de otra familia de modelo la ataca con estadística determinista;
3. se preregistra en un journal con cadena de hashes;
4. la compu sortea y aplica la intervención (abrir el trabajo sola, primer paso mínimo, retrasar distracciones,
   cuenta regresiva) y mide tu latencia de arranque;
5. al llegar al N preregistrado, un test de permutación dice si **en vos** funciona.

> Ajustes de flujo de trabajo medidos sobre una sola persona. No es tratamiento ni consejo médico.

Todo es local: el sensor, los modelos (Ollama) y los datos. Los títulos de ventana nunca salen del SQLite local, y el
journal se puede compartir.

## Estado
En construcción con 4 agentes en paralelo. Ver [`docs/coordinacion/`](docs/coordinacion/README.md).

| Documento | Para qué |
|---|---|
| [`docs/superpowers/specs/2026-09-26-consejo-n-de-1-design.md`](docs/superpowers/specs/2026-09-26-consejo-n-de-1-design.md) | El diseño |
| [`docs/outcome-rules.md`](docs/outcome-rules.md) | Reglas normativas de la métrica |
| [`docs/journal-events.md`](docs/journal-events.md) | Eventos del journal |
| [`contracts/README.md`](contracts/README.md) | Contratos y protocolo de arranque Electron ↔ núcleo |

## Desarrollo
```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m core --port 0 --data-dir data
```

El journal, el lock de proceso y el cliente LLM vienen de Night Council, del mismo autor.

# Procedencia de las trazas

- `start.synthetic.jsonl`: fixture construido a mano; no es actividad real.
- `phase2-windows-20260927.jsonl`: captura **real** de Windows de 20 segundos,
  realizada con `tools/capture/record.py phase2-windows-20260927 --seconds 20`.
  Contiene un tramo de `ShellHost.exe` inactivo. El título quedó vacío al pasar
  `tools/capture/sanitize.py`, sin argumentos `--keep`. El archivo crudo y su SQLite
  están ignorados por Git y no se incorporan a esta entrega.
- `phase2-windows-20260927.outcome.json`: resultado esperado revisado para un
  **bloque de prueba**, derivado de `contracts/examples/Block.json` y con su inicio
  situado al inicio de esa traza. No representa una tarea programada por Josué.
  Al fin realmente observado el resultado es `pending`, sin trabajo ni distracciones,
  con cobertura `20 / 5400`. No se adelanta el reloj para producir una censura.

Esta captura verifica el camino Win32 → compresión → SQLite → sanitización → outcome.
No valida arranques sostenidos, suspensión real ni 2–3 días de uso: esas trazas siguen
pendientes. No renombrar las trazas sintéticas para presentarlas como reales.

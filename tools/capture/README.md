# Captura local del Frente A

Desde `n-de-1/n-de-1-frente-a`, usando el Python 3.11 del proyecto padre:

```powershell
..\.venv\Scripts\python.exe tools/capture/record.py dia1 --hours 48
```

Dejá esta consola abierta mientras trabajás. `Ctrl+C` termina y exporta. No se instala
una tarea automática ni queda un proceso en segundo plano. Los datos se guardan cada
segundo en `data/capture-dia1.sqlite`; al terminar se exportan a
`tests/fixtures/traces/dia1.raw.jsonl`. Ambos quedan excluidos de Git por las reglas
existentes. La captura aplica `raw_retention_days` (14 por defecto); el archivo raw
exportado debe eliminarse manualmente cuando deje de ser necesario.

Si la consola o el equipo se cierran antes de exportar, recuperá la captura:

```powershell
..\.venv\Scripts\python.exe tools/capture/record.py dia1 --export-only
```

Sanitizá antes de compartir cualquier traza:

```powershell
..\.venv\Scripts\python.exe tools/capture/sanitize.py tests/fixtures/traces/dia1.raw.jsonl --keep cap3 --keep tesis
```

El resultado `dia1.jsonl` conserva proceso, tiempos, inactividad y bloqueo. En el título
solo quedan los tokens explícitamente permitidos y los patrones de distracción de
navegadores. La lista `--keep` debe contener fragmentos genéricos necesarios para los
matchers, nunca nombres, rutas ni textos personales. `--settings ruta/settings.json`
permite usar los patrones personalizados del usuario. El sanitizador no sobrescribe
archivos existentes ni imprime títulos, incluso si una línea tiene errores.

Para una prueba breve usá un nombre nuevo y `--seconds 5`. No confundas esa prueba
con la captura de 2–3 días que requiere la validación del proyecto.

## Formatos y límites

- Una línea JSON por `ActivitySpan`, conforme a `contracts/schemas/ActivitySpan.schema.json`.
- Los fixtures hechos a mano contienen `synthetic` en el nombre. No representan uso real.
- El primer muestreo establece un punto; el siguiente establece duración. Al cerrar o
  detectar un hueco se extrapola como máximo un segundo desde la última observación.
- Huecos de más de 5 segundos o saltos entre reloj monotónico y reloj civil no se
  convierten en trabajo continuo. Tras un salto hacia atrás se omiten observaciones
  hasta alcanzar el último timestamp guardado, evitando solapamientos.
- No se manipulan ventanas, teclado ni mouse. La captura observa la ventana activa
  en cualquier monitor. Un proceso inaccesible se registra como `?`.
- Los errores de muestreo se omiten y se informa solo su clase. Bajo `outcome@1`, los
  huecos por errores del sensor son indistinguibles de equipo apagado: la cobertura
  derivada permite detectarlos, pero haría falta un contrato nuevo para distinguirlos.

La implementación de las llamadas nativas sigue la documentación de Microsoft de
[QueryFullProcessImageNameW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew),
[OpenInputDesktop](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-openinputdesktop)
y [GetTickCount](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-gettickcount).
El empaquetado usa el formato documentado de
[specs de PyInstaller](https://pyinstaller.org/en/stable/spec-files.html).

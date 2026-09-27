# Chequeo antes de publicar

Desde la raíz de la copia que se va a publicar:

```powershell
python scripts/check_private.py
python scripts/check_private.py --history
```

Desde el worktree A se puede revisar la copia principal sin modificarla:

```powershell
python scripts/check_private.py --root .. --history
```

Se leen los archivos **versionados** que enumera `git ls-files`, con su contenido
actual en disco. Los archivos nuevos deben añadirse a Git antes del control final.
No se recorren `.git`, worktrees anidados, archivos ignorados ni datos locales sin
versionar. Un archivo aún versionado que se borró del disco se reporta como ilegible;
resolver o registrar esa eliminación antes del control final.

`--history` revisa líneas añadidas y eliminadas de los parches de todas las referencias
alcanzables, incluidos merges. Los metadatos de autor de Git se omiten; los emails
dentro de archivos sí se controlan. No revisa reflogs, objetos inaccesibles ni el
texto de los mensajes de commit. No modifica archivos, índice, ramas ni historial.

- Exit **0**: sin errores de las reglas implementadas; puede haber avisos.
- Exit **1**: emails, rutas de usuario fuera de docs, claves/tokens, archivos crudos
  prohibidos, títulos no permitidos o archivos ilegibles.
- Exit **2**: no pudo completarse el chequeo (Git, allowlist o acceso).

La salida muestra archivo, línea, regla y, en historial, commit; nunca el valor que
coincidió. Las rutas locales bajo `docs/` son avisos por decisión explícita del brief.
Las imágenes, videos y otros binarios se avisan para revisión manual: no se hace OCR.
Los patrones de texto son heurísticos; no certifican que un nombre o texto libre sea
anónimo ni detectan todos los formatos posibles de secretos.

`check_private_allow.txt` usa `regla|glob de archivo|valor exacto|motivo`. Solo el
nombre de archivo admite globs. Las excepciones existentes cubren ejemplos ficticios,
títulos sintéticos revisados, expresiones de código y atribución autorizada. No añadir
un secreto real a esa lista. Para títulos nuevos, revisar el fixture y añadir únicamente
los títulos genéricos necesarios para ese archivo. Un aviso histórico no desaparece
al borrar el dato actual: requiere revisión separada antes de publicar.

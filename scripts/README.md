# Chequeo antes de publicar

## Fase 6 de A: CI y candidato del sidecar

Instalar las dependencias de desarrollo y empaquetado en el Python elegido:
`python -m pip install -e ".[dev,packaging]"`. Commitear las fuentes antes de correr:

```powershell
python scripts/ci_a.py --out build/ci-a
# Windows x64: también reconstruye, prueba y empaqueta el ejecutable.
python scripts/ci_a.py --out build/candidate-a --build-sidecar --history
```

Cada salida debe ser una carpeta nueva bajo `build/`. Se exige un checkout limpio
antes de iniciar y se vuelve a comprobar el commit y estado al finalizar. Un
fallo detiene la cadena y deja `checks_passed=false` en `ci-report.json`. Preparación
fallida devuelve exit 2; chequeos fallidos, 1; todos aprobados, 0. Las fuentes no se
modifican y no se reutiliza `dist/` ni un workpath anterior.

Secuencia: exportación de contratos sin cambios, scanner de privacidad de archivos
versionados, suite completa de `tests/sensing`, smoke sintético de 181 s lógicos;
con `--build-sidecar`, PyInstaller limpio y smoke HTTP del ejecutable con pausa,
reinicio, prompts y autenticación. La ejecución breve no satisface las 48 h de F5.
`--history` añade el historial disponible en Git; una copia superficial no puede
auditar commits que no tiene. La suite general de todos los frentes sigue siendo
un chequeo adicional del integrador.

El candidato `nde1-core-windows-x64.zip` contiene TODO `nde1-core/` y un manifiesto
con commit, versión de Python, ruta relativa, tamaño y SHA-256 de cada archivo.
Se vuelve a leer el ZIP para comprobar cada hash antes de darle su nombre final.
`SHA256SUMS.txt` contiene el hash del ZIP. Se rechazan enlaces/junctions, entradas
fuera de la estructura prevista, datos crudos reconocidos por el scanner y bundles
sin EXE o prompts. Este formato se entrega a D; no es el instalador NSIS.

Solo compartir `ci-report.json`, `bundle-manifest.json`, `SHA256SUMS.txt` y el ZIP
tras revisar el resultado. Los logs detallados y el SQLite del smoke quedan bajo
`build/` para diagnóstico local; pueden incluir rutas del entorno y **no se suben**
por la plantilla. Los hashes comprueban integridad, no firma/autenticidad del autor.
Las dependencias conservan los rangos de `pyproject.toml`: no se promete un binario
idéntico byte por byte entre distintas instalaciones.

`scripts/ci-frente-a.yml` es una plantilla lista para que el **Frente 0** la integre
en `.github/workflows/frente-a.yml`: jobs Ubuntu y Windows, Python 3.11 x64, permisos
de lectura y subida exclusiva de los cuatro archivos indicados. No usa datos reales,
secretos, tags, GitHub Releases ni publicación automática. El workflow aún no está
activado desde `scripts/`; A respeta las carpetas asignadas por la coordinación.
Fuentes de las acciones usadas: [checkout](https://github.com/actions/checkout),
[setup-python](https://github.com/actions/setup-python) y
[upload-artifact](https://github.com/actions/upload-artifact).

La comprobación local de resolución/soak está en
`tools/capture/release_check.py`; ver `tools/capture/README.md`. No trasladar los
datos reales a CI para aprobarla. Una ejecución verde de CI solo valida el
candidato de A: `release_approved` permanece en `false`.

## Scanner de privacidad

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

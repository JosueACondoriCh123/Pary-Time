# Inicio, perfil y acceso de demo

La app abre en **Inicio**, con enlaces al planificador, Hoy, experimento y
resultados. Todas las herramientas siguen disponibles como invitado, también
desde la navegación del escritorio. La bandeja conserva sus destinos existentes.

**Mi perfil** permite guardar un nombre opcional y una intención. Se conservan
en `localStorage`, bajo `nde1.local-profile.v1`, solo al tocar Guardar perfil.
No cambian el sensor, los bloques, los contratos ni las reglas del experimento.
Si el almacenamiento no está disponible, se aplican durante la sesión y se
explica que no se conservarán. Una entrada corrupta recupera los valores iniciales.

**Iniciar sesión / Crear perfil** son simulaciones explícitas. Los formularios
validan datos de ejemplo, pero no envían solicitudes, crean cuentas reales ni
persisten correo o contraseña. La sesión de demo vive en memoria y vuelve a
invitado al recargar o cerrar. El nombre del registro también queda en memoria
hasta guardarlo expresamente desde Mi perfil. El acceso como invitado está
encima de los campos y funciona aunque estén vacíos. Cambiar de modo no borra
los bloques de esta instalación ni separa usuarios o datos.

Los componentes están en `src/views/{Welcome,Profile,Access}.tsx`, los datos de
presentación en `src/lib/local-profile.ts` y los estilos en `src/secondary.css`.
Los estilos aprovechan las variables del tema; no agregan fuentes ni paquetes.
Se verifican escritorio y anchos de 390 y 320 px. La navegación mueve el foco
al contenido y vuelve al inicio de la nueva pantalla.

## Desarrollo y comprobación

Desde `app/`, con sus dependencias instaladas:

```powershell
npm ci
npm run typecheck
npm run lint
npm test
npm run build
npm run test:secondary
```

`test:secondary` inicia Vite en `127.0.0.1:5207` con los ejemplos existentes de
contratos. Usa Edge en Windows, Chromium de Playwright en otros sistemas.
No inicia Electron ni el sensor. Capturas: `app/test-results/secondary/`,
ignoradas por Git. La franja DATOS DE EJEMPLO permanece visible.
El build de producción sigue rechazando `VITE_FIXTURES=1`.

Para abrir la vista previa en navegador desde PowerShell:

```powershell
$env:VITE_FIXTURES = '1'
npx vite --host 127.0.0.1 --port 5207
```

Después de detenerla, quitar esa variable (`Remove-Item Env:VITE_FIXTURES`)
antes de compilar para producción.

## Integración con el trabajo paralelo

La entrega está en la rama `frente-a`, por el pedido explícito de pantallas
secundarias. Se integró `main@c913de2`, que incorporó Mi tiempo durante este
trabajo: `History`, el destino `history` y sus contratos se conservan y la
prueba de acceso invitado también recorre esa sección. El tema glass seguía
sin commit en `main`; no se copió ni sobrescribió. Al integrar estas pantallas,
conservar esas fuentes y estilos. Las vistas nuevas no requieren modificar
el bridge de Electron ni el backend.

La allowlist de privacidad incorpora exclusivamente el correo ficticio del
dominio reservado `example.com`, con rutas y valor exactos para el placeholder,
la prueba y su propia documentación en la lista. No se agregó ninguna dirección
personal ni se amplió una excepción a todo el repositorio.

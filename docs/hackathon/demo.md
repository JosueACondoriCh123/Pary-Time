# Guion de la demo en vivo (~3:30)

## Antes de subir (10 min antes)
```powershell
cd C:\Users\HP\Documents\n-de-1
ollama ps                                   # Ollama arriba (si no: "ollama serve" o abrir la app de Ollama)
Remove-Item -Recurse -Force demo-live -ErrorAction SilentlyContinue
.venv\Scripts\python -m core.simulate --out demo-data --weeks 5 --seed 11 --llm cache   # solo si demo-data no existe (~5 min)
```
- Abrí **WhatsApp de escritorio** y **YouTube en Chrome** (con un video pausado). Tienen que verse en la barra de
  tareas.
- Cerrá la app de Consejo N-de-1 si quedó abierta: hay instancia única.
- Pantalla duplicada con el proyector; letra del sistema al 125%.

## 1. El problema (20 s), sin tocar nada
> "Con TDAH, lo que le sirve a otro no te dice nada sobre vos. Las apps te dan consejos genéricos. Nosotros hacemos
> que tu compu **experimente sobre vos**, con el rigor de un ensayo clínico, pero sobre una sola persona y todo local."

## 2. Runtime en vivo (70 s)
```powershell
.venv\Scripts\python tools/demo_live.py --data-dir demo-live --in 2m --arm retrasar_distracciones
cd app; npm run demo:live
```
1. La app abre con la franja **DATOS SINTÉTICOS**. En "Hoy" se ve el bloque que empieza en 2 min.
2. Arriba a la derecha, el **overlay**: "Tesis cap. 3 · arrancás en 1:5x".
   > "El sorteo decidió que este bloque lleva la intervención 'retrasar distracciones'."
3. A la hora del bloque, **WhatsApp y YouTube se minimizan solos**.
4. Abrí WhatsApp de nuevo: **se vuelve a minimizar** en ~2 s.
   > "Hasta que hagas 15 minutos de trabajo real."
5. "Salida de emergencia": todo vuelve.
   > "Siempre tenés la salida. Nunca se cierra nada, solo se minimiza."

**Plan B:** si WhatsApp no se minimiza, mostrá solo YouTube. Si el overlay no aparece, seguí: la intervención igual
se aplicó y la vista "Hoy" lo muestra.

## 3. El consejo delibera (60 s)
Cerrá la app. `npm run demo` (sobre `demo-data`) → **Experimento** → **Reunir al consejo ahora**.
- Tarda 60–90 s con Ollama. Mientras tanto contás esto:
  > "El Scout es Qwen y el Red Team es Granite, dos familias distintas, las dos corriendo en esta GPU de 6 GB. Nada
  > sale de la compu."
- Mostrá las tarjetas: la hipótesis y las **5 herramientas** con ✅/❌.
  > "El modelo propone, pero **no puede aprobar lo que la estadística rechaza**: acá la potencia vetó esta hipótesis
  > porque necesitaría 5 semanas."
- Si hay un ❌ del verificador:
  > "El modelo inventó una cifra y lo atrapamos."
- En `demo-data` ya se ve en la segunda reunión: Qwen dijo "47% de censura en lectura" y era 0%.
- El preregistro muestra el hash de la semilla.
  > "Esto se sella **antes** del primer sorteo."

**Plan B:** si Ollama tarda más de 2 min o falla, el consejo cae solo al respaldo determinista y lo dice en pantalla.
Eso también es parte del diseño.

## 4. Resultados de 5 semanas simuladas (40 s)
**Resultados** → el experimento resuelto:
- `cuenta_regresiva`: latencia mediana **14.2 → 9.0 min**, ratio **0.53**, **p = 0.002 < α = 0.024**;
- **"✅ el sorteo no se tocó"**: sha256 de la semilla revelada igual al compromiso, calculado en tu navegador;
- el ledger y el veto regret.

> "Estas 5 semanas las generó el **código real** con reloj acelerado y un efecto verdadero de 0.5. Recuperamos 0.53.
> En 10 semillas lo detecta 9 veces, y con efecto cero no descubre nada. Además el simulador nos encontró un error: nuestro primer test perdía el efecto
> al mezclar mañanas y tardes. Lo cambiamos antes de usarlo con una persona real."

## 5. Privacidad y límites (20 s)
**Reporte** → mostrá que no hay títulos ni nombres de archivo.
> "Esto se lo podés llevar a tu terapeuta. No es tratamiento ni consejo médico, es una sola persona, sin ciego y
> con poca potencia. Lo decimos en la app."

## Checklist del ensayo (dos corridas seguidas sin tocar nada fuera del guion)
- [ ] `demo_live.py` + `npm run demo:live`: overlay, minimizar, re-minimizar, emergencia
- [ ] `npm run demo`: Reunir al consejo con Ollama (medir el tiempo)
- [ ] Resultados: semilla ✅ visible sin hacer scroll
- [ ] Reporte sin textos privados
- [ ] Plan B de Ollama probado (con `ollama stop` o sin Ollama)

// Overlay: ventana transparente, siempre arriba y sin foco. Consulta /runtime/overlay cada 1 s.
import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { httpApi } from "./api";
import type { OverlayState } from "./contracts";
import { FIXTURES } from "./core";
import { overlayContent } from "./lib/overlay";
import "./styles.css";

const HIDDEN: OverlayState = { visible: false };

function Overlay() {
  const [state, setState] = useState<OverlayState>(HIDDEN);

  useEffect(() => {
    if (FIXTURES || !window.nde1) return; // en modo ejemplos el overlay no molesta
    const bridge = window.nde1;
    const api = httpApi(() => bridge.connection());
    let alive = true;
    const tick = async () => {
      try {
        const s = await api.overlay();
        if (alive) setState(s);
      } catch {
        if (alive) setState(HIDDEN); // 501 mientras B no esté, o el núcleo reiniciando
      }
    };
    void tick();
    const id = setInterval(tick, 1000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const content = overlayContent(state);
  const shown = content !== null;
  useEffect(() => window.nde1?.setOverlayVisible(shown), [shown]);

  if (!content) return null;
  return (
    <div className="overlay-card" role="status">
      <div className="overlay-caption">{content.caption}</div>
      <div className="overlay-text">{content.text}</div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Overlay />
  </StrictMode>,
);

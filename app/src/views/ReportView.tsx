// "Reporte": integridad del journal y exportación en HTML autocontenido o JSON.
import { useState } from "react";
import { useLoad } from "../core";
import { DEFAULT_DISCLAIMER, reportHtml } from "../lib/report";
import { dateTime, today } from "../lib/time";
import { Card, Disclaimer, ErrorNote } from "../ui";
import { useSeedChecks } from "./Results";

export function ReportView() {
  const report = useLoad((a) => a.report(), []);
  const verify = useLoad((a) => a.verifyJournal(), []);
  const checks = useSeedChecks(report.data?.experiments);
  const [saved, setSaved] = useState<string | null>(null);
  const r = report.data;

  async function save(ext: "html" | "json") {
    if (!r || !window.nde1) return;
    const content = ext === "html" ? reportHtml(r, checks) : JSON.stringify(r, null, 2);
    const ok = await window.nde1.saveFile({ defaultName: `consejo-n-de-1-${today()}.${ext}`, content, ext });
    setSaved(ok ? `Guardado como ${ext.toUpperCase()}.` : null);
  }

  return (
    <div className="view">
      <header className="view-head">
        <h1>Reporte</h1>
      </header>
      <Disclaimer text={r?.disclaimer || DEFAULT_DISCLAIMER} />

      <Card>
        <h2>Journal</h2>
        <ErrorNote error={verify.error} />
        {verify.data && (
          <p className={verify.data.ok ? "pass" : "fail"}>
            {verify.data.ok
              ? `✓ Cadena de hashes íntegra: ${verify.data.n_events} eventos.`
              : `✗ La cadena no verifica: ${verify.data.error ?? "error desconocido"}`}
          </p>
        )}
        <p className="muted small">
          Cada decisión queda encadenada con un hash. Si alguien edita una línea, esto deja de verificar.
        </p>
      </Card>

      <Card>
        <h2>Exportar</h2>
        <ErrorNote error={report.error} />
        {r && (
          <>
            <p className="muted small">
              Generado el {dateTime(r.generated_ms)} · {r.experiments.length}{" "}
              {r.experiments.length === 1 ? "experimento" : "experimentos"}. Sin títulos de ventana ni textos
              personales: se puede compartir con un profesional.
            </p>
            <div className="row">
              <button type="button" className="primary" disabled={!window.nde1} onClick={() => void save("html")}>
                Guardar como HTML
              </button>
              <button type="button" disabled={!window.nde1} onClick={() => void save("json")}>
                Guardar como JSON
              </button>
              {saved && <span className="pass small">{saved}</span>}
            </div>
          </>
        )}
      </Card>
    </div>
  );
}

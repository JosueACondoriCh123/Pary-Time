// "Mi tiempo": todo el tiempo en la compu, clasificado y ordenado. Solo agregados del núcleo: apps y sitios de
// distracción por nombre, nunca títulos de ventana.
import { useState } from "react";
import type { ActivityHistory } from "../contracts";
import { useLoad } from "../core";
import {
  CAT_COLOR, CAT_LABEL, CATEGORIES, RANGE_LABEL, dayLabel, donutArcs, fmtMinutes, pct, rangeFor, sumCats,
  type RangeKind, type UsageCat,
} from "../lib/usage";
import { Card, Chips, ErrorNote } from "../ui";

const ACTIVE: UsageCat[] = ["work", "distraction", "other"];

export function History() {
  const [range, setRange] = useState<RangeKind>("week");
  const [from, to] = rangeFor(range);
  const h = useLoad((a) => a.activityHistory(from, to), [from, to], 60_000);
  const data = h.data;

  return (
    <div className="view history">
      <header className="view-head">
        <h1>Mi tiempo</h1>
        <Chips<RangeKind> name="Rango" options={["today", "week", "twoWeeks"]} value={range}
                          label={(r) => RANGE_LABEL[r]} onChange={setRange} />
      </header>
      <ErrorNote error={h.error} />
      {data && (data.active_minutes === 0 && sumCats(data.totals) === 0 ? <Empty history={data} /> : <Body history={data} range={range} />)}
    </div>
  );
}

function Empty({ history }: { history: ActivityHistory }) {
  return (
    <Card>
      <h2>Todavía no hay actividad en este rango.</h2>
      <p className="muted">El sensor registra la ventana activa mientras la app está abierta. Se guardan los últimos {history.retention_days} días.</p>
    </Card>
  );
}

function Body({ history: d, range }: { history: ActivityHistory; range: RangeKind }) {
  return (
    <>
      <div className="kpis">
        <Kpi label="Tiempo activo" value={fmtMinutes(d.active_minutes)} />
        <Kpi label="Trabajo en bloques" value={pct(d.work_share)} tone="work" />
        <Kpi label="Distracción" value={pct(d.distraction_share)} tone="distraction" />
        <Kpi label="Foco más largo" value={fmtMinutes(d.longest_focus_min)} hint="en una misma app, sin cortar" />
        <Kpi label="Cambios de app" value={`${d.switches_per_hour.toFixed(1)}/h`} hint="por hora activa" />
      </div>

      <div className="history-grid">
        <Card className="span-2">
          <h2>{range === "today" ? "Hoy, por categoría" : "Por día"}</h2>
          {range === "today" ? <HourBars history={d} /> : <DayBars history={d} />}
          <Legend />
        </Card>
        <Card>
          <h2>Reparto</h2>
          <Donut history={d} />
        </Card>
        <Card>
          <h2>Apps</h2>
          <AppRanking history={d} />
        </Card>
        {range !== "today" && (
          <Card className="span-2">
            <h2>Hora del día</h2>
            <p className="muted small">Minutos sumados de todos los días del rango: cuándo trabajás y cuándo te distraés.</p>
            <HourBars history={d} />
          </Card>
        )}
        <Card>
          <h2>Sitios de distracción</h2>
          {d.sites.length === 0 ? <p className="muted">Ninguno en este rango.</p> : (
            <ul className="sites">
              {d.sites.map((s) => (
                <li key={s.site}><span>{s.site}</span><strong>{fmtMinutes(s.minutes)}</strong></li>
              ))}
            </ul>
          )}
          <p className="muted small">Solo el patrón que coincidió, nunca el título de la ventana.</p>
        </Card>
      </div>
      <p className="muted small">Se guardan los últimos {d.retention_days} días de actividad detallada; lo anterior se borra por privacidad.</p>
    </>
  );
}

function Kpi({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: UsageCat }) {
  return (
    <div className="kpi" style={tone ? { borderTopColor: CAT_COLOR[tone] } : undefined}>
      <span className="kpi-label">{label}</span>
      <strong className="kpi-value">{value}</strong>
      {hint && <span className="kpi-hint">{hint}</span>}
    </div>
  );
}

function Legend() {
  return (
    <ul className="legend">
      {CATEGORIES.map((c) => (
        <li key={c}><i style={{ background: CAT_COLOR[c] }} />{CAT_LABEL[c]}</li>
      ))}
    </ul>
  );
}

/** Barras apiladas por día (solo tiempo con la compu prendida: activo + inactivo + pausa). */
function DayBars({ history }: { history: ActivityHistory }) {
  const W = 640, H = 200, pad = 26;
  const max = Math.max(60, ...history.days.map((d) => sumCats(d.minutes_by_category)));
  const bw = (W - pad) / history.days.length;
  return (
    <svg className="chart" viewBox={`0 -12 ${W} ${H + 34}`} role="img" aria-label="Minutos por día y categoría">
      {[0.5, 1].map((f) => (
        <g key={f}>
          <line x1={pad} x2={W} y1={H - f * H} y2={H - f * H} className="grid" />
          <text x={0} y={H - f * H + 4} className="axis">{Math.round((f * max) / 60)}h</text>
        </g>
      ))}
      {history.days.map((d, i) => {
        let y = H;
        return (
          <g key={d.local_date}>
            {CATEGORIES.map((c) => {
              const v = d.minutes_by_category[c] ?? 0;
              const hgt = (v / max) * H;
              y -= hgt;
              return v > 0 ? (
                <rect key={c} x={pad + i * bw + bw * 0.15} y={y} width={bw * 0.7} height={hgt} fill={CAT_COLOR[c]} rx={2}>
                  <title>{`${dayLabel(d.local_date)} · ${CAT_LABEL[c]}: ${fmtMinutes(v)}`}</title>
                </rect>
              ) : null;
            })}
            <text x={pad + i * bw + bw / 2} y={H + 16} textAnchor="middle" className="axis">{dayLabel(d.local_date)}</text>
          </g>
        );
      })}
    </svg>
  );
}

/** 24 barras apiladas: una por hora local. */
function HourBars({ history }: { history: ActivityHistory }) {
  const W = 640, H = 150, pad = 4;
  const max = Math.max(10, ...history.hours.map((h) => sumCats(h.minutes_by_category, ACTIVE)));
  const bw = (W - pad) / 24;
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H + 20}`} role="img" aria-label="Minutos activos por hora del día">
      {history.hours.map((h) => {
        let y = H;
        return (
          <g key={h.hour}>
            {ACTIVE.map((c) => {
              const v = h.minutes_by_category[c] ?? 0;
              const hgt = (v / max) * H;
              y -= hgt;
              return v > 0 ? (
                <rect key={c} x={pad + h.hour * bw + 2} y={y} width={bw - 4} height={hgt} fill={CAT_COLOR[c]} rx={2}>
                  <title>{`${h.hour}:00 · ${CAT_LABEL[c]}: ${fmtMinutes(v)}`}</title>
                </rect>
              ) : null;
            })}
            {h.hour % 3 === 0 && <text x={pad + h.hour * bw + bw / 2} y={H + 15} textAnchor="middle" className="axis">{h.hour}h</text>}
          </g>
        );
      })}
    </svg>
  );
}

function Donut({ history }: { history: ActivityHistory }) {
  const arcs = donutArcs(history.totals);
  const total = sumCats(history.totals);
  return (
    <div className="donut">
      <svg viewBox="-70 -70 140 140" role="img" aria-label="Reparto del tiempo por categoría">
        {arcs.map((a) => (
          <path key={a.cat} d={a.d} fill={CAT_COLOR[a.cat]}><title>{`${CAT_LABEL[a.cat]}: ${fmtMinutes(a.minutes)}`}</title></path>
        ))}
        <text y={-2} textAnchor="middle" className="donut-total">{fmtMinutes(total)}</text>
        <text y={14} textAnchor="middle" className="axis">con la compu</text>
      </svg>
      <ul className="legend vertical">
        {CATEGORIES.filter((c) => (history.totals[c] ?? 0) > 0).map((c) => (
          <li key={c}><i style={{ background: CAT_COLOR[c] }} />{CAT_LABEL[c]} <strong>{fmtMinutes(history.totals[c])}</strong></li>
        ))}
      </ul>
    </div>
  );
}

function AppRanking({ history }: { history: ActivityHistory }) {
  if (history.apps.length === 0) return <p className="muted">Sin apps con más de un minuto.</p>;
  const max = history.apps[0].minutes;
  return (
    <ol className="apps">
      {history.apps.slice(0, 10).map((a) => (
        <li key={a.process}>
          <span className="app-name" title={CAT_LABEL[a.category]}>{a.process.replace(/\.exe$/i, "")}</span>
          <span className="app-bar"><i style={{ width: `${(a.minutes / max) * 100}%`, background: CAT_COLOR[a.category] }} /></span>
          <span className="app-min">{fmtMinutes(a.minutes)}</span>
        </li>
      ))}
    </ol>
  );
}

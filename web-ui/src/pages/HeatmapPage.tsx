// src/pages/HeatmapPage.tsx
import React, { useEffect, useState } from "react";
import { fetchAnalyticsSummary, fetchCameras } from "../lib/api";
import { fetchOccupancyAll, fetchRisk, fetchMatrix } from "../lib/api";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, CartesianGrid, PieChart, Pie, Cell } from "recharts";

const SEV_COLORS: Record<string, string> = {
  low: "#6ee7b7",
  medium: "#fbbf24",
  high: "#ef4444",
};

export default function HeatmapPage() {
  const [summary, setSummary] = useState<any>(null);
  const [cameras, setCameras] = useState<string[]>([]);
  const [tick, setTick] = useState(0);
  const [occ, setOcc] = useState<Record<string, number>>({});
  const [risk, setRisk] = useState<{ severityPie: any[]; riskByCamera: { camera_id: string; risk: number }[] } | null>(null);
  const [matrix, setMatrix] = useState<{ types: string[]; matrix: any[] } | null>(null);

  // refresh heatmap image
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const s = await fetchAnalyticsSummary();
        setSummary(s);
        const c = await fetchCameras();
        setCameras(c.cameras || []);
        const r = await fetchRisk();
        setRisk(r);
        const m = await fetchMatrix();
        setMatrix(m);
      } catch (e) { console.error(e); }
    })();
  }, []);

  // poll occupancy every 1s
  useEffect(() => {
    const poll = async () => {
      try {
        const o = await fetchOccupancyAll();
        const map: Record<string, number> = {};
        for (const it of o.cameras || []) map[it.camera_id] = it.occupancy;
        setOcc(map);
      } catch (e) { /* ignore */ }
    };
    poll();
    const id = setInterval(poll, 1000);
    return () => clearInterval(id);
  }, []);

  // risk lookup helper
  const riskFor = (cam: string) => risk?.riskByCamera?.find(x => x.camera_id === cam)?.risk ?? 0;

  return (
    <div className="p-4 space-y-6">
      <h1 className="text-2xl font-bold">Heatmaps & Analytics</h1>

      {/* Heatmaps with occupancy & risk chips */}
      <section className="grid md:grid-cols-2 gap-6">
        {cameras.map((cam) => (
          <div key={cam} className="border rounded-xl p-3 bg-black/40">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                <h2 className="font-semibold">{cam}</h2>
                <span className="px-2 py-0.5 rounded-full text-xs bg-blue-500/20 text-blue-300 border border-blue-500/30">
                  Occupancy: {occ[cam] ?? 0}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400">live</span>
                <span className={`px-2 py-0.5 rounded-full text-xs border ${
                    (riskFor(cam) >= 70 && "bg-red-500/20 text-red-300 border-red-500/40") ||
                    (riskFor(cam) >= 35 && "bg-yellow-500/20 text-yellow-200 border-yellow-500/40") ||
                    "bg-green-500/20 text-green-300 border-green-500/40"
                }`}>
                  Risk {riskFor(cam)}
                </span>
              </div>
            </div>
            <img
              src={`http://localhost:8001/heatmap/${cam}?mode=overlay&palette=turbo&alpha=0.65&t=${tick}`}
              alt={`heatmap ${cam}`}
              crossOrigin="anonymous"
              referrerPolicy="no-referrer"
              className="w-full rounded-lg"
            />
          </div>
        ))}
      </section>

      {/* Severity pie + Events by Type / Camera */}
      <section className="grid md:grid-cols-2 gap-6">
        <div className="border rounded-xl p-3 bg-black/40">
          <h3 className="font-semibold mb-2">Severity (24h)</h3>
          {risk?.severityPie?.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={risk.severityPie} dataKey="count" nameKey="severity" innerRadius={60} outerRadius={90} stroke="#0b0f14">
                  {risk.severityPie.map((s, i) => (
                    <Cell key={i} fill={SEV_COLORS[s.severity] || "#5b8cff"} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "#0b0f14",
                    border: "1px solid #243241",
                    color: "#e6eefc"
                  }}
                  itemStyle={{ color: "#e6eefc" }}
                  labelStyle={{ color: "#e6eefc" }}
                />

              </PieChart>
            </ResponsiveContainer>
          ) : <div className="text-sm text-gray-400">No data</div>}
        </div>

        <div className="border rounded-xl p-3 bg-black/40">
          <h3 className="font-semibold mb-2">Events by Camera (24h)</h3>
          {summary && (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={summary.byCamera}>
                <CartesianGrid stroke="#2a2a2a" />
                <XAxis dataKey="camera_id" stroke="#bdbdbd" tick={{ fill: "#bdbdbd" }} />
                <YAxis allowDecimals={false} stroke="#bdbdbd" tick={{ fill: "#bdbdbd" }} />
                <Tooltip contentStyle={{ background: "#0b0f14", border: "1px solid #243241", color: "#e6eefc" }} />
                <Bar dataKey="count" fill="#5b8cff" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </section>

      {/* Time-of-day matrix */}
      <section className="border rounded-xl p-3 bg-black/40">
        <h3 className="font-semibold mb-3">Time-of-Day Matrix (last 24h)</h3>
        {matrix ? (
          <TimeOfDayMatrix types={matrix.types} matrix={matrix.matrix} />
        ) : (
          <div className="text-sm text-gray-400">No data</div>
        )}
      </section>
    </div>
  );
}

// ---- tiny matrix renderer (CSS grid) ----
function TimeOfDayMatrix({ types, matrix }: { types: string[]; matrix: any[] }) {
  // Build max for scaling colors
  const max = Math.max(1, ...matrix.flatMap((row: any) => types.map((t) => row[t] || 0)));
  const cell = (v: number) => {
    const p = v / max; // 0..1
    // blue scale on dark bg
    const bg = `rgba(91,140,255,${0.15 + 0.85 * p})`;
    const br = `rgba(255,255,255,0.05)`;
    return { background: bg, border: `1px solid ${br}` };
  };
  return (
    <div className="overflow-auto">
      <div className="min-w-[720px]">
        <div className="grid" style={{ gridTemplateColumns: `120px repeat(24, 1fr)` }}>
          {/* header row */}
          <div></div>
          {Array.from({ length: 24 }).map((_, h) => (
            <div key={h} className="text-center text-xs text-gray-400 py-1">{h}</div>
          ))}
          {/* rows */}
          {types.map((t) => (
            <React.Fragment key={t}>
              <div className="text-right pr-2 text-sm text-gray-300 py-1">{t}</div>
              {matrix.map((row: any, h: number) => (
                <div key={`${t}-${h}`} className="h-6" style={cell(row[t] || 0)} />
              ))}
            </React.Fragment>
          ))}
        </div>
      </div>
    </div>
  );
}

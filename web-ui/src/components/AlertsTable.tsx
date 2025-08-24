import { useEffect, useMemo, useState } from "react";
import { fetchEvents } from "../lib/api";
import type { Event } from "../lib/api";
import EventDrawer, { type EventT } from "./EventDrawer";
import { badgeColor, fmtTime } from "../lib/format";
import { clsx } from "clsx";

const TYPES = [
  "abandoned_object","intrusion","loitering","camera_tamper",
  "ppe_missing","fall","violence_proxy"
];

export default function AlertsTable() {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [sevFilter, setSevFilter] = useState<string>("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [selected, setSelected] = useState<EventT | undefined>();
  const [drawerOpen, setDrawerOpen] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await fetchEvents(typeFilter ? { type: typeFilter } : {});
      setEvents(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); /* load on mount & when type changes */ }, [typeFilter]);

  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [autoRefresh, typeFilter]);

  const filtered = useMemo(
    () => events.filter(e => (sevFilter ? e.severity === sevFilter : true)),
    [events, sevFilter]
  );

  return (
    <div className="p-4">
      <div className="flex items-center gap-3 flex-wrap">
        <h2 className="text-xl font-semibold">Recent Events</h2>
        <div className="grow" />
        <label className="text-sm text-gray-400 flex items-center gap-2">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={e => setAutoRefresh(e.target.checked)}
          />
          Auto‑refresh 5s
        </label>
        <button
          onClick={load}
          className="text-sm px-3 py-1 rounded border border-gray-700 hover:bg-white/10"
        >
          Refresh now
        </button>
      </div>

      <div className="mt-3 flex items-center gap-2 flex-wrap">
        <select
          className="bg-gray-900 border border-gray-800 rounded px-2 py-1 text-sm"
          value={typeFilter}
          onChange={e=>setTypeFilter(e.target.value)}
        >
          <option value="">All types</option>
          {TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>

        <select
          className="bg-gray-900 border border-gray-800 rounded px-2 py-1 text-sm"
          value={sevFilter}
          onChange={e=>setSevFilter(e.target.value)}
        >
          <option value="">All severities</option>
          <option value="high">high</option>
          <option value="med">med</option>
          <option value="low">low</option>
        </select>
      </div>

      {loading ? (
        <div className="p-4 text-gray-400">Loading events…</div>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full border border-gray-800 text-sm">
            <thead className="bg-gray-900">
              <tr>
                <th className="px-2 py-1 text-left">Time</th>
                <th className="px-2 py-1 text-left">Type</th>
                <th className="px-2 py-1 text-left">Camera</th>
                <th className="px-2 py-1 text-left">Zone</th>
                <th className="px-2 py-1 text-left">Severity</th>
                <th className="px-2 py-1 text-left">Explanation</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((ev) => (
                <tr
                  key={ev._id}
                  className="border-t border-gray-800 hover:bg-gray-900 cursor-pointer"
                  onClick={() => { setSelected(ev as unknown as EventT); setDrawerOpen(true); }}
                >
                  <td className="px-2 py-1">{fmtTime(ev.ts_utc)}</td>
                  <td className="px-2 py-1 font-medium">{ev.event_type}</td>
                  <td className="px-2 py-1">{ev.camera_id}</td>
                  <td className="px-2 py-1">{ev.zone ?? "-"}</td>
                  <td className="px-2 py-1">
                    <span className={clsx("px-2 py-0.5 rounded border", badgeColor(ev.severity))}>
                      {ev.severity ?? "low"}
                    </span>
                  </td>
                  <td className="px-2 py-1 text-gray-300 truncate max-w-[480px]">
                    {ev.explanation ?? "-"}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={6} className="px-2 py-6 text-center text-gray-500">No events yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <EventDrawer open={drawerOpen} onOpenChange={setDrawerOpen} event={selected} />
    </div>
  );
}

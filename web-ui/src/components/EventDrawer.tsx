import * as Dialog from "@radix-ui/react-dialog";
import { fmtTime, badgeColor } from "../lib/format";
import { useEffect, useRef } from "react";
import { clsx } from "clsx";

export type EventT = {
  _id: string;
  ts_utc: string;
  camera_id: string;
  event_type: string;
  severity?: string;
  zone?: string;
  explanation?: string;
  metrics?: Record<string, any>;
  tracks?: Array<{track_id:number; klass:string; role?:string;}>;
  artifacts?: { clip_mp4?: string; keyframes?: string[]; overlay_json?: string; crops?: {label:string; path:string}[] };
};

export default function EventDrawer({
  open, onOpenChange, event
}: { open: boolean; onOpenChange: (o:boolean)=>void; event?: EventT }) {

  const jsonRef = useRef<HTMLDetailsElement>(null);
  useEffect(() => { if (open && jsonRef.current) jsonRef.current.open = false; }, [open]);

  if (!event) return null;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60" />
        <Dialog.Content className="fixed right-0 top-0 h-full w-[520px] bg-gray-950 border-l border-gray-800 p-4 overflow-y-auto">
          <div className="flex items-start justify-between">
            <Dialog.Title className="text-xl font-semibold">
              {event.event_type}
            </Dialog.Title>
            <Dialog.Close className="px-2 py-1 rounded bg-white/10 hover:bg-white/20">✕</Dialog.Close>
          </div>

          <div className="mt-3 space-y-2 text-sm">
            <div className="flex gap-2 flex-wrap">
              <span className={clsx("px-2 py-0.5 rounded border", badgeColor(event.severity))}>
                {event.severity ?? "low"}
              </span>
              <span className="px-2 py-0.5 rounded border border-gray-800 text-gray-300">
                Cam: {event.camera_id}
              </span>
              {event.zone && (
                <span className="px-2 py-0.5 rounded border border-gray-800 text-gray-300">
                  Zone: {event.zone}
                </span>
              )}
              <span className="px-2 py-0.5 rounded border border-gray-800 text-gray-400">
                {fmtTime(event.ts_utc)}
              </span>
            </div>

            {event.explanation && (
              <p className="text-gray-200 mt-2">{event.explanation}</p>
            )}

            {event.tracks?.length ? (
              <div className="mt-2">
                <h4 className="text-gray-400 font-medium">Tracks</h4>
                <ul className="mt-1 space-y-1">
                  {event.tracks.map(t => (
                    <li key={t.track_id} className="text-gray-300">
                      #{t.track_id} • {t.klass}{t.role?` (${t.role})`:""}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {event.metrics && (
              <div className="mt-2">
                <h4 className="text-gray-400 font-medium">Metrics</h4>
                <div className="mt-1 grid grid-cols-2 gap-2">
                  {Object.entries(event.metrics).map(([k,v]) => (
                    <div key={k} className="rounded border border-gray-800 p-2">
                      <div className="text-xs text-gray-400">{k}</div>
                      <div className="text-gray-200">{String(v)}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <details ref={jsonRef} className="mt-3">
              <summary className="cursor-pointer text-gray-400 hover:text-gray-200">Raw JSON</summary>
              <pre className="mt-2 text-xs bg-black/40 p-2 rounded border border-gray-900 overflow-x-auto">
                {JSON.stringify(event, null, 2)}
              </pre>
            </details>

            {event.artifacts?.clip_mp4 ? (
              <div className="mt-3">
                <h4 className="text-gray-400 font-medium">Clip</h4>
                <video
                  controls
                  preload="metadata"
                  className="mt-1 w-full rounded border border-gray-800"
                  crossOrigin="anonymous"
                >
                  <source src={event.artifacts.clip_mp4} type="video/mp4" />
                </video>

              </div>
            ) : null}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

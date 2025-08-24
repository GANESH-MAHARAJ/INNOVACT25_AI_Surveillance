import { Router } from "express";
import Event from "../models/Event";
import dayjs from "dayjs";

const r = Router();

/**
 * CREATE EVENT
 * POST /events
 * Body: {
 *   ts_utc?: string | number,  // ISO or epoch ms/sec; will be parsed to Date
 *   camera_id: string,
 *   event_type: string,
 *   severity?: "low" | "med" | "high",
 *   zone?: string,
 *   metrics?: object,
 *   tracks?: Array<{ track_id?: number; klass?: string; role?: string }>,
 *   artifacts?: { clip_mp4?: string; keyframes?: string[]; overlay_json?: string;
 *                 crops?: Array<{ label?: string; path?: string }> },
 *   explanation?: string,
 *   tags?: string[]
 * }
 */
r.post("/", async (req, res) => {
  try {
    const body = req.body || {};
    const { camera_id, event_type } = body;
    if (!camera_id || !event_type) {
      return res.status(400).json({ ok: false, error: "camera_id and event_type are required" });
    }

    // Normalize ts_utc -> Date
    const tsRaw = body.ts_utc ?? Date.now();
    let ts: Date | null = null;
    if (typeof tsRaw === "number") {
      // seconds or ms
      ts = new Date(tsRaw < 2e10 ? tsRaw * 1000 : tsRaw);
    } else if (typeof tsRaw === "string") {
      const d = dayjs(tsRaw);
      if (!d.isValid()) {
        return res.status(400).json({ ok: false, error: "invalid ts_utc" });
      }
      ts = d.toDate();
    } else if (tsRaw instanceof Date) {
      ts = tsRaw;
    } else {
      ts = new Date();
    }

    const doc = await Event.create({
      ts_utc: ts,
      camera_id,
      event_type,
      severity: body.severity ?? "med",
      zone: body.zone,
      tracks: body.tracks ?? [],
      metrics: body.metrics ?? {},
      artifacts: body.artifacts ?? {},
      explanation: body.explanation,
      tags: body.tags ?? []
    });

    return res.status(201).json({ ok: true, id: doc._id, event: doc });
  } catch (e: any) {
    console.error(e);
    return res.status(500).json({ ok: false, error: e?.message || "error" });
  }
});

/**
 * ATTACH A CLIP TO A NEARBY EVENT (±5s)
 * POST /events/attach
 */
r.post("/events/attach", async (req, res) => {
  try {
    const { camera_id, event_type, ts_utc, clip_mp4 } = req.body || {};
    if (!camera_id || !event_type || !ts_utc || !clip_mp4) {
      return res.status(400).json({ ok: false, error: "camera_id, event_type, ts_utc, clip_mp4 required" });
    }
    const ts = dayjs(ts_utc);
    if (!ts.isValid()) {
      return res.status(400).json({ ok: false, error: "invalid ts_utc" });
    }
    const start = ts.subtract(5, "second").toDate();
    const end = ts.add(5, "second").toDate();

    const doc = await Event.findOneAndUpdate(
      { camera_id, event_type, ts_utc: { $gte: start, $lte: end } },
      { $set: { "artifacts.clip_mp4": clip_mp4 } },
      { new: true }
    );

    return res.json({ ok: true, updated: !!doc });
  } catch (e: any) {
    console.error(e);
    return res.status(500).json({ ok: false, error: e?.message || "error" });
  }
});

/**
 * LIST EVENTS
 * GET /events?type=&cam=&zone=&start=&end=
 */
r.get("/", async (req, res) => {
  const { type, cam, zone, start, end } = req.query as any;
  const q: any = {};
  if (type) q.event_type = type;
  if (cam) q.camera_id = cam;
  if (zone) q.zone = zone;
  if (start || end)
    q.ts_utc = {
      ...(start ? { $gte: new Date(start) } : {}),
      ...(end ? { $lte: new Date(end) } : {}),
    };
  const data = await Event.find(q).sort({ ts_utc: -1 }).limit(200);
  res.json(data);
});

/**
 * LIST DISTINCT CAMERAS
 * GET /events/cameras
 */
r.get("/cameras", async (_req, res) => {
  try {
    const cams = await Event.distinct("camera_id");
    res.json({ ok: true, cameras: cams });
  } catch (e: any) {
    res.status(500).json({ ok: false, error: e?.message || "error" });
  }
});

export default r;

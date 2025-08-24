import { Router } from "express";
import dayjs from "dayjs";
import EventModel from "../models/Event";

const router = Router();

// Customize your mapping here
const SEVERITY_OF: Record<string, "low"|"medium"|"high"> = {
  loitering: "medium",
  intrusion: "high",
  fall: "high",
  camera_tamper: "high",
  abandoned_object: "high",
  ppe_missing: "medium",
  violence_proxy: "high",
};

const WEIGHT_OF: Record<"low"|"medium"|"high", number> = {
  low: 1,
  medium: 3,
  high: 7,
};

// ---------- Severity Pie + Risk Index (relative scaling) ----------
router.get("/risk", async (req, res) => {
  const windowHrs = Number(req.query.hours ?? 24); // optional ?hours=12
  const since = dayjs().subtract(windowHrs, "hour").toDate();

  try {
    // 1) counts by event type (for severity pie)
    const byType = await EventModel.aggregate([
      { $match: { ts_utc: { $gte: since } } },
      { $group: { _id: "$event_type", count: { $sum: 1 } } },
      { $project: { _id: 0, event_type: "$_id", count: 1 } }
    ]);

    // map to severity buckets
    const sevCounts: Record<"low"|"medium"|"high", number> = { low: 0, medium: 0, high: 0 };
    for (const row of byType) {
      const sev = (SEVERITY_OF[row.event_type] ?? "low") as "low"|"medium"|"high";
      sevCounts[sev] += row.count;
    }
    const severityPie = (["low","medium","high"] as const)
      .filter(s => sevCounts[s] > 0)
      .map(s => ({ severity: s, count: sevCounts[s] }));

    // 2) weighted risk per camera
    const byCamType = await EventModel.aggregate([
      { $match: { ts_utc: { $gte: since } } },
      { $group: { _id: { cam: "$camera_id", type: "$event_type" }, count: { $sum: 1 } } },
      { $project: { _id: 0, camera_id: "$_id.cam", event_type: "$_id.type", count: 1 } }
    ]);

    // accumulate weighted counts
    const acc: Record<string, number> = {};
    for (const row of byCamType) {
      const sev = (SEVERITY_OF[row.event_type] ?? "low") as "low"|"medium"|"high";
      const w = WEIGHT_OF[sev];
      acc[row.camera_id] = (acc[row.camera_id] ?? 0) + w * row.count;
    }

    // relative scaling: top camera = 100, others scale 0..100
    const vals = Object.values(acc);
    const maxRaw = vals.length ? Math.max(...vals) : 1; // avoid div-by-zero
    const riskByCamera = Object.keys(acc).map(cam => ({
      camera_id: cam,
      raw: acc[cam],
      risk: Math.round((acc[cam] / maxRaw) * 100)
    }));

    // sort by risk desc for nicer UI
    riskByCamera.sort((a, b) => b.risk - a.risk);

    return res.json({
      ok: true,
      windowHours: windowHrs,
      severityPie,
      riskByCamera,
      weights: WEIGHT_OF
    });
  } catch (e: any) {
    console.error(e);
    return res.status(500).json({ ok: false, error: e?.message || "error" });
  }
});

// ---------- Time-of-Day Matrix (last 24h, grouped by local hour) ----------
router.get("/matrix", async (req, res) => {
  const now = dayjs();
  const since = now.subtract(24, "hour").toDate();

  try {
    const rows = await EventModel.aggregate([
      { $match: { ts_utc: { $gte: since } } },
      {
        $group: {
          _id: {
            h: { $hour: "$ts_utc" },  // hour in UTC; for local TZ use $dateToParts with timezone if needed
            t: "$event_type"
          },
          count: { $sum: 1 }
        }
      },
      { $project: { _id: 0, hour: "$_id.h", event_type: "$_id.t", count: 1 } },
      { $sort: { hour: 1, event_type: 1 } }
    ]);

    // Build a matrix with all 24 hours and all types present
    const types = Array.from(new Set(rows.map(r => r.event_type))).sort();
    const matrix: { hour: number; [k: string]: number }[] = [];
    for (let h = 0; h < 24; h++) {
      const row: any = { hour: h };
      for (const t of types) row[t] = 0;
      for (const r of rows.filter(r => r.hour === h)) {
        row[r.event_type] = r.count;
      }
      matrix.push(row);
    }

    res.json({ ok: true, types, matrix });
  } catch (e:any) {
    console.error(e);
    res.status(500).json({ ok: false, error: e?.message || "error" });
  }
});

export default router;

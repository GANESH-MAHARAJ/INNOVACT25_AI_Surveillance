// api/src/routes/analytics.ts
import { Router } from "express";
import EventModel from "../models/Event";
import dayjs from "dayjs";

const router = Router();

router.get("/summary", async (req, res) => {
  const now = dayjs();
  const since = now.subtract(24, "hour").toDate();
  const since12 = now.subtract(12, "hour").toDate();

  try {
    const [byType, byCamera, hourly] = await Promise.all([
      EventModel.aggregate([
        { $match: { ts_utc: { $gte: since } } },
        { $group: { _id: "$event_type", count: { $sum: 1 } } },
        { $project: { _id: 0, event_type: "$_id", count: 1 } },
        { $sort: { count: -1 } }
      ]),
      EventModel.aggregate([
        { $match: { ts_utc: { $gte: since } } },
        { $group: { _id: "$camera_id", count: { $sum: 1 } } },
        { $project: { _id: 0, camera_id: "$_id", count: 1 } },
        { $sort: { count: -1 } }
      ]),
      EventModel.aggregate([
        { $match: { ts_utc: { $gte: since12 } } },
        {
          $group: {
            _id: {
              y: { $year: "$ts_utc" },
              m: { $month: "$ts_utc" },
              d: { $dayOfMonth: "$ts_utc" },
              h: { $hour: "$ts_utc" }
            },
            count: { $sum: 1 }
          }
        },
        {
          $project: {
            _id: 0,
            ts_hour: {
              $dateFromParts: {
                year: "$_id.y", month: "$_id.m", day: "$_id.d", hour: "$_id.h"
              }
            },
            count: 1
          }
        },
        { $sort: { ts_hour: 1 } }
      ])
    ]);

    res.json({ ok: true, byType, byCamera, hourly });
  } catch (e:any) {
    console.error(e);
    res.status(500).json({ ok: false, error: e?.message || "error" });
  }
});

export default router;

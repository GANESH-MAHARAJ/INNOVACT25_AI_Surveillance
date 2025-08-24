import analytics from "./routes/analytics";
import analyticsExtras from "./routes/analytics_extras";
import dotenv from "dotenv";
dotenv.config();
import express from "express";
import cors from "cors";
import morgan from "morgan";
import { connectDB } from "./lib/db";
import events from "./routes/events";
import path from "path";
import fs from "fs";

const app = express();
app.use(cors({ origin: true }));  
app.use(express.json({ limit: "5mb" }));
app.use(morgan("dev"));
app.use("/analytics", analytics);
app.use("/analytics", analyticsExtras);
const ASSETS_DIR = process.env.ASSETS_DIR || path.resolve("./clips");
if (!fs.existsSync(ASSETS_DIR)) {
  fs.mkdirSync(ASSETS_DIR, { recursive: true });
}
app.use(
  "/static",
  (req, res, next) => {
    res.setHeader("Cross-Origin-Resource-Policy", "cross-origin");
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Cache-Control", "public, max-age=60, immutable");
    next();
  },
  express.static(ASSETS_DIR)
);

/**
 * Range-aware MP4 streaming
 * GET /media/:name
 */
app.get("/media/:name", (req, res) => {
  const name = req.params.name;
  const file = path.join(ASSETS_DIR, name);

  if (!fs.existsSync(file)) {
    return res.status(404).json({ ok: false, error: "Not found" });
  }

  const stat = fs.statSync(file);
  const total = stat.size;
  const range = req.headers.range;

  // Common headers
  res.setHeader("Content-Type", "video/mp4");
  res.setHeader("Accept-Ranges", "bytes");
  res.setHeader("Cross-Origin-Resource-Policy", "cross-origin");
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Cache-Control", "public, max-age=60");

  if (!range) {
    // No range → send whole file
    res.setHeader("Content-Length", total.toString());
    // Explicitly suggest inline playback
    res.setHeader("Content-Disposition", `inline; filename="${name}"`);
    fs.createReadStream(file).pipe(res);
    return;
  }

  // Parse "bytes=start-end"
  const match = /bytes=(\d*)-(\d*)/.exec(range);
  let start = match && match[1] ? parseInt(match[1], 10) : 0;
  let end = match && match[2] ? parseInt(match[2], 10) : total - 1;

  if (isNaN(start) || isNaN(end) || start > end || end >= total) {
    // invalid range → 416
    res.status(416).setHeader("Content-Range", `bytes */${total}`).end();
    return;
  }

  const chunk = end - start + 1;
  res.status(206);
  res.setHeader("Content-Range", `bytes ${start}-${end}/${total}`);
  res.setHeader("Content-Length", chunk.toString());
  res.setHeader("Content-Disposition", `inline; filename="${name}"`);

  fs.createReadStream(file, { start, end }).pipe(res);
});
app.get("/", (_req, res) => res.json({ ok: true, service: "api" }));
app.use("/events", events);
app.use("/api/events", events);

const PORT = Number(process.env.PORT || 8080);

connectDB().then(() => {
  app.listen(PORT, () => console.log("API listening on", PORT));
});

import mongoose from "mongoose";
const MetricSchema = new mongoose.Schema({}, { strict: false, _id: false });

const EventSchema = new mongoose.Schema({
  ts_utc: { type: Date, index: true },
  camera_id: { type: String, index: true },
  event_type: { type: String, index: true },
  severity: { type: String, default: "med" },
  zone: { type: String },
  tracks: [{ track_id: Number, klass: String, role: String }],
  metrics: { type: MetricSchema },
  artifacts: {
    clip_mp4: String,
    keyframes: [String],
    overlay_json: String,
    crops: [{ label: String, path: String }]
  },
  explanation: String,
  tags: [String]
}, { timestamps: true });

export default mongoose.model("Event", EventSchema);

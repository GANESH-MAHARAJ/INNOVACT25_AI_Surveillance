import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8080", // backend API
});

export interface Event {
  _id: string;
  ts_utc: string;
  camera_id: string;
  event_type: string;
  severity: string;
  zone?: string;
  explanation?: string;
  metrics?: Record<string, any>;
}

export async function fetchEvents(params: { type?: string } = {}) {
  const res = await api.get<Event[]>("/events", { params });
  return res.data;
}

export async function fetchAnalyticsSummary() {
  const r = await api.get("/analytics/summary");
  return r.data;
}

export async function fetchCameras() {
  const r = await api.get("/events/cameras");
  return r.data;
}

export async function fetchCvCameras() {
  const r = await fetch("http://localhost:8001/cameras", { method: "GET" });
  return r.json(); // { ok: true, cameras: string[] }
}

export async function fetchOccupancyAll() {
  const r = await fetch("http://localhost:8001/occupancy", { cache: "no-store" });
  return r.json();
}

export async function fetchRisk() {
  const r = await api.get("/analytics/risk");
  return r.data;
}

export async function fetchMatrix() {
  const r = await api.get("/analytics/matrix");
  return r.data;
}



export default api;

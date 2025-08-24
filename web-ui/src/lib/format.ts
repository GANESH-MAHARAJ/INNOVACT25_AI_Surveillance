export const fmtTime = (iso?: string) =>
  iso ? new Date(iso).toLocaleString() : "-";

export const badgeColor = (sev?: string) =>
  sev === "high" ? "text-red-300 bg-red-900/40 border-red-800"
  : sev === "med" ? "text-yellow-300 bg-yellow-900/40 border-yellow-800"
  : "text-green-300 bg-green-900/40 border-green-800";

export const pct = (v: number | null | undefined, d = 1) =>
  v == null ? "n.m." : `${(v * 100).toFixed(d)}%`;
export const mult = (v: number | null | undefined, d = 2) =>
  v == null ? "n.m." : `${v.toFixed(d)}x`;
export const cr = (v: number | null | undefined) =>
  v == null ? "—" : `₹${Math.round(v).toLocaleString("en-IN")} cr`;

function el(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const c of kids.flat()) e.append(c);
  return e;
}
async function api(url, opts = {}) {
  const r = await fetch(url, { credentials: "same-origin", ...opts });
  let d = {};
  try { d = await r.json(); } catch (_) {}
  if (r.status === 401) { location.href = "/login"; throw new Error("Please log in."); }
  if (!r.ok) throw new Error(d.error || "Something went wrong.");
  return d;
}
const fmtDate = (s) => new Date(s).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
const sourceLabel = (s) => s.filename + (s.location ? " — " + s.location : "");

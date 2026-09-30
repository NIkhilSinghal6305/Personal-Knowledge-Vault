const LABELS = { queued: "Uploading...", extracting: "Extracting text...", chunking: "Creating chunks...",
  embedding: "Generating embeddings...", indexing: "Updating knowledge base...", ready: "Ready", failed: "Failed" };
const BUSY = ["queued", "extracting", "chunking", "embedding", "indexing"];
const $ = (s) => document.querySelector(s);
let wasBusy = false, scopeDoc = null, timer = null;

async function loadDocs() {
  clearTimeout(timer);
  try {
    const { documents } = await api("/api/documents");
    $("#docs").replaceChildren(...(documents.length ? documents.map(row) : [el("tr", {}, el("td", { colspan: 6, class: "muted" }, "No documents yet."))]));
    const busy = documents.filter(d => BUSY.includes(d.status));
    if (busy.length) {
      $("#status").textContent = busy[0].filename + ": " + LABELS[busy[0].status];
      wasBusy = true;
      timer = setTimeout(loadDocs, 1200);
    } else if (wasBusy) {
      $("#status").textContent = documents.some(d => d.status === "failed") ? "Finished with errors." : "✓ Document processed successfully. Complete.";
      wasBusy = false;
    }
  } catch (e) { $("#status").textContent = e.message; }
}

function row(d) {
  const act = (label, fn) => el("button", { class: "btn secondary small", onclick: fn }, label);
  return el("tr", {}, el("td", {}, d.filename), el("td", {}, d.file_type.toUpperCase()), el("td", {}, String(d.num_chunks)),
    el("td", {}, fmtDate(d.created_at)),
    el("td", {}, LABELS[d.status] || d.status, d.error ? el("br") : "", d.error ? el("small", {}, d.error) : ""),
    el("td", {}, act("View", () => view(d.id)), act("Search", () => { scopeDoc = d; $("#scope").hidden = false;
        $("#scope").textContent = "Searching only in " + d.filename + " (submit an empty search to clear)"; $("#q").focus(); }),
      act("Re-process", () => call(d.id, "POST", "/reprocess")), act("Delete", () => confirm("Delete " + d.filename + "?") && call(d.id, "DELETE", ""))));
}

async function call(id, method, suffix) {
  try { await api("/api/documents/" + id + suffix, { method }); } catch (e) { $("#status").textContent = e.message; }
  loadDocs();
}

async function view(id) {
  try {
    const { document: d, preview } = await api("/api/documents/" + id);
    $("#info-body").replaceChildren(el("h2", {}, d.filename),
      el("p", { class: "muted" }, `ID ${d.id} · ${d.file_type.toUpperCase()} · ${d.num_chunks} chunks · ${LABELS[d.status]} · ${fmtDate(d.created_at)}`),
      ...preview.map(p => el("div", { class: "result" }, el("small", {}, "Chunk " + p.chunk_index + (p.location ? " · " + p.location : "")), el("div", {}, p.text + "..."))));
    $("#info").showModal();
  } catch (e) { $("#status").textContent = e.message; }
}

async function upload(files) {
  if (!files.length) return;
  const fd = new FormData();
  for (const f of files) fd.append("files", f);
  $("#status").textContent = "Uploading...";
  try {
    const { results } = await api("/api/documents/upload", { method: "POST", body: fd });
    const errs = results.filter(r => r.error).map(r => r.filename + ": " + r.error);
    if (errs.length) $("#status").textContent = errs.join(" ");
    wasBusy = results.some(r => r.id);
  } catch (e) { $("#status").textContent = e.message; }
  loadDocs();
}

$("#search-form").onsubmit = async (ev) => {
  ev.preventDefault();
  const q = $("#q").value.trim(), box = $("#results");
  if (!q) { scopeDoc = null; $("#scope").hidden = true; box.replaceChildren(); return; }
  box.replaceChildren(el("p", { class: "muted" }, "Searching..."));
  try {
    const { results } = await api("/api/search?q=" + encodeURIComponent(q) + (scopeDoc ? "&document_id=" + scopeDoc.id : ""));
    box.replaceChildren(...(results.length ? results.map(r => el("div", { class: "result" },
      el("b", {}, r.filename), el("small", {}, (r.location ? " · " + r.location : "") + " · score " + r.score), el("div", {}, r.text + "...")))
      : [el("p", { class: "muted" }, "No matching passages found.")]));
  } catch (e) { box.replaceChildren(el("p", {}, e.message)); }
};

const pick = () => $("#file").click();
$("#choose").onclick = pick; $("#choose2").onclick = pick;
$("#file").onchange = (e) => { upload([...e.target.files]); e.target.value = ""; };
$("#info-close").onclick = () => $("#info").close();
const drop = $("#drop");
["dragenter", "dragover"].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", e => upload([...e.dataTransfer.files]));
loadDocs();

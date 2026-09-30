(async () => {
  try {
    const s = await api("/api/dashboard/stats");
    for (const k of ["documents", "chunks", "conversations"]) document.getElementById("s-" + k).textContent = s[k];
    const docs = (await api("/api/documents")).documents.slice(0, 5);
    const dt = document.getElementById("recent-docs");
    dt.replaceChildren(...(docs.length ? docs.map(d => el("tr", {}, el("td", {}, d.filename), el("td", {}, d.file_type.toUpperCase()),
      el("td", {}, fmtDate(d.created_at)), el("td", {}, d.status))) : [el("tr", {}, el("td", { colspan: 4, class: "muted" }, "No documents yet."))]));
    const convs = (await api("/api/conversations")).conversations.slice(0, 5);
    document.getElementById("recent-convs").replaceChildren(...(convs.length ? convs.map(c => el("tr", {}, el("td", {}, c.title),
      el("td", {}, fmtDate(c.created_at)), el("td", {}, el("a", { href: "/chat?c=" + c.id }, "Open")))) : [el("tr", {}, el("td", { colspan: 3, class: "muted" }, "No conversations yet."))]));
  } catch (e) { console.error(e); }
})();

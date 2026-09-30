const root = document.querySelector(".chat");
const box = document.getElementById("messages");
let mode = "knowledge_base", convId = root.dataset.conversation ? Number(root.dataset.conversation) : null;
const LABEL = { knowledge_base: "Knowledge Base Answer", general: "General AI Answer" };

function setMode(m) {
  mode = m;
  document.getElementById("m-kb").className = "btn" + (m === "knowledge_base" ? "" : " secondary");
  document.getElementById("m-gen").className = "btn" + (m === "general" ? "" : " secondary");
}
document.getElementById("m-kb").onclick = () => setMode("knowledge_base");
document.getElementById("m-gen").onclick = () => setMode("general");

function addMessage(m) {
  const empty = document.getElementById("empty"); if (empty) empty.remove();
  const node = el("div", { class: "msg " + m.role }, el("div", { class: "who" }, m.role === "user" ? "You" : (m.label || LABEL[m.mode] || "AI")), m.content);
  if (m.role === "assistant" && m.mode === "knowledge_base" && m.sources && m.sources.length)
    node.append(el("div", { class: "sources" }, "Sources", el("ol", {}, m.sources.map(s => el("li", {}, sourceLabel(s))))));
  if (m.role === "assistant" && m.id) node.append(el("div", { class: "sources" }, el("a", { href: "/api/messages/" + m.id + "/pdf" }, "Download PDF")));
  box.append(node); box.scrollTop = box.scrollHeight;
  return node;
}

document.getElementById("form").onsubmit = async (ev) => {
  ev.preventDefault();
  const input = document.getElementById("input"), send = document.getElementById("send");
  const text = input.value.trim(); if (!text) return;
  input.value = ""; send.disabled = true;
  addMessage({ role: "user", content: text });
  const pending = el("div", { class: "msg muted" }, "Thinking..."); box.append(pending);
  try {
    const d = await api("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, mode, conversation_id: convId }) });
    convId = d.conversation_id; pending.remove();
    addMessage({ role: "assistant", content: d.answer, mode: d.mode, label: d.label, sources: d.sources, id: d.message_id });
  } catch (e) { pending.textContent = e.message; }
  send.disabled = false; input.focus();
};
document.getElementById("input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); document.getElementById("form").requestSubmit(); }
});

if (convId) api("/api/conversations/" + convId).then(d => d.messages.forEach(addMessage)).catch(e => addMessage({ role: "assistant", content: e.message }));

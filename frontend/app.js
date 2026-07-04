/* ============================================================
   ULTRON v2 — multi-user frontend
   Accounts · conversation history · streaming · markdown · voice
   ============================================================ */

let TOKEN = localStorage.getItem("ultron-token") || "";
let USER = null;          // {id, email, is_admin}
let CONV = null;          // current conversation id (null = fresh, created on send)
let ws = null;
let voiceOn = true;
let pendingImage = null;
let responseMode = localStorage.getItem("ultron-mode") || "auto";

const $ = (id) => document.getElementById(id);
const els = {
  messages: $("messages"), input: $("input"), send: $("send"), mic: $("mic"),
  voiceToggle: $("voice-toggle"), reactor: $("reactor"), ops: $("ops"),
  connDot: $("conn-dot"), connText: $("conn-text"), brainText: $("brain-text"),
  attach: $("attach"), fileInput: $("file-input"), attachPreview: $("attach-preview"),
  attachImg: $("attach-img"), attachRemove: $("attach-remove"),
  convList: $("conv-list"), chatTitle: $("chat-title"), newChat: $("new-chat"),
  adminLink: $("admin-link"),
};

function authFetch(url, opts = {}) {
  opts.headers = Object.assign({ "Content-Type": "application/json" },
    opts.headers, { "Authorization": "Bearer " + TOKEN });
  return fetch(url, opts);
}

/* ---------------- auth ---------------- */
let authMode = "login";
function showAuth() {
  $("auth-overlay").hidden = false;
  renderAuthMode();
  $("auth-email").focus();
}
function renderAuthMode() {
  const login = authMode === "login";
  $("auth-sub").textContent = login ? "Sign in to your account" : "Create your account";
  $("auth-submit").textContent = login ? "Sign in" : "Create account";
  $("auth-switch-text").textContent = login ? "New here?" : "Already have an account?";
  $("auth-switch").textContent = login ? "Create an account" : "Sign in";
  $("auth-pw").autocomplete = login ? "current-password" : "new-password";
}
$("auth-switch").onclick = (e) => { e.preventDefault(); authMode = authMode === "login" ? "register" : "login"; $("auth-err").textContent = ""; renderAuthMode(); };
$("auth-form").onsubmit = async (e) => {
  e.preventDefault();
  const email = $("auth-email").value.trim();
  const password = $("auth-pw").value;
  const err = $("auth-err");
  err.textContent = "";
  try {
    const r = await fetch("/api/" + (authMode === "login" ? "login" : "register"), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const d = await r.json();
    if (!r.ok) { err.textContent = d.detail || "Something went wrong."; return; }
    TOKEN = d.token; USER = d.user;
    localStorage.setItem("ultron-token", TOKEN);
    $("auth-overlay").hidden = true;
    initApp();
  } catch (_) { err.textContent = "Connection error."; }
};

$("account-pill").onclick = () => {
  const p = $("account-panel");
  p.hidden = !p.hidden;
  $("account-email").textContent = USER ? USER.email : "";
};
$("logout-btn").onclick = () => {
  localStorage.removeItem("ultron-token");
  TOKEN = ""; USER = null;
  location.reload();
};

/* ---------------- WebSocket ---------------- */
function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(TOKEN)}`);
  ws.onopen = () => { els.connDot.classList.add("live"); els.connText.textContent = "online"; };
  ws.onclose = () => { els.connDot.classList.remove("live"); els.connText.textContent = "reconnecting…"; setTimeout(connect, 1500); };
  ws.onmessage = (e) => handleEvent(JSON.parse(e.data));
}
function handleEvent(ev) {
  switch (ev.type) {
    case "conversation": CONV = ev.id; els.chatTitle.textContent = ev.title || "New chat"; loadConversations(); break;
    case "title": els.chatTitle.textContent = ev.title; loadConversations(); break;
    case "thought": setReactor("thinking"); addEvent("thought", "reasoning", ev.text); break;
    case "tool": setReactor("thinking"); addEvent("tool", "tool", `${ev.name}(${JSON.stringify(ev.input)})`); break;
    case "observation": addEvent("event", ev.name, truncate(ev.text, 220)); break;
    case "final": setReactor("idle"); typeUltron(ev.text); if (voiceOn) speak(ev.text); refreshOps(); break;
    case "error": setReactor("idle"); addUltron("System fault: " + ev.text); break;
    case "done": setReactor("idle"); break;
  }
}

/* ---------------- messages ---------------- */
function addUser(text, imageUrl) {
  const d = document.createElement("div");
  d.className = "msg user";
  const img = imageUrl ? `<img class="thumb" src="${imageUrl}" alt="attachment"/>` : "";
  d.innerHTML = `<div class="who">${escapeHtml(USER ? USER.email.split("@")[0] : "You")}</div>${escapeHtml(text)}${img}`;
  els.messages.appendChild(d);
  scroll();
}
function typeUltron(text) {
  const d = document.createElement("div");
  d.className = "msg ultron";
  const who = document.createElement("div"); who.className = "who"; who.textContent = "ULTRON";
  const body = document.createElement("div"); body.className = "md type-caret";
  const raw = document.createElement("span"); body.appendChild(raw);
  d.appendChild(who); d.appendChild(body); els.messages.appendChild(d);
  const tokens = text.split(/(\s+)/); let i = 0;
  const timer = setInterval(() => {
    for (let k = 0; k < 2 && i < tokens.length; k++, i++) raw.textContent += tokens[i];
    scroll();
    if (i >= tokens.length) {
      clearInterval(timer);
      body.classList.remove("type-caret");
      body.innerHTML = renderMarkdown(text);
      enhanceCodeBlocks(body); scroll();
    }
  }, 16);
}
function addUltron(text) {
  const d = document.createElement("div");
  d.className = "msg ultron";
  const who = document.createElement("div"); who.className = "who"; who.textContent = "ULTRON";
  const body = document.createElement("div"); body.className = "md"; body.innerHTML = renderMarkdown(text);
  d.appendChild(who); d.appendChild(body); els.messages.appendChild(d);
  enhanceCodeBlocks(body); scroll();
}
function renderMarkdown(text) {
  if (window.marked) { try { return marked.parse(text, { breaks: true, gfm: true }); } catch (_) {} }
  return escapeHtml(text);
}
function enhanceCodeBlocks(root) {
  root.querySelectorAll("pre").forEach((pre) => {
    const code = pre.querySelector("code");
    let lang = "code";
    if (code) {
      const c = [...code.classList].find((x) => x.startsWith("language-"));
      if (c) lang = c.replace("language-", "");
      if (window.hljs) { try { hljs.highlightElement(code); } catch (_) {} }
    }
    const wrap = document.createElement("div"); wrap.className = "code-wrap";
    const head = document.createElement("div"); head.className = "code-head";
    const label = document.createElement("span"); label.className = "code-lang"; label.textContent = lang;
    const btn = document.createElement("button"); btn.className = "code-copy"; btn.textContent = "Copy";
    btn.onclick = () => { navigator.clipboard.writeText(code ? code.innerText : pre.innerText).then(() => { btn.textContent = "Copied"; setTimeout(() => (btn.textContent = "Copy"), 1500); }); };
    head.appendChild(label); head.appendChild(btn);
    pre.parentNode.insertBefore(wrap, pre); wrap.appendChild(head); wrap.appendChild(pre);
  });
}
function addEvent(cls, tag, text) {
  const d = document.createElement("div");
  d.className = "event " + cls;
  d.innerHTML = `<span class="tag">[${escapeHtml(tag)}]</span> ${escapeHtml(text)}`;
  els.messages.appendChild(d); scroll();
}
const scroll = () => (els.messages.scrollTop = els.messages.scrollHeight);

/* ---------------- send ---------------- */
function send() {
  const text = els.input.value.trim();
  if ((!text && !pendingImage) || !ws || ws.readyState !== 1) return;
  addUser(text || "(look at this)", pendingImage);
  const payload = { message: text, conversation_id: CONV, mode: responseMode };
  if (pendingImage) payload.image = pendingImage;
  els.input.value = ""; clearAttachment(); setReactor("thinking");
  ws.send(JSON.stringify(payload));
}
els.send.onclick = send;
els.input.addEventListener("keydown", (e) => e.key === "Enter" && send());

/* ---------------- image attachment ---------------- */
els.attach.onclick = () => els.fileInput.click();
els.fileInput.onchange = () => {
  const file = els.fileInput.files[0]; if (!file) return;
  const reader = new FileReader();
  reader.onload = () => { pendingImage = reader.result; els.attachImg.src = pendingImage; els.attachPreview.hidden = false; };
  reader.readAsDataURL(file);
};
els.attachRemove.onclick = clearAttachment;
function clearAttachment() { pendingImage = null; els.fileInput.value = ""; els.attachPreview.hidden = true; els.attachImg.src = ""; }

/* ---------------- conversations ---------------- */
async function loadConversations() {
  try {
    const r = await authFetch("/api/conversations");
    const d = await r.json();
    els.convList.innerHTML = "";
    (d.conversations || []).forEach((c) => {
      const row = document.createElement("div");
      row.className = "conv-item" + (c.id === CONV ? " active" : "");
      const t = document.createElement("span"); t.className = "title"; t.textContent = c.title || "New chat";
      t.onclick = () => openConversation(c.id, c.title);
      const del = document.createElement("button"); del.className = "del"; del.textContent = "×";
      del.title = "Delete"; del.onclick = (e) => { e.stopPropagation(); deleteConversation(c.id); };
      row.appendChild(t); row.appendChild(del); els.convList.appendChild(row);
    });
  } catch (_) {}
}
async function openConversation(id, title) {
  CONV = id;
  els.chatTitle.textContent = title || "Conversation";
  els.messages.innerHTML = "";
  try {
    const r = await authFetch(`/api/conversations/${id}/messages`);
    const d = await r.json();
    (d.messages || []).forEach((m) => (m.role === "user" ? addUser(m.content) : addUltron(m.content)));
  } catch (_) {}
  loadConversations();
}
function newChat() {
  CONV = null;
  els.chatTitle.textContent = "New chat";
  els.messages.innerHTML = "";
  addUltron(`New conversation, ${USER ? USER.email.split("@")[0] : "sir"}. What are we working on?`);
  loadConversations();
}
async function deleteConversation(id) {
  await authFetch(`/api/conversations/${id}`, { method: "DELETE" });
  if (id === CONV) newChat(); else loadConversations();
}
els.newChat.onclick = newChat;

/* ---------------- reactor ---------------- */
function setReactor(state) {
  els.reactor.classList.remove("thinking", "speaking");
  if (state === "thinking") els.reactor.classList.add("thinking");
  if (state === "speaking") els.reactor.classList.add("speaking");
}

/* ---------------- response length toggle ---------------- */
const modePill = $("mode-pill");
function renderModePill() { modePill.textContent = "length: " + responseMode; }
renderModePill();
modePill.onclick = () => { responseMode = { auto: "brief", brief: "deep", deep: "auto" }[responseMode]; localStorage.setItem("ultron-mode", responseMode); renderModePill(); };
function setMode(m) { responseMode = m; localStorage.setItem("ultron-mode", m); renderModePill(); }

/* ---------------- voice: TTS ---------------- */
const voicePrefs = {
  name: localStorage.getItem("ultron-voice") || "",
  rate: parseFloat(localStorage.getItem("ultron-rate") || "1.02"),
  pitch: parseFloat(localStorage.getItem("ultron-pitch") || "0.9"),
};
function pickVoice() {
  const voices = window.speechSynthesis.getVoices();
  if (voicePrefs.name) { const v = voices.find((x) => x.name === voicePrefs.name); if (v) return v; }
  return voices.find(v => /male|david|daniel|google uk english male/i.test(v.name)) || voices.find(v => /en-GB|en-US/i.test(v.lang));
}
function speak(text) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(stripForSpeech(text));
  u.rate = voicePrefs.rate; u.pitch = voicePrefs.pitch;
  const pref = pickVoice(); if (pref) u.voice = pref;
  u.onstart = () => setReactor("speaking"); u.onend = () => setReactor("idle");
  window.speechSynthesis.speak(u);
}
els.voiceToggle.onclick = () => {
  voiceOn = !voiceOn;
  els.voiceToggle.classList.toggle("active", voiceOn);
  els.voiceToggle.classList.toggle("muted", !voiceOn);
  if (!voiceOn) window.speechSynthesis.cancel();
};
const voicePanel = $("voice-panel"), voiceSelect = $("voice-select"), rateRange = $("rate-range"), pitchRange = $("pitch-range");
$("voice-pill").onclick = () => { voicePanel.hidden = !voicePanel.hidden; if (!voicePanel.hidden) populateVoices(); };
function populateVoices() {
  const voices = window.speechSynthesis.getVoices();
  voiceSelect.innerHTML = voices.map(v => `<option value="${escapeHtml(v.name)}" ${v.name === voicePrefs.name ? "selected" : ""}>${escapeHtml(v.name)} (${v.lang})</option>`).join("");
  rateRange.value = voicePrefs.rate; pitchRange.value = voicePrefs.pitch;
  $("rate-val").textContent = voicePrefs.rate.toFixed(2); $("pitch-val").textContent = voicePrefs.pitch.toFixed(2);
}
voiceSelect.onchange = () => { voicePrefs.name = voiceSelect.value; localStorage.setItem("ultron-voice", voicePrefs.name); };
rateRange.oninput = () => { voicePrefs.rate = parseFloat(rateRange.value); localStorage.setItem("ultron-rate", voicePrefs.rate); $("rate-val").textContent = voicePrefs.rate.toFixed(2); };
pitchRange.oninput = () => { voicePrefs.pitch = parseFloat(pitchRange.value); localStorage.setItem("ultron-pitch", voicePrefs.pitch); $("pitch-val").textContent = voicePrefs.pitch.toFixed(2); };
$("voice-test").onclick = () => speak("Systems online. This is how I sound, sir.");

/* ---------------- voice: STT ---------------- */
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let recog = null, listening = false;
if (SR) {
  recog = new SR(); recog.lang = "en-US"; recog.interimResults = false;
  recog.onresult = (e) => { els.input.value = e.results[0][0].transcript; send(); };
  recog.onend = () => { listening = false; els.mic.classList.remove("listening"); };
  recog.onerror = () => { listening = false; els.mic.classList.remove("listening"); };
} else { els.mic.classList.add("muted"); els.mic.title = "Voice input needs Chrome or Edge"; }
els.mic.onclick = () => {
  if (!recog) { addUltron("Voice input isn't supported in this browser. Open ULTRON in Chrome or Edge for the mic; I can still speak replies here."); return; }
  if (listening) { recog.stop(); return; }
  window.speechSynthesis && window.speechSynthesis.cancel();
  try { listening = true; els.mic.classList.add("listening"); recog.start(); }
  catch (_) { listening = false; els.mic.classList.remove("listening"); }
};

/* ---------------- status + ops ---------------- */
async function loadStatus() {
  try { const s = await (await authFetch("/api/status")).json(); els.brainText.textContent = "brain: " + s.provider; } catch (_) {}
}
async function refreshOps() {
  try {
    const d = await (await authFetch("/api/tasks")).json();
    els.ops.innerHTML =
      opsGroup("Tasks", d.tasks.map(t => `<div class="ops-item ${t.done ? "done" : ""}">#${t.id} ${escapeHtml(t.title)}</div>`)) +
      opsGroup("Notes", d.notes.map(n => `<div class="ops-item">#${n.id} ${escapeHtml(n.text)}</div>`)) +
      opsGroup("Reminders", d.reminders.map(rm => `<div class="ops-item">#${rm.id} ${escapeHtml(rm.text)}</div>`));
  } catch (_) {}
}
function opsGroup(title, items) {
  const body = items.length ? items.join("") : `<div class="empty">none yet</div>`;
  return `<div class="ops-group"><h3>${title}</h3>${body}</div>`;
}

/* ---------------- export ---------------- */
async function getConversation() {
  if (!CONV) return [];
  try { return (await (await authFetch(`/api/conversations/${CONV}/messages`)).json()).messages || []; } catch (_) { return []; }
}
function downloadFile(name, text, type) {
  const blob = new Blob([text], { type }); const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function exportMarkdown() {
  const msgs = await getConversation();
  let md = `# ULTRON — ${els.chatTitle.textContent}\n\n_Exported ${new Date().toLocaleString()}_\n\n`;
  for (const m of msgs) md += (m.role === "user" ? "**You:**\n\n" : "**ULTRON:**\n\n") + m.content + "\n\n---\n\n";
  downloadFile("ultron-chat.md", md, "text/markdown");
}
async function exportPDF() {
  const msgs = await getConversation();
  const rows = msgs.map(m => `<div class="turn ${m.role}"><b>${m.role === "user" ? "You" : "ULTRON"}</b><div>${escapeHtml(m.content).replace(/\n/g, "<br>")}</div></div>`).join("");
  const w = window.open("", "_blank");
  w.document.write(`<html><head><title>ULTRON</title><style>body{font-family:Segoe UI,system-ui,sans-serif;max-width:760px;margin:40px auto;color:#111;padding:0 20px}h1{color:#0a7ea4}.turn{margin:0 0 18px;padding-bottom:12px;border-bottom:1px solid #eee}.turn b{display:block;color:#0a7ea4;margin-bottom:4px}.user b{color:#b8860b}</style></head><body><h1>ULTRON — ${els.chatTitle.textContent}</h1>${rows}<scr`+`ipt>window.onload=()=>window.print()</scr`+`ipt></body></html>`);
  w.document.close();
}

/* ---------------- brain + clear ---------------- */
async function setBrain(provider) {
  try {
    const r = await authFetch("/api/brain", { method: "POST", body: JSON.stringify({ provider }) });
    if (!r.ok) { addUltron("Only the admin can switch the brain."); return; }
    const d = await r.json(); els.brainText.textContent = "brain: " + d.provider;
    addUltron(`Brain switched to **${d.provider}** — ${d.brain}`);
  } catch (_) { addUltron("Couldn't switch brain, sir."); }
}
function clearChat() { if (CONV) deleteConversation(CONV); else newChat(); }

/* ---------------- command palette ---------------- */
const cmdk = $("cmdk"), cmdkInput = $("cmdk-input"), cmdkList = $("cmdk-list");
let cmdkSel = 0, cmdkCmds = [];
function buildCommands() {
  const cmds = [
    { label: "New chat", run: newChat },
    { label: "Delete this conversation", run: clearChat },
    { label: "Export as Markdown", run: exportMarkdown },
    { label: "Export as PDF", run: exportPDF },
    { label: "Toggle voice replies", run: () => els.voiceToggle.click() },
    { label: "Length: Auto", run: () => setMode("auto") },
    { label: "Length: Brief", run: () => setMode("brief") },
    { label: "Length: Deep", run: () => setMode("deep") },
    { label: "Log out", run: () => $("logout-btn").click() },
  ];
  if (USER && USER.is_admin) {
    cmds.push({ label: "Open admin dashboard", run: () => (location.href = "/admin") });
    cmds.push({ label: "Brain: Claude (Anthropic)", run: () => setBrain("anthropic") });
    cmds.push({ label: "Brain: GPT-4o (OpenAI)", run: () => setBrain("openai") });
    cmds.push({ label: "Brain: Groq (Llama)", run: () => setBrain("groq") });
    cmds.push({ label: "Brain: Gemini", run: () => setBrain("gemini") });
  }
  return cmds;
}
function openCmdk() { cmdk.hidden = false; cmdkInput.value = ""; cmdkSel = 0; renderCmdk(""); cmdkInput.focus(); }
function closeCmdk() { cmdk.hidden = true; }
function renderCmdk(q) {
  cmdkCmds = buildCommands().filter(c => c.label.toLowerCase().includes(q.toLowerCase()));
  if (cmdkSel >= cmdkCmds.length) cmdkSel = 0;
  cmdkList.innerHTML = cmdkCmds.map((c, i) => `<div class="cmdk-item ${i === cmdkSel ? "sel" : ""}" data-i="${i}">${escapeHtml(c.label)}</div>`).join("");
  [...cmdkList.children].forEach(el => (el.onclick = () => runCmdk(parseInt(el.dataset.i))));
}
function runCmdk(i) { const c = cmdkCmds[i]; closeCmdk(); if (c) c.run(); }
cmdkInput.addEventListener("input", () => { cmdkSel = 0; renderCmdk(cmdkInput.value); });
cmdkInput.addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown") { cmdkSel = Math.min(cmdkSel + 1, cmdkCmds.length - 1); renderCmdk(cmdkInput.value); e.preventDefault(); }
  else if (e.key === "ArrowUp") { cmdkSel = Math.max(cmdkSel - 1, 0); renderCmdk(cmdkInput.value); e.preventDefault(); }
  else if (e.key === "Enter") runCmdk(cmdkSel);
  else if (e.key === "Escape") closeCmdk();
});
document.addEventListener("keydown", (e) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); cmdk.hidden ? openCmdk() : closeCmdk(); } });
cmdk.addEventListener("click", (e) => { if (e.target === cmdk) closeCmdk(); });

/* ---------------- helpers ---------------- */
function escapeHtml(s) { return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
const truncate = (s, n) => (s.length > n ? s.slice(0, n) + "…" : s);
function stripForSpeech(t) { return t.replace(/https?:\/\/\S+/g, "link").replace(/[#*_`>-]/g, " ").slice(0, 600); }

/* ---------------- app init ---------------- */
async function initApp() {
  if (USER && USER.is_admin) els.adminLink.hidden = false;
  connect(); loadStatus(); loadConversations(); refreshOps();
  if (window.speechSynthesis) window.speechSynthesis.onvoiceschanged = () => {};
  const r = await authFetch("/api/conversations");
  const d = await r.json();
  if (d.conversations && d.conversations.length) {
    openConversation(d.conversations[0].id, d.conversations[0].title);
  } else {
    setTimeout(() => addUltron(`ULTRON online. Welcome, ${USER ? USER.email.split("@")[0] : "sir"}. Start typing and I'll open your first conversation. I can search the web, look at images, run your notes and tasks, and remember everything you tell me.`), 300);
  }
}

/* ---------------- boot ---------------- */
window.addEventListener("load", async () => {
  if (TOKEN) {
    try {
      const r = await fetch("/api/me", { headers: { "Authorization": "Bearer " + TOKEN } });
      if (r.ok) { USER = await r.json(); initApp(); return; }
    } catch (_) {}
    TOKEN = ""; localStorage.removeItem("ultron-token");
  }
  showAuth();
});

/* ============================================================
   ULTRON — frontend controller
   WebSocket chat + Web Speech voice (STT in, TTS out) + live HUD.
   ============================================================ */

/* Stable session id so past conversations persist across restarts. */
let SESSION = localStorage.getItem("ultron-session");
if (!SESSION) {
  SESSION = "s-" + Math.random().toString(36).slice(2, 10);
  localStorage.setItem("ultron-session", SESSION);
}
let TOKEN = localStorage.getItem("ultron-token") || "";

const els = {
  messages: document.getElementById("messages"),
  input: document.getElementById("input"),
  send: document.getElementById("send"),
  mic: document.getElementById("mic"),
  voiceToggle: document.getElementById("voice-toggle"),
  reactor: document.getElementById("reactor"),
  tools: document.getElementById("tools"),
  ops: document.getElementById("ops"),
  connDot: document.getElementById("conn-dot"),
  connText: document.getElementById("conn-text"),
  brainText: document.getElementById("brain-text"),
  attach: document.getElementById("attach"),
  fileInput: document.getElementById("file-input"),
  attachPreview: document.getElementById("attach-preview"),
  attachImg: document.getElementById("attach-img"),
  attachRemove: document.getElementById("attach-remove"),
};

let ws = null;
let voiceOn = true;
let pendingImage = null;   // data URL of an attached image
let responseMode = localStorage.getItem("ultron-mode") || "auto";  // auto|brief|deep

/* Fetch helper that always attaches the auth token. */
function authFetch(url, opts = {}) {
  opts.headers = Object.assign({}, opts.headers, {
    "Authorization": "Bearer " + TOKEN,
  });
  return fetch(url, opts);
}

/* ---------------- WebSocket ---------------- */
function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(TOKEN)}`);

  ws.onopen = () => {
    els.connDot.classList.add("live");
    els.connText.textContent = "online";
  };
  ws.onclose = () => {
    els.connDot.classList.remove("live");
    els.connText.textContent = "reconnecting…";
    setTimeout(connect, 1500);
  };
  ws.onmessage = (e) => handleEvent(JSON.parse(e.data));
}

function handleEvent(ev) {
  switch (ev.type) {
    case "thought":
      setReactor("thinking");
      addEvent("thought", "reasoning", ev.text);
      break;
    case "tool":
      setReactor("thinking");
      addEvent("tool", "tool", `${ev.name}(${JSON.stringify(ev.input)})`);
      break;
    case "observation":
      addEvent("event", ev.name, truncate(ev.text, 220));
      break;
    case "final":
      setReactor("idle");
      typeUltron(ev.text);
      if (voiceOn) speak(ev.text);
      refreshOps();
      break;
    case "error":
      setReactor("idle");
      addUltron("System fault: " + ev.text);
      break;
    case "done":
      setReactor("idle");
      break;
  }
}

/* ---------------- messages ---------------- */
function addUser(text, imageUrl) {
  const d = document.createElement("div");
  d.className = "msg user";
  const img = imageUrl ? `<img class="thumb" src="${imageUrl}" alt="attachment"/>` : "";
  d.innerHTML = `<div class="who">You</div>${escapeHtml(text)}${img}`;
  els.messages.appendChild(d);
  scroll();
}
function addUltron(text) {
  const d = document.createElement("div");
  d.className = "msg ultron";
  const who = document.createElement("div");
  who.className = "who";
  who.textContent = "ULTRON";
  const body = document.createElement("div");
  body.className = "md";
  body.innerHTML = renderMarkdown(text);
  d.appendChild(who);
  d.appendChild(body);
  els.messages.appendChild(d);
  enhanceCodeBlocks(body);
  scroll();
}

/* Typewriter streaming: reveal the answer token-by-token, then render
   full markdown + code blocks once complete (like modern AI chats). */
function typeUltron(text) {
  const d = document.createElement("div");
  d.className = "msg ultron";
  const who = document.createElement("div");
  who.className = "who";
  who.textContent = "ULTRON";
  const body = document.createElement("div");
  body.className = "md type-caret";
  const raw = document.createElement("span");
  body.appendChild(raw);
  d.appendChild(who);
  d.appendChild(body);
  els.messages.appendChild(d);

  const tokens = text.split(/(\s+)/);   // keep whitespace between words
  let i = 0;
  const timer = setInterval(() => {
    // reveal a few tokens per tick for a snappy but visible stream
    for (let k = 0; k < 2 && i < tokens.length; k++, i++) raw.textContent += tokens[i];
    scroll();
    if (i >= tokens.length) {
      clearInterval(timer);
      body.classList.remove("type-caret");
      body.innerHTML = renderMarkdown(text);
      enhanceCodeBlocks(body);
      scroll();
    }
  }, 16);
}

/* Render markdown -> HTML (falls back to plain text if lib not loaded). */
function renderMarkdown(text) {
  if (window.marked) {
    try { return marked.parse(text, { breaks: true, gfm: true }); }
    catch (_) {}
  }
  return escapeHtml(text);
}

/* Give every code block a language header + a Copy button, and highlight it. */
function enhanceCodeBlocks(root) {
  root.querySelectorAll("pre").forEach((pre) => {
    const code = pre.querySelector("code");
    let lang = "code";
    if (code) {
      const c = [...code.classList].find((x) => x.startsWith("language-"));
      if (c) lang = c.replace("language-", "");
      if (window.hljs) { try { hljs.highlightElement(code); } catch (_) {} }
    }
    const wrap = document.createElement("div");
    wrap.className = "code-wrap";
    const head = document.createElement("div");
    head.className = "code-head";
    const label = document.createElement("span");
    label.className = "code-lang";
    label.textContent = lang;
    const btn = document.createElement("button");
    btn.className = "code-copy";
    btn.textContent = "Copy";
    btn.onclick = () => {
      const t = code ? code.innerText : pre.innerText;
      navigator.clipboard.writeText(t).then(() => {
        btn.textContent = "Copied";
        setTimeout(() => (btn.textContent = "Copy"), 1500);
      });
    };
    head.appendChild(label);
    head.appendChild(btn);
    pre.parentNode.insertBefore(wrap, pre);
    wrap.appendChild(head);
    wrap.appendChild(pre);
  });
}
function addEvent(cls, tag, text) {
  const d = document.createElement("div");
  d.className = "event " + cls;
  d.innerHTML = `<span class="tag">[${escapeHtml(tag)}]</span> ${escapeHtml(text)}`;
  els.messages.appendChild(d);
  scroll();
}
const scroll = () => (els.messages.scrollTop = els.messages.scrollHeight);

/* ---------------- send ---------------- */
function send() {
  const text = els.input.value.trim();
  if ((!text && !pendingImage) || !ws || ws.readyState !== 1) return;
  addUser(text || "(look at this)", pendingImage);
  const payload = { message: text, session: SESSION, mode: responseMode };
  if (pendingImage) payload.image = pendingImage;
  els.input.value = "";
  clearAttachment();
  setReactor("thinking");
  ws.send(JSON.stringify(payload));
}
els.send.onclick = send;
els.input.addEventListener("keydown", (e) => e.key === "Enter" && send());

/* ---------------- image attachment ---------------- */
els.attach.onclick = () => els.fileInput.click();
els.fileInput.onchange = () => {
  const file = els.fileInput.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    pendingImage = reader.result;         // data URL
    els.attachImg.src = pendingImage;
    els.attachPreview.hidden = false;
  };
  reader.readAsDataURL(file);
};
els.attachRemove.onclick = clearAttachment;
function clearAttachment() {
  pendingImage = null;
  els.fileInput.value = "";
  els.attachPreview.hidden = true;
  els.attachImg.src = "";
}

/* ---------------- reactor state ---------------- */
function setReactor(state) {
  els.reactor.classList.remove("thinking", "speaking");
  if (state === "thinking") els.reactor.classList.add("thinking");
  if (state === "speaking") els.reactor.classList.add("speaking");
}

/* ---------------- projects / workspaces ---------------- */
/* Each project is its own conversation memory (keyed by session id on the
   backend), so ULTRON keeps separate context per topic. */
let projects = JSON.parse(localStorage.getItem("ultron-projects") || "null");
if (!projects) {
  projects = [{ id: SESSION, name: "General" }];
  localStorage.setItem("ultron-projects", JSON.stringify(projects));
  localStorage.setItem("ultron-current", SESSION);
}
SESSION = localStorage.getItem("ultron-current") || projects[0].id;

const projectPill = document.getElementById("project-pill");
const projectPanel = document.getElementById("project-panel");
const projectList = document.getElementById("project-list");

function saveProjects() {
  localStorage.setItem("ultron-projects", JSON.stringify(projects));
  localStorage.setItem("ultron-current", SESSION);
}
function currentProjectName() {
  const p = projects.find((x) => x.id === SESSION);
  return p ? p.name : "General";
}
function renderProjectPill() { projectPill.textContent = "project: " + currentProjectName(); }

function renderProjectList() {
  projectList.innerHTML = "";
  projects.forEach((p) => {
    const row = document.createElement("div");
    row.className = "project-row";
    const open = document.createElement("button");
    open.className = "open" + (p.id === SESSION ? " active" : "");
    open.textContent = p.name;
    open.onclick = () => switchProject(p.id);
    const del = document.createElement("button");
    del.className = "del";
    del.textContent = "×";
    del.title = "Delete project";
    del.onclick = (e) => { e.stopPropagation(); deleteProject(p.id); };
    row.appendChild(open);
    if (projects.length > 1) row.appendChild(del);
    projectList.appendChild(row);
  });
}

async function switchProject(id) {
  if (id === SESSION) { projectPanel.hidden = true; return; }
  SESSION = id;
  saveProjects();
  renderProjectPill();
  els.messages.innerHTML = "";
  projectPanel.hidden = true;
  const had = await loadHistory();
  if (!had) addUltron(`Switched to "${currentProjectName()}". Fresh context, sir — what are we working on?`);
  refreshOps();
}

function createProject(name) {
  const id = "p-" + Math.random().toString(36).slice(2, 10);
  projects.push({ id, name: name.trim() || "Untitled" });
  saveProjects();
  switchProject(id);
}

function deleteProject(id) {
  projects = projects.filter((p) => p.id !== id);
  if (!projects.length) projects = [{ id: "p-" + Math.random().toString(36).slice(2, 10), name: "General" }];
  if (SESSION === id) { SESSION = projects[0].id; els.messages.innerHTML = ""; loadHistory(); }
  saveProjects();
  renderProjectPill();
  renderProjectList();
}

projectPill.onclick = () => {
  projectPanel.hidden = !projectPanel.hidden;
  if (!projectPanel.hidden) renderProjectList();
};
document.getElementById("new-project-btn").onclick = () => {
  const inp = document.getElementById("new-project-name");
  if (inp.value.trim()) { createProject(inp.value); inp.value = ""; }
};
document.getElementById("new-project-name").addEventListener("keydown", (e) => {
  if (e.key === "Enter") document.getElementById("new-project-btn").click();
});
renderProjectPill();

/* ---------------- response length toggle ---------------- */
const modePill = document.getElementById("mode-pill");
function renderModePill() { modePill.textContent = "length: " + responseMode; }
renderModePill();
modePill.onclick = () => {
  responseMode = { auto: "brief", brief: "deep", deep: "auto" }[responseMode];
  localStorage.setItem("ultron-mode", responseMode);
  renderModePill();
};

/* ---------------- voice: text to speech ---------------- */
const voicePrefs = {
  name: localStorage.getItem("ultron-voice") || "",
  rate: parseFloat(localStorage.getItem("ultron-rate") || "1.02"),
  pitch: parseFloat(localStorage.getItem("ultron-pitch") || "0.9"),
};

function pickVoice() {
  const voices = window.speechSynthesis.getVoices();
  if (voicePrefs.name) {
    const v = voices.find((x) => x.name === voicePrefs.name);
    if (v) return v;
  }
  return voices.find(v => /male|david|daniel|google uk english male/i.test(v.name))
      || voices.find(v => /en-GB|en-US/i.test(v.lang));
}

function speak(text) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(stripForSpeech(text));
  u.rate = voicePrefs.rate; u.pitch = voicePrefs.pitch;
  const pref = pickVoice();
  if (pref) u.voice = pref;
  u.onstart = () => setReactor("speaking");
  u.onend = () => setReactor("idle");
  window.speechSynthesis.speak(u);
}

/* ---------------- voice settings panel ---------------- */
const voicePanel = document.getElementById("voice-panel");
const voiceSelect = document.getElementById("voice-select");
const rateRange = document.getElementById("rate-range");
const pitchRange = document.getElementById("pitch-range");
document.getElementById("voice-pill").onclick = () => {
  voicePanel.hidden = !voicePanel.hidden;
  if (!voicePanel.hidden) populateVoices();
};
function populateVoices() {
  const voices = window.speechSynthesis.getVoices();
  voiceSelect.innerHTML = voices.map(v =>
    `<option value="${escapeHtml(v.name)}" ${v.name === voicePrefs.name ? "selected" : ""}>${escapeHtml(v.name)} (${v.lang})</option>`
  ).join("");
  rateRange.value = voicePrefs.rate;
  pitchRange.value = voicePrefs.pitch;
  document.getElementById("rate-val").textContent = voicePrefs.rate.toFixed(2);
  document.getElementById("pitch-val").textContent = voicePrefs.pitch.toFixed(2);
}
voiceSelect.onchange = () => {
  voicePrefs.name = voiceSelect.value;
  localStorage.setItem("ultron-voice", voicePrefs.name);
};
rateRange.oninput = () => {
  voicePrefs.rate = parseFloat(rateRange.value);
  localStorage.setItem("ultron-rate", voicePrefs.rate);
  document.getElementById("rate-val").textContent = voicePrefs.rate.toFixed(2);
};
pitchRange.oninput = () => {
  voicePrefs.pitch = parseFloat(pitchRange.value);
  localStorage.setItem("ultron-pitch", voicePrefs.pitch);
  document.getElementById("pitch-val").textContent = voicePrefs.pitch.toFixed(2);
};
document.getElementById("voice-test").onclick = () =>
  speak("Systems online. This is how I sound, sir.");

els.voiceToggle.onclick = () => {
  voiceOn = !voiceOn;
  els.voiceToggle.classList.toggle("active", voiceOn);
  els.voiceToggle.classList.toggle("muted", !voiceOn);
  if (!voiceOn) window.speechSynthesis.cancel();
};

/* ---------------- voice: speech to text ---------------- */
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let recog = null, listening = false;
if (SR) {
  recog = new SR();
  recog.lang = "en-US";
  recog.interimResults = false;
  recog.onresult = (e) => {
    els.input.value = e.results[0][0].transcript;
    send();
  };
  recog.onend = () => { listening = false; els.mic.classList.remove("listening"); };
  recog.onerror = () => { listening = false; els.mic.classList.remove("listening"); };
} else {
  els.mic.classList.add("muted");
  els.mic.title = "Voice input needs Chrome or Edge";
}
els.mic.onclick = () => {
  if (!recog) {
    addUltron(
      "Voice input isn't supported in this browser (Firefox doesn't ship the " +
      "Web Speech recognition API). Open ULTRON in Google Chrome or Microsoft " +
      "Edge and the mic will work. You can still type here, and I can speak my " +
      "replies aloud in any browser."
    );
    return;
  }
  if (listening) { recog.stop(); return; }
  window.speechSynthesis && window.speechSynthesis.cancel();
  try {
    listening = true;
    els.mic.classList.add("listening");
    recog.start();
  } catch (_) {
    listening = false;
    els.mic.classList.remove("listening");
  }
};

/* ---------------- status + ops panels ---------------- */
async function loadStatus() {
  try {
    const r = await authFetch("/api/status");
    const s = await r.json();
    els.brainText.textContent = "brain: " + s.provider;
    els.tools.innerHTML = s.tools.map(t =>
      `<div class="tool-item"><span>▸</span><div><b>${t.name}</b>${escapeHtml(t.description)}</div></div>`
    ).join("");
  } catch (_) {}
}

async function loadHistory() {
  try {
    const r = await authFetch("/api/history?session=" + encodeURIComponent(SESSION));
    const d = await r.json();
    if (d.messages && d.messages.length) {
      for (const m of d.messages) {
        if (m.role === "user") addUser(m.content);
        else addUltron(m.content);
      }
      return true;
    }
  } catch (_) {}
  return false;
}

async function refreshOps() {
  try {
    const r = await authFetch("/api/tasks");
    const d = await r.json();
    els.ops.innerHTML =
      opsGroup("Tasks", d.tasks.map(t =>
        `<div class="ops-item ${t.done ? "done" : ""}">#${t.id} ${escapeHtml(t.title)}</div>`)) +
      opsGroup("Notes", d.notes.map(n =>
        `<div class="ops-item">#${n.id} ${escapeHtml(n.text)}</div>`)) +
      opsGroup("Reminders", d.reminders.map(rm =>
        `<div class="ops-item">#${rm.id} ${escapeHtml(rm.text)}</div>`));
  } catch (_) {}
}
function opsGroup(title, items) {
  const body = items.length ? items.join("") : `<div class="empty">none yet</div>`;
  return `<div class="ops-group"><h3>${title}</h3>${body}</div>`;
}

/* ---------------- helpers ---------------- */
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
const truncate = (s, n) => (s.length > n ? s.slice(0, n) + "…" : s);
function stripForSpeech(t) {
  return t.replace(/https?:\/\/\S+/g, "link").replace(/[#*_`>-]/g, " ").slice(0, 600);
}

/* ---------------- auth / login ---------------- */
async function ensureAuth() {
  let required = false;
  try {
    const r = await fetch("/api/auth-required");
    required = (await r.json()).required;
  } catch (_) {}

  if (!required) {
    // Local mode: grab a free token so the token param is always valid.
    if (!TOKEN) {
      try {
        const r = await fetch("/api/login", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ password: "" }),
        });
        TOKEN = (await r.json()).token;
        localStorage.setItem("ultron-token", TOKEN);
      } catch (_) {}
    }
    return true;
  }

  // Validate an existing token by hitting a protected endpoint.
  if (TOKEN) {
    const r = await authFetch("/api/status");
    if (r.ok) return true;
    TOKEN = ""; localStorage.removeItem("ultron-token");
  }
  return await showLogin();
}

function showLogin() {
  return new Promise((resolve) => {
    const ov = document.getElementById("login-overlay");
    ov.hidden = false;
    const form = document.getElementById("login-form");
    const pw = document.getElementById("login-pw");
    const err = document.getElementById("login-err");
    pw.focus();
    form.onsubmit = async (e) => {
      e.preventDefault();
      err.textContent = "";
      try {
        const r = await fetch("/api/login", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ password: pw.value }),
        });
        if (!r.ok) { err.textContent = "Access denied."; return; }
        TOKEN = (await r.json()).token;
        localStorage.setItem("ultron-token", TOKEN);
        ov.hidden = true;
        resolve(true);
      } catch (_) { err.textContent = "Connection error."; }
    };
  });
}

/* ---------------- export / share ---------------- */
async function getConversation() {
  try {
    const r = await authFetch("/api/history?session=" + encodeURIComponent(SESSION));
    return (await r.json()).messages || [];
  } catch (_) { return []; }
}
function downloadFile(name, text, type) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function exportMarkdown() {
  const msgs = await getConversation();
  const name = currentProjectName();
  let md = `# ULTRON — ${name}\n\n_Exported ${new Date().toLocaleString()}_\n\n`;
  for (const m of msgs)
    md += (m.role === "user" ? "**You:**\n\n" : "**ULTRON:**\n\n") + m.content + "\n\n---\n\n";
  downloadFile(`ultron-${name.replace(/\s+/g, "-").toLowerCase()}.md`, md, "text/markdown");
}
async function exportPDF() {
  const msgs = await getConversation();
  const name = currentProjectName();
  const rows = msgs.map(m =>
    `<div class="turn ${m.role}"><b>${m.role === "user" ? "You" : "ULTRON"}</b>` +
    `<div>${escapeHtml(m.content).replace(/\n/g, "<br>")}</div></div>`).join("");
  const w = window.open("", "_blank");
  w.document.write(
    `<html><head><title>ULTRON — ${name}</title><style>` +
    `body{font-family:Segoe UI,system-ui,sans-serif;max-width:760px;margin:40px auto;color:#111;padding:0 20px}` +
    `h1{color:#0a7ea4}.turn{margin:0 0 18px;padding-bottom:12px;border-bottom:1px solid #eee}` +
    `.turn b{display:block;color:#0a7ea4;margin-bottom:4px}.user b{color:#b8860b}` +
    `</style></head><body><h1>ULTRON — ${name}</h1><p>${new Date().toLocaleString()}</p>` +
    rows + `<scr` + `ipt>window.onload=()=>window.print()</scr` + `ipt></body></html>`);
  w.document.close();
}

/* ---------------- live brain switch + clear ---------------- */
async function setBrain(provider) {
  try {
    const r = await authFetch("/api/brain", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider }),
    });
    const d = await r.json();
    els.brainText.textContent = "brain: " + d.provider;
    addUltron(`Brain switched to **${d.provider}** — ${d.brain}`);
  } catch (_) { addUltron("Couldn't switch brain, sir."); }
}
function setMode(m) { responseMode = m; localStorage.setItem("ultron-mode", m); renderModePill(); }
async function clearConversation() {
  await authFetch("/api/clear", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: "", session: SESSION }),
  });
  els.messages.innerHTML = "";
  addUltron("Conversation cleared, sir. Fresh slate.");
}

/* ---------------- command palette (Ctrl/Cmd + K) ---------------- */
const cmdk = document.getElementById("cmdk");
const cmdkInput = document.getElementById("cmdk-input");
const cmdkList = document.getElementById("cmdk-list");
let cmdkSel = 0, cmdkCmds = [];

function buildCommands() {
  const cmds = [
    { label: "New project…", run: () => { const n = prompt("Project name:"); if (n) createProject(n); } },
    { label: "Clear this conversation", run: clearConversation },
    { label: "Export as Markdown", run: exportMarkdown },
    { label: "Export as PDF", run: exportPDF },
    { label: "Toggle voice replies", run: () => els.voiceToggle.click() },
    { label: "Length: Auto", run: () => setMode("auto") },
    { label: "Length: Brief", run: () => setMode("brief") },
    { label: "Length: Deep", run: () => setMode("deep") },
    { label: "Brain: Claude (Anthropic)", run: () => setBrain("anthropic") },
    { label: "Brain: GPT-4o (OpenAI)", run: () => setBrain("openai") },
    { label: "Brain: Groq (Llama)", run: () => setBrain("groq") },
    { label: "Brain: Gemini", run: () => setBrain("gemini") },
  ];
  projects.forEach(p => {
    if (p.id !== SESSION) cmds.push({ label: "Switch to: " + p.name, run: () => switchProject(p.id) });
  });
  return cmds;
}
function openCmdk() { cmdk.hidden = false; cmdkInput.value = ""; cmdkSel = 0; renderCmdk(""); cmdkInput.focus(); }
function closeCmdk() { cmdk.hidden = true; }
function renderCmdk(q) {
  cmdkCmds = buildCommands().filter(c => c.label.toLowerCase().includes(q.toLowerCase()));
  if (cmdkSel >= cmdkCmds.length) cmdkSel = 0;
  cmdkList.innerHTML = cmdkCmds.map((c, i) =>
    `<div class="cmdk-item ${i === cmdkSel ? "sel" : ""}" data-i="${i}">${escapeHtml(c.label)}</div>`).join("");
  [...cmdkList.children].forEach(el => (el.onclick = () => runCmdk(parseInt(el.dataset.i))));
}
function runCmdk(i) { const c = cmdkCmds[i]; closeCmdk(); if (c) c.run(); }
cmdkInput.addEventListener("input", () => { cmdkSel = 0; renderCmdk(cmdkInput.value); });
cmdkInput.addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown") { cmdkSel = Math.min(cmdkSel + 1, cmdkCmds.length - 1); renderCmdk(cmdkInput.value); e.preventDefault(); }
  else if (e.key === "ArrowUp") { cmdkSel = Math.max(cmdkSel - 1, 0); renderCmdk(cmdkInput.value); e.preventDefault(); }
  else if (e.key === "Enter") { runCmdk(cmdkSel); }
  else if (e.key === "Escape") { closeCmdk(); }
});
document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    cmdk.hidden ? openCmdk() : closeCmdk();
  }
});
cmdk.addEventListener("click", (e) => { if (e.target === cmdk) closeCmdk(); });

/* ---------------- boot ---------------- */
window.addEventListener("load", async () => {
  await ensureAuth();
  connect();
  loadStatus();
  refreshOps();
  if (window.speechSynthesis) window.speechSynthesis.onvoiceschanged = () => {};
  const hadHistory = await loadHistory();
  if (!hadHistory) {
    setTimeout(() => addUltron(
      "ULTRON online. Systems nominal. I can search the web, pull news, manage " +
      "your notes, tasks and reminders, look at images, and remember what you " +
      "tell me. How can I help, sir?"), 300);
  }
});

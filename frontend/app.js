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
      addUltron(ev.text);
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
  d.innerHTML = `<div class="who">ULTRON</div>${escapeHtml(text)}`;
  els.messages.appendChild(d);
  scroll();
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
  const payload = { message: text, session: SESSION };
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

/* ---------------- voice: text to speech ---------------- */
function speak(text) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(stripForSpeech(text));
  u.rate = 1.02; u.pitch = 0.9;
  const voices = window.speechSynthesis.getVoices();
  const pref = voices.find(v => /male|david|daniel|google uk english male/i.test(v.name))
            || voices.find(v => /en-GB|en-US/i.test(v.lang));
  if (pref) u.voice = pref;
  u.onstart = () => setReactor("speaking");
  u.onend = () => setReactor("idle");
  window.speechSynthesis.speak(u);
}

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

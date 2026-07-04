/* ULTRON — admin dashboard */
const TOKEN = localStorage.getItem("ultron-token") || "";
const H = { "Authorization": "Bearer " + TOKEN, "Content-Type": "application/json" };
const $ = (id) => document.getElementById(id);

function fmtDate(ts) { return ts ? new Date(ts * 1000).toLocaleDateString() : "—"; }
function fmtUptime(s) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h ? `${h}h ${m}m` : `${m}m`;
}

async function load() {
  // verify admin
  let me;
  try { const r = await fetch("/api/me", { headers: H }); if (!r.ok) throw 0; me = await r.json(); } catch (_) { return deny(); }
  if (!me.is_admin) return deny();

  $("panel").hidden = false;

  const [stats, health, users] = await Promise.all([
    fetch("/api/admin/stats", { headers: H }).then(r => r.json()),
    fetch("/api/admin/health", { headers: H }).then(r => r.json()),
    fetch("/api/admin/users", { headers: H }).then(r => r.json()),
  ]);

  // cards
  const t = stats.totals;
  $("cards").innerHTML = [
    ["Users", t.users], ["Conversations", t.conversations], ["Messages", t.messages],
  ].map(([l, n]) => `<div class="card"><div class="n">${n}</div><div class="l">${l}</div></div>`).join("");

  // health
  $("health").innerHTML = [
    `Brain: <b>${health.provider}</b>`, `Store: <b>${health.store}</b>`,
    `Tools: <b>${health.tools}</b>`, `Public mode: <b>${health.public_mode}</b>`,
    `Uptime: <b>${fmtUptime(health.uptime_seconds)}</b>`,
  ].map(x => `<span>${x}</span>`).join("");

  // per-user message counts
  const counts = {};
  (stats.per_user || []).forEach(u => (counts[u.id] = u));

  // users table
  $("users").innerHTML = (users.users || []).map(u => {
    const c = counts[u.id] || { conversations: 0, messages: 0 };
    const role = u.is_admin ? `<span class="badge admin">admin</span>` : `<span class="badge">user</span>`;
    const status = u.disabled ? `<span class="badge off">disabled</span>` : `<span class="badge ok">active</span>`;
    const toggle = u.disabled
      ? `<button class="act" onclick="setDisabled(${u.id},false)">Enable</button>`
      : `<button class="act" onclick="setDisabled(${u.id},true)">Disable</button>`;
    const del = u.is_admin ? "" : `<button class="act danger" onclick="delUser(${u.id})">Delete</button>`;
    return `<tr><td>${u.id}</td><td>${u.email}</td><td>${role}</td><td>${status}</td>
      <td>${c.conversations}</td><td>${c.messages}</td><td>${fmtDate(u.created)}</td>
      <td>${toggle}${del}</td></tr>`;
  }).join("");
}

function deny() { $("denied").hidden = false; $("panel").hidden = true; }

async function setDisabled(id, disabled) {
  await fetch(`/api/admin/users/${id}/disable`, { method: "POST", headers: H, body: JSON.stringify({ disabled }) });
  load();
}
async function delUser(id) {
  if (!confirm("Delete this user and all their data? This cannot be undone.")) return;
  await fetch(`/api/admin/users/${id}`, { method: "DELETE", headers: H });
  load();
}
window.setDisabled = setDisabled;
window.delUser = delUser;

load();

"use strict";
// Offline ship log: downloads a snapshot, queues what the crew enters, uploads when a connection exists.
// It holds no business rules; the server (sedar.ship.log.entry) validates and applies every entry.

const API = "/sedar/ship-log";
const SYNC_RETRY_MS = 30000;
const $ = (id) => document.getElementById(id);
const esc = (value) => String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const store = {
  get(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
  },
  set(key, value) { localStorage.setItem(key, JSON.stringify(value)); },
};

let snapshot = store.get("snapshot", null);
let queue = store.get("queue", []);
let done = store.get("done", []);
let syncing = false;
let reachable = true;

const uuid = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`);
const today = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);

async function rpc(path, params) {
  let response;
  try {
    response = await fetch(API + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", method: "call", params }),
    });
  } catch (error) {
    reachable = false;
    throw error;
  }
  reachable = true;
  const body = await response.json();
  if (body.error) {
    const error = new Error(body.error.data?.message || body.error.message);
    error.expired = (body.error.data?.name || "").includes("SessionExpired");
    throw error;
  }
  return body.result;
}

function banner(text) {
  $("banner").style.display = text ? "block" : "none";
  $("banner").innerHTML = text || "";
}

function status() {
  $("net").textContent = !navigator.onLine ? "Offline" : reachable ? "Online" : "Can't reach server";
  $("pending").textContent = `${queue.length} waiting`;
  $("synced").textContent = snapshot ? `Data from ${snapshot.generated_at} UTC` : "Not synced yet";
}

function persist() {
  store.set("queue", queue);
  store.set("done", done.slice(-5));
  status();
  renderQueue();
}

async function refresh() {
  try {
    snapshot = await rpc("/snapshot", {});
    store.set("snapshot", snapshot);
    banner("");
    render();
  } catch (error) {
    showSyncProblem(error);
  }
  status();
}

function showSyncProblem(error) {
  if (error.expired) {
    banner(`Your Odoo session expired. <a href="/web/login?redirect=${encodeURIComponent(location.pathname)}" >Log in</a> to send what is waiting. Nothing is lost.`);
  } else if (error instanceof TypeError) {
    banner("");
  } else {
    banner(`Could not sync: ${esc(error.message)}`);
  }
}

async function sync() {
  if (syncing) return;
  syncing = true;
  try {
    const waiting = queue.filter((item) => !item.error);
    if (waiting.length) {
      const results = await rpc("/sync", { items: waiting.map(({ label, error, ...entry }) => entry) });
      for (const result of results) {
        const item = queue.find((entry) => entry.client_id === result.client_id);
        if (!item) continue;
        if (result.ok) {
          queue = queue.filter((entry) => entry !== item);
          done.push(`${esc(item.label)}: ${result.message}`);
        } else {
          item.error = result.message;
        }
      }
      persist();
    }
    await refresh();
  } catch (error) {
    showSyncProblem(error);
  } finally {
    syncing = false;
    status();
  }
}

function enqueue(item) {
  queue.push({ client_id: uuid(), ...item });
  persist();
  sync();
}

function currentTug() {
  return snapshot?.tugs.find((tug) => String(tug.id) === $("tug").value);
}

function render() {
  if (!snapshot) return;
  const selected = $("tug").value;
  $("tug").innerHTML = snapshot.tugs.map((tug) => `<option value="${tug.id}">${esc(tug.name)}</option>`).join("");
  if (snapshot.tugs.some((tug) => String(tug.id) === selected)) $("tug").value = selected;
  renderTasks();
  renderQueue();
}

function renderTasks() {
  const tug = currentTug();
  $("tasks").innerHTML = (tug?.tasks || []).map((task) => `
    <div class="task" data-task="${task.id}">
      <div><strong>${esc(task.name)}</strong> <span class="muted">${esc(task.equipment)}</span>
        <span class="badge ${esc(task.state)}">${esc(task.state)}</span></div>
      <div class="muted">Checkpoint at ${task.next_checkpoint.toFixed(0)} h (${task.remaining.toFixed(1)} h remaining)</div>
      <div class="row">
        <label>Done on <input type="date" data-f="done_on" value="${today()}"></label>
        <label style="flex:1">Remarks <input type="text" data-f="remarks"></label>
        <button data-done="${task.id}">Mark done</button>
      </div>
    </div>`).join("") || '<p class="muted">Nothing is approaching or due.</p>';
}

function renderQueue() {
  $("queue").innerHTML = queue.map((item) => `
    <div class="task">
      <div><strong>${esc(item.label)}</strong></div>
      ${item.error ? `<div class="due">${esc(item.error)}</div><button class="secondary" data-discard="${item.client_id}">Discard</button>` : '<div class="muted">Waiting for a connection</div>'}
    </div>`).join("") || '<p class="muted">Nothing waiting.</p>';
  $("done-log").innerHTML = done.slice(-5).reverse().map(esc).join("<br>");
}

document.addEventListener("click", (event) => {
  const taskId = event.target.dataset.done;
  const discard = event.target.dataset.discard;
  if (taskId) {
    const row = event.target.closest(".task");
    const task = currentTug().tasks.find((entry) => String(entry.id) === taskId);
    enqueue({
      kind: "completion", task_id: task.id, label: `${esc(task.name)} (${esc(task.equipment)})`,
      done_on: row.querySelector('[data-f="done_on"]').value,
      remarks: row.querySelector('[data-f="remarks"]').value || undefined,
    });
    snapshot.tugs.forEach((tug) => { tug.tasks = tug.tasks.filter((entry) => entry.id !== task.id); });
    renderTasks();
  }
  if (discard) { queue = queue.filter((item) => item.client_id !== discard); persist(); }
});

$("sync-now").addEventListener("click", sync);
window.addEventListener("online", sync);
window.addEventListener("offline", status);
setInterval(() => { if (queue.some((item) => !item.error)) sync(); }, SYNC_RETRY_MS);

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
render();
status();
sync();

/*
 * local-runtime.js
 * Provides window.claude.use(name) for running the app outside claude.ai.
 * It implements the same small API the app uses, backed by the local FastAPI server:
 *   db         -> /api/collections/...  (polled every 2 s for changes from other users)
 *   user       -> a local user picker stored in this browser
 *   sample     -> /api/ask (only when the server has ANTHROPIC_API_KEY set)
 *   downloads  -> a normal browser download
 */
(function () {
  "use strict";
  const API = "/api";
  const POLL_MS = 2000;

  async function http(method, url, body) {
    const res = await fetch(API + url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      const err = new Error(`${method} ${url} failed (${res.status})`);
      err.code = res.status === 404 || res.status === 400 ? "invalid_argument" : "unavailable";
      throw err;
    }
    return res.json();
  }

  /* ---------- db ---------- */
  const listeners = new Map(); // collection -> Set of {next, error}
  let lastVersion = -1;

  async function refreshCollection(col) {
    const set = listeners.get(col);
    if (!set || !set.size) return;
    try {
      const rows = await http("GET", `/collections/${encodeURIComponent(col)}`);
      const docs = rows.map((r) => ({ id: r.id, exists: true, data: () => r.data, metadata: { fromCache: false, hasPendingWrites: false } }));
      const snap = { docs, size: docs.length, empty: !docs.length, docChanges: () => [], metadata: { fromCache: false, hasPendingWrites: false } };
      set.forEach((l) => l.next(snap));
    } catch (e) {
      console.warn("Refresh failed for", col, e);
    }
  }
  const refreshAll = () => Promise.all([...listeners.keys()].map(refreshCollection));

  async function poll() {
    try {
      const { version } = await http("GET", "/version");
      if (version !== lastVersion) {
        lastVersion = version;
        await refreshAll();
      }
    } catch (e) { /* server offline; keep trying */ }
    setTimeout(poll, POLL_MS);
  }

  function splitDoc(path) {
    const parts = path.split("/");
    if (parts.length !== 2) throw new TypeError("This local runtime supports document paths of the form collection/id: " + path);
    return parts;
  }

  function docRef(col, id) {
    const url = `/collections/${encodeURIComponent(col)}/${encodeURIComponent(id)}`;
    const after = async (p) => { const r = await p; await refreshCollection(col); return r; };
    return {
      id,
      path: `${col}/${id}`,
      async get() { const r = await http("GET", url); return { id, exists: r.exists, data: () => r.data || undefined }; },
      set: (data) => after(http("PUT", url, data)).then(() => undefined),
      update: (data) => after(http("PATCH", url, data)).then(() => undefined),
      delete: () => after(http("DELETE", url)).then(() => undefined),
    };
  }

  function collectionRef(col) {
    if (col.includes("/")) throw new TypeError("This local runtime supports top-level collections only: " + col);
    return {
      path: col,
      doc(id) { return docRef(col, id || Math.random().toString(36).slice(2) + Date.now().toString(36)); },
      async add(data) { const r = await http("POST", `/collections/${encodeURIComponent(col)}`, data); await refreshCollection(col); return docRef(col, r.id); },
      async get() {
        const rows = await http("GET", `/collections/${encodeURIComponent(col)}`);
        const docs = rows.map((r) => ({ id: r.id, exists: true, data: () => r.data }));
        return { docs, size: docs.length, empty: !docs.length };
      },
      onSnapshot(next, error) {
        if (!listeners.has(col)) listeners.set(col, new Set());
        const l = { next, error: error || (() => {}) };
        listeners.get(col).add(l);
        refreshCollection(col);
        return () => listeners.get(col).delete(l);
      },
    };
  }

  const db = {
    collection: collectionRef,
    doc(path) { const [c, i] = splitDoc(path); return docRef(c, i); },
  };

  /* ---------- user (local picker) ---------- */
  const USERS_KEY = "ipc-local-users", CURRENT_KEY = "ipc-local-current";
  const read = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } };
  const write = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} };
  let users = read(USERS_KEY, null);
  if (!users || !users.length) { users = [{ id: "user-1", name: "ICN 1" }, { id: "user-2", name: "ICN 2" }]; write(USERS_KEY, users); }
  let current = read(CURRENT_KEY, users[0].id);
  if (!users.some((u) => u.id === current)) current = users[0].id;

  // Share user names through the server so everyone sees the same names.
  async function syncUsers() {
    try {
      const rows = await http("GET", "/collections/users");
      rows.forEach((r) => { if (!users.some((u) => u.id === r.id)) users.push({ id: r.id, name: r.data.name }); });
      for (const u of users) if (!rows.some((r) => r.id === u.id)) await http("PUT", `/collections/users/${u.id}`, { name: u.name });
      write(USERS_KEY, users); drawPicker();
    } catch {}
  }

  const user = {
    async id() { return current; },
    async me() { const u = users.find((x) => x.id === current); return { id: current, name: u ? u.name : "" }; },
    async name() { return (users.find((x) => x.id === current) || {}).name || ""; },
    async isOwner() { return true; },
    async canEdit() { return true; },
    async can() { return true; },
    async profiles(ids) {
      const out = {};
      [].concat(ids).forEach((id) => { const u = users.find((x) => x.id === id); out[id] = { id, name: u ? u.name : "" }; });
      return out;
    },
  };

  function drawPicker() {
    let box = document.getElementById("localUserBox");
    if (!box) {
      box = document.createElement("div");
      box.id = "localUserBox";
      box.style.cssText = "position:fixed;right:12px;bottom:calc(12px + env(safe-area-inset-bottom,0px));z-index:60;background:var(--surface,#fff);border:1px solid var(--line,#ccc);border-radius:10px;padding:8px 10px;font-size:.85rem;display:flex;gap:6px;align-items:center;box-shadow:0 2px 8px rgba(0,0,0,.08)";
      document.body.appendChild(box);
    }
    box.innerHTML = `<label for="localUserSel" style="color:var(--muted,#666)">Signed in as</label><select id="localUserSel" style="min-height:32px;padding:4px 6px">${users.map((u) => `<option value="${u.id}"${u.id === current ? " selected" : ""}>${u.name.replace(/</g, "&lt;")}</option>`).join("")}<option value="__new">Add a user…</option></select>`;
    box.querySelector("select").onchange = async (e) => {
      if (e.target.value === "__new") {
        const name = (window.prompt("Name of the new user") || "").trim();
        if (name) {
          const u = { id: "user-" + Date.now().toString(36), name };
          users.push(u); write(USERS_KEY, users);
          try { await http("PUT", `/collections/users/${u.id}`, { name }); } catch {}
          current = u.id;
        }
      } else current = e.target.value;
      write(CURRENT_KEY, current);
      location.reload(); // the app reads the user id at start-up
    };
  }

  /* ---------- sample (Claude via the server) ---------- */
  async function sample(input, opts = {}) {
    const prompt = Array.isArray(input) ? input.map((m) => `${m.role}: ${m.content}`).join("\n\n") : String(input);
    let r;
    try { r = await http("POST", "/ask", { prompt }); }
    catch (e) { throw { code: "upstream_error", message: e.message }; }
    if (opts.onText) opts.onText({ text: r.text, delta: r.text });
    return { text: r.text, truncated: !!r.truncated };
  }
  sample.json = async (input, opts) => { const { text } = await sample(input, opts); const m = text.match(/[\[{][\s\S]*[\]}]/); return JSON.parse(m ? m[0] : text); };

  /* ---------- downloads ---------- */
  const downloads = {
    async save({ filename, data }) {
      const blob = data instanceof Blob ? data : new Blob([data], { type: "application/octet-stream" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = filename;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      return { status: "saved" };
    },
  };

  /* ---------- entry point ---------- */
  let aiEnabled = null;
  async function aiOn() {
    if (aiEnabled === null) { try { aiEnabled = (await http("GET", "/config")).ai; } catch { aiEnabled = false; } }
    return aiEnabled;
  }

  window.claude = {
    async use(name) {
      switch (name) {
        case "db": try { await http("GET", "/version"); return db; } catch { return null; }
        case "user": return user;
        case "sample": return (await aiOn()) ? sample : null;
        case "downloads": return downloads;
        default: return null;
      }
    },
  };

  const start = () => { drawPicker(); syncUsers(); poll(); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();

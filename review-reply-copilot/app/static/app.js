(() => {
  const $ = (id) => document.getElementById(id);
  const state = { analyzing: 0, keyHint: null, lastSeconds: null, holdStep3: false, stepDone: { 1: false, 2: false, 3: false }, stepOverride: { 1: null, 2: null, 3: null }, brand: null, brands: [], reviews: [], selected: null, sentiment: new Set(), topic: "", person: false, drafts: {} };

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pretty = (s) => String(s || "").replace(/_/g, " ");
  const money = (v) => "$" + (v || 0).toFixed(4);
  const secs = (v) => (v < 10 ? v.toFixed(1) : Math.round(v)) + " s";

  let toastTimer;
  function toast(message, error = false) {
    const t = $("toast");
    t.textContent = message; t.className = "toast" + (error ? " error" : ""); t.hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => (t.hidden = true), error ? 6000 : 2800);
  }

  async function api(path, options = {}) {
    const response = await fetch(path, options);
    if (!response.ok) {
      let detail = response.statusText;
      try { detail = (await response.json()).detail || detail; } catch (_) { /* keep status text */ }
      throw new Error(typeof detail === "string" ? detail : "Request failed");
    }
    return response.json();
  }
  const post = (path, body) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });

  async function busy(button, label, fn) {
    const original = button.innerHTML;
    button.disabled = true; button.innerHTML = `<span class="spin"></span>${label}`;
    try { return await fn(); } catch (error) { toast(error.message, true); } finally { button.disabled = false; button.innerHTML = original; }
  }

  // ---- loading ---------------------------------------------------------
  async function init() {
    const health = await api("/api/health");
    setKeyState(await api("/api/account"));
    state.brands = await api("/api/brands");
    const select = $("brand");
    select.innerHTML = state.brands.map((b) => `<option value="${esc(b.id)}">${esc(b.name)} (${esc(b.type)})</option>`).join("");
    select.addEventListener("change", () => switchBrand(select.value));
    await switchBrand(state.brands[0].id);
  }

  async function switchBrand(id) {
    state.brand = state.brands.find((b) => b.id === id);
    state.selected = null; state.lastSeconds = null; state.sentiment.clear(); state.topic = ""; state.person = false; $("f-person").checked = false;
    $("f-topic").innerHTML = `<option value="">All topics</option>` + state.brand.topics.map((t) => `<option value="${t}">${pretty(t)}</option>`).join("");
    await refresh();
  }

  async function refresh() {
    state.reviews = await api(`/api/reviews?brand=${encodeURIComponent(state.brand.id)}`);
    revealResults(); renderSteps(); renderFilters(); renderList(); renderStudio(); refreshMetrics();
  }

  // Reviews stay hidden until the first analysis, so the sample data is not shown before Clef-Flash has labeled it.
  function revealResults() {
    const analyzed = state.reviews.some((r) => r.labels);
    $("results").hidden = !(analyzed || state.analyzing);
    const note = $("ready-note"), waiting = state.reviews.filter((r) => !r.labels).length;
    note.hidden = !waiting || !!state.analyzing;
    note.textContent = waiting ? `${waiting} review${waiting > 1 ? "s are" : " is"} ready. ${state.keySet ? "They stay hidden until you analyze them with Clef-Flash." : "Save your Regolo key in step 1, then analyze them."}` : "";
  }

  async function refreshMetrics() {
    const m = await api(`/api/metrics?brand=${encodeURIComponent(state.brand.id)}`);
    $("m-reviews").textContent = m.reviews; $("m-analyzed").textContent = `${m.analyzed} analyzed`;
    const d = m.usage.decide, w = m.usage.write;
    const a = m.last_analysis;
    if (a && a.reviews) { $("m-decide").textContent = secs(a.seconds); $("m-decide-sub").textContent = `last run: ${a.reviews} reviews · ${a.requests} requests · ${money(a.cost_usd)}`; }
    else { $("m-decide").textContent = "–"; $("m-decide-sub").textContent = `${d.calls} requests · ${money(d.cost_usd)}`; }
    $("m-write").textContent = w.calls ? secs(w.seconds / w.calls) : "–";
    $("m-write-sub").textContent = `average per reply · ${w.calls} requests · ${money(w.cost_usd)}`;
    $("m-drafts").textContent = m.drafts; $("m-approved").textContent = `${m.approved} approved`;
  }

  // ---- list ------------------------------------------------------------
  function visible() {
    return state.reviews.filter((r) => {
      const l = r.labels;
      if (state.sentiment.size && !(l && state.sentiment.has(l.sentiment.label))) return false;
      if (state.topic && !(l && l.topic.label === state.topic)) return false;
      if (state.person && !(l && (l.escalation.label === "escalate" || l.low_confidence))) return false;
      return true;
    });
  }

  function renderFilters() {
    const box = $("f-sentiment");
    box.innerHTML = ["positive", "neutral", "negative", "mixed"].map((s) => `<button type="button" class="chip" data-s="${s}" aria-pressed="${state.sentiment.has(s)}">${s}</button>`).join("");
    box.querySelectorAll(".chip").forEach((chip) => chip.addEventListener("click", () => {
      const s = chip.dataset.s; state.sentiment.has(s) ? state.sentiment.delete(s) : state.sentiment.add(s); renderFilters(); renderList();
    }));
  }

  function stars(n) { return n ? "★".repeat(n) + "☆".repeat(5 - n) : "no rating"; }

  function renderList() {
    if (state.analyzing) {
      $("f-count").textContent = "Analyzing…";
      $("list").innerHTML = Array.from({ length: Math.min(state.analyzing, 6) }, () => `<div class="skeleton" aria-hidden="true"><i></i><i></i><i></i><i></i></div>`).join("");
      return;
    }
    const rows = visible();
    $("f-count").textContent = `${rows.length} of ${state.reviews.length} reviews`;
    if (!state.reviews.length) {
      $("list").innerHTML = `<div class="empty"><strong>No reviews yet</strong>Load the sample reviews or import a CSV export.</div>`;
      return;
    }
    $("list").innerHTML = rows.map((r) => {
      const l = r.labels, d = r.draft;
      const tags = [
        l ? `<span class="tag tag--${l.sentiment.label}">${l.sentiment.label}</span>` : `<span class="tag">not analyzed</span>`,
        l ? `<span class="tag">${pretty(l.topic.label)}</span>` : "",
        l ? `<span class="tag tag--lang">${l.language.label}</span>` : "",
        l && l.escalation.label === "escalate" ? `<span class="tag tag--escalate">escalate</span>` : "",
        l && l.low_confidence ? `<span class="tag tag--check">check labels</span>` : "",
        d && d.status !== "escalate" ? `<span class="tag tag--${d.status}">${pretty(d.status)}</span>` : "",
      ].join("");
      return `<button type="button" class="row" data-id="${r.id}" aria-current="${state.selected === r.id}">
        <span class="stars" aria-label="${r.rating || 0} stars">${stars(r.rating)}</span>
        <span class="row__main">
          <span class="row__head"><span class="row__author">${esc(r.author || "Anonymous")}</span><span class="row__date">${esc(r.date)}</span></span>
          <p class="row__text"><strong>${esc(r.title)}</strong> ${esc(r.text)}</p>
          <span class="tags">${tags}</span></span></button>`;
    }).join("") || `<div class="empty"><strong>No reviews match these filters</strong></div>`;
    $("list").querySelectorAll(".row").forEach((row) => row.addEventListener("click", () => { state.selected = row.dataset.id; renderList(); renderStudio(); }));
  }

  // ---- reply studio ----------------------------------------------------
  function checkItem(c) {
    const cls = c.passed ? "ok" : c.blocking ? "fail" : "warn";
    const sym = c.passed ? "✓" : c.blocking ? "✕" : "!";
    const conf = c.confidence != null ? ` · ${Math.round(c.confidence * 100)}%` : "";
    return `<li><span class="mark ${cls}">${sym}</span><span>${esc(c.label)}${c.passed ? "" : `<br><small>${esc(c.detail)}${c.blocking ? "" : " (warning)"}</small>`}</span><span class="src">${c.source === "clef" ? "Clef-Flash" : "Rule"}${conf}</span></li>`;
  }

  function renderStudio() {
    const box = $("studio");
    const r = state.reviews.find((x) => x.id === state.selected);
    if (!r) { box.innerHTML = `<div class="empty"><strong>Reply studio</strong>Select a review to see its labels and write a reply.</div>`; return; }
    const l = r.labels, d = r.draft;
    const labels = l ? ["sentiment", "topic", "escalation", "priority", "language"].map((k) => `
      <dt>${k}</dt><dd>${esc(pretty(l[k].label))}</dd>
      <span class="meter ${l[k].confidence < 0.8 ? "low" : ""}" title="Confidence ${Math.round(l[k].confidence * 100)}%"><span style="width:${Math.round(l[k].confidence * 100)}%"></span></span>`).join("") : "";
    const escalate = l && l.escalation.label === "escalate";
    box.innerHTML = `
      <h2>${esc(r.author || "Anonymous")} <span class="stars">${stars(r.rating)}</span></h2>
      <div class="row__date">${esc(r.date)} · ${esc(r.source)}</div>
      <p class="quote"><strong>${esc(r.title)}</strong>\n${esc(r.text)}</p>
      <h3>Labels from Clef-Flash</h3>
      ${l ? `<dl class="labels">${labels}</dl>` : `<p class="hint">Run "Analyze with Clef-Flash" first.</p>`}
      ${escalate ? `<div class="banner banner--escalate"><strong>A person should handle this first.</strong> The draft below is a neutral holding reply and cannot be marked ready.</div>` : ""}
      <h3>Reply</h3>
      <label class="lbl" for="feedback">Extra instruction for the writer (optional)</label>
      <input type="text" id="feedback" placeholder="For example: mention the 30 day return window">
      <div class="actions"><button class="btn btn--primary" id="btn-reply" type="button" ${l ? "" : "disabled"}>${d ? "Write a new draft" : "Write a draft"}</button></div>
      ${d ? `
        <label class="lbl" for="draft">Draft (edit it, then check again)</label>
        <textarea id="draft">${esc(d.text)}</textarea>
        <div class="charcount" id="count"></div>
        <h3>Checks</h3>
        <ul class="checks">${d.checks.map(checkItem).join("")}</ul>
        ${d.status === "needs_edit" ? `<div class="banner banner--escalate">A blocking check failed. Edit the text and check again, or write a new draft.</div>` : ""}
        ${d.status === "ready" ? `<div class="banner banner--info">All blocking checks passed after ${d.attempts} attempt${d.attempts > 1 ? "s" : ""}. A person still approves.</div>` : ""}
        ${d.status === "approved" ? `<div class="banner banner--info">Approved. Copy the text and post it from the platform's own console.</div>` : ""}
        <div class="actions">
          <button class="btn" id="btn-check" type="button">Check again</button>
          <button class="btn btn--primary" id="btn-approve" type="button" ${d.status === "needs_edit" ? "disabled" : ""}>Approve and copy</button>
        </div>` : ""}`;
    wireStudio(r, d);
  }

  function wireStudio(r, d) {
    const reply = $("btn-reply");
    reply.addEventListener("click", () => busy(reply, "Writing and checking", async () => {
      await post(`/api/reviews/${r.id}/reply`, { feedback: $("feedback").value }); await refresh(); await refreshMetrics();
    }));
    if (!d) return;
    const area = $("draft"), count = $("count");
    const update = () => { count.textContent = `${area.value.length} characters`; area.style.height = "auto"; area.style.height = area.scrollHeight + 6 + "px"; };
    update(); area.addEventListener("input", update);
    const check = $("btn-check");
    check.addEventListener("click", () => busy(check, "Checking", async () => { await post(`/api/drafts/${d.id}/check`, { text: area.value }); await refresh(); await refreshMetrics(); }));
    const approve = $("btn-approve");
    approve.addEventListener("click", () => busy(approve, "Approving", async () => {
      if (area.value !== d.text) { await post(`/api/drafts/${d.id}/check`, { text: area.value }); }
      await post(`/api/drafts/${d.id}/approve`);
      try { await navigator.clipboard.writeText(area.value); toast("Approved and copied to the clipboard"); } catch (_) { toast("Approved. Copy the text from the box."); }
      await refresh();
    }));
  }

  // ---- collapsible steps -----------------------------------------------
  // A finished step closes and shows a check mark and a one line summary on its closed bar.
  // Click a bar to open or close it again. The choice holds until that step changes state.
  const SOURCE_NAMES = { sample: "sample reviews", csv: "CSV file" };
  function stepsDone() {
    const analyzed = state.reviews.filter((r) => r.labels).length, pending = state.reviews.length - analyzed;
    return { 1: !!state.keySet, 2: state.reviews.length > 0, 3: analyzed > 0 && pending === 0 && !state.analyzing && !state.holdStep3 };
  }
  function stepSummary(n) {
    if (n === 1) return `Key saved (${state.keyHint || "verified"})`;
    if (n === 2) {
      const sources = [...new Set(state.reviews.map((r) => SOURCE_NAMES[r.source] || r.source))].join(", ");
      return `${state.reviews.length} reviews ready · ${state.brand.name} · ${sources}`;
    }
    const analyzed = state.reviews.filter((r) => r.labels).length;
    return `${analyzed} reviews analyzed` + (state.lastSeconds ? ` in ${state.lastSeconds.toFixed(1)} s` : "");
  }
  function renderSteps() {
    const done = stepsDone(), cards = { 1: $("connect"), 2: $("import"), 3: $("analyze") };
    for (const n of [1, 2, 3]) {
      if (done[n] !== state.stepDone[n]) { state.stepOverride[n] = null; state.stepDone[n] = done[n]; }
      const open = state.stepOverride[n] ?? !done[n], card = cards[n];
      card.classList.toggle("collapsed", !open); card.classList.toggle("is-done", done[n]);
      $("toggle-" + n).setAttribute("aria-expanded", String(open));
      $("body-" + n).inert = !open;
      $("step-" + n).textContent = done[n] ? "✓" : String(n);
      const sum = $("sum-" + n); sum.hidden = !done[n]; if (done[n]) sum.textContent = stepSummary(n);
    }
  }
  [1, 2, 3].forEach((n) => $("toggle-" + n).addEventListener("click", () => {
    const open = state.stepOverride[n] ?? !state.stepDone[n];
    state.stepOverride[n] = !open; renderSteps();
  }));

  // ---- connect card ----------------------------------------------------
  function setKeyState(account) {
    state.keySet = !!(account && account.key_set); state.keyHint = account && account.key_hint;
    const badge = $("badge-key"); badge.classList.toggle("bad", !state.keySet);
    $("badge-key-text").textContent = state.keySet ? "Regolo key set" : "Add your Regolo key";
    const line = $("key-state");
    if (state.keySet) { line.className = "keystate ok"; line.textContent = `Key saved (${account.key_hint}). Paste another one to replace it.`; }
    else { line.className = "keystate"; line.textContent = "No key saved yet."; }
    gateAnalyze(); renderSteps();
  }
  function gateAnalyze() {
    $("btn-analyze").disabled = !state.keySet || state.analyzing > 0;
    $("btn-analyze").title = state.keySet ? "" : "Save your Regolo key in step 1 first";
  }
  $("key-toggle").addEventListener("click", () => {
    const input = $("api-key"), show = input.type === "password";
    input.type = show ? "text" : "password"; $("key-toggle").textContent = show ? "Hide" : "Show";
  });
  $("keyform").addEventListener("submit", (e) => {
    e.preventDefault();
    busy($("key-save"), "Verifying", async () => {
      const response = await fetch("/api/account/key", { method: "POST", headers: { "Content-Type": "application/json", "X-RRC": "1" }, body: JSON.stringify({ key: $("api-key").value }) });
      const body = await response.json();
      if (!response.ok) { $("key-state").className = "keystate bad"; $("key-state").textContent = body.detail || "Could not save the key."; return; }
      $("api-key").value = ""; $("api-key").type = "password"; $("key-toggle").textContent = "Show";
      setKeyState(body); toast("Regolo key verified and saved");
    });
  });

  // ---- import card -----------------------------------------------------
  const importButtons = () => ["brand", "btn-sample", "btn-analyze", "btn-reset"].map($);
  function lockImport(locked) { importButtons().forEach((b) => { if (b) b.disabled = locked; }); $("csv-file").disabled = locked; }

  $("btn-sample").addEventListener("click", (e) => busy(e.currentTarget, "Loading", async () => {
    const out = await post("/api/reviews/sample", { brand: state.brand.id }); toast(`Added ${out.added} sample reviews (${out.total} in total)`); await refresh();
  }));
  $("csv-file").addEventListener("change", async (e) => {
    const file = e.target.files[0]; if (!file) return;
    const form = new FormData(); form.append("brand", state.brand.id); form.append("file", file);
    try { const out = await api("/api/reviews/csv", { method: "POST", body: form }); toast(`Imported ${out.added} reviews from ${file.name}`); await refresh(); } catch (error) { toast(error.message, true); }
    e.target.value = "";
  });

  // ---- analysis with a real progress bar ------------------------------
  let pollTimer = null;
  function showProgress(p) {
    const total = Math.max(p.total, 1), pct = Math.max(3, Math.round((p.done / total) * 100));
    $("progress-bar").style.width = pct + "%";
    $("progress-count").textContent = `${p.done} of ${p.total} reviews`;
    $("progress-sub").textContent = `${p.elapsed.toFixed(1)} s · five questions per review, eight requests at a time`;
  }
  $("btn-analyze").addEventListener("click", async (e) => {
    const button = e.currentTarget, original = button.innerHTML;
    const pending = state.reviews.filter((r) => !r.labels).length;
    if (!pending) { toast(state.reviews.length ? "Every review is already analyzed" : "Add some reviews first"); return; }
    state.analyzing = pending; revealResults(); renderSteps(); renderList(); lockImport(true);
    button.innerHTML = `<span class="spin"></span>Analyzing`;
    $("progress").hidden = false; $("progress-title").textContent = "Clef-Flash is labeling your reviews";
    showProgress({ done: 0, total: pending, elapsed: 0 });
    pollTimer = setInterval(async () => { try { showProgress(await api("/api/analyze/progress")); } catch (_) { /* keep polling */ } }, 350);
    try {
      const out = await post("/api/analyze", { brand: state.brand.id });
      showProgress({ done: out.analyzed, total: out.analyzed, elapsed: out.seconds }); state.lastSeconds = out.seconds;
      $("progress-title").textContent = `Done: ${out.analyzed} reviews labeled`;
      toast(`Analyzed ${out.analyzed} reviews in ${out.seconds.toFixed(1)} s`);
    } catch (error) { toast(error.message, true); }
    finally {
      clearInterval(pollTimer); state.analyzing = 0; button.innerHTML = original; lockImport(false); gateAnalyze();
      state.holdStep3 = true;  // keep step 3 open for a moment so the full progress bar is seen
      await refresh();
      setTimeout(() => { state.holdStep3 = false; $("progress").hidden = true; renderSteps(); }, 1400);
    }
  });
  $("btn-reset").addEventListener("click", async () => {
    if (!confirm(`Remove all reviews and drafts for ${state.brand.name} from this computer?`)) return;
    await post("/api/reviews/reset", { brand: state.brand.id }); state.selected = null; await refresh();
  });
  $("f-topic").addEventListener("change", (e) => { state.topic = e.target.value; renderList(); });
  $("f-person").addEventListener("change", (e) => { state.person = e.target.checked; renderList(); });

  init().catch((error) => toast(error.message, true));
})();

"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtMs = (v) => (v == null ? "–" : v < 10 ? `${v.toFixed(1)} ms` : `${Math.round(v).toLocaleString("en")} ms`);
const fmtUsd = (v, digits = 5) => (v == null ? "–" : `$${v.toFixed(digits)}`);
const fmtInt = (v) => (v == null ? "–" : Math.round(v).toLocaleString("en"));
const fmtWhen = (iso) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
const LEVELS = { rule: "Hard rules", prescore: "Pre-score", model: "Clef-Flash", fail_mode: "Fail mode" };
const DECISIONS = { approve: "Approve", step_up: "Step-up", hold: "Hold", block: "Block" };
const TYPE_TITLES = {
  habitual: "Everyday payment", unusual_legit: "Unusual but genuine", card_testing: "Card testing",
  stolen_card_online: "Stolen card online", account_takeover: "Account takeover", impersonation_scam: "Impersonation scam",
  atm_cashout: "ATM cash-out abroad", rogue_direct_debit: "Unknown direct debit",
  cloned_card: "Cloned card in a shop", sanctions: "Sanctioned country", risky_merchant: "Crypto or gambling site",
  fraud: "Other fraud", legit: "Genuine payment", unlabelled: "Unlabelled",
};
const FRAUD_TYPES = new Set(["card_testing", "stolen_card_online", "account_takeover", "impersonation_scam", "atm_cashout",
  "rogue_direct_debit", "cloned_card", "sanctions", "risky_merchant"]);
const MIX_DEFAULT = { habitual: 50, unusual_legit: 20, card_testing: 5, stolen_card_online: 5, account_takeover: 5,
  impersonation_scam: 5, atm_cashout: 5, rogue_direct_debit: 5 };
const MODES = { always: "Clef-Flash on every payment", cascade: "Clef-Flash only when needed", never: "Rules only, no Clef-Flash" };
const modeText = (m) => (MODES[m] || m).replace(/^Rules/, "rules");  // mid-sentence: keep the product name capitalised

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : body.detail ? JSON.stringify(body.detail) : `${res.status} ${res.statusText}`);
  return body;
}
const post = (path, body, method = "POST") => api(path, { method, body: JSON.stringify(body) });
const badge = (d) => `<span class="decision ${esc(d)}">${esc(DECISIONS[d] || d)}</span>`;

/* ── routing: #view or #view?key=value ─────────────────────────────── */
const VIEWS = { start: loadStart, test: loadTest, policies: loadPolicies, audit: loadAudit };
// Older links: Scenarios was the set-up, Benchmark the results; both now live in Test.
const ALIASES = { scenarios: ["test", ""], benchmark: ["test", "section=results"] };
let leaveGuard = null;
function route() {
  let [view0, query] = location.hash.slice(1).split("?");
  if (ALIASES[view0]) [view0, query] = [ALIASES[view0][0], [ALIASES[view0][1], query].filter(Boolean).join("&")];
  const view = VIEWS[view0] ? view0 : "start";
  // Start lives at "/": drop "#start" (or any unknown hash) from the address bar.
  if (view === "start" && location.hash) history.replaceState(null, "", "/");
  const params = new URLSearchParams(query || "");
  $$(".view").forEach((v) => (v.hidden = v.id !== `view-${view}`));
  $$(".tabs a").forEach((a) => (a.dataset.view === view ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
  VIEWS[view](params);
}
window.addEventListener("hashchange", () => {
  if (leaveGuard && !leaveGuard()) { history.replaceState(null, "", `#policies?name=${encodeURIComponent(polName)}`); return; }
  route();
});
// Links to "/" open Start without reloading the page.
document.addEventListener("click", (e) => {
  const a = e.target.closest('a[href="/"]');
  if (!a || e.metaKey || e.ctrlKey || e.shiftKey) return;
  e.preventDefault();
  if (!location.hash) return;
  if (location.hash.startsWith("#policies") && dirty() && !confirm("The policy has unsaved changes. Leave and lose them?")) return;
  history.pushState(null, "", "/");
  route();
});
window.addEventListener("popstate", () => { if (!location.hash) route(); });

/* ── status, sidebar and API key ───────────────────────────────────── */
let STATUS = null;
const keyActive = () => !!(STATUS && STATUS.regolo.key_present && STATUS.regolo.key_valid);

async function loadStatus() {
  try {
    STATUS = await api("/api/status");
  } catch (e) {
    $("#lights").innerHTML = `<li class="bad"><b>Console</b><span>not responding: ${esc(e.message)}</span></li>`;
    return;
  }
  const s = STATUS, r = s.regolo, items = [];
  items.push([r.reachable && r.model_listed ? "ok" : "bad", "Regolo", r.reachable ? (r.model_listed ? "clef-flash available" : "clef-flash not listed") : "unreachable"]);
  items.push([!r.key_present ? "bad" : r.key_valid ? "ok" : "bad", "API key", !r.key_present ? "not set" : r.key_valid ? "active" : r.key_valid === false ? "rejected" : "not checked"]);
  if (s.backend !== "regolo") items.push(["warn", "Mode", "offline demo, no Regolo calls"]);
  const bad = s.policies.filter((p) => !p.ok);
  items.push([bad.length ? "bad" : "ok", "Policies", bad.length ? `${bad.length} of ${s.policies.length} invalid` : `${s.policies.length} valid`]);
  items.push([!s.audit.exists ? "warn" : s.audit.ok === false ? "bad" : "ok", "Audit chain", !s.audit.exists ? "empty" : s.audit.ok ? `intact, ${fmtInt(s.audit.records)} records` : "broken"]);
  items.push([s.data.scenarios ? "ok" : "warn", "Test data", `${s.data.scenarios} scenarios${s.data.random_dataset ? ", random set" : ""}`]);
  $("#lights").innerHTML = items.map(([c, k, v]) => `<li class="${c}"><b>${esc(k)}</b><span>${esc(v)}</span></li>`).join("");
  $("#price").textContent = s.price ? `Clef-Flash: $${(s.price.usd_per_input_token * 1e6).toFixed(2)} per million input tokens, output free (${s.price.source}).` : "";

  renderAccount();
  fillPolicyOptions();
  const def = s.policies.find((p) => p.name === "retail-eu" && p.ok);
  if (def) $("#start-history").textContent = def.history_payments;
  $("select[name=concurrency]").innerHTML = Array.from({ length: s.max_concurrency }, (_, i) => `<option${i + 1 === 2 ? " selected" : ""}>${i + 1}</option>`).join("");
}

function renderAccount() {
  const r = STATUS.regolo, active = keyActive();
  document.body.classList.toggle("needs-key", !active);
  $("#promo").hidden = active;
  $("#key-state").className = "key-state" + (active ? " ok" : "");
  $("#key-state").textContent = active ? "Active and saved in .env. Scenarios and benchmarks call Clef-Flash with it."
    : r.key_present && r.key_valid === false ? "The saved key was rejected by Regolo. Paste a valid one."
    : r.key_present ? "A key is saved but could not be checked: Regolo is unreachable."
    : "Not set yet. Without a key the console cannot call Clef-Flash.";
  $("#key-fields").hidden = active;
  $("#key-replace").hidden = !active;
  const create = $('.path li[data-step="create"]');
  create.classList.toggle("done", r.key_present);
  $(".state", create).hidden = !r.key_present;
  $("#key-create").hidden = r.key_present;
  const step = $('.path li[data-step="key"]');
  step.classList.toggle("done", active);
  $(".state", step).textContent = "Done";
  $(".state", step).hidden = !active;
  $("#key-focus").hidden = active;
  $("#quick-bench").disabled = !active && STATUS.backend === "regolo";
  $("#quick-bench").title = $("#quick-bench").disabled ? "Add your Regolo API key first" : "";
}

$("#key-focus").addEventListener("click", () => { $("#key-input").focus(); $("#key-form").scrollIntoView({ behavior: "smooth", block: "center" }); });
$("#key-replace").addEventListener("click", () => { $("#key-fields").hidden = false; $("#key-replace").hidden = true; $("#key-input").focus(); });
$("#key-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("#key-input"), btn = $("#key-save");
  $("#key-error").hidden = true;
  btn.disabled = true; btn.classList.add("busy"); btn.textContent = "Checking with Regolo…";
  try {
    await post("/api/settings/regolo-key", { key: input.value });
    input.value = "";
    await loadStatus();
  } catch (err) {
    $("#key-error").textContent = err.message; $("#key-error").hidden = false;
  } finally {
    btn.disabled = false; btn.classList.remove("busy"); btn.textContent = "Check and save key";
  }
});

function fillPolicyOptions() {
  const ok = STATUS.policies.filter((p) => p.ok);
  $$(".policy-options").forEach((sel) => {
    const current = sel.value || "retail-eu";
    sel.innerHTML = ok.map((p) => `<option value="${esc(p.name)}">${esc(p.name)}</option>`).join("");
    sel.value = ok.some((p) => p.name === current) ? current : "retail-eu";
  });
}

/* ── benchmark runs: shared helpers ────────────────────────────────── */
// A run holds one result per (policy, mode); runs saved before policy comparison have `modes` only.
const cellsOf = (run) => run.configs || Object.values(run.modes).map((m) => ({ policy: run.policy, ...m }));
const pct = (a, b) => (b ? Math.round((100 * a) / b) : 0);
const mean = (v) => (v.length ? v.reduce((a, b) => a + b, 0) / v.length : null);
// Average and slowest wait per payment: the median hides the model when rules settle most payments.
const waits = (c) => { const t = c.rows.map((r) => r.total_ms); return { avg: mean(t), max: Math.max(...t) }; };
const typeTitle = (t) => TYPE_TITLES[t] || t.replaceAll("_", " ");
const plural = (n, one, many = `${one}s`) => `${fmtInt(n)} ${n === 1 ? one : many}`;

// Fraud stopped and genuine customers interrupted, from the rows: works for every saved run.
function tally(c) {
  const f = c.rows.filter((r) => r.label === "fraud"), g = c.rows.filter((r) => r.label === "legit");
  return { fraud: f.length, stopped: f.filter((r) => r.decision !== "approve").length,
    legit: g.length, bothered: g.filter((r) => r.decision !== "approve").length };
}

let LATEST;  // the latest benchmark, preferring Regolo runs; undefined until fetched
async function latestRun() {
  if (LATEST !== undefined) return LATEST;
  const runs = await api("/api/bench/runs").catch(() => []);
  const pick = runs.find((r) => r.backend === "regolo") || runs[0];
  LATEST = pick ? await api(`/api/bench/runs/${pick.id}`).catch(() => null) : null;
  return LATEST;
}

/* ── start ─────────────────────────────────────────────────────────── */
async function loadStart() {
  const run = await latestRun();
  $('.path li[data-step="bench"]').classList.toggle("done", !!run);
  if (run) renderOverview(run);
}

$("#quick-bench").addEventListener("click", () => {
  location.hash = "#test?section=results";
  startBench({ dataset: "scenarios", n: 50, modes: ["always", "cascade"], concurrency: 2, policies: ["retail-eu"] });
});

function renderOverview(run) {
  const cs = cellsOf(run), mine = cs.filter((x) => x.policy === cs[0].policy);
  const c = mine.find((m) => m.mode === "cascade") || mine[0];
  const a = mine.find((m) => m.mode === "always" && m !== c);
  const setName = run.dataset_meta?.title || run.dataset || "a dataset";
  $("#cascade-caption").innerHTML =
    `${fmtInt(c.n)} payments from ${esc(setName)}, ${esc(modeText(c.mode))}, ${esc(fmtWhen(run.started_at))}, ${esc(run.backend)}. <a href="#test">Run another</a>`;
  const levels = Object.entries(c.decided_by).filter(([, v]) => v > 0);
  $("#cascade").innerHTML = levels.map(([k, v]) =>
    `<div class="seg ${k}" style="flex-grow:${v}" title="${esc(LEVELS[k])}: ${v}"><b>${v}</b><span>${esc(LEVELS[k])}, ${Math.round((100 * v) / c.n)}%</span></div>`).join("");
  const lat = c.latency_by_level_ms;
  const legend = {
    rule: ["--rule-level", "Hard rules", `${fmtMs(lat.rules.mean + lat.features.mean)} for features and rules, no cost`],
    prescore: ["--prescore-level", "Pre-score", `${fmtMs(lat.prescore.mean)} on top, no cost`],
    model: ["--model-level", "Clef-Flash on Regolo", `${fmtMs(c.latency_model_ms.p50)} median, ${fmtUsd(c.cost_usd_per_model_call)} per call`],
    fail_mode: ["--fail-level", "Fail mode", "no answer within the timeout, or circuit breaker open: the channel's fallback decided"],
  };
  $("#cascade-legend").innerHTML = levels.map(([k]) => `<div style="--c:var(${legend[k][0]})"><b>${legend[k][1]}</b><span>${legend[k][2]}</span></div>`).join("");

  const row = (k, v) => `<dt>${esc(k)}</dt><dd>${v}</dd>`;
  const vs = (fc, fa) => (a ? `${fc} <small>vs ${fa}</small>` : fc);
  const t = tally(c);
  $("#figures").innerHTML = `
    <section><h3>Time</h3><dl>
      ${row("Per payment, median", fmtMs(c.latency_total_ms.p50))}
      ${row("Per payment, 95th percentile", fmtMs(c.latency_total_ms.p95))}
      ${row("Model call, median", fmtMs(c.latency_model_ms.p50))}
      ${row("Model call, 95th percentile", fmtMs(c.latency_model_ms.p95))}
      ${row("Features + rules + pre-score", fmtMs(lat.features.mean + lat.rules.mean + lat.prescore.mean))}
    </dl></section>
    <section><h3>Cost</h3><dl>
      ${row("Input tokens per model call", fmtInt(c.input_tokens_per_call))}
      ${row("Per model call", fmtUsd(c.cost_usd_per_model_call))}
      ${row("Per 1,000 payments", vs(fmtUsd(c.cost_usd_per_1k_payments, 3), a ? fmtUsd(a.cost_usd_per_1k_payments, 3) + " on every payment" : ""))}
      ${row("Per million payments", vs(`$${fmtInt(c.cost_usd_per_1k_payments * 1000)}`, a ? `$${fmtInt(a.cost_usd_per_1k_payments * 1000)} on every payment` : ""))}
      <dd class="src">Price ${esc(run.price.source)}: $${(run.price.usd_per_input_token * 1e6).toFixed(2)} per million input tokens; output tokens are free.</dd>
    </dl></section>
    <section><h3>Fraud</h3><dl>
      ${t.fraud ? row("Fraud stopped", `${t.stopped} of ${t.fraud}`) : ""}
      ${t.legit ? row("Genuine customers interrupted", `${t.bothered} of ${t.legit}`) : ""}
      ${row("Sent to the model", vs(`${c.sent_to_model_pct}%`, a ? `${a.sent_to_model_pct}% on every payment` : ""))}
      ${row("Throughput", vs(`${c.throughput_rps} /s`, a ? `${a.throughput_rps} /s on every payment` : ""))}
      <dd class="src">${run.concurrency} parallel request${run.concurrency > 1 ? "s" : ""}, policy ${esc(c.policy)}.</dd>
    </dl></section>`;
}

/* ── test: a four-step set-up, then results (one page, two sections) ─ */
let DATASETS = [];
const tw = { policies: ["retail-eu"], modes: ["cascade", "always"], dataset: "scenarios", step: 1, section: "setup" };
const ROUTING = [
  ["cascade", "Only when needed", "Rules and a quick score settle the clear cases. Clef-Flash checks the uncertain ones, high amounts and instant transfers.", "Best balance: most payments never wait for the model."],
  ["always", "On every payment", "Every payment the rules let through is checked by Clef-Flash, even the clearly ordinary ones.", "Most thorough: one model call per payment."],
  ["never", "Never", "Rules and the quick score only, no call to Regolo.", "Free and instant, but blind to scams that look normal on paper."],
];
const STEPS = ["Policies", "Decision model", "Dataset", "Run"];
const okPolicies = () => STATUS.policies.filter((p) => p.ok).sort((a, b) => (b.name === "retail-eu") - (a.name === "retail-eu") || a.name.localeCompare(b.name));

const policyFacts = (p) => {
  const t = p.timeouts_ms || {};
  return [
    ["Waits for Clef-Flash on cards", `${fmtInt(t.card_present ?? t.default)} ms`],
    ["Questions to Clef-Flash", `${p.questions.length}`],
    ["Past payments read", `${p.history_payments}`],
  ];
};

async function loadTest(params) {
  if (params.get("policy")) { tw.policies = [params.get("policy")]; tw.step = 1; }
  if (params.get("section")) tw.section = params.get("section");
  if (params.get("step")) tw.step = Math.min(4, Math.max(1, +params.get("step") || 1));
  showSection(tw.section);
  renderPolicyStep(); renderRoutingStep(); renderWhy();
  await renderDatasets();
  showStep(tw.step);
  const runs = await loadRuns();
  if (!benchShown && runs[0]) { benchShown = true; renderBench(await api(`/api/bench/runs/${runs[0].id}`)); }
  if (params.get("cell") && SHOWN_RUN) renderCellDetail(Math.min(+params.get("cell") || 0, cellsOf(SHOWN_RUN).length - 1));
  if (params.get("generate")) openGenerator(params.get("generate") === "tabformer" ? "tabformer" : undefined);
}

function showSection(name) {
  tw.section = name;
  $("#sec-setup").hidden = name !== "setup";
  $("#sec-results").hidden = name !== "results";
  $$("#test-switch button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.section === name)));
}
$("#test-switch").addEventListener("click", (e) => { const b = e.target.closest("button[data-section]"); if (b) showSection(b.dataset.section); });

function stepSummary(i) {
  if (i === 1) return tw.policies.join(", ") || "none chosen";
  if (i === 2) return tw.modes.map((m) => ROUTING.find(([v]) => v === m)[1].toLowerCase()).join(", ") || "none chosen";
  if (i === 3) return DATASETS.find((d) => d.id === tw.dataset)?.title || "";
  return "cost and start";
}

function showStep(n) {
  tw.step = n;
  $$(".wstep").forEach((s) => (s.hidden = +s.dataset.step !== n));
  $("#stepper").innerHTML = STEPS.map((t, i) => `<li${i + 1 === n ? ' aria-current="step"' : ""}${i + 1 < n ? ' class="done"' : ""}>
    <button type="button" data-goto="${i + 1}"><span>${i + 1}</span><b>${t}</b><small>${esc(stepSummary(i + 1))}</small></button></li>`).join("");
  $("#w-back").hidden = n === 1;
  const invalid = (n === 1 && !tw.policies.length) || (n === 2 && !tw.modes.length);
  $("#w-hint").textContent = n === 1 && !tw.policies.length ? "Choose at least one policy." : n === 2 && !tw.modes.length ? "Choose at least one option." : "";
  $("#w-next").disabled = invalid;
  $("#w-next").textContent = n < 4 ? `Next: ${STEPS[n]}` : "Run";
  if (n === 4) renderPlan();
}
$("#stepper").addEventListener("click", (e) => { const b = e.target.closest("button[data-goto]"); if (b && tw.policies.length && tw.modes.length) showStep(+b.dataset.goto); });
$("#w-back").addEventListener("click", () => showStep(tw.step - 1));
$("#w-next").addEventListener("click", () => (tw.step < 4 ? showStep(tw.step + 1) : runPlan()));

function renderPolicyStep() {
  const pols = okPolicies();
  tw.policies = tw.policies.filter((n) => pols.some((p) => p.name === n));
  if (!tw.policies.length && pols[0]) tw.policies = [pols[0].name];
  const ex = pols.find((p) => p.name === tw.policies[0])?.example_rule;
  $("#t-example").innerHTML = ex ? `<code>- { id: ${esc(ex.id)}, when: "${esc(ex.when)}", decision: ${esc(ex.decision)} }</code><span>${esc(ex.reason)}: ${badge(ex.decision)}</span>` : "";
  $("#t-policies").innerHTML = pols.map((p) => {
    const on = tw.policies.includes(p.name);
    return `<label class="choice${on ? " on" : ""}">
      <input type="checkbox" name="t-policy" value="${esc(p.name)}"${on ? " checked" : ""}${!on && tw.policies.length >= 3 ? " disabled" : ""}>
      <b>${esc(p.name)}</b>
      <span class="choice-text">${esc(p.description || "No description: add one in the policy file.")}</span>
      <dl>${policyFacts(p).map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>
    </label>`;
  }).join("");
}

function renderRoutingStep() {
  const own = new Set(okPolicies().filter((p) => tw.policies.includes(p.name)).map((p) => p.routing));
  $("#t-routing").innerHTML = ROUTING.map(([v, title, what, cost]) => {
    const on = tw.modes.includes(v);
    return `<label class="choice${on ? " on" : ""}">
      <input type="checkbox" name="t-mode" value="${v}"${on ? " checked" : ""}>
      <b>${title}</b><span class="choice-text">${what}</span>
      ${own.has(v) ? `<span class="tag own">the policy's own setting</span>` : ""}<span class="choice-note">${cost}</span>
    </label>`;
  }).join("");
}

$("#view-test").addEventListener("change", (e) => {
  const t = e.target;
  const pick = (list, v, on) => (on ? [...new Set([...list, v])] : list.filter((x) => x !== v));
  if (t.name === "t-policy") { tw.policies = pick(tw.policies, t.value, t.checked); renderPolicyStep(); renderRoutingStep(); renderWhy(); showStep(1); }
  if (t.name === "t-mode") { tw.modes = ROUTING.map(([v]) => v).filter((v) => pick(tw.modes, t.value, t.checked).includes(v)); renderRoutingStep(); showStep(2); }
  if (t.name === "t-dataset") { tw.dataset = t.value; $$("#t-datasets .choice").forEach((c) => c.classList.toggle("on", c.contains(t))); showStep(3); }
  if (t.name === "n" || t.name === "concurrency") renderPlan();
});

// Why ask Clef-Flash at all: with figures from the latest benchmark when there is one.
async function renderWhy() {
  const run = await latestRun();
  const first = tw.policies[0];
  const pol = STATUS.policies.find((p) => p.name === first) || {};
  const used = run ? cellsOf(run).filter((c) => c.input_tokens_per_call) : [];
  const cell = used.find((c) => c.policy === first && c.mode === "always") || used.find((c) => c.policy === first) || used[0];
  const tokens = cell?.input_tokens_per_call || 2500;
  const price = STATUS.price?.usd_per_input_token;
  const per1k = price ? tokens * price * 1000 : null;
  const speed = cell?.latency_model_ms?.p50 ? `About ${fmtMs(cell.latency_model_ms.p50)} per answer` : "A few hundred milliseconds per answer";
  const items = [
    ["It reads the customer, not one signal", `It sees the new payment next to the customer's last ${pol.history_payments || 10} payments and names the pattern that fits: fake bank operator, account takeover, stolen card. A rule checks one condition at a time.`],
    ["Fewer good customers stopped", "It gives a graded risk, not a yes or no, so a trip abroad or a one-off purchase can go through where a fixed threshold would hold it."],
    ["Fast and cheap enough for every payment", `${speed}, ${per1k != null ? `about $${per1k.toFixed(2)} per 1,000 payments checked` : "a fraction of a cent per payment"}: ${fmtInt(tokens)} input tokens each, output free${cell ? `, measured in your latest benchmark at ${run.concurrency} parallel request${run.concurrency > 1 ? "s" : ""} on the shared API` : ""}.`],
    ["Nothing to train, nothing exposed", "The policy's questions are enough: no training on your data. Names, IBANs and device ids are replaced by keyed hashes before anything leaves this computer."],
  ];
  $("#t-why").innerHTML = items.map(([h, t]) => `<li><b>${esc(h)}</b><span>${t}</span></li>`).join("");
}

// One line per type, largest first, as a bar and a list.
function composition(meta, limit = 99) {
  const total = Object.values(meta.types).reduce((a, b) => a + b, 0) || 1;
  const fraudTypes = (t) => (FRAUD_TYPES.has(t) || t === "fraud");
  const entries = Object.entries(meta.types).sort((a, b) => fraudTypes(a[0]) - fraudTypes(b[0]) || b[1] - a[1]);
  const bar = `<div class="comp" aria-hidden="true">${entries.map(([t, n]) => `<i class="${fraudTypes(t) ? "fraud" : "legit"}" style="flex-grow:${n}" title="${esc(typeTitle(t))}: ${n}"></i>`).join("")}</div>`;
  const shown = entries.slice(0, limit);
  const list = `<ul class="comp-list">${shown.map(([t, n]) => `<li class="${fraudTypes(t) ? "fraud" : "legit"}"><span>${esc(typeTitle(t))}</span><b>${pct(n, total)}%</b><small>${n}</small></li>`).join("")}${entries.length > limit ? `<li class="more"><span>${entries.length - limit} more types</span></li>` : ""}</ul>`;
  return { bar, list };
}

function setFacts(d) {
  const g = d.generation;
  return [
    ["Payments", d.id === "scenarios" ? `${fmtInt(d.n)}, plus 3 demos` : fmtInt(d.n)],
    ["Fraud in the set", `${pct(d.labels?.fraud || 0, d.n)}%`],
    ["Past payments each", fmtInt(d.history)],
    ...(g?.cost_usd ? [["Cost to write", `$${g.cost_usd.toFixed(4)}`]] : []),
  ];
}

async function renderDatasets() {
  DATASETS = await api("/api/datasets");
  if (!DATASETS.some((d) => d.id === tw.dataset)) tw.dataset = "scenarios";
  $("#t-datasets").innerHTML = DATASETS.map((d) => {
    const c = composition(d, 3);
    return `<label class="choice set${d.id === tw.dataset ? " on" : ""}">
      <input type="radio" name="t-dataset" value="${esc(d.id)}"${d.id === tw.dataset ? " checked" : ""}>
      <b>${esc(d.title)}</b><span class="choice-how">${esc(d.how)}</span>
      ${d.detail ? `<span class="choice-text">${esc(d.detail)}</span>` : ""}
      ${c.bar}${c.list}
      <dl>${setFacts(d).map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl></label>`;
  }).join("");
}

// Step 4: every combination, how many payments reach Clef-Flash (counted offline) and the price.
let planSeq = 0;
function planBody() {
  const f = $("#plan-form").elements;
  return { dataset: tw.dataset, n: +f.n.value, modes: tw.modes, policies: tw.policies, concurrency: +f.concurrency.value };
}
async function renderPlan() {
  const set = DATASETS.find((d) => d.id === tw.dataset);
  $("#plan-n").hidden = !set || set.id === "scenarios" || set.n <= 5;
  const seq = ++planSeq;
  $("#plan-table tbody").innerHTML = '<tr><td colspan="4" class="empty">Counting the payments that reach the decision model…</td></tr>';
  let e;
  try { e = await post("/api/bench/estimate", planBody()); } catch (err) {
    $("#plan-table tbody").innerHTML = `<tr><td colspan="4" class="error">${esc(err.message)}</td></tr>`; return;
  }
  if (seq !== planSeq) return;
  const regolo = STATUS.backend === "regolo";
  $("#plan-table tbody").innerHTML = e.configs.map((c) => `<tr>
      <td><b>${esc(c.policy)}</b><small>${esc(MODES[c.mode])}</small></td>
      <td class="num">${fmtInt(e.n)}</td>
      <td class="num">${fmtInt(c.model_calls)}<small>${c.model_calls ? `${fmtInt(c.tokens_per_call)} tokens each${c.tokens_measured ? "" : ", estimated"}` : "none"}</small></td>
      <td class="num">${regolo ? fmtUsd(c.usd, 4) : "$0"}</td></tr>`).join("");
  $("#plan-table tfoot").innerHTML = `<tr><th>Total</th><td class="num">${fmtInt(e.n * e.configs.length)}</td><td class="num">${fmtInt(e.model_calls)}</td><td class="num"><b>${regolo ? `about ${fmtUsd(e.usd, 4)}` : "$0"}</b></td></tr>`;
  $("#plan-note").textContent = regolo
    ? `Charged to your Regolo account at ${esc(e.price.source)} prices: $${(e.price.usd_per_input_token * 1e6).toFixed(2)} per million input tokens, output free. The count of model calls is exact: routing was simulated offline on these payments. Tokens per call come from your latest run of each policy, or are estimated from its number of questions.`
    : "Offline demo: no call to Regolo, nothing is charged.";
  const checks = e.n * e.configs.length;
  $("#w-next").textContent = `Run all ${fmtInt(checks)} checks${regolo && e.usd ? `, about ${fmtUsd(e.usd, 4)}` : ""}`;
}

async function runPlan() {
  const body = planBody();
  showSection("results");
  await startBench(body);
}

/* ── run, live progress and results ────────────────────────────────── */
let benchShown = false;

async function loadRuns() {
  const runs = await api("/api/bench/runs");
  $("#runs").innerHTML = runs.length ? runs.map((r) =>
    `<li><button data-runid="${esc(r.id)}">${esc(fmtWhen(r.started_at))}</button>
      ${esc(r.dataset_title || r.dataset || "")}, ${r.n} payments: ${esc((r.policies || []).join(" vs ") || "")}${r.policies?.length ? ", " : ""}${esc(r.modes.map((m) => modeText(m)).join(" vs "))}, ${esc(r.backend)}</li>`).join("")
    : '<li class="empty">No runs yet. Set one up and start it.</li>';
  return runs;
}
$("#runs").addEventListener("click", async (e) => {
  const b = e.target.closest("button[data-runid]");
  if (b) { renderBench(await api(`/api/bench/runs/${b.dataset.runid}`)); $("#bench-result").scrollIntoView({ behavior: "smooth" }); }
});

async function startBench(body) {
  $("#bench-error").hidden = true;
  $("#w-next").disabled = true;
  benchShown = true;  // keep the previous-run view from replacing this one
  try {
    const { job } = await post("/api/bench", body);
    $("#bench-result").innerHTML = "";
    $("#live-events").innerHTML = "";
    $("#bench-live").hidden = false;
    $("#bench-live").scrollIntoView({ behavior: "smooth", block: "start" });
    await poll(job);
  } catch (err) { showBenchError(err.message); }
  finally { $("#w-next").disabled = false; }
}

function showBenchError(msg) { $("#bench-error").textContent = msg; $("#bench-error").hidden = false; }

// Say what is happening: which setting is running, which payment was just checked and how.
function liveEvent(ev) {
  const by = ev.decided_by === "model" ? `Clef-Flash in ${fmtMs(ev.model_ms)}${ev.tokens ? `, ${fmtInt(ev.tokens)} tokens` : ""}`
    : ev.decided_by === "rule" ? "a hard rule, no model call" : ev.decided_by === "prescore" ? "the quick score, no model call" : "the fail mode: no answer in time";
  return `<li>${badge(ev.decision)} <span>${esc(ev.description)}</span><small>${esc(typeTitle(ev.type))}, decided by ${esc(by)}; ${esc(ev.policy)}, ${esc(modeText(ev.mode))}</small></li>`;
}

async function poll(job) {
  for (;;) {
    const j = await api(`/api/bench/jobs/${job}`);
    const [pol, mode] = (j.mode || "").includes("|") ? j.mode.split("|") : [null, j.mode];
    $("#bench-live .progress-fill").style.width = `${j.total ? (100 * j.done) / j.total : 0}%`;
    $("#live-count").textContent = `${fmtInt(j.done)} of ${fmtInt(j.total)} checks`;
    $("#live-now").textContent = j.status !== "running" ? "" : !mode ? "Starting: loading the policies and the payments…"
      : `Now checking with ${pol ? `${pol}, ` : ""}${modeText(mode)}. Each payment: features from its history, hard rules, quick score${mode === "never" ? "" : ", then Clef-Flash if needed"}; every decision is written to the audit log.`;
    if (j.events?.length) $("#live-events").innerHTML = j.events.map(liveEvent).join("");
    if (j.status === "done") {
      $("#bench-live").hidden = true;
      LATEST = undefined;
      renderBench(j.report); loadRuns(); loadStatus();
      return;
    }
    if (j.status === "error") throw new Error(j.error);
    await new Promise((r) => setTimeout(r, 500));
  }
}

function answersHtml(modelAnswers) {
  let out = "";
  for (const [q, a] of Object.entries(modelAnswers || {})) {
    const probs = a.type === "noul" ? { true: a.noul, false: 1 - a.noul } : a.probabilities;
    const head = a.type === "choice" ? `${esc(q)}: ${esc(a.choice)} (confidence ${a.confidence.toFixed(2)})` : a.type === "score" ? `${esc(q)}: ${a.score.toFixed(2)} of ${Object.keys(probs).length - 1}` : esc(q);
    const legend = a.legend || {};
    out += `<div><b>${head}</b>${Object.entries(probs).map(([k, p]) =>
      `<div class="prob"><span>${esc(legend[k] || k)}</span><i style="width:${Math.max(1, p * 100)}%"></i><span>${(p * 100).toFixed(1)}%</span></div>`).join("")}</div>`;
  }
  return out ? `<b>Clef-Flash answers</b><div class="answers">${out}</div>` : "";
}

function detail(d) {
  const reasons = d.reasons.map((r) => `<li>${esc(r.source)}: ${esc(r.id)}${r.value != null ? ` = ${esc(r.value)}` : ""}${r.detail && r.source !== "model" ? ` <small>${esc(r.detail)}</small>` : ""}</li>`).join("");
  return `<b>Why</b><ul class="reasons">${reasons}</ul>${answersHtml(d.model_answers)}<small>Policy ${esc(d.policy)}${d.sca_exemption ? `, SCA exemption: ${esc(d.sca_exemption)}` : ""}. Recorded in the <a href="#audit">audit log</a>.</small>`;
}

/* ── generate a set with a Regolo chat model (sidebar → dialog) ────── */
let GEN = null, genTimer = null, genBusy = false, titleTouched = false;
const PRESETS = {
  mixed: ["Payment transactions (mixed)", "Every channel: mostly everyday payments, some unusual but genuine ones, and each kind of fraud.", MIX_DEFAULT],
  ecommerce: ["E-commerce payments", "Online card payments: stolen cards and card testing among genuine purchases.",
    { habitual: 50, unusual_legit: 15, card_testing: 15, stolen_card_online: 20 }],
  instant: ["Instant transfers and scams", "Bank transfers: account takeovers and fake bank operators among genuine transfers.",
    { habitual: 40, unusual_legit: 20, account_takeover: 20, impersonation_scam: 20 }],
  abroad: ["Cards abroad", "Travel and cloned cards: cash-outs at foreign ATMs next to genuine trips.",
    { habitual: 40, unusual_legit: 30, atm_cashout: 20, stolen_card_online: 10 }],
  custom: ["Custom mix", "Set the sliders yourself.", null],
};
const slug = (t) => t.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 30) || "set";

document.addEventListener("click", (e) => { const b = e.target.closest("[data-open-gen]"); if (b) openGenerator(b.dataset.source); });
$("#gen-close").addEventListener("click", () => $("#gen-dialog").close());
$$("[data-close-gen]").forEach((b) => b.addEventListener("click", () => $("#gen-dialog").close()));

// Two sources in one dialog: a Regolo model writes the set, or it is sampled from IBM TabFormer.
let genSource = "regolo";
function showSource(src) {
  genSource = src;
  $$(".source-switch button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.source === src)));
  $("#gen-panel").hidden = src !== "regolo";
  $("#tf-panel").hidden = src !== "tabformer";
  if (src === "tabformer") loadTabformer(); else if (GEN) estimateGeneration(); else loadGenerator();
}
$(".source-switch").addEventListener("click", (e) => { const b = e.target.closest("button[data-source]"); if (b) showSource(b.dataset.source); });

async function openGenerator(source) {
  const dlg = $("#gen-dialog");
  if (!genBusy) { $("#gen-result").hidden = true; $("#gen-progress").hidden = true; $("#gen-error").hidden = true; }
  if (!dlg.open) dlg.showModal();
  showSource(source || genSource);
}

/* ── IBM TabFormer: download once, then sample ─────────────────────── */
let TF = null, tfPolling = false;
const fmtBytes = (b) => (b >= 1e9 ? `${(b / 1e9).toFixed(2)} GB` : `${Math.round(b / 1e6)} MB`);

async function loadTabformer() {
  $("#tf-error").hidden = true;
  TF = await api("/api/tabformer");
  $("#tf-download").innerHTML = TF.csv
    ? `<p class="done-line">Downloaded: <code>data/tabformer/raw/card_transaction.v1.csv</code>, ${fmtBytes(TF.csv_bytes)}. It stays on this computer and is not committed.</p>`
    : `<p>About ${fmtBytes(TF.archive_bytes)} from IBM's public Box folder, ${fmtBytes(2.35e9)} once extracted. Only the CSV is kept, in <code>data/tabformer/raw/</code>.</p>
       <button type="button" id="tf-download-start">Download TabFormer, ${fmtBytes(TF.archive_bytes)}</button>`;
  $("#tf-sample-step").classList.toggle("locked", !TF.csv);
  $("#tf-start").disabled = !TF.csv || !!TF.job;
  $("#tf-estimate").innerHTML = TF.csv
    ? `<p class="cost-line"><b>Free</b>: nothing is sent to Regolo. About a minute: the 24.4 million rows are read twice.</p>`
    : `<p class="cost-line">Download the dataset first. The sample itself is free.</p>`;
  if (TF.job && !tfPolling) pollTabformer(TF.job);
}

$("#tf-panel").addEventListener("click", async (e) => {
  if (e.target.id !== "tf-download-start") return;
  e.target.disabled = true;
  try { const { job } = await post("/api/tabformer/download", {}); await pollTabformer(job); }
  catch (err) { $("#tf-error").textContent = err.message; $("#tf-error").hidden = false; e.target.disabled = false; }
});

async function pollTabformer(job) {
  tfPolling = true;
  try {
    for (;;) {
      const j = await api(`/api/tabformer/jobs/${job}`);
      const dl = j.stage === "downloading" || j.stage === "extracting";
      const bar = dl ? $("#tf-dl-progress") : $("#tf-progress");
      bar.hidden = false;
      $(".progress-fill", bar).style.width = `${j.total ? Math.min(100, (100 * j.done) / j.total) : 100}%`;
      $("span", bar).textContent = j.stage === "downloading" ? `Downloading: ${fmtBytes(j.done)} of ${fmtBytes(j.total || TF.archive_bytes)}`
        : j.stage === "extracting" ? "Extracting the CSV from the archive…"
        : j.stage === "selecting" ? `Pass 1 of 2: choosing the payments, ${(j.done / 1e6).toFixed(0)} of ${(j.total / 1e6).toFixed(1)} million rows`
        : `Pass 2 of 2: collecting each customer's history, ${(j.done / 1e6).toFixed(0)} of ${(j.total / 1e6).toFixed(1)} million rows`;
      if (j.status === "error") throw new Error(j.error);
      if (j.status === "done") {
        bar.hidden = true;
        if (j.result?.tabformer) await tabformerReady(j.result);
        await loadTabformer();
        return;
      }
      await new Promise((r) => setTimeout(r, 700));
    }
  } catch (err) { $("#tf-error").textContent = err.message; $("#tf-error").hidden = false; }
  finally { tfPolling = false; }
}

async function tabformerReady(m) {
  const t = m.tabformer;
  $("#tf-result").innerHTML = `<b>${esc(m.title)}</b> is ready: ${t.fraud} fraudulent and ${t.legit} genuine payments from ${esc(t.period)} (${fmtInt(t.period_transactions)} payments in the period, ${(100 * t.base_rate).toFixed(3)}% fraud). It is selected in step 3 of <a href="#test">Test</a>.`;
  $("#tf-result").hidden = false;
  tw.dataset = `generated:${m.name}`;
  await renderDatasets();
  if (!$("#view-test").hidden) showStep(tw.section === "setup" ? Math.max(tw.step, 3) : tw.step);
}

$("#tf-panel").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target.elements, title = f.title.value.trim();
  const stamp = new Date().toISOString().slice(5, 16).replace(/[-T:]/g, "");
  $("#tf-error").hidden = true; $("#tf-result").hidden = true; $("#tf-start").disabled = true;
  try {
    const { job } = await post("/api/tabformer/sample", { name: `${slug(title)}-${stamp}`, title, period: f.period.value,
      fraud: +f.fraud.value, legit: +f.legit.value, seed: +f.seed.value });
    await pollTabformer(job);
  } catch (err) { $("#tf-error").textContent = err.message; $("#tf-error").hidden = false; }
  finally { $("#tf-start").disabled = !TF?.csv; }
});
$("#tf-panel").addEventListener("click", (e) => { if (e.target.closest("#tf-result a")) $("#gen-dialog").close(); });

async function loadGenerator() {
  $("#gen-error").hidden = true;
  try {
    GEN = await api("/api/generate/models");
  } catch (err) {
    GEN = null;
    $("#gen-error").textContent = `${err.message}. The models and their prices come from your Regolo account: add a valid API key in the sidebar first.`;
    $("#gen-error").hidden = false;
    $("#gen-start").disabled = true;
    return;
  }
  const per = (v) => `$${(v * 1e6).toFixed(2)}`;
  $("#gen-model").innerHTML = GEN.models.map((m) => `<option value="${esc(m.id)}">${esc(m.id)}: ${per(m.input)} in, ${per(m.output)} out per million tokens</option>`).join("");
  $("#gen-model").value = GEN.models.some((m) => m.id === "mistral-small-4-119b") ? "mistral-small-4-119b" : GEN.models[0]?.id;
  $("#gen-presets").innerHTML = Object.entries(PRESETS).map(([k, [title, text]]) => `
    <label class="preset"><input type="radio" name="preset" value="${k}"${k === "mixed" ? " checked" : ""}><b>${esc(title)}</b><span>${esc(text)}</span></label>`).join("");
  const kinds = Object.entries(GEN.types);
  const group = (label, head) => `<h4 class="mix-head">${head}</h4>` + kinds.filter(([, t]) => t.label === label).map(([k, t]) => `
    <div class="mix-row">
      <div><b>${esc(t.title)}</b><small>${esc(t.brief.replaceAll("_", " "))}</small></div>
      <input type="range" min="0" max="100" step="5" name="mix-${k}" value="${MIX_DEFAULT[k] ?? 0}" aria-label="${esc(t.title)}, share">
      <output data-for="${k}"><b>0%</b><small></small></output>
    </div>`).join("");
  $("#gen-mix").innerHTML = group("legit", "Genuine payments") + group("fraud", "Fraud");
  applyPreset("mixed");
}

function applyPreset(key) {
  const [title, , mix] = PRESETS[key];
  if (mix) $$("#gen-mix input[type=range]").forEach((r) => (r.value = mix[r.name.slice(4)] ?? 0));
  const f = $("#gen-panel").elements;
  if (mix && !titleTouched) f.title.value = title;
  estimateGeneration();
}

function genBody() {
  const f = $("#gen-panel").elements;
  const mix = {};
  $$("#gen-mix input[type=range]").forEach((r) => (mix[r.name.slice(4)] = +r.value));
  const title = f.title.value.trim();
  const stamp = new Date().toISOString().slice(5, 16).replace(/[-T:]/g, "");
  return { title, name: `${slug(title)}-${stamp}`, model: f.model.value, n: +f.n.value, history: +f.history.value, vulnerable_pct: +f.vulnerable_pct.value, mix };
}

// Seconds per customer measured on earlier sets written by the same model, if any.
function measuredPace(model) {
  const paces = DATASETS.filter((d) => d.generation?.model === model && d.generation.seconds_per_item).map((d) => d.generation.seconds_per_item);
  return paces.length ? paces.reduce((a, b) => a + b, 0) / paces.length : null;
}
const fmtDuration = (s) => (s < 90 ? `${Math.max(5, Math.round(s / 5) * 5)} seconds` : `${Math.round(s / 60)} minutes`);

async function estimateGeneration() {
  if (!GEN) return;
  const body = genBody();
  const total = Object.values(body.mix).reduce((a, b) => a + b, 0);
  $$("#gen-mix output").forEach((o) => { $("b", o).textContent = `${total ? Math.round((100 * body.mix[o.dataset.for]) / total) : 0}%`; });
  const model = GEN.models.find((m) => m.id === body.model);
  try {
    const e = await post("/api/generate/estimate", { ...body, title: body.title || "x" });
    $$("#gen-mix output").forEach((o) => ($("small", o).textContent = plural(e.counts[o.dataset.for] || 0, "payment")));
    const fraud = Object.entries(e.counts).filter(([k]) => GEN.types[k].label === "fraud").reduce((a, [, v]) => a + v, 0);
    const pace = measuredPace(body.model);
    const secs = pace ? Math.ceil(body.n / 4) * pace : null;
    $("#gen-what").innerHTML = `<b>${esc(body.model)}</b> on Regolo will write <b>${plural(body.n, "fictional customer")}</b>, each with ${body.history} past payments and one new payment: <b>${body.n - fraud} genuine and ${fraud} fraud</b>. Nothing is checked yet: afterwards you run the set on the Test page and see how each type was handled.`;
    const per = (v) => `$${(v * 1e6).toFixed(2)}`;
    $("#gen-estimate").innerHTML = `<p class="cost-line"><b>About $${e.usd.toFixed(3)}</b> on your Regolo account${secs ? `, about ${fmtDuration(secs)}` : ""}.</p>
      <p class="fine">Price from Regolo for ${esc(body.model)}: ${per(model.input)} per million input tokens and ${per(model.output)} per million output. Expected about ${fmtInt(e.input_tokens)} input and ${fmtInt(e.output_tokens)} output tokens. ${pace ? `Time measured on your earlier sets with this model, four customers at a time.` : "Time not measured yet for this model: models that reason before answering are much slower and bill the reasoning as output."}</p>`;
    $("#gen-start").disabled = genBusy;
  } catch (err) {
    $("#gen-estimate").innerHTML = `<p class="error">${esc(err.message)}</p>`;
    $("#gen-start").disabled = true;
  }
}

$("#gen-panel").addEventListener("input", (e) => {
  if (e.target.name === "title") titleTouched = true;
  if (e.target.name === "preset") { applyPreset(e.target.value); return; }
  if (e.target.type === "range") { const c = $('#gen-presets input[value="custom"]'); if (c) c.checked = true; }
  clearTimeout(genTimer); genTimer = setTimeout(estimateGeneration, 300);
});

$("#gen-panel").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = genBody(), btn = $("#gen-start");
  $("#gen-error").hidden = true; $("#gen-result").hidden = true;
  btn.disabled = true; genBusy = true;
  try {
    const { job } = await post("/api/generate", body);
    $("#gen-progress").hidden = false;
    for (;;) {
      const j = await api(`/api/generate/jobs/${job}`);
      $("#gen-progress .progress-fill").style.width = `${j.total ? (100 * j.done) / j.total : 0}%`;
      $("#gen-progress span").textContent = `${j.done} of ${j.total} customers written by ${body.model}`;
      if (j.status === "error") throw new Error(j.error);
      if (j.status === "done") {
        const m = j.result;
        $("#gen-progress span").textContent = `Finished: ${m.generated} of ${m.requested} written`;
        $("#gen-result").innerHTML = `<b>${esc(m.title || m.name)}</b> is ready: ${m.generated} of ${m.requested} payments passed validation${m.repaired ? `, ${m.repaired} after one correction` : ""}${m.failed.length ? `, ${m.failed.length} discarded (${esc(m.failed[0].error.slice(0, 120))})` : ""}. It took ${m.wall_s} s and cost $${m.cost_usd.toFixed(4)}. It is selected in step 3 of <a href="#test">Test</a>.`;
        $("#gen-result").hidden = false;
        tw.dataset = `generated:${m.name}`;
        await renderDatasets();
        if (!$("#view-test").hidden) showStep(tw.section === "setup" ? Math.max(tw.step, 3) : tw.step);
        titleTouched = false;
        break;
      }
      await new Promise((r) => setTimeout(r, 800));
    }
  } catch (err) {
    $("#gen-error").textContent = err.message; $("#gen-error").hidden = false;
  } finally { genBusy = false; btn.disabled = false; }
});
$("#gen-dialog").addEventListener("click", (e) => { if (e.target.closest("#gen-result a")) $("#gen-dialog").close(); });

// The set a run used: saved with the run, or rebuilt from its rows for older runs.
function runSet(run) {
  if (run.dataset_meta) return run.dataset_meta;
  const types = {};
  cellsOf(run)[0].rows.forEach((r) => (types[r.type || r.label || "unlabelled"] = (types[r.type || r.label || "unlabelled"] || 0) + 1));
  return { title: run.dataset || "Payments", how: "", n: run.n, types, history: run.history_payments };
}

function renderBench(run) {
  const cs = cellsOf(run), set = runSet(run), price = run.price.usd_per_input_token || 0;
  const name = (c) => `<b>${esc(c.policy || "policy")}</b><span>${esc(MODES[c.mode])}</span>`;
  const plain = (c) => `${c.policy}, ${modeText(c.mode)}`;
  const ts = cs.map(tally);
  const hasFraud = ts[0].fraud > 0, hasLegit = ts[0].legit > 0;

  // The best value of each measure, marked only when settings differ on it.
  const best = (fn, better) => { const v = cs.map(fn); const b = v.reduce((x, y) => (better(y, x) ? y : x)); const wins = v.filter((x) => x === b).length; return v.map((x) => x === b && wins <= cs.length / 2); };
  const bStop = best((c, i = cs.indexOf(c)) => pct(ts[i].stopped, ts[i].fraud), (a, b) => a > b);
  const bBother = best((c, i = cs.indexOf(c)) => pct(ts[i].bothered, ts[i].legit), (a, b) => a < b);
  const bTime = best((c) => Math.round(waits(c).avg), (a, b) => a < b);
  const bCost = best((c) => c.cost_usd_total, (a, b) => a < b);
  const tag = (on) => (on ? '<em class="best">best</em>' : "");

  // One sentence for the reader in a hurry: most fraud stopped, then fewest interrupted, then cheapest.
  const order = cs.map((c, i) => i).sort((a, b) =>
    (hasFraud ? pct(ts[b].stopped, ts[b].fraud) - pct(ts[a].stopped, ts[a].fraud) : 0) ||
    pct(ts[a].bothered, ts[a].legit) - pct(ts[b].bothered, ts[b].legit) || cs[a].cost_usd_total - cs[b].cost_usd_total);
  const w = order[0], wt = ts[w];
  const what = hasFraud ? `stopped ${wt.stopped} of ${wt.fraud} fraudulent payments` : "approved the most genuine payments";
  // A run where the model often did not answer measures the fallback, not the policy: say so first.
  const failing = cs.filter((c) => c.decided_by.fail_mode / c.n > 0.05);
  const warning = failing.length ? `<p class="callout warn"><b>Not a valid measure for ${esc(failing.map(plain).join("; "))}.</b> The decision model did not answer in time for ${failing.map((c) => `${pct(c.decided_by.fail_mode, c.n)}%`).join(", ")} of the payments, so the channel fallback decided them. The shared Regolo API was slow or busy: run it again later, or with fewer parallel requests.</p>` : "";
  const verdict = warning + `<p class="verdict">${cs.length > 1 ? "Best trade-off on" : "Result on"} <b>${esc(set.title)}</b>: <b>${esc(plain(cs[w]))}</b>. It ${what}${hasLegit ? `${hasFraud ? " and" : ","} interrupted ${wt.bothered} of ${wt.legit} genuine customers` : ""}, in ${fmtMs(waits(cs[w]).avg)} per payment on average, for ${fmtUsd(cs[w].cost_usd_total, 4)}.</p>`;

  const cards = cs.map((c, i) => `
    <article class="score panel" data-cell="${i}" tabindex="0" role="button" aria-expanded="false" aria-controls="cell-detail">
      <header>${name(c)}<span class="more">Details</span></header>
      <dl>
        ${hasFraud ? `<div><dt>Fraud stopped ${tag(bStop[i])}</dt><dd><b>${ts[i].stopped} of ${ts[i].fraud}</b><small>${pct(ts[i].stopped, ts[i].fraud)}%</small></dd></div>` : ""}
        ${hasLegit ? `<div><dt>Genuine customers interrupted ${tag(bBother[i])}</dt><dd><b>${ts[i].bothered} of ${ts[i].legit}</b><small>${pct(ts[i].bothered, ts[i].legit)}%</small></dd></div>` : ""}
        <div><dt>Time per payment, average ${tag(bTime[i])}</dt><dd><b>${fmtMs(waits(c).avg)}</b><small>slowest ${fmtMs(waits(c).max)}</small></dd></div>
        <div><dt>Cost ${tag(bCost[i])}</dt><dd><b>${fmtUsd(c.cost_usd_total, 4)}</b><small>$${c.cost_usd_per_1k_payments.toFixed(2)} per 1,000 payments</small></dd></div>
      </dl>
    </article>`).join("");

  $("#bench-result").innerHTML = `
    ${verdict}
    <div class="scores">${cards}</div>
    <p class="fine">Stopped means not approved straight away: the customer was asked to confirm, or the payment was held or blocked. Time is the wait for one payment, measured from this computer over the shared Regolo API; payments settled by the rules take under a millisecond. Select a card for more detail and every payment it checked.</p>
    <div id="cell-detail"></div>
    <p>${run.id ? `<a href="#audit?group=${encodeURIComponent(run.id)}">See every decision of this run in the audit log</a>.` : ""}</p>`;
  SHOWN_RUN = run;
}

// A card opens its setting: who decided, model use, each type of payment, and on request
// every payment with its reasons. Older runs saved no reasons, so their rows do not open.
let SHOWN_RUN = null, SHOWN_CELL = null;
function renderCellDetail(i) {
  const run = SHOWN_RUN, cs = cellsOf(run), c = cs[i], set = runSet(run), price = run.price.usd_per_input_token || 0;
  $$("#bench-result .score").forEach((el) => { const on = +el.dataset.cell === i; el.classList.toggle("on", on); el.setAttribute("aria-expanded", String(on)); });
  SHOWN_CELL = i;
  const decided = Object.entries(c.decided_by).filter(([, v]) => v).map(([k, v]) => `${esc(LEVELS[k])} ${v}`).join(", ");
  const decisions = Object.entries(c.decisions).filter(([, v]) => v).map(([k, v]) => `<span class="count">${badge(k)} ${v}</span>`).join(" ");
  const fact = (k, v) => `<div><dt>${k}</dt><dd>${v}</dd></div>`;
  const types = Object.keys(set.types).map((t) => {
    const rows = c.rows.filter((r) => (r.type || r.label || "unlabelled") === t);
    if (!rows.length) return "";
    const fraud = rows[0].label === "fraud", stopped = rows.filter((r) => r.decision !== "approve").length;
    const good = fraud ? stopped === rows.length : stopped === 0;
    const cost = rows.reduce((a, r) => a + (r.tokens || 0) * price, 0);
    return `<tr><th scope="row">${esc(typeTitle(t))}<small>${fraud ? "fraud" : "genuine"}</small></th>
      <td class="num">${pct(rows.length, c.rows.length)}%<small>${rows.length}</small></td>
      <td><span class="${good ? "pass" : "fail"}">${stopped} of ${rows.length}</span> ${fraud ? "stopped" : "interrupted"}</td>
      <td class="num">${fmtMs(mean(rows.map((r) => r.total_ms)))}</td><td class="num">${fmtUsd(cost, 4)}</td></tr>`;
  }).join("");
  $("#cell-detail").innerHTML = `
    <section class="cell-detail panel">
      <header class="cell-head"><h4>${esc(c.policy)}, ${esc(modeText(c.mode))}</h4><button type="button" class="close" data-close-cell aria-label="Close the detail">✕</button></header>
      <div class="cell-set">
        <p><b>${esc(set.title)}</b>: ${plural(set.n, "payment")}, ${pct(c.rows.filter((r) => r.label === "fraud").length, c.rows.length)}% fraud, ${set.history} past payments each. ${esc(set.how ? `${set.how}.` : set.model ? `Written by ${set.model}.` : "")}
          <small>Run ${esc(fmtWhen(run.started_at))}, ${run.concurrency} parallel request${run.concurrency > 1 ? "s" : ""}, ${esc(run.backend === "regolo" ? "Clef-Flash on Regolo" : "offline demo")}.</small></p>
        ${composition(set).bar}
      </div>
      <dl class="cell-facts">
        ${fact("Who decided", decided)}
        ${fact("Decisions", decisions)}
        ${fact("Calls to the decision model", c.model_calls ? `${c.model_calls} of ${c.n} payments (${c.sent_to_model_pct}%), ${fmtInt(c.input_tokens_per_call)} tokens and ${fmtUsd(c.cost_usd_per_model_call)} each${c.model_unanswered ? `; ${c.model_unanswered} unanswered` : ""}` : "none")}
        ${c.model_calls ? fact("Decision model wait", `${fmtMs(c.latency_model_ms.p50)} typical, ${fmtMs(c.latency_model_ms.p95)} at the slow end`) : ""}
        ${fact("Whole set", `${c.wall_s} s, ${c.throughput_rps} payments per second`)}
        ${fact("Per million payments", `$${fmtInt(c.cost_usd_per_1k_payments * 1000)}`)}
        ${c.expected_pass ? fact("Analyst's expected decision", `met on ${c.expected_pass[0]} of ${c.expected_pass[1]}`) : ""}
        ${fact("Policy", `${esc(c.policy_ref || c.policy)}, reads ${c.history_payments ?? run.history_payments ?? "–"} past payments${c.questions ? `, asks ${esc(c.questions.join(", "))}` : ""}`)}
      </dl>
      ${c.decided_by.fail_mode ? `<p class="fine">${c.decided_by.fail_mode} payments were decided by the fail mode: the decision model did not answer within the policy's timeout, or was skipped after earlier timeouts.</p>` : ""}
      <h5 class="cell-sub">By type of payment</h5>
      <div class="table-scroll"><table class="grid by-type">
        <thead><tr><th>Type</th><th class="num">Share</th><th>Result</th><th class="num">Average time</th><th class="num">Cost</th></tr></thead>
        <tbody>${types}</tbody></table></div>
      <button type="button" class="show-payments" aria-expanded="false" aria-controls="pay-wrap">Show every payment (${c.rows.length})</button>
      <div id="pay-wrap" hidden>
        <p class="fine">Open a payment to see why it was decided that way and what the decision model answered.</p>
        <div class="table-scroll"><table class="grid clickable" id="detail-table">
          <thead><tr><th>Payment</th><th>Channel</th><th class="num">Amount</th><th>Expected</th><th>Result</th><th class="num">Time</th><th class="num">Tokens</th><th class="num">Cost</th></tr></thead>
          <tbody>${c.rows.map((r, k) => `
            <tr${r.reasons ? ` data-key="${k}"` : ""}>
              <td>${esc(r.description || r.name)}<small>${esc(typeTitle(r.type || r.label || "unlabelled"))}, ${esc(r.name)}</small></td>
              <td class="nowrap">${esc((r.channel || "–").replaceAll("_", " "))}</td>
              <td class="num">${r.amount != null ? `${r.amount.toLocaleString("en", { minimumFractionDigits: 2 })} ${esc(r.currency)}` : "–"}</td>
              <td class="nowrap">${r.expected?.length ? r.expected.map(badge).join(" ") : esc(r.label === "fraud" ? "fraud" : r.label === "legit" ? "genuine" : "–")}</td>
              <td>${badge(r.decision)}${r.pass == null ? "" : ` <span class="${r.pass ? "pass" : "fail"}">${r.pass ? "as expected" : "unexpected"}</span>`}<small>by ${esc(LEVELS[r.decided_by])}</small></td>
              <td class="num">${fmtMs(r.total_ms)}${r.model_ms != null ? `<small>model ${fmtMs(r.model_ms)}</small>` : ""}</td>
              <td class="num">${r.tokens ? fmtInt(r.tokens) : "–"}</td>
              <td class="num">${r.tokens ? fmtUsd(r.tokens * price) : "$0"}</td></tr>`).join("")}</tbody></table></div>
        ${run.dataset === "scenarios" ? `<h5 class="cell-sub">Outage and shadow demos</h5>
          <p class="fine">Three cases left out of the comparison because they change the conditions: the decision model unreachable on a card payment and on an instant transfer, and a policy in shadow mode. Run them one at a time with ${esc(c.policy)}.</p>
          <div class="table-scroll"><table class="grid" id="demo-table"><tbody></tbody></table></div>` : ""}
      </div>
    </section>`;
  if (run.dataset === "scenarios") renderDemos(c.policy);
  $("#cell-detail").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function closeCellDetail() {
  $("#cell-detail").innerHTML = ""; SHOWN_CELL = null;
  $$("#bench-result .score").forEach((el) => { el.classList.remove("on"); el.setAttribute("aria-expanded", "false"); });
}

$("#bench-result").addEventListener("click", (e) => {
  const card = e.target.closest(".score[data-cell]");
  if (card) { +card.dataset.cell === SHOWN_CELL ? closeCellDetail() : renderCellDetail(+card.dataset.cell); return; }
  if (e.target.closest("[data-close-cell]")) { closeCellDetail(); return; }
  const more = e.target.closest(".show-payments");
  if (more) {
    const wrap = $("#pay-wrap"), open = wrap.hidden;
    wrap.hidden = !open; more.setAttribute("aria-expanded", String(open));
    more.textContent = `${open ? "Hide" : "Show"} every payment (${cellsOf(SHOWN_RUN)[SHOWN_CELL].rows.length})`;
    return;
  }
  const tr = e.target.closest("#detail-table tr[data-key]");
  if (!tr) return;
  if (tr.nextElementSibling?.classList.contains("detail")) { tr.nextElementSibling.remove(); return; }
  const c = cellsOf(SHOWN_RUN)[SHOWN_CELL], r = c.rows[+tr.dataset.key];
  const d = { reasons: r.reasons, model_answers: r.model_answers, policy: c.policy_ref || c.policy };
  tr.insertAdjacentHTML("afterend", `<tr class="detail"><td colspan="8">${detail(d)}${r.history_available ? `<small> Read ${r.history_used} of ${r.history_available} past payments.</small>` : ""}</td></tr>`);
});
$("#bench-result").addEventListener("keydown", (e) => {
  const card = e.target.closest(".score[data-cell]");
  if (card && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); card.click(); }
});

// The demos of the hand-written set, scored one at a time through /api/score.
async function renderDemos(policy) {
  const demos = (await api("/api/scenarios?dataset=scenarios")).filter((s) => s.demo);
  $("#demo-table tbody").innerHTML = demos.map((s) => `<tr data-demo="${esc(s.name)}">
    <td>${esc(s.description)}<small>${esc(s.name)}</small></td><td class="nowrap">${s.expected.map(badge).join(" ")}</td>
    <td class="res">–</td><td><button data-run-demo="${esc(s.name)}" data-policy="${esc(policy)}">Run</button></td></tr>`).join("");
}
$("#bench-result").addEventListener("click", async (e) => {
  const b = e.target.closest("button[data-run-demo]");
  if (!b) return;
  const tr = b.closest("tr"), res = $(".res", tr);
  b.disabled = true; res.textContent = "Checking…";
  if (tr.nextElementSibling?.classList.contains("detail")) tr.nextElementSibling.remove();
  try {
    const r = await post("/api/score", { dataset: "scenarios", scenario: b.dataset.runDemo, policy: b.dataset.policy });
    const d = r.decision;
    res.innerHTML = `${badge(d.decision)} <span class="${r.pass ? "pass" : "fail"}">${r.pass ? "as expected" : "unexpected"}</span><small>by ${esc(LEVELS[d.decided_by])}${d.enforced ? "" : ", not enforced (shadow)"}, ${fmtMs(d.latency_ms.total)}</small>`;
    tr.insertAdjacentHTML("afterend", `<tr class="detail"><td colspan="4">${detail(d)}</td></tr>`);
  } catch (err) { res.innerHTML = `<span class="fail">${esc(err.message)}</span>`; }
  finally { b.disabled = false; }
});

/* ── policies: YAML editor ─────────────────────────────────────────── */
let editor = null, polName = null, polSaved = "", checkTimer = null, errorLine = null;

function makeEditor() {
  const ta = $("#pol-text");
  if (window.CodeMirror) {
    editor = CodeMirror.fromTextArea(ta, {
      mode: "yaml", lineNumbers: true, indentUnit: 2, tabSize: 2, indentWithTabs: false, lineWrapping: false,
      extraKeys: { Tab: (cm) => cm.execCommand("insertSoftTab"), "Cmd-S": savePolicy, "Ctrl-S": savePolicy },
    });
    editor.on("change", onEdit);
  } else {
    // CDN unavailable: a plain textarea still works, with two-space tabs.
    editor = { getValue: () => ta.value, setValue: (v) => (ta.value = v), refresh() {}, clearHistory() {} };
    ta.addEventListener("input", onEdit);
    ta.addEventListener("keydown", (e) => {
      if (e.key === "Tab") { e.preventDefault(); ta.setRangeText("  ", ta.selectionStart, ta.selectionEnd, "end"); onEdit(); }
    });
  }
}

const dirty = () => editor && editor.getValue() !== polSaved;
leaveGuard = () => !dirty() || location.hash.startsWith("#policies") || confirm("The policy has unsaved changes. Leave and lose them?");
window.addEventListener("beforeunload", (e) => { if (dirty()) e.preventDefault(); });

async function loadPolicies(params) {
  if (!editor) makeEditor();
  const want = params.get("name") || polName || "retail-eu";
  if (want !== polName) await openPolicy(want);
  else editor.refresh();
}

async function openPolicy(name) {
  if (dirty() && !confirm("Discard unsaved changes to this policy?")) { $("#pol-select").value = polName; return; }
  const p = await api(`/api/policies/${encodeURIComponent(name)}`);
  polName = name; polSaved = p.yaml;
  $("#pol-select").value = name;
  editor.setValue(p.yaml); editor.clearHistory();
  renderPolicyInfo(p);
  renderPolicySummary(p);
  setCheck("ok", `Valid: ${p.ref}.`);
  updateButtons();
}

function renderPolicyInfo(p) {
  const parent = p.extends ? ` It inherits <a href="#policies?name=${encodeURIComponent(p.extends.replace(/\.yaml$/, ""))}">${esc(p.extends)}</a> and holds only what changes; the summary below shows the result.` : "";
  $("#pol-info").innerHTML = `<code>policies/${esc(p.name)}.yaml</code>, ${esc(p.ref)}.${parent}`;
}

function renderPolicySummary(p) {
  const th = Object.entries(p.thresholds).map(([k, t]) => `<li>${esc(k)}: step-up ≥ ${t.step_up}, hold ≥ ${t.hold}, block ≥ ${t.block}</li>`).join("");
  $("#pol-summary").innerHTML = `
    <div><b>Hard rules, in order</b><ul>${p.hard_rules.map((r) => `<li>${badge(r.decision)} ${esc(r.reason)}</li>`).join("")}</ul></div>
    <div><b>Questions to Clef-Flash</b><ul>${Object.entries(p.questions).map(([k, q]) => `<li>${esc(k)} (${esc(q.type)}, weight ${q.weight})</li>`).join("")}</ul>
      <b>History</b><ul><li>Reads the last ${p.history_payments} payments before the one being checked</li></ul>
      <b>Thresholds</b><ul>${th}</ul>
      <b>Routing</b><ul><li>${esc(p.routing.mode)}; approve below ${p.routing.approve_if_prescore_below}, always ask the model from €${p.routing.always_call_model_if.amount_at_least} and for ${esc(p.routing.always_call_model_if.channels.join(", "))}</li></ul>
      <b>Model timeouts</b><ul>${Object.entries(p.timeouts_ms).map(([k, v]) => `<li>${esc(k.replaceAll("_", " "))}: ${v} ms</li>`).join("")}</ul></div>`;
}

function setCheck(kind, text) {
  $("#pol-check").className = `check ${kind}`;
  $("#pol-check").textContent = text;
}

function markErrorLine(msg) {
  if (!editor.addLineClass) return;
  if (errorLine != null) editor.removeLineClass(errorLine, "background", "line-error");
  errorLine = null;
  const m = /line (\d+)/.exec(msg || "");
  if (m) { errorLine = +m[1] - 1; editor.addLineClass(errorLine, "background", "line-error"); }
}

function updateButtons() {
  $("#pol-save").disabled = !dirty();
  $("#pol-revert").disabled = !dirty();
}

function onEdit() {
  updateButtons();
  clearTimeout(checkTimer);
  if (!dirty()) { markErrorLine(null); setCheck("ok", "No changes."); return; }
  setCheck("", "Checking…");
  checkTimer = setTimeout(checkPolicy, 600);
}

async function checkPolicy() {
  try {
    const r = await post("/api/policies/validate", { yaml: editor.getValue(), name: polName });
    markErrorLine(null);
    setCheck("ok", `Valid: ${r.ref}, ${r.rules} hard rules, reads the last ${r.history_payments} payments, questions ${r.questions.join(", ")}. Not saved yet.`);
    return true;
  } catch (e) {
    markErrorLine(e.message);
    setCheck("bad", e.message);
    return false;
  }
}

async function savePolicy() {
  if (!dirty()) return;
  clearTimeout(checkTimer);
  $("#pol-save").disabled = true;
  try {
    const r = await post(`/api/policies/${encodeURIComponent(polName)}`, { yaml: editor.getValue(), name: polName }, "PUT");
    polSaved = editor.getValue();
    const p = await api(`/api/policies/${encodeURIComponent(polName)}`);
    renderPolicyInfo(p); renderPolicySummary(p);
    setCheck("ok", `Saved ${p.ref}. The previous version is in ${r.backup}. Scenarios and benchmarks now use it.`);
    loadStatus();
  } catch (e) {
    markErrorLine(e.message);
    setCheck("bad", e.message);
  } finally { updateButtons(); }
}

$("#pol-select").addEventListener("change", (e) => (location.hash = `#policies?name=${encodeURIComponent(e.target.value)}`));
$("#pol-save").addEventListener("click", savePolicy);
$("#pol-revert").addEventListener("click", () => { editor.setValue(polSaved); markErrorLine(null); setCheck("ok", "Changes discarded."); updateButtons(); });
$("#pol-test").addEventListener("click", () => {
  if (dirty()) { setCheck("bad", "Save the policy first: scenarios run on the saved file."); return; }
  location.hash = `#test?step=1&policy=${encodeURIComponent(polName)}`;
});
$("#pol-new-toggle").addEventListener("click", (e) => {
  const form = $("#pol-new");
  form.hidden = !form.hidden;
  e.target.setAttribute("aria-expanded", String(!form.hidden));
  if (!form.hidden) { form.elements.base.value = polName || "retail-eu"; form.elements.name.focus(); }
});
$("#pol-new").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  $("#pol-new-error").hidden = true;
  try {
    const name = f.get("name").trim();
    await post("/api/policies", { name, base: f.get("base"), copy_content: f.get("how") === "copy" });
    e.target.reset(); e.target.hidden = true;
    $("#pol-new-toggle").setAttribute("aria-expanded", "false");
    await loadStatus();
    location.hash = `#policies?name=${encodeURIComponent(name)}`;
  } catch (err) { $("#pol-new-error").textContent = err.message; $("#pol-new-error").hidden = false; }
});

/* ── audit ─────────────────────────────────────────────────────────── */
let auditGroup = null;
const SOURCES = {
  "console-bench": "Benchmark",
  "cli-bench": "Benchmark from the command line",
  "console-scenario": "Scenario runs in the console",
  "console-request": "Custom requests in the console",
  "cli-score": "Scoring from the command line",
};

function groupLabel(g) {
  if (g.id === "before-run-tracking") return "<b>Recorded before run tracking</b><small>Earlier decisions, kept as they are: rewriting them would break the hash chain.</small>";
  const modes = g.modes.map((m) => modeText(m) || m).join(" vs ");
  if (g.id.startsWith("bench_")) return `<b>${esc(SOURCES[g.source] || "Benchmark")}</b><small>${esc(modes)}, run ${esc(g.id)}</small>`;
  if (g.id.startsWith("scenarios_")) return `<b>Run all scenarios</b><small>${esc(modes)}</small>`;
  return `<b>${esc(SOURCES[g.source] || g.source || "Other")}</b><small>One at a time, ${esc(modes)}</small>`;
}

async function loadAudit(params) {
  auditGroup = params ? params.get("group") : auditGroup;
  const a = await api(`/api/audit?limit=200${auditGroup ? `&group=${encodeURIComponent(auditGroup)}` : ""}`);
  $("#audit-verify").innerHTML = !a.verify ? "No decisions recorded yet. Run a scenario to create the first record."
    : a.verify.ok ? `<span class="pass">Hash chain intact</span> across ${fmtInt(a.verify.records)} records: no line was edited or removed.`
      : `<span class="fail">Hash chain broken: ${esc(a.verify.message)}</span>. A record was edited or removed.`;
  $("#audit-groups tbody").innerHTML = a.groups.length ? a.groups.map((g) => `
    <tr data-key="${esc(g.id)}"${g.id === auditGroup ? ' class="selected"' : ""}>
      <td class="nowrap">${esc(fmtWhen(g.first))}</td><td>${groupLabel(g)}</td><td class="num">${fmtInt(g.count)}</td>
      <td>${Object.entries(g.decisions).filter(([, v]) => v).map(([k, v]) => `<span class="count">${badge(k)} ${v}</span>`).join(" ")}</td>
      <td>${g.policies.map((x) => { const [ref, sha] = x.split(" "); return `${esc(ref)}<small>${esc(sha || "")}</small>`; }).join("")}</td></tr>`).join("")
    : '<tr><td colspan="5" class="empty">Nothing recorded yet.</td></tr>';

  const g = a.groups.find((x) => x.id === auditGroup);
  $("#audit-records-title").textContent = g ? `Decisions in this run (${fmtInt(a.matching)})` : `Latest decisions, all runs (${fmtInt(a.matching)})`;
  $("#audit-all").hidden = !g;
  $("#audit-table tbody").innerHTML = a.records.map((r) => `
    <tr data-key="${r.line}">
      <td class="nowrap">${esc(r.ts.slice(0, 10))}<small>${esc(r.ts.slice(11, 19))}</small></td>
      <td>${esc(r.scenario || r.transaction_id)}${r.scenario || r.mode ? `<small>${[r.scenario ? `payment ${esc(r.transaction_id)}` : "", r.mode ? esc(modeText(r.mode)) : "", esc(r.policy.split(" ")[0])].filter(Boolean).join(", ")}</small>` : ""}</td>
      <td>${badge(r.decision)}${r.enforced ? "" : '<span class="tag">shadow</span>'}</td><td class="nowrap">${esc(LEVELS[r.decided_by])}</td>
      <td class="num">${r.risk.toFixed(3)}</td><td class="num">${r.tokens ? fmtInt(r.tokens) : "–"}</td><td class="num">${fmtMs(r.total_ms)}</td>
      <td><code>${esc(r.record_hash)}</code></td></tr>`).join("") || '<tr><td colspan="8" class="empty">No decisions.</td></tr>';
}

$("#audit-groups").addEventListener("click", (e) => {
  const tr = e.target.closest("tr[data-key]");
  if (tr) location.hash = `#audit?group=${encodeURIComponent(tr.dataset.key)}`;
});
$("#audit-all").addEventListener("click", () => (location.hash = "#audit"));
$("#audit-refresh").addEventListener("click", () => { loadAudit(); loadStatus(); });
$("#audit-table").addEventListener("click", async (e) => {
  const tr = e.target.closest("tr[data-key]");
  if (!tr || e.target.closest("a")) return;
  if (tr.nextElementSibling?.classList.contains("detail")) { tr.nextElementSibling.remove(); return; }
  const r = await api(`/api/audit/records/${tr.dataset.key}`);
  const d = r.decision, ctx = r.context || {};
  const reasons = d.reasons.map((x) => `<li>${esc(x.source)}: ${esc(x.id)}${x.value != null ? ` = ${esc(x.value)}` : ""}</li>`).join("");
  tr.insertAdjacentHTML("afterend", `<tr class="detail"><td colspan="8">
    <p>${ctx.source ? `Started by: ${esc(SOURCES[ctx.source] || ctx.source)}${ctx.scenario ? `, scenario ${esc(ctx.scenario)}` : ""}${ctx.run_id ? `, run ${esc(ctx.run_id)}` : ""}.` : "Recorded before run tracking."} Policy ${esc(r.policy)}.${d.history_available ? ` Read ${d.history_used} of ${d.history_available} past payments.` : ""}</p>
    <b>Why</b><ul class="reasons">${reasons}</ul>${answersHtml(d.model_answers)}
    <div class="record-detail">
      <div><h4>Sent to Regolo (pseudonymised)</h4>${r.model_state ? `<pre class="json">${esc(JSON.stringify(r.model_state, null, 1))}</pre>` : "<p class=\"fine\">Nothing: decided without the model.</p>"}</div>
      <div><h4>Computed features</h4><pre class="json">${esc(JSON.stringify(r.features, null, 1))}</pre></div>
    </div>
    <small>Input hash ${esc(r.input_hash)}<br>Previous record ${esc(r.prev_hash)}<br>This record ${esc(r.record_hash)}</small>
  </td></tr>`);
});

/* ── boot ──────────────────────────────────────────────────────────── */
loadStatus().then(route);

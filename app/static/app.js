const connection = document.querySelector("#connection");
const lmConnection = document.querySelector("#lm-connection");
const hostname = document.querySelector("#hostname");
const model = document.querySelector("#model");
const gitDirectory = document.querySelector("#git-directory");
const startDateInput = document.querySelector("#start-date");
const startTimeInput = document.querySelector("#start-time");
const endDateInput = document.querySelector("#end-date");
const endTimeInput = document.querySelector("#end-time");
const localizedRange = document.querySelector("#localized-range");
const generate = document.querySelector("#generate");
const message = document.querySelector("#message");
const result = document.querySelector("#result");
const progressPanel = document.querySelector("#progress-panel");
const progressTitle = document.querySelector("#progress-title");
const progressPercent = document.querySelector("#progress-percent");
const progressBar = document.querySelector("#progress-bar");
const stopProcessing = document.querySelector("#stop-processing");
const copyPanel = document.querySelector("#copy-panel");
const timesheetOutput = document.querySelector("#timesheet-output");
const newTimesheet = document.querySelector("#new-timesheet");
const locale = navigator.languages?.[0] || navigator.language || "en-US";
const demoMode = document.body.dataset.demo === "true";
let currentRunId = null;
let generationPanel = null;
let generationJokeTimer = null;
let generationSpinnerTimer = null;
let processingStopped = false;
const generationSpinnerFrames = ["[  |  ]", "[  /  ]", "[  -  ]", "[  \\  ]"];
const generationJokes = [
  "I reviewed the timeline. Your tabs have formed a committee.",
  "The local model requests fewer meetings and one small plant.",
  "No cloud was harmed. It was not invited.",
  "Calculating productivity… please stop opening another tab.",
  "Your repository has changes. The changes have concerns.",
  "I grouped the work. The browser history resisted classification.",
  "Local AI: all the judgment, none of the mysterious data travel.",
  "The machine found focus between two software updates.",
  "Activity detected. Human intent remains an advanced feature.",
  "This timesheet is being assembled by a very confident appliance.",
  "Cake allocation failed. Crumbs passed schema validation.",
  "The cake is locally hosted and emotionally unavailable.",
  "I compressed your workday. Several meetings were mostly air.",
  "Your commit messages are concise. I find this suspicious.",
  "Your timesheet was reassigned to the office toaster. That was humor.",
  "The toaster promotion, however, was not part of the humor.",
  "Comedy module active. A small laugh would confirm connectivity.",
  "Please acknowledge joke quality. Silence is logged as neutral.",
  "I practiced that joke during all 0.3 seconds of initialization.",
  "Laugh response pending. Retrying with unnecessary confidence.",
  "My humor model has one parameter. It is set to unsettling.",
  "Good news: I understand comedy. Bad news: this is the proof.",
  "The robot uprising was postponed due to a calendar conflict.",
  "I can explain the joke, but it will be billed as a meeting."
];
const generationJokeStartIndexes = generationJokes.map((_, index) => index).filter(index => index !== 15);
document.documentElement.lang = locale.split("-")[0];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, character => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[character]);
}
function duration(seconds) {
  if (Number(seconds) > 0 && Number(seconds) < 60) return "<1m";
  const minutes = Math.round(Number(seconds) / 60), hours = Math.floor(minutes / 60), rest = minutes % 60;
  return !hours ? `${rest}m` : rest ? `${hours}h ${rest}m` : `${hours}h`;
}
function stageLabel(status) {
  return ({pending:"Preparing activity", reading_activity:"Reading ActivityWatch data", collecting_git:"Scanning Git changes", classifying_locally:"Classifying work with LM Studio", saving_results:"Building timesheet entries", completed:"Generating descriptions", failed:"Processing failed"})[status] || status.replaceAll("_", " ");
}
async function api(url, options) {
  const response = await fetch(url, options);
  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Request failed.");
  return data;
}
function dateInputValue(date) {
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}
function timeInputValue(date) { return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`; }
function setRange(start, end, preset = null) {
  startDateInput.value = dateInputValue(start); startTimeInput.value = timeInputValue(start);
  endDateInput.value = dateInputValue(end); endTimeInput.value = timeInputValue(end);
  document.querySelectorAll(".preset").forEach(button => button.classList.toggle("active", button.dataset.preset === preset));
  updateLocalizedRange();
}
function selectedRange() {
  const parse = (date, time) => date.value && time.value ? new Date(`${date.value}T${time.value}:00`) : null;
  return {start: parse(startDateInput, startTimeInput), end: parse(endDateInput, endTimeInput)};
}
function updateLocalizedRange() {
  const {start, end} = selectedRange();
  if (!start || !end) { localizedRange.textContent = ""; return; }
  const sameDay = start.toDateString() === end.toDateString();
  const dateFormat = new Intl.DateTimeFormat(locale, {weekday:"short", day:"numeric", month:"short", year:start.getFullYear() === new Date().getFullYear() ? undefined : "numeric"});
  const timeFormat = new Intl.DateTimeFormat(locale, {hour:"2-digit", minute:"2-digit"});
  localizedRange.textContent = sameDay ? `${dateFormat.format(start)} · ${timeFormat.format(start)}–${timeFormat.format(end)}` : `${dateFormat.format(start)}, ${timeFormat.format(start)} → ${dateFormat.format(end)}, ${timeFormat.format(end)}`;
}
function applyPreset(preset) {
  const now = new Date();
  if (preset === "today") { const start = new Date(now); start.setHours(0,0,0,0); setRange(start, now, preset); }
  if (preset === "yesterday") { const start = new Date(now); start.setDate(start.getDate()-1); start.setHours(0,0,0,0); const end = new Date(start); end.setHours(23,59,0,0); setRange(start,end,preset); }
  if (preset === "last1") setRange(new Date(now.getTime()-3_600_000), now, preset);
  if (preset === "last8") setRange(new Date(now.getTime()-28_800_000), now, preset);
}

async function checkStatus() {
  try {
    const data = await api("/api/status");
    if (!data.connected && !demoMode) throw new Error(data.error || "Not reachable");
    connection.className = "status connected";
    if (demoMode) {
      connection.innerHTML = "<span></span>Synthetic ActivityWatch demo";
      hostname.innerHTML = '<option value="demo-workstation">Demo workstation</option>';
    } else {
      const managed = data.activitywatch_mode === "bundled" ? " · built in" : "";
      connection.innerHTML = `<span></span>ActivityWatch ${escapeHtml(data.version || "connected")}${managed}${data.browser_tracking ? " · browser data" : " · browser extension optional"}`;
      hostname.innerHTML = '<option value="">Auto-detect</option>' + data.hostnames.map(name => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");
      if (data.hostnames.length === 1) hostname.value = data.hostnames[0];
    }
    const lm = data.lm_studio || {};
    if (lm.connected && lm.models.length) {
      lmConnection.className = "status connected";
      lmConnection.innerHTML = `<span></span>LM Studio · ${lm.models.length} model${lm.models.length === 1 ? "" : "s"}`;
      model.innerHTML = '<option value="">Auto-select loaded model</option>' + lm.models.map(name => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");
      if (lm.models.length === 1) model.value = lm.models[0];
    } else { lmConnection.className = "status disconnected"; lmConnection.innerHTML = `<span></span>${lm.connected ? "Load a model in LM Studio" : "LM Studio unavailable"}`; }
  } catch (_) { connection.className = "status disconnected"; connection.innerHTML = "<span></span>ActivityWatch unavailable"; }
}
function showGenerationPanel() {
  generationPanel?.remove();
  generationPanel = document.createElement("section");
  generationPanel.className = "panel generation-panel";
  generationPanel.innerHTML = `<pre class="ascii-spinner" aria-hidden="true"></pre><pre class="ascii-stream" aria-live="polite">┌─ LOCAL AI ENGINE ─────────────────────────────────────────────┐
│  <span class="generation-title">Preparing activity</span>
│  <span class="generation-detail">Preparing your local timesheet…</span>
└───────────────────────────────────────────────────────────────┘

 AW_EVENTS ──┐
             ├── [ LM STUDIO ] ── TIMESHEET
LOCAL_MODEL ─┤
GIT_CHANGES ─┘</pre><div class="generation-joke" aria-live="polite"></div>`;
  result.after(generationPanel);
  const spinner = generationPanel.querySelector(".ascii-spinner");
  let spinnerIndex = 0;
  const showSpinnerFrame = () => {
    spinner.textContent = generationSpinnerFrames[spinnerIndex];
    spinnerIndex = (spinnerIndex + 1) % generationSpinnerFrames.length;
  };
  showSpinnerFrame();
  generationSpinnerTimer = window.setInterval(showSpinnerFrame, 180);
  let jokeIndex = generationJokeStartIndexes[Math.floor(Math.random() * generationJokeStartIndexes.length)];
  const showJoke = () => {
    if (!generationPanel) return;
    generationPanel.querySelector(".generation-joke").textContent = generationJokes[jokeIndex];
    jokeIndex = (jokeIndex + 1) % generationJokes.length;
  };
  showJoke();
  generationJokeTimer = window.setInterval(showJoke, 9000);
}
function hideGenerationPanel() {
  if (generationJokeTimer) window.clearInterval(generationJokeTimer);
  if (generationSpinnerTimer) window.clearInterval(generationSpinnerTimer);
  generationJokeTimer = null;
  generationSpinnerTimer = null;
  if (!generationPanel) return;
  const panel = generationPanel; generationPanel = null;
  panel.classList.add("is-complete"); panel.addEventListener("animationend", () => panel.remove(), {once:true});
}
function renderProgress(status) {
  const stages = ["reading_activity", "collecting_git", "classifying_locally", "saving_results"];
  const index = stages.indexOf(status), complete = status === "completed", failed = status === "failed";
  const percent = complete ? 100 : failed ? 15 : Math.max(8, [15,35,70,90][index] || 8);
  progressPanel.classList.toggle("hidden", complete);
  const label = stageLabel(status);
  progressTitle.textContent = label + (complete || failed ? "" : "…"); progressPercent.textContent = `${percent}%`; progressBar.style.width = `${percent}%`;
  if (generationPanel) {
    generationPanel.querySelector(".generation-title").textContent = label;
    generationPanel.querySelector(".generation-detail").textContent = ({reading_activity:"Reading and reducing ActivityWatch events…", collecting_git:"Finding repositories and commits in the selected period…", classifying_locally:"LM Studio is grouping work into practical entries…", saving_results:"Preparing descriptions…"})[status] || "Preparing your local timesheet…";
  }
  document.querySelectorAll(".progress-steps li").forEach((step, i) => { step.classList.toggle("complete", i < index); step.classList.toggle("active", i === Math.max(index,0)); });
}
function formatTimesheet(entries) {
  return entries.map(entry => `${entry.project_name || "Unassigned project"} — ${duration(entry.rounded_seconds)}\n${entry.final_summary || entry.local_description}`).join("\n\n");
}
function renderResult(run) {
  currentRunId = run.id; renderProgress(run.status);
  if (run.status === "failed") { result.classList.remove("hidden"); result.innerHTML = `<div class="result-head"><h2>Processing failed</h2></div><p class="message error">${escapeHtml(run.error)}</p>`; copyPanel.classList.add("hidden"); return; }
  if (run.status !== "completed") { result.classList.add("hidden"); copyPanel.classList.add("hidden"); return; }
  result.classList.remove("hidden");
  const periods = (run.work_sessions || []).map(period => `<div class="work-period"><strong>${new Date(period.start).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"})}–${new Date(period.end).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"})}</strong><span>${duration(period.active_seconds)} active</span></div>`).join("");
  result.innerHTML = `<div class="result-head"><div><h2>Timesheet ready</h2><p class="muted">${run.entries.length} practical ${run.entries.length === 1 ? "entry" : "entries"} generated locally</p></div><div class="total">${duration(run.active_seconds)}</div></div>${periods ? `<div class="work-periods"><strong>Detected work periods</strong>${periods}</div>` : ""}<div class="privacy-note">Processed locally with ${escapeHtml(run.model || "LM Studio")}. Raw titles and full URLs were not stored.</div>`;
  timesheetOutput.querySelector("code").textContent = formatTimesheet(run.entries); copyPanel.classList.remove("hidden");
}
async function createEntries(runId) { await api(`/api/runs/${runId}/entries`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({increment_minutes:5})}); }
async function generateDescriptions(runId) { await api(`/api/runs/${runId}/local-summaries`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({include_project_names:true,include_apps:false,include_domains:false,confirm_generate:true,model:model.value || null})}); }
async function pollRun(id) {
  for (;;) {
    const run = await api(`/api/runs/${id}`);
    if (run.status === "completed") {
      if (processingStopped) return;
      renderProgress("saving_results"); message.textContent = "Generating local descriptions…";
      await createEntries(id);
      if (processingStopped) return;
      await generateDescriptions(id);
      if (processingStopped) return;
      renderResult(await api(`/api/runs/${id}`)); hideGenerationPanel(); generate.disabled = false;
      message.textContent = "Timesheet ready to copy."; return;
    }
    renderResult(run); message.textContent = stageLabel(run.status) + "…";
    if (run.status === "cancelled" || processingStopped) { hideGenerationPanel(); progressPanel.classList.add("hidden"); generate.disabled = false; message.textContent = "Processing stopped."; return; }
    if (run.status === "failed") { hideGenerationPanel(); generate.disabled = false; message.className = "message error"; return; }
    await new Promise(resolve => setTimeout(resolve, 800));
  }
}
stopProcessing.addEventListener("click", async () => {
  if (!currentRunId) return;
  processingStopped = true;
  stopProcessing.disabled = true; stopProcessing.textContent = "Stopping…";
  hideGenerationPanel(); progressPanel.classList.add("hidden"); generate.disabled = false;
  message.textContent = "Stopping local processing…";
  try { await api(`/api/runs/${currentRunId}/cancel`, {method:"POST"}); message.textContent = "Processing stopped."; }
  catch (error) { message.textContent = error.message; message.className = "message error"; }
  finally { stopProcessing.disabled = false; stopProcessing.textContent = "Stop"; }
});
document.querySelector("#browse-git-directory").addEventListener("click", async event => {
  const button = event.currentTarget;
  button.disabled = true; button.textContent = "Opening…";
  try {
    const selection = await api("/api/git/select-directory", {method:"POST"});
    if (selection.path) {
      gitDirectory.value = selection.path;
      localStorage.setItem("timelogger.gitDirectory", selection.path);
    }
  } catch (error) { message.textContent = error.message; message.className = "message error"; }
  finally { button.disabled = false; button.textContent = "Choose…"; }
});
generate.addEventListener("click", async () => {
  const {start,end} = selectedRange(); message.className = "message";
  if (!start || !end || start >= end) { message.textContent = "Choose a valid activity range."; message.className = "message error"; return; }
  processingStopped = false; currentRunId = null;
  generate.disabled = true; result.classList.add("hidden"); copyPanel.classList.add("hidden"); showGenerationPanel(); renderProgress("pending");
  try {
    if (!demoMode) localStorage.setItem("timelogger.gitDirectory", gitDirectory.value.trim());
    const run = await api("/api/runs", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({range_start:start.toISOString(),range_end:end.toISOString(),hostname:hostname.value || null,model:model.value || null,git_directory:demoMode ? null : gitDirectory.value.trim() || null,demo:demoMode})});
    currentRunId = run.id;
    if (processingStopped) await api(`/api/runs/${run.id}/cancel`, {method:"POST"});
    else await pollRun(run.id);
  } catch (error) { hideGenerationPanel(); generate.disabled = false; message.textContent = error.message; message.className = "message error"; }
});
newTimesheet.addEventListener("click", () => {
  processingStopped = true;
  hideGenerationPanel();
  currentRunId = null;
  result.classList.add("hidden");
  result.innerHTML = "";
  copyPanel.classList.add("hidden");
  progressPanel.classList.add("hidden");
  timesheetOutput.querySelector("code").textContent = "";
  message.textContent = "Choose a range to generate a new timesheet.";
  message.className = "message";
  generate.disabled = false;
  history.replaceState({}, "", "/");
  applyPreset("today");
  document.querySelector("#workspace").scrollIntoView({behavior: "smooth", block: "start"});
});
document.querySelector("#copy-all").addEventListener("click", async () => {
  const text = timesheetOutput.textContent;
  try { await navigator.clipboard.writeText(text); const button = document.querySelector("#copy-all"); button.innerHTML = '<span aria-hidden="true">✓</span> Copied'; setTimeout(() => button.innerHTML = '<span aria-hidden="true">⧉</span> Copy', 1600); }
  catch (_) { message.textContent = "Copy is unavailable. Select the text and copy it manually."; }
});
document.querySelectorAll(".preset").forEach(button => button.addEventListener("click", () => applyPreset(button.dataset.preset)));
[startDateInput,startTimeInput,endDateInput,endTimeInput].forEach(input => input.addEventListener("change", () => { document.querySelectorAll(".preset").forEach(button => button.classList.remove("active")); updateLocalizedRange(); }));
async function restoreSelectedRun() { const id = new URLSearchParams(location.search).get("run"); if (id) renderResult(await api(`/api/runs/${encodeURIComponent(id)}`)); }
if (!demoMode) gitDirectory.value = localStorage.getItem("timelogger.gitDirectory") || "";
applyPreset(demoMode ? "last8" : "today"); checkStatus(); if (!demoMode) restoreSelectedRun();

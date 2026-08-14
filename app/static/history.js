const historyList = document.querySelector("#history-list");
const locale = navigator.languages?.[0] || navigator.language || "en-US";
document.documentElement.lang = locale.split("-")[0];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, character => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[character]);
}
function duration(seconds) {
  const minutes = Math.round(Number(seconds) / 60), hours = Math.floor(minutes / 60), rest = minutes % 60;
  if (!hours) return `${rest}m`; return rest ? `${hours}h ${rest}m` : `${hours}h`;
}
function formatRange(run) {
  const start = new Date(run.range_start), end = new Date(run.range_end);
  const date = new Intl.DateTimeFormat(locale, {dateStyle: "medium"}).format(start);
  const time = new Intl.DateTimeFormat(locale, {hour: "2-digit", minute: "2-digit"});
  return `${date} · ${time.format(start)}–${time.format(end)}`;
}
async function loadHistory() {
  try {
    const response = await fetch("/api/runs?limit=100");
    const runs = await response.json();
    if (!runs.length) { historyList.innerHTML = '<p class="muted">No local runs yet.</p>'; return; }
    historyList.innerHTML = runs.map(run => `
      <a class="history-row" href="/?run=${encodeURIComponent(run.id)}">
        <span class="history-run-main"><strong>${escapeHtml(formatRange(run))}</strong></span>
        <span class="history-device">${escapeHtml(run.hostname || "ActivityWatch")}</span>
        <span class="history-duration">${run.status === "completed" ? duration(run.active_seconds) : "—"}</span>
        <span class="history-state ${escapeHtml(run.status)}">${escapeHtml(run.status)}</span>
      </a>`).join("");
  } catch (_) { historyList.innerHTML = '<p class="message error">Could not load local runs.</p>'; }
}
document.querySelector("#refresh-history").addEventListener("click", loadHistory);
loadHistory();

const REFRESH_INTERVAL_MS = 90_000;
const platformsEl = document.getElementById("platforms");
const updatedAtEl = document.getElementById("updated-at");
const refreshBtn = document.getElementById("refresh-btn");

const BOARD_ROWS = 6;

const platformSelect = document.getElementById("platform-select");
let selectedPlatformId = null;

let lastGoodView = null;

function render(view) {
  platformsEl.innerHTML = "";

  platformSelect.replaceChildren(...view.platforms.map((p) => {
    const opt = document.createElement("option");
    opt.value = p.stop_id;
    opt.textContent = p.directions.length
      ? `→ ${p.directions.slice(0, 2).join(", ")}`
      : `Słupek ${p.pole || p.stop_id}`;
    return opt;
  }));
  platformSelect.hidden = view.platforms.length < 2;
  const platform = view.platforms.find((p) => p.stop_id === selectedPlatformId) || view.platforms[0];
  if (platform) platformSelect.value = platform.stop_id;

  if (!platform || platform.upcoming.length === 0) {
    platformsEl.innerHTML = "<p>Brak danych o odjazdach.</p>";
    return;
  }

  for (const item of platform.upcoming.slice(0, BOARD_ROWS)) {
    const timeLabel = item.minutes <= 0 ? "TERAZ" : `${item.minutes}'`;

    const row = document.createElement("div");
    row.className = "board-row";
    row.innerHTML = `
      <span class="route">${item.route_short_name}</span>
      <span class="destination">${item.headsign}</span>
      <span class="time">${timeLabel}</span>
    `;
    platformsEl.appendChild(row);
  }
}

function setUpdatedAt(timestampSeconds, { stale = false } = {}) {
  const date = new Date(timestampSeconds * 1000);
  const label = date.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
  updatedAtEl.textContent = stale ? `${label} (nieaktualne)` : label;
  updatedAtEl.classList.toggle("stale", stale);
}

async function loadDepartures() {
  try {
    const response = await fetch(`/api/departures?stop=${encodeURIComponent(getSelectedStop())}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const view = await response.json();
    lastGoodView = view;
    render(view);
    setUpdatedAt(view.generated_at);
  } catch (err) {
    if (lastGoodView) {
      render(lastGoodView);
      setUpdatedAt(lastGoodView.generated_at, { stale: true });
    } else {
      platformsEl.innerHTML = "<p>Nie udało się pobrać danych.</p>";
    }
  }
}

refreshBtn.addEventListener("click", loadDepartures);
platformSelect.addEventListener("change", () => {
  selectedPlatformId = platformSelect.value;
  render(lastGoodView);
});
initStopPicker(() => {
  lastGoodView = null;
  selectedPlatformId = null;
  loadDepartures();
});
loadDepartures();
setInterval(loadDepartures, REFRESH_INTERVAL_MS);

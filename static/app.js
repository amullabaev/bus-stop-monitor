const REFRESH_INTERVAL_MS = 90_000;
const platformsEl = document.getElementById("platforms");
const updatedAtEl = document.getElementById("updated-at");
const refreshBtn = document.getElementById("refresh-btn");

let lastGoodView = null;

function formatMoreArrivals(arrivals) {
  return arrivals
    .slice(1)
    .map((a) => (a.minutes <= 0 ? "teraz" : `${a.minutes}'`))
    .join(", ");
}

function render(view) {
  platformsEl.innerHTML = "";

  if (view.platforms.length === 0) {
    platformsEl.innerHTML = "<p>Brak danych o odjazdach.</p>";
    return;
  }

  for (const platform of view.platforms) {
    const section = document.createElement("section");
    section.className = "platform";

    const heading = document.createElement("h2");
    heading.textContent = platform.pole
      ? `${platform.stop_name} · słupek ${platform.pole}`
      : platform.stop_name;
    if (platform.wheelchair) heading.append(" ♿");
    section.appendChild(heading);

    const meta = document.createElement("p");
    meta.className = "platform-meta";
    const towards = platform.directions.slice(0, 3).join(", ");
    meta.append(towards ? `Kierunek: ${towards}` : "");
    if (platform.lat != null && platform.lon != null) {
      const map = document.createElement("a");
      map.href = `https://www.openstreetmap.org/?mlat=${platform.lat}&mlon=${platform.lon}#map=18/${platform.lat}/${platform.lon}`;
      map.target = "_blank";
      map.rel = "noopener";
      map.textContent = "Mapa";
      if (towards) meta.append(" · ");
      meta.appendChild(map);
    }
    section.appendChild(meta);

    const list = document.createElement("div");
    list.className = "lines";

    for (const line of platform.lines) {
      const first = line.arrivals[0];
      const nextLabel = first.minutes <= 0 ? "TERAZ" : `${first.minutes}'`;
      const more = formatMoreArrivals(line.arrivals);

      const row = document.createElement("div");
      row.className = "line-row";
      row.innerHTML = `
        <div class="line-badge transport-${line.transport_type}">
          <span class="transport-label">${line.transport_type === "tram" ? "TRAM" : "BUS"}</span>
          <span class="line-number">${line.route_short_name}</span>
        </div>
        <div class="line-info">
          <div class="headsign">${line.headsign}</div>
          <div class="arrivals">
            <span class="next-arrival">${nextLabel}<span class="clock-time">${first.time}</span></span>
            ${more ? `<span class="more-arrivals">${more}</span>` : ""}
          </div>
        </div>
      `;
      list.appendChild(row);
    }

    section.appendChild(list);
    platformsEl.appendChild(section);
  }
}

function setUpdatedAt(timestampSeconds, { stale = false } = {}) {
  const date = new Date(timestampSeconds * 1000);
  const label = date.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
  updatedAtEl.textContent = stale ? `Ostatnie dane: ${label} (nieaktualne)` : `Odświeżono: ${label}`;
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
initStopPicker(() => {
  lastGoodView = null;
  loadDepartures();
});
loadDepartures();
setInterval(loadDepartures, REFRESH_INTERVAL_MS);

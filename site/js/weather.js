/* ── Config ────────────────────────────────────────────────────────── */
const API_URL    = '/api/';
const ADMIN_URL  = '/admin/';
const REFRESH_MS = 60000;      // 60-second auto-refresh
// NWS_ZONE is no longer hardcoded here — it's stored in AWS Secrets Manager
// (weather/api-keys) and returned by the API in each response as `nws_zone`.

// Human-readable names for each nodeId
const NODE_NAMES = {
  'garden-01':    'Garden',
  'outside-01':   "Parents' House",
  'outside-home': 'Outside (Home)',
};

/* ── Data fetching ─────────────────────────────────────────────────── */
async function fetchWeather() {
  const res = await fetch(API_URL);
  if (!res.ok) throw new Error(`Weather API returned ${res.status}`);
  return res.json();
}

async function fetchAdmin() {
  const res = await fetch(ADMIN_URL);
  if (!res.ok) throw new Error(`Admin API returned ${res.status}`);
  return res.json();
}

async function fetchAlerts(nwsZone) {
  try {
    const res  = await fetch(`https://api.weather.gov/alerts/active?zone=${nwsZone}`);
    const data = await res.json();
    return data.features || [];
  } catch {
    return [];   // Alerts are best-effort — never block a refresh
  }
}

/* ── Rendering ─────────────────────────────────────────────────────── */
function renderAlerts(alerts) {
  const container = document.getElementById('alerts-container');
  if (!alerts.length) {
    container.innerHTML = '';
    return;
  }
  container.innerHTML = alerts.map(a => `
    <div class="alert alert-warning d-flex align-items-start gap-2" role="alert">
      <span>⚠️</span>
      <div>
        <strong>${a.properties.event}</strong>
        — ${a.properties.headline}
      </div>
    </div>
  `).join('');
}

function fmt(val, decimals = 1) {
  return val !== null && val !== undefined ? val.toFixed(decimals) : '—';
}

function buildCard(node, statusInfo) {
  const name        = NODE_NAMES[node.nodeId] || node.nodeId;
  const l           = node.latest;
  const t           = node.today;
  const status      = statusInfo?.status   ?? 'unknown';
  const minutesAgo  = statusInfo?.minutesAgo;

  const statusClass = { ok: 'success', warning: 'warning', offline: 'danger' }[status] ?? 'secondary';
  const offlineClass = status === 'offline' ? 'node-offline' : '';

  const lastSeenText = minutesAgo === null || minutesAgo === undefined
    ? 'unknown'
    : minutesAgo === 0 ? 'just now' : `${minutesAgo}m ago`;

  // Only show CO2 row if node has a CO2 sensor (non-zero value or explicit reading)
  const co2Row = l.co2
    ? `<div class="reading-row">
         <span class="reading-label">CO₂</span>
         <span class="reading-value">${fmt(l.co2, 0)} <span class="unit">ppm</span></span>
       </div>`
    : '';

  // Only show lux row if node has a light sensor (value > 0)
  const luxRow = l.lux > 0
    ? `<div class="reading-row">
         <span class="reading-label">Light</span>
         <span class="reading-value">${fmt(l.lux, 0)} <span class="unit">lux</span></span>
       </div>`
    : '';

  const co2Range = t.maxCo2 !== null
    ? `<div class="range-row">
         <span class="range-label">CO₂</span>
         <span class="range-value">${fmt(t.minCo2, 0)} – ${fmt(t.maxCo2, 0)} ppm</span>
       </div>`
    : '';

  return `
    <div class="col-sm-12 col-md-6 col-lg-4 mb-4">
      <div class="card weather-card h-100 ${offlineClass}">

        <div class="card-header d-flex justify-content-between align-items-center">
          <span class="node-name">${name}</span>
          <span class="badge bg-${statusClass} status-badge">${status}</span>
        </div>

        <div class="card-body">
          <div class="temp-display">
            <span class="temp-f">${fmt(l.tempF)}°F</span>
            <span class="temp-c">${fmt(l.tempC)}°C</span>
          </div>

          <div class="readings">
            <div class="reading-row">
              <span class="reading-label">Humidity</span>
              <span class="reading-value">${fmt(l.humidity)}<span class="unit">%</span></span>
            </div>
            <div class="reading-row">
              <span class="reading-label">Pressure</span>
              <span class="reading-value">${fmt(l.pressure)} <span class="unit">hPa</span></span>
            </div>
            ${co2Row}
            ${luxRow}
          </div>

          <hr class="my-3">

          <div class="ranges">
            <div class="range-header">Today's range</div>
            <div class="range-row">
              <span class="range-label">Temp</span>
              <span class="range-value">${fmt(t.minTempF)}° – ${fmt(t.maxTempF)}°F</span>
            </div>
            <div class="range-row">
              <span class="range-label">Pressure</span>
              <span class="range-value">${fmt(t.minPressure)} – ${fmt(t.maxPressure)} hPa</span>
            </div>
            ${co2Range}
          </div>
        </div>

        <div class="card-footer">
          Updated ${lastSeenText} &nbsp;·&nbsp; ${l.eventTimestamp}
        </div>

      </div>
    </div>`;
}

function renderCards(weather, admin) {
  // Build a lookup map: nodeId → admin status
  const statusMap = {};
  admin.nodes.forEach(n => { statusMap[n.nodeId] = n; });

  const container = document.getElementById('node-cards');
  const loadingMsg = document.getElementById('loading-msg');
  if (loadingMsg) loadingMsg.remove();

  container.innerHTML = weather.nodes
    .map(node => buildCard(node, statusMap[node.nodeId]))
    .join('');
}

/* ── Refresh cycle ─────────────────────────────────────────────────── */
async function refresh() {
  try {
    const [weather, admin] = await Promise.all([
      fetchWeather(),
      fetchAdmin(),
    ]);
    const alerts = await fetchAlerts(weather.nws_zone || 'NYZ072');

    renderCards(weather, admin);
    renderAlerts(alerts);

    document.getElementById('as-of').textContent       = weather.asOf;
    document.getElementById('last-refresh').textContent = new Date().toLocaleTimeString();

    resetCountdown();
  } catch (err) {
    console.error('Refresh failed:', err);
  }
}

/* ── Countdown timer ───────────────────────────────────────────────── */
let countdownValue = REFRESH_MS / 1000;
let countdownTimer = null;

function resetCountdown() {
  countdownValue = REFRESH_MS / 1000;
  if (countdownTimer) clearInterval(countdownTimer);
  countdownTimer = setInterval(() => {
    countdownValue--;
    const el = document.getElementById('countdown');
    if (el) el.textContent = countdownValue;
    if (countdownValue <= 0) clearInterval(countdownTimer);
  }, 1000);
}

/* ── Boot ──────────────────────────────────────────────────────────── */
refresh();
setInterval(refresh, REFRESH_MS);

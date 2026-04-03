// --- State ---
let currentPage = "status";
let currentRange = "24h";
let healthRange = "24h";
let latencyPlot = null;
let packetLossPlot = null;
let speedPlot = null;
let statusInterval = null;
let errorHours = 24;

// --- Navigation ---
document.querySelectorAll("nav button").forEach((btn) => {
  btn.addEventListener("click", () => {
    switchPage(btn.dataset.page);
  });
});

function switchPage(page) {
  currentPage = page;
  document.querySelectorAll("nav button").forEach((b) => b.classList.remove("active"));
  document.querySelector(`nav button[data-page="${page}"]`).classList.add("active");
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  document.getElementById(`page-${page}`).classList.add("active");

  clearInterval(statusInterval);

  if (page === "status") {
    loadStatus();
    statusInterval = setInterval(loadStatus, 5000);
  } else if (page === "health") {
    loadHealth(healthRange);
  } else if (page === "timeline") {
    loadTimeline(currentRange);
  } else if (page === "outages") {
    loadOutages();
  } else if (page === "errors") {
    loadErrors(errorHours);
  } else if (page === "speedtests") {
    loadSpeedTests();
  }
}

// --- Range Selectors ---
document.querySelectorAll("#page-timeline .range-selector button").forEach((btn) => {
  btn.addEventListener("click", () => {
    currentRange = btn.dataset.range;
    document.querySelectorAll("#page-timeline .range-selector button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    loadTimeline(currentRange);
  });
});

document.querySelectorAll("#health-range-selector button").forEach((btn) => {
  btn.addEventListener("click", () => {
    healthRange = btn.dataset.range;
    document.querySelectorAll("#health-range-selector button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    loadHealth(healthRange);
  });
});

document.querySelectorAll("#error-range-selector button").forEach((btn) => {
  btn.addEventListener("click", () => {
    errorHours = parseInt(btn.dataset.hours, 10);
    document.querySelectorAll("#error-range-selector button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    loadErrors(errorHours);
  });
});

// --- Helpers ---
function formatMs(ms) {
  if (ms === null || ms === undefined) return "--";
  return ms < 1 ? "<1 ms" : ms.toFixed(1) + " ms";
}

function formatDuration(seconds) {
  if (seconds < 60) return Math.round(seconds) + "s";
  if (seconds < 3600) return Math.round(seconds / 60) + "m";
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return h + "h " + m + "m";
}

function formatTime(ts) {
  return new Date(ts * 1000).toLocaleString();
}

function statusClass(target) {
  if (!target.is_success) return "down";
  if (target.rtt_ms > 200) return "degraded";
  return "ok";
}

// --- Live Status ---
async function loadStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    renderStatus(data);
  } catch (e) {
    console.error("Failed to load status:", e);
  }
}

function renderStatus(data) {
  const targets = data.targets || [];
  const allUp = targets.length > 0 && targets.every((t) => t.is_success);
  const banner = document.getElementById("status-banner");

  if (targets.length === 0) {
    banner.className = "status-banner down";
    banner.textContent = "No monitoring data yet — waiting for first results...";
  } else if (allUp) {
    banner.className = "status-banner up";
    banner.textContent = "All targets reachable";
  } else {
    const downTargets = targets.filter((t) => !t.is_success);
    banner.className = "status-banner down";
    banner.textContent = downTargets.map((t) => t.target_name).join(", ") + " unreachable";
  }

  const cardsEl = document.getElementById("target-cards");
  cardsEl.innerHTML = targets
    .map((t) => {
      const cls = statusClass(t);
      return `
      <div class="card">
        <div class="label"><span class="status-dot ${cls}"></span>${escapeHtml(t.target_name)}</div>
        <div class="value">${formatMs(t.rtt_ms)}</div>
        <div class="meta">
          ${t.is_success ? `Jitter: ${formatMs(t.jitter_ms)}` : escapeHtml(t.error_message || "Unreachable")}
          <br>${escapeHtml(t.target)}
        </div>
      </div>`;
    })
    .join("");

  // DNS card
  const dns = data.dns;
  document.getElementById("dns-value").textContent = dns ? formatMs(dns.resolution_ms) : "--";
  document.getElementById("dns-meta").textContent = dns
    ? dns.is_success
      ? "Resolving google.com"
      : dns.error_message
    : "";

  // HTTP card
  const http = data.http;
  document.getElementById("http-value").textContent = http ? formatMs(http.response_ms) : "--";
  document.getElementById("http-meta").textContent = http
    ? http.is_success
      ? `Status ${http.status_code}`
      : http.error_message
    : "";
}

// --- Timeline ---
async function loadTimeline(range) {
  try {
    const [timelineRes, lossRes] = await Promise.all([
      fetch(`/api/timeline?range=${encodeURIComponent(range)}`),
      fetch(`/api/packet-loss?range=${encodeURIComponent(range)}`),
    ]);
    const timelineData = await timelineRes.json();
    const lossData = await lossRes.json();
    renderTimeline(timelineData);
    renderPacketLoss(lossData);
  } catch (e) {
    console.error("Failed to load timeline:", e);
  }
}

function renderTimeline(data) {
  const container = document.getElementById("latency-chart");
  container.innerHTML = "";

  if (!data.length) {
    container.innerHTML = '<p style="text-align:center;padding:2rem;color:var(--text-secondary)">No data for this time range</p>';
    return;
  }

  // Group by target
  const targets = {};
  data.forEach((row) => {
    const name = row.target_name || row.target;
    if (!targets[name]) targets[name] = [];
    targets[name].push(row);
  });

  const targetNames = Object.keys(targets);
  // Build aligned timestamp array from first target
  const firstTarget = targets[targetNames[0]];
  const timestamps = firstTarget.map((r) => r.timestamp);

  const series = [{}]; // first entry is for x-axis labels
  const dataArrays = [timestamps];
  const colors = ["#4c8bfa", "#34d399", "#fbbf24", "#f87171"];

  targetNames.forEach((name, i) => {
    series.push({
      label: name,
      stroke: colors[i % colors.length],
      width: 1.5,
    });
    // Use avg_rtt_ms for aggregated data, rtt_ms for raw
    const values = targets[name].map((r) => r.avg_rtt_ms ?? r.rtt_ms ?? null);
    dataArrays.push(values);
  });

  const opts = {
    width: container.clientWidth - 20,
    height: 300,
    series: series,
    axes: [
      {},
      {
        label: "Latency (ms)",
        stroke: "var(--text-secondary)",
        grid: { stroke: "rgba(255,255,255,0.05)" },
      },
    ],
    scales: { x: { time: true } },
    cursor: { show: true },
  };

  if (latencyPlot) latencyPlot.destroy();
  latencyPlot = new uPlot(opts, dataArrays, container);
}

// --- Outage Log ---
async function loadOutages() {
  try {
    const res = await fetch("/api/outages?hours=720");
    const data = await res.json();
    renderOutages(data);
  } catch (e) {
    console.error("Failed to load outages:", e);
  }
}

function renderOutages(outages) {
  const tbody = document.getElementById("outage-table-body");
  const emptyMsg = document.getElementById("outage-empty");

  if (!outages.length) {
    tbody.innerHTML = "";
    emptyMsg.style.display = "block";
    return;
  }

  emptyMsg.style.display = "none";
  tbody.innerHTML = outages
    .map(
      (o) => `
    <tr>
      <td>${formatTime(o.start_time)}</td>
      <td>${formatTime(o.end_time)}</td>
      <td>${formatDuration(o.duration_seconds)}</td>
      <td>${escapeHtml(o.target_name)}</td>
      <td>${escapeHtml(o.error_messages || "--")}</td>
    </tr>`
    )
    .join("");
}

// --- Speed Tests ---
async function loadSpeedTests() {
  try {
    const res = await fetch("/api/speedtests");
    const data = await res.json();
    renderSpeedTests(data);
  } catch (e) {
    console.error("Failed to load speed tests:", e);
  }
}

function renderSpeedTests(data) {
  // Table
  const tbody = document.getElementById("speed-table-body");
  tbody.innerHTML = data
    .map(
      (s) => `
    <tr>
      <td>${formatTime(s.timestamp)}</td>
      <td>${s.download_mbps.toFixed(1)} Mbps</td>
      <td>${s.upload_mbps.toFixed(1)} Mbps</td>
      <td>${s.ping_ms.toFixed(1)} ms</td>
      <td>${escapeHtml(s.server_name)}</td>
    </tr>`
    )
    .join("");

  // Chart
  const container = document.getElementById("speed-chart");
  container.innerHTML = "";

  if (!data.length) return;

  const reversed = [...data].reverse(); // oldest first
  const timestamps = reversed.map((s) => s.timestamp);
  const downloads = reversed.map((s) => s.download_mbps);
  const uploads = reversed.map((s) => s.upload_mbps);

  const opts = {
    width: container.clientWidth - 20,
    height: 250,
    series: [
      {},
      { label: "Download (Mbps)", stroke: "#4c8bfa", width: 2, fill: "rgba(76,139,250,0.1)" },
      { label: "Upload (Mbps)", stroke: "#34d399", width: 2, fill: "rgba(52,211,153,0.1)" },
    ],
    axes: [
      {},
      { label: "Speed (Mbps)", stroke: "var(--text-secondary)", grid: { stroke: "rgba(255,255,255,0.05)" } },
    ],
    scales: { x: { time: true } },
  };

  if (speedPlot) speedPlot.destroy();
  speedPlot = new uPlot(opts, [timestamps, downloads, uploads], container);
}

// --- Health ---
async function loadHealth(range) {
  try {
    const res = await fetch(`/api/health?range=${encodeURIComponent(range)}`);
    const data = await res.json();
    renderHealth(data);
  } catch (e) {
    console.error("Failed to load health:", e);
  }
}

function renderHealth(data) {
  const cardsEl = document.getElementById("health-cards");
  const targets = data.targets || [];

  if (!targets.length) {
    cardsEl.innerHTML = '<p style="text-align:center;padding:2rem;color:var(--text-secondary)">No data yet</p>';
    return;
  }

  cardsEl.innerHTML = targets
    .map((t) => {
      const uptimeClass =
        t.uptime_pct >= 99.9 ? "uptime-excellent" : t.uptime_pct >= 99 ? "uptime-good" : "uptime-poor";
      const pctHtml = t.percentiles_available && t.p50 !== null
        ? `<div class="percentiles">P50: ${formatMs(t.p50)} &nbsp;|&nbsp; P95: ${formatMs(t.p95)} &nbsp;|&nbsp; P99: ${formatMs(t.p99)}</div>`
        : t.percentiles_available
        ? ""
        : '<div class="percentiles">Percentiles available for 24h range</div>';
      return `
      <div class="card">
        <div class="label"><span class="status-dot ${t.uptime_pct >= 99.9 ? "ok" : t.uptime_pct >= 99 ? "degraded" : "down"}"></span>${escapeHtml(t.target_name)}</div>
        <div class="value ${uptimeClass}">${t.uptime_pct.toFixed(2)}%</div>
        <div class="meta">
          Streak: ${t.current_streak.toLocaleString()} pings
          &nbsp;·&nbsp; Outages: ${t.outage_count}
        </div>
        ${pctHtml}
      </div>`;
    })
    .join("");
}

// --- Packet Loss Chart ---
function renderPacketLoss(data) {
  const container = document.getElementById("packet-loss-chart");
  container.innerHTML = "";

  if (!data.length) {
    container.innerHTML = '<p style="text-align:center;padding:2rem;color:var(--text-secondary)">No data for this time range</p>';
    return;
  }

  const targets = {};
  data.forEach((row) => {
    const name = row.target_name || row.target;
    if (!targets[name]) targets[name] = [];
    targets[name].push(row);
  });

  const targetNames = Object.keys(targets);
  const firstTarget = targets[targetNames[0]];
  const timestamps = firstTarget.map((r) => r.timestamp);

  const series = [{}];
  const dataArrays = [timestamps];
  const colors = ["#f87171", "#fb923c", "#fbbf24", "#a78bfa"];

  targetNames.forEach((name, i) => {
    series.push({
      label: name,
      stroke: colors[i % colors.length],
      width: 1.5,
      fill: colors[i % colors.length] + "33",
    });
    const values = targets[name].map((r) => r.packet_loss_pct ?? null);
    dataArrays.push(values);
  });

  const opts = {
    width: container.clientWidth - 20,
    height: 250,
    series: series,
    axes: [
      {},
      {
        label: "Packet Loss (%)",
        stroke: "var(--text-secondary)",
        grid: { stroke: "rgba(255,255,255,0.05)" },
      },
    ],
    scales: { x: { time: true }, y: { min: 0 } },
    cursor: { show: true },
  };

  if (packetLossPlot) packetLossPlot.destroy();
  packetLossPlot = new uPlot(opts, dataArrays, container);
}

// --- Error Log ---
async function loadErrors(hours) {
  try {
    const res = await fetch(`/api/errors?hours=${hours}`);
    const data = await res.json();
    renderErrors(data);
  } catch (e) {
    console.error("Failed to load errors:", e);
  }
}

function renderErrors(errors) {
  const tbody = document.getElementById("error-table-body");
  const emptyMsg = document.getElementById("error-empty");

  if (!errors.length) {
    tbody.innerHTML = "";
    emptyMsg.style.display = "block";
    return;
  }

  emptyMsg.style.display = "none";
  tbody.innerHTML = errors
    .map(
      (e) => `
    <tr>
      <td>${formatTime(e.timestamp)}</td>
      <td><span class="error-type error-type-${escapeHtml(e.check_type)}">${escapeHtml(e.check_type.toUpperCase())}</span></td>
      <td>${escapeHtml(e.source)}</td>
      <td>${escapeHtml(e.error_message)}</td>
    </tr>`
    )
    .join("");
}

// --- XSS Protection ---
function escapeHtml(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// --- Init ---
loadStatus();
statusInterval = setInterval(loadStatus, 5000);

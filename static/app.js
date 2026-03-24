const state = {
  performanceChart: null,
  flowChart: null,
};

function formatPercent(value) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function formatMillions(value) {
  return `${(value / 1_000_000).toFixed(1)}M`;
}

function formatBillions(value) {
  return `${(value / 1_000_000_000).toFixed(2)}B`;
}

function setStatus(message, isError = false) {
  const box = document.getElementById("statusBox");
  box.textContent = message;
  box.classList.toggle("error", isError);
}

function daysAgo(days) {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date.toISOString().slice(0, 10);
}

function createMiniSparkline(values, color) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = values.map((value, index) => {
    const x = (index / (values.length - 1 || 1)) * 100;
    const y = 26 - ((value - min) / span) * 22;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  });

  return `
    <svg viewBox="0 0 100 30" class="sparkline" preserveAspectRatio="none" aria-hidden="true">
      <polyline fill="none" stroke="${color}" stroke-width="3" points="${points.join(" ")}" />
    </svg>
  `;
}

function renderSummaryCards(overview) {
  const total = overview.total_sectors;
  const items = [
    {
      label: "平均涨幅",
      value: formatPercent(overview.avg_change_pct),
      tone: overview.avg_change_pct >= 0 ? "positive" : "negative",
      detail: `${overview.positive_sector_count} / ${total} 个板块为正收益`,
    },
    {
      label: "最强上涨",
      value: `${overview.top_gainer.name} ${formatPercent(overview.top_gainer.change_pct)}`,
      tone: "positive",
      detail: overview.top_gainer.symbol,
    },
    {
      label: "最大流入",
      value: `${overview.strongest_inflow.name} ${formatMillions(overview.strongest_inflow.net_flow)}`,
      tone: overview.strongest_inflow.net_flow >= 0 ? "positive" : "negative",
      detail: `${overview.inflow_sector_count} / ${total} 个板块呈净流入代理`,
    },
    {
      label: "最大流出",
      value: `${overview.strongest_outflow.name} ${formatMillions(overview.strongest_outflow.net_flow)}`,
      tone: overview.strongest_outflow.net_flow >= 0 ? "positive" : "negative",
      detail: overview.strongest_outflow.symbol,
    },
  ];

  document.getElementById("summaryGrid").innerHTML = items
    .map(
      (item) => `
        <article class="summary-card ${item.tone}">
          <p>${item.label}</p>
          <strong>${item.value}</strong>
          <span>${item.detail}</span>
        </article>
      `,
    )
    .join("");
}

function renderTable(sectors) {
  document.getElementById("sectorTableBody").innerHTML = sectors
    .map(
      (item) => `
        <tr>
          <td><span class="ticker-pill" style="--ticker-color:${item.color}">${item.symbol}</span></td>
          <td>${item.name}</td>
          <td class="${item.change_pct >= 0 ? "positive-text" : "negative-text"}">${formatPercent(item.change_pct)}</td>
          <td class="${item.net_flow >= 0 ? "positive-text" : "negative-text"}">${formatMillions(item.net_flow)}</td>
          <td>${formatPercent(item.flow_intensity)}</td>
          <td>${formatBillions(item.avg_dollar_volume)}</td>
          <td>${item.last_volume_ratio.toFixed(2)}x</td>
          <td>${createMiniSparkline(item.sparkline, item.color)}</td>
        </tr>
      `,
    )
    .join("");
}

function destroyChart(instance) {
  if (instance) {
    instance.destroy();
  }
}

function renderCharts(sectors) {
  const perfCtx = document.getElementById("performanceChart");
  const flowCtx = document.getElementById("flowChart");
  const labels = sectors.map((item) => item.symbol);

  destroyChart(state.performanceChart);
  destroyChart(state.flowChart);

  state.performanceChart = new Chart(perfCtx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "涨幅 %",
        data: sectors.map((item) => item.change_pct),
        backgroundColor: sectors.map((item) => item.change_pct >= 0 ? "rgba(76, 201, 155, 0.75)" : "rgba(255, 107, 107, 0.75)"),
        borderRadius: 12,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: "#bfd3ff" } },
        y: { ticks: { color: "#bfd3ff", callback: (value) => `${value}%` }, grid: { color: "rgba(148, 163, 184, 0.18)" } },
      },
    },
  });

  state.flowChart = new Chart(flowCtx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "净流向代理",
        data: sectors.map((item) => item.net_flow / 1_000_000),
        backgroundColor: sectors.map((item) => item.net_flow >= 0 ? "rgba(255, 209, 102, 0.8)" : "rgba(108, 140, 255, 0.75)"),
        borderRadius: 12,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: "#bfd3ff" } },
        y: { ticks: { color: "#bfd3ff", callback: (value) => `${value}M` }, grid: { color: "rgba(148, 163, 184, 0.18)" } },
      },
    },
  });
}

async function fetchDashboard(start, end) {
  setStatus("正在刷新板块数据...");
  const response = await fetch(`/api/sectors?start=${start}&end=${end}`);
  const payload = await response.json();

  if (!response.ok) {
    throw new Error(payload.error || "数据拉取失败");
  }

  return payload;
}

async function loadDashboard(start, end) {
  try {
    const payload = await fetchDashboard(start, end);
    renderSummaryCards(payload.overview);
    renderCharts(payload.sectors);
    renderTable(payload.sectors);
    document.getElementById("rangeLabel").textContent = `${payload.meta.start} 至 ${payload.meta.end}`;
    document.getElementById("methodText").textContent = payload.meta.method;
    setStatus(`已更新 ${payload.meta.sector_count} 个板块，区间 ${payload.meta.days} 天。`);
  } catch (error) {
    setStatus(error.message, true);
  }
}

function syncPreset(days) {
  document.getElementById("startDate").value = daysAgo(days);
  document.getElementById("endDate").value = daysAgo(0);
}

document.addEventListener("DOMContentLoaded", () => {
  syncPreset(30);

  document.querySelectorAll(".preset-btn").forEach((button) => {
    button.addEventListener("click", () => {
      syncPreset(Number(button.dataset.range));
      loadDashboard(document.getElementById("startDate").value, document.getElementById("endDate").value);
    });
  });

  document.getElementById("filters").addEventListener("submit", (event) => {
    event.preventDefault();
    loadDashboard(document.getElementById("startDate").value, document.getElementById("endDate").value);
  });

  loadDashboard(document.getElementById("startDate").value, document.getElementById("endDate").value);
});

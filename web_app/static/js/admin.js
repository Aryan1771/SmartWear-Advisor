import { initAppShell, loadSidebarWeather, scrollToSection } from "/static/js/ui.js";

initAppShell();
void loadSidebarWeather();

const payloadNode = document.getElementById("admin-payload");
const payload = JSON.parse(payloadNode?.textContent || "{}");

const state = {
  history: payload.history || [],
  auditLogs: payload.audit_logs || [],
  users: payload.users || [],
  filteredHistory: payload.history || [],
  filteredAudit: payload.audit_logs || [],
};

const elements = {
  historySearch: document.getElementById("history-search"),
  auditSearch: document.getElementById("audit-search"),
  userSelect: document.getElementById("user-filter"),
  historyBody: document.getElementById("history-tbody"),
  auditBody: document.getElementById("audit-tbody"),
  userBody: document.getElementById("users-tbody"),
};

function formatCell(value) {
  return value == null || value === "" ? "-" : String(value);
}

function renderUsers() {
  elements.userBody.innerHTML = state.users
    .map(
      (user) => `
        <tr>
          <td>${formatCell(user.name)}</td>
          <td>${formatCell(user.registered_on)}</td>
          <td>${formatCell(user.notes)}</td>
          <td>${formatCell(user.detection_count)}</td>
        </tr>
      `
    )
    .join("");
}

function renderHistory(rows) {
  elements.historyBody.innerHTML = rows
    .map(
      (item) => `
        <tr>
          <td>${formatCell(item.name)}</td>
          <td>${formatCell(item.timestamp)}</td>
          <td>${formatCell(item.mask)}</td>
          <td>${formatCell(item.glasses)}</td>
          <td>${formatCell(item.city)}</td>
          <td>${formatCell(item.temp)}</td>
          <td>${formatCell(item.aqi_label)}</td>
          <td>${formatCell(item.uv_index)}</td>
        </tr>
      `
    )
    .join("");
}

function renderAudit(rows) {
  elements.auditBody.innerHTML = rows
    .map(
      (item) => `
        <tr>
          <td>${formatCell(item.timestamp)}</td>
          <td>${formatCell(item.event)}</td>
          <td>${formatCell(item.detail)}</td>
          <td>${formatCell(item.ip)}</td>
        </tr>
      `
    )
    .join("");
}

function applyHistoryFilters() {
  const query = elements.historySearch.value.trim().toLowerCase();
  const user = elements.userSelect.value;

  state.filteredHistory = state.history.filter((item) => {
    const matchesUser = !user || item.name === user;
    const haystack = [
      item.name,
      item.mask,
      item.glasses,
      item.city,
      item.timestamp,
      item.aqi_label,
    ]
      .join(" ")
      .toLowerCase();

    return matchesUser && (!query || haystack.includes(query));
  });

  renderHistory(state.filteredHistory);
}

function applyAuditFilters() {
  const query = elements.auditSearch.value.trim().toLowerCase();
  state.filteredAudit = state.auditLogs.filter((item) => {
    const haystack = [item.timestamp, item.event, item.detail, item.ip].join(" ").toLowerCase();
    return !query || haystack.includes(query);
  });
  renderAudit(state.filteredAudit);
}

let trendChart;

async function loadAnalytics() {
  const response = await fetch("/admin/analytics");
  if (!response.ok) {
    return;
  }
  const data = await response.json();
  if (trendChart) {
    trendChart.destroy();
  }

  trendChart = new Chart(document.getElementById("trendChart"), {
    type: "line",
    data: {
      labels: data.days,
      datasets: [
        {
          label: "Detections",
          data: data.detections,
          borderColor: "#5cd6ff",
          backgroundColor: "rgba(92, 214, 255, 0.16)",
          fill: true,
          tension: 0.35,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: {
            color: "#dce7f4",
          },
        },
      },
      scales: {
        x: {
          ticks: { color: "#9fb2c8" },
          grid: { color: "rgba(159, 178, 200, 0.15)" },
        },
        y: {
          ticks: { color: "#9fb2c8", precision: 0 },
          grid: { color: "rgba(159, 178, 200, 0.15)" },
        },
      },
    },
  });
}

function bindFilters() {
  elements.historySearch.addEventListener("input", applyHistoryFilters);
  elements.auditSearch.addEventListener("input", applyAuditFilters);
  elements.userSelect.addEventListener("change", applyHistoryFilters);
  document.querySelectorAll("[data-scroll-target]").forEach((button) => {
    button.addEventListener("click", () => scrollToSection(button.dataset.scrollTarget));
  });
}

renderUsers();
renderHistory(state.filteredHistory);
renderAudit(state.filteredAudit);
bindFilters();
void loadAnalytics();

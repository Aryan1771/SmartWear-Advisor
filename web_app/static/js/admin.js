import { initAppShell, loadSidebarWeather, scrollToSection, showToast } from "/static/js/ui.js";

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
  exportHistory: document.getElementById("export-history"),
  exportAudit: document.getElementById("export-audit"),
  deleteUserHistory: document.getElementById("delete-user-history"),
  deleteAllHistory: document.getElementById("delete-all-history"),
  deleteAllAudit: document.getElementById("delete-all-audit"),
  runRetention: document.getElementById("run-retention"),
};

function formatCell(value) {
  return value == null || value === "" ? "-" : String(value);
}

function formatMetric(value) {
  return value == null || value === "" || Number(value) === 0 ? "-" : String(value);
}

function emptyRow(colspan, message) {
  return `<tr><td class="table-empty" colspan="${colspan}">${message}</td></tr>`;
}

function renderUsers() {
  if (!state.users.length) {
    elements.userBody.innerHTML = emptyRow(4, "No registered users yet.");
    return;
  }

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
  if (!rows.length) {
    elements.historyBody.innerHTML = emptyRow(8, "No detection history matches the current filter.");
    return;
  }

  elements.historyBody.innerHTML = rows
    .map(
      (item) => `
        <tr>
          <td>${formatCell(item.name)}</td>
          <td>${formatCell(item.timestamp)}</td>
          <td>${formatCell(item.mask)}</td>
          <td>${formatCell(item.glasses)}</td>
          <td>${formatCell(item.city)}</td>
          <td>${formatMetric(item.temp)}</td>
          <td>${formatCell(item.aqi_label)}</td>
          <td>${formatMetric(item.uv_index)}</td>
        </tr>
      `
    )
    .join("");
}

function renderAudit(rows) {
  if (!rows.length) {
    elements.auditBody.innerHTML = emptyRow(4, "No audit entries match the current filter.");
    return;
  }

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
  updateActionAvailability();
}

function applyAuditFilters() {
  const query = elements.auditSearch.value.trim().toLowerCase();
  state.filteredAudit = state.auditLogs.filter((item) => {
    const haystack = [item.timestamp, item.event, item.detail, item.ip].join(" ").toLowerCase();
    return !query || haystack.includes(query);
  });
  renderAudit(state.filteredAudit);
}

function updateActionAvailability() {
  if (elements.deleteUserHistory) {
    elements.deleteUserHistory.disabled = !elements.userSelect?.value;
  }
}

function promptPassword(actionLabel) {
  const password = window.prompt(`Enter the admin password to ${actionLabel}.`);
  return password ? password.trim() : "";
}

async function downloadCsv(endpoint, body, fallbackName) {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error("export_failed");
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const header = response.headers.get("Content-Disposition") || "";
  const filenameMatch = header.match(/filename="([^"]+)"/);
  link.href = url;
  link.download = filenameMatch?.[1] || fallbackName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function postAdminAction(endpoint, body, successMessage) {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const payloadData = await response.json().catch(() => ({}));
  if (!response.ok || !payloadData.success) {
    const error = payloadData.error === "invalid_password"
      ? "Wrong admin password."
      : payloadData.message || "The action could not be completed.";
    throw new Error(error);
  }

  showToast(successMessage, "success");
  window.setTimeout(() => window.location.reload(), 700);
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

function bindActions() {
  elements.exportHistory?.addEventListener("click", async () => {
    try {
      await downloadCsv(
        "/admin/export/history",
        {
          rows: state.filteredHistory,
          query: elements.historySearch.value,
          user: elements.userSelect.value,
        },
        "smartwear-history.csv",
      );
      showToast("Detection history exported.", "success");
    } catch (error) {
      showToast("Could not export detection history.", "danger");
    }
  });

  elements.exportAudit?.addEventListener("click", async () => {
    try {
      await downloadCsv(
        "/admin/export/audit",
        {
          rows: state.filteredAudit,
          query: elements.auditSearch.value,
        },
        "smartwear-audit.csv",
      );
      showToast("Audit log exported.", "success");
    } catch (error) {
      showToast("Could not export audit log.", "danger");
    }
  });

  elements.deleteUserHistory?.addEventListener("click", async () => {
    const selectedUser = elements.userSelect.value;
    if (!selectedUser) {
      showToast("Select a user first to delete only that person's history.", "warning");
      return;
    }

    const password = promptPassword(`delete ${selectedUser}'s history`);
    if (!password) {
      return;
    }

    try {
      await postAdminAction(
        "/admin/history/delete-user",
        { name: selectedUser, password },
        `${selectedUser}'s detection history was cleared.`,
      );
    } catch (error) {
      showToast(error.message, "danger");
    }
  });

  elements.deleteAllHistory?.addEventListener("click", async () => {
    const password = promptPassword("clear all detection history");
    if (!password) {
      return;
    }

    try {
      await postAdminAction(
        "/admin/history/delete-all",
        { password },
        "All detection history was cleared.",
      );
    } catch (error) {
      showToast(error.message, "danger");
    }
  });

  elements.deleteAllAudit?.addEventListener("click", async () => {
    const password = promptPassword("clear the audit log");
    if (!password) {
      return;
    }

    try {
      await postAdminAction(
        "/admin/audit/delete-all",
        { password },
        "Audit log was cleared.",
      );
    } catch (error) {
      showToast(error.message, "danger");
    }
  });

  elements.runRetention?.addEventListener("click", async () => {
    const password = promptPassword("run the 30-day retention cleanup");
    if (!password) {
      return;
    }

    try {
      await postAdminAction(
        "/admin/retention/run",
        { password },
        "Retention cleanup finished.",
      );
    } catch (error) {
      showToast(error.message, "danger");
    }
  });
}

renderUsers();
renderHistory(state.filteredHistory);
renderAudit(state.filteredAudit);
updateActionAvailability();
bindFilters();
bindActions();
void loadAnalytics();

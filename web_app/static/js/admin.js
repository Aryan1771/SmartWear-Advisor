// ===================== SMARTWEAR ADMIN DASHBOARD =====================


// ===================== THEME =====================
function toggleTheme() {
  const html = document.documentElement;

  const next = html.getAttribute("data-theme") === "dark"
    ? "light"
    : "dark";

  html.setAttribute("data-theme", next);
}


// ===================== SIDEBAR =====================
function toggleSidebar() {
  const sidebar = document.getElementById("sidebar");
  if (sidebar) sidebar.classList.toggle("collapsed");
}


// ===================== SCROLL =====================
function scrollToSection(id) {
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({ behavior: "smooth" });
}


// ===================== SOCKET =====================
const socket = io({
  transports: ["websocket", "polling"]
});

socket.on("connect", () => {
  console.log("✅ Admin WebSocket connected");
});

socket.on("disconnect", () => {
  console.log("❌ Admin WebSocket disconnected");
});


// ===================== LIVE DETECTIONS =====================
socket.on("new_detection", (data) => {
  const tbody = document.getElementById("history-tbody");
  if (!tbody) return;

  const row = document.createElement("tr");

  row.innerHTML = `
    <td>${data.name}</td>
    <td>${data.time}</td>
    <td>${data.mask}</td>
    <td>${data.glasses}</td>
    <td>${data.city || "-"}</td>
    <td>${data.temp ? data.temp + "°C" : "-"}</td>
    <td>${data.aqi || "-"}</td>
    <td>${data.uv || "-"}</td>
  `;

  tbody.prepend(row);

  const det = document.getElementById("stat-detections");
  if (det) det.textContent = Number(det.textContent || 0) + 1;
});


// ===================== ANALYTICS =====================
let trendChart = null;
let maskChart = null;
let glassesChart = null;

async function loadAnalytics() {
  try {
    const res = await fetch("/admin/analytics");
    if (!res.ok) return;

    const data = await res.json();

    renderCharts(data);

    const maskEl = document.getElementById("stat-mask");
    if (maskEl && data.mask_rate !== undefined) {
      maskEl.textContent = data.mask_rate.toFixed(1) + "%";
    }

  } catch (err) {
    console.warn("Analytics error:", err);
  }
}


// ===================== CHART RENDER =====================
function renderCharts(data) {
  if (!data) return;

  if (trendChart) trendChart.destroy();
  trendChart = new Chart(document.getElementById("trendChart"), {
    type: "line",
    data: {
      labels: data.days || [],
      datasets: [{
        label: "Detections",
        data: data.detections || []
      }]
    }
  });

  if (maskChart) maskChart.destroy();
  maskChart = new Chart(document.getElementById("maskChart"), {
    type: "pie",
    data: {
      labels: Object.keys(data.mask || {}),
      datasets: [{
        data: Object.values(data.mask || {})
      }]
    }
  });

  if (glassesChart) glassesChart.destroy();
  glassesChart = new Chart(document.getElementById("glassesChart"), {
    type: "bar",
    data: {
      labels: Object.keys(data.glasses || {}),
      datasets: [{
        data: Object.values(data.glasses || {})
      }]
    }
  });
}


// ===================== HEARTBEAT =====================
setInterval(() => {
  fetch("/admin/heartbeat").catch(() => {});
}, 60000);


// ===================== INIT =====================
(function initAdmin() {
  loadAnalytics();
  setInterval(loadAnalytics, 30000);
  console.log("Admin dashboard initialized");
})();


// ===================== GLOBAL EXPORTS =====================
window.toggleTheme = toggleTheme;
window.toggleSidebar = toggleSidebar;
window.scrollToSection = scrollToSection;

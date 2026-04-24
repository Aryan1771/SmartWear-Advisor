// ===================== ADMIN DASHBOARD =====================

const socket = io({ transports: ["websocket"] });

// LIVE DETECTIONS
socket.on("new_detection", data => {
  const tbody = document.getElementById("history-tbody");
  if (!tbody) return;

  const row = document.createElement("tr");

  row.innerHTML = `
    <td>${data.name}</td>
    <td>${data.time}</td>
    <td>${data.mask}</td>
    <td>${data.glasses}</td>
    <td>${data.city || "-"}</td>
    <td>${data.temp || "-"}°C</td>
    <td>${data.aqi || "-"}</td>
    <td>${data.uv || "-"}</td>
  `;

  tbody.prepend(row);
});

// CHARTS
let trendChart;

async function loadAnalytics() {
  const res = await fetch("/admin/analytics");
  const data = await res.json();

  if (trendChart) trendChart.destroy();

  trendChart = new Chart(document.getElementById("trendChart"), {
    type: "line",
    data: {
      labels: data.days,
      datasets: [{ data: data.detections }]
    }
  });
}

loadAnalytics();
setInterval(loadAnalytics, 30000);

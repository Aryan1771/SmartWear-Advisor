// ===================== UI CORE =====================

// THEME
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);

  const icon = theme === "dark" ? "🌙" : "☀️";

  document.querySelectorAll(".theme-toggle").forEach(btn => {
    btn.textContent = icon;
  });
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "dark";
  const next = current === "dark" ? "light" : "dark";

  localStorage.setItem("theme", next);
  applyTheme(next);
}

(function initTheme() {
  applyTheme(localStorage.getItem("theme") || "dark");
})();


// SIDEBAR
function toggleSidebar() {
  const sidebar = document.getElementById("sidebar");
  if (sidebar) sidebar.classList.toggle("collapsed");
}


// SCROLL
function scrollToSection(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
}


// STATUS
function updateStatus(text) {
  const el = document.getElementById("status-text");
  if (el) el.textContent = text;
}

function updateLocation(text) {
  const el = document.getElementById("location-msg");
  if (el) el.textContent = text;
}

function installPWA() {
  if (!deferredPrompt) return;

  deferredPrompt.prompt();

  deferredPrompt.userChoice.then(() => {
    deferredPrompt = null;
  });
}
// EXPORT GLOBAL
window.toggleTheme = toggleTheme;
window.toggleSidebar = toggleSidebar;
window.scrollToSection = scrollToSection;
window.updateStatus = updateStatus;
window.updateLocation = updateLocation;
window.installPWA = installPWA;

// ===================== SMARTWEAR UI CORE =====================


// ===================== THEME =====================
function toggleTheme() {
  const html = document.documentElement;

  const current = html.getAttribute("data-theme") || "dark";
  const next = current === "dark" ? "light" : "dark";

  html.setAttribute("data-theme", next);
  localStorage.setItem("theme", next);
}

function initTheme() {
  const saved = localStorage.getItem("theme") || "dark";
  document.documentElement.setAttribute("data-theme", saved);
}


// ===================== SIDEBAR =====================
function toggleSidebar() {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;

  sidebar.classList.toggle("collapsed");
}


// ===================== STATUS HELPERS =====================
function updateStatus(text) {
  const el = document.getElementById("status-text");
  if (!el) return;

  el.textContent = text;
}

function updateLocation(text) {
  const el = document.getElementById("location-msg");
  if (!el) return;

  el.textContent = text;
}


// ===================== PWA INSTALL =====================
let deferredPrompt = null;

window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredPrompt = e;

  const btn = document.getElementById("pwa-install-btn");
  if (btn) btn.style.display = "block";
});

function installPWA() {
  if (!deferredPrompt) return;

  deferredPrompt.prompt();

  deferredPrompt.userChoice.then(() => {
    deferredPrompt = null;
  });
}


// ===================== INIT =====================
(function initUI() {
  initTheme();
  console.log("UI module loaded");
})();


// ===================== SAFE GLOBAL EXPORT =====================
// (so it works even without type="module")

window.toggleTheme = toggleTheme;
window.initTheme = initTheme;
window.toggleSidebar = toggleSidebar;
window.updateStatus = updateStatus;
window.updateLocation = updateLocation;
window.installPWA = installPWA;

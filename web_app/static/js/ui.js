// ui.js (UI ONLY)

// ── THEME ───────────────────────
export function toggleTheme() {
  const html = document.documentElement;
  const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
}

export function initTheme() {
  const saved = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
}

// ── SIDEBAR ─────────────────────
export function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('collapsed');
}

// ── STATUS HELPERS ──────────────
export function updateStatus(text) {
  document.getElementById('status-text').textContent = text;
}

export function updateLocation(text) {
  document.getElementById('location-msg').textContent = text;
}

// ── PWA ─────────────────────────
let deferredPrompt;

window.addEventListener('beforeinstallprompt', e => {
  e.preventDefault();
  deferredPrompt = e;
  document.getElementById('pwa-install-btn').style.display = 'block';
});

export function installPWA() {
  if (!deferredPrompt) return;
  deferredPrompt.prompt();
}

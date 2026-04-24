let deferredPrompt = null;

export function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const label = theme === "dark" ? "Light mode" : "Dark mode";
  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    button.setAttribute("aria-label", label);
    button.textContent = theme === "dark" ? "Light" : "Dark";
  });
}

export function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "dark";
  const next = current === "dark" ? "light" : "dark";
  localStorage.setItem("smartwear-theme", next);
  applyTheme(next);
}

export function initTheme() {
  applyTheme(localStorage.getItem("smartwear-theme") || "dark");
}

export function toggleSidebar(forceOpen) {
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebar-overlay");
  if (!sidebar) {
    return;
  }

  const willOpen = typeof forceOpen === "boolean"
    ? forceOpen
    : !sidebar.classList.contains("mobile-open");

  sidebar.classList.toggle("mobile-open", willOpen);
  overlay?.classList.toggle("visible", willOpen);
}

export function setStatus(message, tone = "neutral") {
  const node = document.getElementById("status-text");
  if (!node) {
    return;
  }
  node.textContent = message;
  node.dataset.tone = tone;
}

export function setLocationStatus(message) {
  const node = document.getElementById("location-msg");
  if (node) {
    node.textContent = message;
  }
}

export function showToast(message, tone = "info") {
  const root = document.getElementById("toast-root");
  if (!root) {
    return;
  }

  const toast = document.createElement("div");
  toast.className = `toast toast-${tone}`;
  toast.textContent = message;
  root.appendChild(toast);

  window.setTimeout(() => {
    toast.classList.add("toast-hide");
    window.setTimeout(() => toast.remove(), 220);
  }, 2800);
}

export function scrollToSection(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function bindChrome() {
  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    button.addEventListener("click", toggleTheme);
  });
  document.querySelectorAll("[data-sidebar-open]").forEach((button) => {
    button.addEventListener("click", () => toggleSidebar(true));
  });
  document.getElementById("sidebar-overlay")?.addEventListener("click", () => toggleSidebar(false));
}

export function bindInstallPrompt() {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;
    document.querySelectorAll("[data-install-button]").forEach((button) => {
      button.hidden = false;
    });
  });

  document.querySelectorAll("[data-install-button]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!deferredPrompt) {
        showToast("Install prompt is not available on this device yet.", "warning");
        return;
      }

      deferredPrompt.prompt();
      await deferredPrompt.userChoice;
      deferredPrompt = null;
      button.hidden = true;
    });
  });
}

export function initAppShell() {
  initTheme();
  bindChrome();
  bindInstallPrompt();
}

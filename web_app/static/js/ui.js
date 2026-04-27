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
  const shell = document.querySelector(".app-shell");
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebar-overlay");
  if (!sidebar) {
    return;
  }

  const desktop = window.innerWidth > 900;
  const willOpen = typeof forceOpen === "boolean"
    ? forceOpen
    : desktop
      ? sidebar.classList.contains("desktop-hidden")
      : !sidebar.classList.contains("mobile-open");

  if (desktop) {
    sidebar.classList.toggle("desktop-hidden", !willOpen);
    shell?.classList.toggle("sidebar-hidden", !willOpen);
    overlay?.classList.remove("visible");
    return;
  }

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
    button.addEventListener("click", () => toggleSidebar());
  });
  document.getElementById("sidebar-overlay")?.addEventListener("click", () => toggleSidebar(false));
  window.addEventListener("resize", () => {
    const shell = document.querySelector(".app-shell");
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("sidebar-overlay");
    if (!sidebar) {
      return;
    }

    if (window.innerWidth > 900) {
      sidebar.classList.remove("mobile-open");
      overlay?.classList.remove("visible");
    } else {
      sidebar.classList.remove("desktop-hidden");
      shell?.classList.remove("sidebar-hidden");
    }
  });
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

function requestBrowserLocation() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve(null);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          lat: Number(position.coords.latitude.toFixed(6)),
          lon: Number(position.coords.longitude.toFixed(6)),
        });
      },
      () => resolve(null),
      { enableHighAccuracy: false, timeout: 5000, maximumAge: 300000 }
    );
  });
}

export async function loadSidebarWeather(coords = null) {
  const widget = document.querySelector("[data-sidebar-weather]");
  if (!widget) {
    return;
  }

  const status = widget.querySelector("[data-weather-status]");
  const city = widget.querySelector("[data-weather-city]");
  const metaPrimary = widget.querySelector("[data-weather-meta-primary]");
  const metaSecondary = widget.querySelector("[data-weather-meta-secondary]");

  if (status) {
    status.textContent = "Loading local weather...";
  }

  const resolvedCoords = coords || await requestBrowserLocation();
  const params = new URLSearchParams();
  if (resolvedCoords?.lat != null && resolvedCoords?.lon != null) {
    params.set("lat", String(resolvedCoords.lat));
    params.set("lon", String(resolvedCoords.lon));
  }

  const url = `/api/sidebar-weather${params.toString() ? `?${params.toString()}` : ""}`;

  try {
    const response = await fetch(url);
    const payload = await response.json();
    if (!response.ok) {
      throw new Error("weather_failed");
    }

    if (city) {
      city.textContent = payload.city || "Unknown";
    }
    if (status) {
      status.textContent = `${payload.temp ?? "--"} °C | ${payload.condition || "Unavailable"}`;
    }
    if (metaPrimary) {
      metaPrimary.textContent = `Humidity ${payload.humidity ?? "--"}%`;
    }
    if (metaSecondary) {
      metaSecondary.textContent = `AQI ${payload.aqi_label || "--"} | UV ${payload.uv_index ?? "--"}`;
    }
  } catch (error) {
    if (status) {
      status.textContent = "Weather temporarily unavailable.";
    }
    if (metaPrimary) {
      metaPrimary.textContent = "Using safe fallback data when needed.";
    }
    if (metaSecondary) {
      metaSecondary.textContent = "";
    }
  }
}

import { initAppShell, setLocationStatus, setStatus, showToast } from "/static/js/ui.js";

const CAMERA = {
  width: 360,
  height: 480,
  jpegQuality: 0.62,
  registerQuality: 0.72,
  requestIntervalMs: 700,
  unknownStopMs: 2000,
  requestTimeoutMs: 1800,
};

const state = {
  mode: "idle",
  processing: false,
  stream: null,
  lastRequestAt: 0,
  recognitionStartedAt: 0,
  coords: { lat: null, lon: null },
  frameLoopId: null,
};

const elements = {
  video: document.getElementById("webcam"),
  overlay: document.getElementById("overlay"),
  hiddenCanvas: document.getElementById("hidden-canvas"),
  nameDisplay: document.getElementById("name-display"),
  accessoryDisplay: document.getElementById("acc-display"),
  cameraState: document.getElementById("camera-state"),
  registerButton: document.getElementById("register-button"),
  startButton: document.getElementById("start-button"),
  stopButton: document.getElementById("stop-button"),
};

const hiddenContext = elements.hiddenCanvas.getContext("2d", { willReadFrequently: true });
const overlayContext = elements.overlay.getContext("2d");

function updateActionState() {
  const canStart = state.mode === "idle" || state.mode === "stopped";
  elements.startButton.disabled = !canStart;
  elements.stopButton.disabled = state.mode === "idle" || state.mode === "stopped";
  elements.registerButton.disabled = !(state.mode === "live" || state.mode === "halted");
  elements.cameraState.textContent = {
    idle: "Idle",
    live: "Scanning",
    processing: "Processing",
    halted: "Paused",
    stopped: "Stopped",
    recognized: "Recognized",
  }[state.mode] || "Idle";
}

function setMode(mode) {
  state.mode = mode;
  updateActionState();
}

function updateIdentity(result = null) {
  if (!result) {
    elements.nameDisplay.textContent = "Awaiting face";
    elements.accessoryDisplay.textContent = "Mask and glasses detection will appear here.";
    return;
  }

  elements.nameDisplay.textContent = result.name || "Unknown";
  elements.accessoryDisplay.textContent = `Mask: ${result.mask || "Unknown"} | Glasses: ${result.glasses || "Unknown"}`;
}

function stopTracks() {
  if (state.stream) {
    state.stream.getTracks().forEach((track) => track.stop());
    state.stream = null;
  }
}

function stopLoop() {
  if (state.frameLoopId) {
    cancelAnimationFrame(state.frameLoopId);
    state.frameLoopId = null;
  }
}

function resetOverlay() {
  overlayContext.clearRect(0, 0, elements.overlay.width, elements.overlay.height);
}

function ensureCanvasSize() {
  const rect = elements.video.getBoundingClientRect();
  elements.overlay.width = rect.width;
  elements.overlay.height = rect.height;
}

function drawGuide(result) {
  ensureCanvasSize();
  resetOverlay();

  const width = elements.overlay.width;
  const height = elements.overlay.height;
  const centerX = width / 2;
  const centerY = height / 2;
  const radiusX = width * 0.26;
  const radiusY = height * 0.36;

  overlayContext.save();
  overlayContext.strokeStyle = result?.recognized ? "#78f0b1" : "rgba(137, 160, 183, 0.92)";
  overlayContext.lineWidth = result?.recognized ? 4 : 2;
  overlayContext.setLineDash(result?.recognized ? [] : [12, 8]);
  overlayContext.beginPath();
  overlayContext.ellipse(centerX, centerY, radiusX, radiusY, 0, 0, Math.PI * 2);
  overlayContext.stroke();
  overlayContext.restore();

  if (result?.box && Array.isArray(result.box) && result.box.length === 4) {
    const [top, right, bottom, left] = result.box;
    const scaleX = width / CAMERA.width;
    const scaleY = height / CAMERA.height;
    overlayContext.strokeStyle = result.recognized ? "#78f0b1" : "#f0c674";
    overlayContext.lineWidth = 2;
    overlayContext.strokeRect(left * scaleX, top * scaleY, (right - left) * scaleX, (bottom - top) * scaleY);
  }
}

function captureFrame(quality) {
  elements.hiddenCanvas.width = CAMERA.width;
  elements.hiddenCanvas.height = CAMERA.height;
  hiddenContext.drawImage(elements.video, 0, 0, CAMERA.width, CAMERA.height);
  return elements.hiddenCanvas.toDataURL("image/jpeg", quality);
}

async function fetchWithTimeout(url, options, timeoutMs) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    window.clearTimeout(timeoutId);
  }
}

async function detectFrame() {
  state.processing = true;
  setMode("processing");

  const image = captureFrame(CAMERA.jpegQuality);
  try {
    const response = await fetchWithTimeout(
      "/process_frame",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image }),
      },
      CAMERA.requestTimeoutMs
    );

    const payload = await response.json();
    const result = {
      recognized: Boolean(payload.recognized),
      name: payload.name || "Unknown",
      mask: payload.mask || "No Mask",
      glasses: payload.glasses || "No Glasses",
      box: payload.box || null,
      error: payload.error || null,
    };

    updateIdentity(result);
    drawGuide(result);

    if (result.recognized) {
      state.processing = false;
      setMode("recognized");
      setStatus("Face recognized. Loading weather-aware advice...", "success");
      stopTracks();
      stopLoop();
      redirectToDetail(result);
      return;
    }

    if (performance.now() - state.recognitionStartedAt >= CAMERA.unknownStopMs) {
      haltRecognition();
      showToast("Face not recognized in time. Press Register to enroll and resume.", "warning");
      return;
    }

    setMode("live");
    setStatus(result.error ? "Recognition server is slow. Retrying safely..." : "Searching for a registered face...", "neutral");
  } catch (error) {
    setMode("live");
    setStatus("Network slowed down. Camera is still ready.", "warning");
  } finally {
    state.processing = false;
  }
}

function haltRecognition() {
  stopLoop();
  stopTracks();
  state.processing = false;
  setMode("halted");
  setStatus("Recognition paused after 2 seconds. Press Register to continue.", "warning");
  drawGuide();
}

function redirectToDetail(result) {
  const params = new URLSearchParams({
    mask: result.mask,
    glasses: result.glasses,
  });

  if (state.coords.lat != null && state.coords.lon != null) {
    params.set("lat", String(state.coords.lat));
    params.set("lon", String(state.coords.lon));
  }

  window.setTimeout(() => {
    window.location.href = `/detail/${encodeURIComponent(result.name)}?${params.toString()}`;
  }, 450);
}

function loop(timestamp) {
  if (state.mode !== "live") {
    return;
  }

  if (!state.processing && timestamp - state.lastRequestAt >= CAMERA.requestIntervalMs) {
    state.lastRequestAt = timestamp;
    void detectFrame();
  }

  state.frameLoopId = requestAnimationFrame(loop);
}

async function requestLocation() {
  if (!navigator.geolocation) {
    setLocationStatus("Location unavailable on this device.");
    return;
  }

  navigator.geolocation.getCurrentPosition(
    (position) => {
      state.coords.lat = Number(position.coords.latitude.toFixed(6));
      state.coords.lon = Number(position.coords.longitude.toFixed(6));
      setLocationStatus("Location locked for weather-aware recommendations.");
    },
    () => {
      setLocationStatus("Location blocked. Weather details will use safe fallback data.");
    },
    { enableHighAccuracy: false, timeout: 5000, maximumAge: 300000 }
  );
}

async function startCamera() {
  try {
    state.stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: "user",
        width: { ideal: 720 },
        height: { ideal: 960 },
      },
      audio: false,
    });
    elements.video.srcObject = state.stream;
    await elements.video.play();
    state.recognitionStartedAt = performance.now();
    state.lastRequestAt = 0;
    setMode("live");
    setStatus("Camera live. Hold your face inside the guide.", "success");
    updateIdentity();
    drawGuide();
    stopLoop();
    state.frameLoopId = requestAnimationFrame(loop);
  } catch (error) {
    setMode("stopped");
    setStatus("Camera permission denied or unavailable.", "danger");
    showToast("Camera access is required to scan or register a face.", "danger");
  }
}

async function registerUser() {
  if (!(state.mode === "live" || state.mode === "halted")) {
    showToast("Start the camera before registering.", "warning");
    return;
  }

  if (!state.stream) {
    await startCamera();
    if (!state.stream) {
      return;
    }
  }

  const name = window.prompt("Enter a name for this face");
  if (!name) {
    return;
  }

  try {
    setStatus("Saving registration...", "neutral");
    const response = await fetchWithTimeout(
      "/register",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          image: captureFrame(CAMERA.registerQuality),
        }),
      },
      2200
    );
    const payload = await response.json();
    if (!response.ok || !payload.success) {
      throw new Error(payload.error || "register_failed");
    }

    showToast(`Registered ${payload.name} successfully.`, "success");
    setStatus("Registration complete. Press Start when you want to scan again.", "success");
    stopCamera();
  } catch (error) {
    setMode("halted");
    setStatus("Registration failed. You can retry safely.", "danger");
    showToast("Registration failed. Please try again with a clearer frame.", "danger");
  }
}

function stopCamera() {
  stopLoop();
  stopTracks();
  state.processing = false;
  setMode("stopped");
  setStatus("Camera stopped. Nothing is being sent to the server.", "neutral");
  drawGuide();
}

function bindEvents() {
  elements.startButton.addEventListener("click", startCamera);
  elements.stopButton.addEventListener("click", stopCamera);
  elements.registerButton.addEventListener("click", () => {
    void registerUser();
  });

  window.addEventListener("resize", drawGuide);
}

initAppShell();
requestLocation();
bindEvents();
updateIdentity();
drawGuide();
updateActionState();

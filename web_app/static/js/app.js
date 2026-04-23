// ===================== SMARTWEAR CORE APP =====================

const video = document.getElementById('webcam');
const overlay = document.getElementById('overlay');
const hiddenCanvas = document.getElementById('hidden-canvas');

const ctx = hiddenCanvas.getContext('2d');
const octx = overlay.getContext('2d');

const nameDisplay = document.getElementById('name-display');
const accDisplay = document.getElementById('acc-display');

let active = false;
let isProcessing = false;
let streamRef = null;

let userCoords = { lat: null, lon: null };

const INFERENCE_THROTTLE = 1200;


// ===================== GPS =====================
function initGPS() {
  if (!navigator.geolocation) return;

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      userCoords = {
        lat: pos.coords.latitude,
        lon: pos.coords.longitude
      };
      updateStatus("GPS OK");
    },
    () => updateStatus("GPS Failed")
  );
}


// ===================== CAMERA =====================
async function startApp() {
  try {
    streamRef = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user" }
    });

    video.srcObject = streamRef;
    active = true;

    updateStatus("Live");
    processLoop();

  } catch (err) {
    console.error(err);
    alert("Camera permission denied or unavailable");
  }
}

function stopApp() {
  active = false;

  if (streamRef) {
    streamRef.getTracks().forEach(track => track.stop());
    streamRef = null;
  }

  updateStatus("Stopped");
}


// ===================== MAIN LOOP =====================
async function processLoop() {
  if (!active) return;

  if (isProcessing) {
    requestAnimationFrame(processLoop);
    return;
  }

  isProcessing = true;

  try {
    hiddenCanvas.width = 320;
    hiddenCanvas.height = 240;

    ctx.drawImage(video, 0, 0, 320, 240);

    const frame = hiddenCanvas.toDataURL("image/jpeg", 0.6);

    const res = await fetch("/process_remote_frame", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: frame })
    });

    const data = await res.json();

    drawOverlay(data);

    if (data?.name && data.name !== "Unknown") {
      handleSuccess(data);
      return;
    }

  } catch (err) {
    console.warn("Inference error:", err);
  }

  setTimeout(() => {
    isProcessing = false;
    requestAnimationFrame(processLoop);
  }, INFERENCE_THROTTLE);
}


// ===================== OVERLAY =====================
function drawOverlay(data) {
  if (!overlay || !octx) return;

  octx.clearRect(0, 0, overlay.width, overlay.height);

  if (!data?.box) return;

  const [t, r, b, l] = data.box;
  const known = data.name !== "Unknown";

  const color = known ? "#22c55e" : "#eab308";

  octx.strokeStyle = color;
  octx.lineWidth = 2;
  octx.strokeRect(l, t, r - l, b - t);

  octx.fillStyle = color;
  octx.font = "bold 14px sans-serif";
  octx.fillText(known ? data.name : "Unknown", l, t - 5);

  if (nameDisplay) {
    nameDisplay.textContent = data.name;
    nameDisplay.style.color = color;
  }

  if (accDisplay) {
    accDisplay.textContent =
      `Mask: ${data.mask} • Glasses: ${data.glasses}`;
  }
}


// ===================== SUCCESS FLOW =====================
function handleSuccess(data) {
  const cityEl = document.getElementById("city");

  const city = cityEl ? cityEl.value : "Unknown";

  const url =
    `/detail/${encodeURIComponent(data.name)}` +
    `?lat=${userCoords.lat || ""}` +
    `&lon=${userCoords.lon || ""}` +
    `&city=${encodeURIComponent(city)}` +
    `&mask=${encodeURIComponent(data.mask || "")}` +
    `&glasses=${encodeURIComponent(data.glasses || "")}`;

  setTimeout(() => {
    active = false;
    window.location.href = url;
  }, 500);
}


// ===================== REGISTER =====================
async function registerUser() {
  const name = prompt("Enter name");
  if (!name) return;

  try {
    hiddenCanvas.width = 320;
    hiddenCanvas.height = 240;

    ctx.drawImage(video, 0, 0, 320, 240);

    const frame = hiddenCanvas.toDataURL("image/jpeg", 0.7);

    const res = await fetch("/register_remote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, image: frame })
    });

    const data = await res.json();

    alert(data.success ? "Registered successfully" : "Registration failed");

  } catch (err) {
    console.error(err);
    alert("Server error");
  }
}


// ===================== STATUS =====================
function updateStatus(msg) {
  console.log("[SmartWear]", msg);
}


// ===================== INIT =====================
(function init() {
  initGPS();
  console.log("SmartWear App Loaded");
})();


// ===================== GLOBAL EXPORTS (safe) =====================
window.startApp = startApp;
window.stopApp = stopApp;
window.registerUser = registerUser;

// ===================== SMARTWEAR APP =====================

const video = document.getElementById("webcam");
const canvas = document.getElementById("hidden-canvas");
const overlay = document.getElementById("overlay");

const ctx = canvas.getContext("2d");
const octx = overlay.getContext("2d");

let running = false;
let busy = false;
let stream = null;

let coords = { lat: null, lon: null };

const INTERVAL = 1500; // 🔥 DO NOT REDUCE


// ===================== GPS =====================
navigator.geolocation.getCurrentPosition(
  pos => {
    coords.lat = pos.coords.latitude;
    coords.lon = pos.coords.longitude;
    updateLocation("GPS OK");
  },
  () => updateLocation("GPS Failed")
);


// ===================== START =====================
async function startApp() {
  stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: "user" }
  });

  video.srcObject = stream;
  running = true;

  updateStatus("Live");

  loop();
}


// ===================== STOP =====================
function stopApp() {
  running = false;

  if (stream) {
    stream.getTracks().forEach(t => t.stop());
    stream = null;
  }

  updateStatus("Stopped");
}


// ===================== LOOP =====================
async function loop() {
  if (!running || busy) {
    requestAnimationFrame(loop);
    return;
  }

  busy = true;

  canvas.width = 320;
  canvas.height = 240;

  ctx.drawImage(video, 0, 0, 320, 240);

  const frame = canvas.toDataURL("image/jpeg", 0.6);

  try {
    const res = await fetch("/process_frame", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: frame })
    });

    const data = await res.json();

    drawBox(data);
    updateUI(data);

  } catch {
    console.warn("Network issue");
  }

  setTimeout(() => {
    busy = false;
    requestAnimationFrame(loop);
  }, INTERVAL);
}


// ===================== DRAW BOX =====================
function drawBox(data) {
  octx.clearRect(0, 0, overlay.width, overlay.height);

  if (!data?.box) return;

  const [t, r, b, l] = data.box;
  const known = data.name !== "Unknown";

  const color = known ? "#22c55e" : "#eab308";

  octx.strokeStyle = color;
  octx.lineWidth = 3;
  octx.strokeRect(l, t, r - l, b - t);

  octx.fillStyle = color;
  octx.fillText(data.name || "Unknown", l, t - 5);
}


// ===================== UI =====================
function updateUI(data) {
  const nameEl = document.getElementById("name-display");
  const accEl = document.getElementById("acc-display");

  if (nameEl) nameEl.textContent = data.name;
  if (accEl) accEl.textContent =
    `Mask: ${data.mask} • Glasses: ${data.glasses}`;

  if (data.name !== "Unknown") {
    goToDetail(data);
  }
}


// ===================== REDIRECT =====================
function goToDetail(data) {
  const url =
    `/detail/${encodeURIComponent(data.name)}` +
    `?lat=${coords.lat}` +
    `&lon=${coords.lon}` +
    `&mask=${data.mask}` +
    `&glasses=${data.glasses}`;

  setTimeout(() => {
    stopApp();
    window.location.href = url;
  }, 500);
}


// ===================== REGISTER =====================
async function registerUser() {
  if (busy) return;

  const name = prompt("Enter name");
  if (!name) return;

  canvas.width = 320;
  canvas.height = 240;

  ctx.drawImage(video, 0, 0, 320, 240);

  const frame = canvas.toDataURL("image/jpeg", 0.7);

  await fetch("/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, image: frame })
  });

  alert("Registered");
}


// ===================== EXPORT =====================
window.startApp = startApp;
window.stopApp = stopApp;
window.registerUser = registerUser;

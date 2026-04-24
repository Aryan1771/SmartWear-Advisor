// ===================== OPTIMIZED APP.JS =====================

const video = document.getElementById('webcam');
const overlay = document.getElementById('overlay');
const hiddenCanvas = document.getElementById('hidden-canvas');

const ctx = hiddenCanvas.getContext('2d');
const octx = overlay.getContext('2d');

const nameDisplay = document.getElementById('name-display');
const accDisplay = document.getElementById('acc-display');

let active = false;
let processing = false;
let lastCall = 0;

const INTERVAL = 1200; // ms (IMPORTANT)

let userCoords = { lat: null, lon: null };


// ===================== GPS =====================
navigator.geolocation.getCurrentPosition(
  pos => {
    userCoords.lat = pos.coords.latitude;
    userCoords.lon = pos.coords.longitude;
    updateLocation("GPS OK");
  },
  () => updateLocation("GPS Error")
);


// ===================== START =====================
export async function startApp() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user' }
    });

    video.srcObject = stream;
    active = true;

    updateStatus("Live");

    requestAnimationFrame(loop);

  } catch {
    alert("Camera permission denied");
  }
}


// ===================== STOP =====================
export function stopApp() {
  active = false;

  if (video.srcObject) {
    video.srcObject.getTracks().forEach(t => t.stop());
  }

  updateStatus("Stopped");
}


// ===================== MAIN LOOP =====================
async function loop(timestamp) {
  if (!active) return;

  // throttle calls
  if (timestamp - lastCall < INTERVAL || processing) {
    requestAnimationFrame(loop);
    return;
  }

  processing = true;
  lastCall = timestamp;

  // low resolution (IMPORTANT)
  hiddenCanvas.width = 320;
  hiddenCanvas.height = 240;
  ctx.drawImage(video, 0, 0, 320, 240);

  const frame = hiddenCanvas.toDataURL('image/jpeg', 0.6);

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2500);
    
    const res = await fetch('/process_frame', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: frame }),
      signal: controller.signal
    });

    clearTimeout(timeout);

    const data = await res.json();

    drawOverlay(data);

    if (data.name && data.name !== "Unknown") {
      handleSuccess(data);
      return; // STOP LOOP
    }

  } catch (e) {
    console.warn("Network error");
  }

  processing = false;
  requestAnimationFrame(loop);
}


// ===================== DRAW =====================
function drawOverlay(data) {
  octx.clearRect(0, 0, overlay.width, overlay.height);

  if (!data || !data.box) return;

  const [t, r, b, l] = data.box;
  const known = data.name !== "Unknown";

  const color = known ? "#22c55e" : "#eab308"; // GREEN / YELLOW

  octx.strokeStyle = color;
  octx.lineWidth = 2;
  octx.strokeRect(l, t, r - l, b - t);

  octx.fillStyle = color;
  octx.font = "bold 14px sans-serif";
  octx.fillText(known ? data.name : "Unknown", l, t - 5);

  nameDisplay.textContent = data.name;
  nameDisplay.style.color = color;

  accDisplay.textContent =
    `Mask: ${data.mask} • Glasses: ${data.glasses}`;
}


// ===================== SUCCESS =====================
function handleSuccess(data) {
  active = false; // STOP EVERYTHING

  const city = document.getElementById('city')?.value || "";

  const url = `/detail/${encodeURIComponent(data.name)}`
    + `?lat=${userCoords.lat}`
    + `&lon=${userCoords.lon}`
    + `&city=${encodeURIComponent(city)}`
    + `&mask=${encodeURIComponent(data.mask)}`
    + `&glasses=${encodeURIComponent(data.glasses)}`;

  setTimeout(() => {
    window.location.href = url;
  }, 400);
}


// ===================== REGISTER =====================
export async function registerUser() {
  if (!active) {
    alert("Start camera first");
    return;
  }

  hiddenCanvas.width = 320;
  hiddenCanvas.height = 240;
  ctx.drawImage(video, 0, 0, 320, 240);

  const frame = hiddenCanvas.toDataURL('image/jpeg', 0.7);

  const name = prompt("Enter name");
  if (!name) return;

  try {
    const res = await fetch('/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, image: frame })
    });

    const data = await res.json();

    alert(data.success ? "Registered" : "Failed");

  } catch {
    alert("Server error");
  }
}

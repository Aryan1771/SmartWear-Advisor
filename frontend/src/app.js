import React, { useEffect, useRef, useState } from "react";
function App() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const wsRef = useRef(null);
  const rafRef = useRef(null);
  const lastSendRef = useRef(0);
  const [result, setResult] = useState({});
  const connectWS = () => {
  const socket = new WebSocket(WS_URL);

  socket.onopen = () => console.log("WS connected");

  socket.onclose = () => {
    console.log("WS disconnected. Reconnecting...");
    setTimeout(connectWS, 2000);
  };

  socket.onerror = () => socket.close();

  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    setResult(data);
    requestAnimationFrame(() => drawBox(data));
  };

  wsRef.current = socket;
};
connectWS();
  useEffect(() => {
    startCamera();
    connectWebSocket();
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);
  const connectWebSocket = () => {
    const host = "smartwear-backend-3moi.onrender.com";
    const WS_URL =
      process.env.REACT_APP_WS_URL ||
      (window.location.hostname === "localhost"
        ? "ws://127.0.0.1:8000/ws"
        : `wss://${host}/ws`);
    const socket = new WebSocket(WS_URL);
    socket.onopen = () => console.log("WS Connected");
    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setResult(data);
        requestAnimationFrame(() => drawBox(data));
      } catch (e) {
        console.warn("Invalid WS message", e);
      }
    };
    socket.onclose = () => {
      console.log("❌ WS Closed → Reconnecting...");
      setTimeout(connectWebSocket, 2000);
    };
    wsRef.current = socket;
  };
  const startCamera = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 480 },
    });
    videoRef.current.srcObject = stream;
    videoRef.current.onloadedmetadata = () => {
      rafRef.current = requestAnimationFrame(sendFrame);
    };
  };
  const sendFrame = (time) => {
    if (!videoRef.current || !wsRef.current) {
      rafRef.current = requestAnimationFrame(sendFrame);
      return;
    }
    if (
      time - lastSendRef.current > 200 &&
      wsRef.current.readyState === 1
    ) {
      const canvas = document.createElement("canvas");
      canvas.width = 320;
      canvas.height = 240;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
      const base64 = canvas.toDataURL("image/jpeg", 0.6);
      try {
        wsRef.current.send(base64);
      } catch (e) {
        console.warn("WS send error");
      }
      lastSendRef.current = time;
    }
    rafRef.current = requestAnimationFrame(sendFrame);
  };
  const drawBox = (data) => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;
    const ctx = canvas.getContext("2d");
    canvas.width = video.clientWidth;
    canvas.height = video.clientHeight;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!data.box || data.status !== "success") return;
    const { top, right, bottom, left } = data.box;
    const scaleX = canvas.width / video.videoWidth;
    const scaleY = canvas.height / video.videoHeight;
    let x = left * scaleX;
    let y = top * scaleY;
    let width = (right - left) * scaleX;
    let height = (bottom - top) * scaleY;
    x = canvas.width - (x + width);
    const color = data.name !== "Unknown" ? "#00ff88" : "#ffaa00";
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.strokeRect(x, y, width, height);
    ctx.fillStyle = color;
    ctx.fillRect(x, y - 28, width, 28);
    ctx.fillStyle = "#000";
    ctx.font = "bold 14px Segoe UI";
    ctx.fillText(
      `${data.name} | ${data.mask} | ${data.glasses}`,
      x + 5,
      y - 8
    );
  };
  return (
    <div style={{
      background: "#0d1117",
      color: "#f0f6fc",
      minHeight: "100vh",
      padding: "20px",
      fontFamily: "Segoe UI"
    }}>
      <h1>SmartWear Advisor</h1>
      <div style={{ display: "flex", gap: "20px" }}>
        {/* CAMERA */}
        <div style={{ position: "relative", flex: 3 }}>
          <video
            ref={videoRef}
            autoPlay
            playsInline
            style={{
              width: "100%",
              borderRadius: "10px",
              transform: "scaleX(-1)"
            }}
          />
          <canvas
            ref={canvasRef}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              pointerEvents: "none"
            }}
          />
        </div>
        {/* PANEL */}
        <div style={{ flex: 2 }}>
          <Card title="User" value={result.name || "Waiting..."} />
          <Card title="Mask" value={result.mask || "--"} />
          <Card title="Glasses" value={result.glasses || "--"} />
          <Card title="Confidence" value={result.confidence || "--"} />
        </div>
      </div>
    </div>
  );
}
function Card({ title, value }) {
  return (
    <div style={{
      background: "#1f2937",
      padding: "15px",
      marginBottom: "10px",
      borderRadius: "10px"
    }}>
      <h3>{title}</h3>
      <p>{value}</p>
    </div>
  );
}
export default App;
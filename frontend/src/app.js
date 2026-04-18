import React, { useEffect, useRef, useState } from "react";

function App() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const wsRef = useRef(null);

  const [result, setResult] = useState({});

  useEffect(() => {
    startCamera();

    // WebSocket URL: prefer REACT_APP_WS_URL, else use production Render URL, then fall back to localhost
    const renderHost = "smartwear-backend-3moi.onrender.com";
    const defaultWs =
      process.env.REACT_APP_WS_URL ||
      `wss://${renderHost}/ws` ||
      "ws://127.0.0.1:8000/ws";
    // API base (for future REST calls)
    const API_BASE = process.env.REACT_APP_API_URL || `https://${renderHost}`;
    const socket = new WebSocket(defaultWs);

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setResult(data);
        drawBox(data);
      } catch (e) {
        console.warn("Invalid WS message", e);
      }
    };

    socket.onopen = () => console.log("WS connected", defaultWs);
    socket.onclose = () => console.log("WS closed");

    wsRef.current = socket;

    return () => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) wsRef.current.close();
    };
  }, []);

  // 🎥 Start Camera
  const startCamera = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    videoRef.current.srcObject = stream;

    requestAnimationFrame(sendFrame); // 🔥 better than setInterval
  };

  // ⚡ PERFORMANCE BOOST
  const lastSendRef = React.useRef(0);
  const rafRef = React.useRef(null);
  const sendFrame = (time) => {
    if (!videoRef.current || !wsRef.current) {
      rafRef.current = requestAnimationFrame(sendFrame);
      return;
    }

    // 🔥 send only every 200ms (5 FPS)
    if (time - lastSendRef.current > 200 && wsRef.current.readyState === 1) {
      const canvas = document.createElement("canvas");
      canvas.width = videoRef.current.videoWidth || 640;
      canvas.height = videoRef.current.videoHeight || 480;

      const ctx = canvas.getContext("2d");
      ctx.drawImage(videoRef.current, 0, 0);

      const base64 = canvas.toDataURL("image/jpeg", 0.6); // 🔥 compress
      try {
        wsRef.current.send(base64);
      } catch (e) {
        console.warn("WS send failed", e);
      }

      lastSendRef.current = time;
    }

    rafRef.current = requestAnimationFrame(sendFrame);
  };

  // 🎯 Draw bounding box
  const drawBox = (data) => {
    const canvas = canvasRef.current;
    const video = videoRef.current;

    if (!canvas || !video) return;

    const ctx = canvas.getContext("2d");

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (data.box) {
      const { top, right, bottom, left } = data.box;

      ctx.strokeStyle = "lime";
      ctx.lineWidth = 3;

      ctx.strokeRect(left, top, right - left, bottom - top);

      ctx.fillStyle = "lime";
      ctx.fillText(data.name || "Unknown", left, top - 10);
    }
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

        {/* CAMERA + OVERLAY */}
        <div style={{ position: "relative", flex: 3 }}>
          <video ref={videoRef} autoPlay style={{ width: "100%" }} />
          <canvas
            ref={canvasRef}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%"
            }}
          />
        </div>

        {/* SIDE PANEL */}
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
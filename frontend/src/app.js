import React, { useEffect, useRef, useState } from "react";

function App() {
  const videoRef = useRef(null);
  const [result, setResult] = useState({});
  const wsRef = useRef(null);

  useEffect(() => {
    startCamera();

    const socket = new WebSocket("ws://127.0.0.1:8000/ws");

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setResult(data);
    };

    wsRef.current = socket;
  }, []);

  const startCamera = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    videoRef.current.srcObject = stream;

    setInterval(captureFrame, 200);
  };

  const captureFrame = () => {
    if (!videoRef.current || !wsRef.current) return;

    const canvas = document.createElement("canvas");
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;

    const ctx = canvas.getContext("2d");
    ctx.drawImage(videoRef.current, 0, 0);

    const base64 = canvas.toDataURL("image/jpeg");
    wsRef.current.send(base64);
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

        {/* Camera */}
        <div style={{
          flex: 3,
          background: "#161b22",
          padding: "15px",
          borderRadius: "10px"
        }}>
          <video ref={videoRef} autoPlay width="100%" />
        </div>

        {/* Side panel */}
        <div style={{
          flex: 2,
          display: "flex",
          flexDirection: "column",
          gap: "15px"
        }}>

          <Card title="Recognition" value={result.name || "Waiting..."} />
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
      borderRadius: "10px"
    }}>
      <h3>{title}</h3>
      <p>{value}</p>
    </div>
  );
}

export default App;
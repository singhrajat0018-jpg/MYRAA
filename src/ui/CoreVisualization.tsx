import { useRef, useEffect, useCallback } from "react";

interface CoreVisualizationProps {
  state: string;
  size?: number;
}

export function CoreVisualization({ state, size = 420 }: CoreVisualizationProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef<number>(0);
  const timeRef = useRef(0);

  const isActive = state !== "disconnected";
  const isListening = state === "listening";
  const isSpeaking = state === "speaking";
  const isConnecting = state === "connecting";

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = size;
    const h = size;

    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.scale(dpr, dpr);

    const cx = w / 2;
    const cy = h / 2;
    const globeRadius = w * 0.34;

    timeRef.current += isSpeaking ? 0.012 : isListening ? 0.008 : 0.004;
    const t = timeRef.current;

    ctx.clearRect(0, 0, w, h);

    // Outer atmospheric glow
    const outerGlow = ctx.createRadialGradient(cx, cy, globeRadius * 0.5, cx, cy, globeRadius * 2);
    outerGlow.addColorStop(0, `rgba(0, 212, 255, ${isSpeaking ? 0.12 : 0.06})`);
    outerGlow.addColorStop(0.4, `rgba(0, 102, 255, ${isSpeaking ? 0.06 : 0.03})`);
    outerGlow.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = outerGlow;
    ctx.fillRect(0, 0, w, h);

    // Second glow layer (bloom)
    if (isActive) {
      const bloom = ctx.createRadialGradient(cx, cy, globeRadius * 0.3, cx, cy, globeRadius * 1.5);
      bloom.addColorStop(0, `rgba(0, 212, 255, ${0.03 + Math.sin(t * 2) * 0.02})`);
      bloom.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = bloom;
      ctx.fillRect(0, 0, w, h);
    }

    // Latitude grid lines
    ctx.strokeStyle = "rgba(0, 212, 255, 0.05)";
    ctx.lineWidth = 0.5;
    for (let i = -4; i <= 4; i++) {
      const lat = (i / 5) * Math.PI;
      const y = cy + Math.sin(lat) * globeRadius;
      const r = Math.cos(lat) * globeRadius;
      if (r > 5) {
        ctx.beginPath();
        ctx.ellipse(cx, y, r, r * 0.25, 0, 0, Math.PI * 2);
        ctx.stroke();
      }
    }

    // Longitude grid lines (rotating)
    for (let i = 0; i < 12; i++) {
      const lon = (i / 12) * Math.PI + t * 0.2;
      ctx.beginPath();
      ctx.ellipse(cx, cy, Math.cos(lon) * globeRadius, globeRadius, 0, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Globe body
    const globeGrad = ctx.createRadialGradient(
      cx - globeRadius * 0.3, cy - globeRadius * 0.3, 0,
      cx, cy, globeRadius
    );
    globeGrad.addColorStop(0, "rgba(0, 50, 100, 0.5)");
    globeGrad.addColorStop(0.4, "rgba(0, 30, 70, 0.35)");
    globeGrad.addColorStop(0.8, "rgba(0, 15, 40, 0.25)");
    globeGrad.addColorStop(1, "rgba(0, 8, 20, 0.2)");
    ctx.beginPath();
    ctx.arc(cx, cy, globeRadius, 0, Math.PI * 2);
    ctx.fillStyle = globeGrad;
    ctx.fill();

    // Globe edge glow
    ctx.strokeStyle = `rgba(0, 212, 255, ${isActive ? 0.3 : 0.15})`;
    ctx.lineWidth = isActive ? 1.5 : 1;
    ctx.stroke();

    // Continental dots
    const dotCount = 200;
    for (let i = 0; i < dotCount; i++) {
      const phi = ((i * 137.508 + 50) % 360) * (Math.PI / 180);
      const theta = ((i * 67.3 + 20) % 180) * (Math.PI / 180) - Math.PI / 2;
      const rotPhi = phi + t * 0.25;

      const x = Math.cos(theta) * Math.sin(rotPhi);
      const y = Math.sin(theta);
      const z = Math.cos(theta) * Math.cos(rotPhi);

      if (z > 0.05) {
        const px = cx + x * globeRadius * z;
        const py = cy + y * globeRadius * 0.9;
        const alpha = z * (isActive ? 0.8 : 0.4);
        const sz = 0.8 + z * 1.5;

        // Color based on "continent" regions (hash)
        const hash = (i * 7 + 13) % 10;
        const isLand = hash < 4;

        if (isLand) {
          ctx.beginPath();
          ctx.arc(px, py, sz, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(0, 212, 255, ${alpha * 0.8})`;
          ctx.fill();
        } else {
          // City lights on land
          ctx.beginPath();
          ctx.arc(px, py, sz * 0.6, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(255, 200, 100, ${alpha * 0.3})`;
          ctx.fill();
        }
      }
    }

    // Orbital ring 1
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(-0.35);
    ctx.beginPath();
    ctx.ellipse(0, 0, globeRadius * 1.25, globeRadius * 0.35, 0, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(0, 212, 255, ${isListening ? 0.25 : 0.12})`;
    ctx.lineWidth = isListening ? 1.2 : 0.8;
    ctx.stroke();

    // Traveling dot on orbital ring 1
    const speed1 = isSpeaking ? 1.5 : isListening ? 1.0 : 0.6;
    const orbAngle1 = t * speed1;
    const orbX1 = Math.cos(orbAngle1) * globeRadius * 1.25;
    const orbY1 = Math.sin(orbAngle1) * globeRadius * 0.35;
    ctx.beginPath();
    ctx.arc(orbX1, orbY1, isSpeaking ? 3.5 : 2.5, 0, Math.PI * 2);
    ctx.fillStyle = "#00d4ff";
    ctx.fill();
    ctx.shadowColor = "#00d4ff";
    ctx.shadowBlur = isSpeaking ? 12 : 6;
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.restore();

    // Orbital ring 2
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(0.55);
    ctx.beginPath();
    ctx.ellipse(0, 0, globeRadius * 1.4, globeRadius * 0.25, 0, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(0, 102, 255, ${isListening ? 0.2 : 0.08})`;
    ctx.lineWidth = 0.6;
    ctx.stroke();

    const speed2 = isSpeaking ? -1.8 : isListening ? -1.2 : -0.8;
    const orbAngle2 = t * speed2;
    const orbX2 = Math.cos(orbAngle2) * globeRadius * 1.4;
    const orbY2 = Math.sin(orbAngle2) * globeRadius * 0.25;
    ctx.beginPath();
    ctx.arc(orbX2, orbY2, 2, 0, Math.PI * 2);
    ctx.fillStyle = "#3388ff";
    ctx.fill();
    ctx.shadowColor = "#3388ff";
    ctx.shadowBlur = 5;
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.restore();

    // Scanning arc (conic sweep)
    ctx.save();
    ctx.translate(cx, cy);
    const scanAngle = t * (isListening ? 0.6 : 0.3);
    ctx.rotate(scanAngle);
    try {
      const scanGrad = ctx.createConicGradient(0, 0, 0);
      scanGrad.addColorStop(0, `rgba(0, 212, 255, ${isListening ? 0.1 : 0.05})`);
      scanGrad.addColorStop(0.15, "rgba(0, 212, 255, 0)");
      scanGrad.addColorStop(1, "rgba(0, 212, 255, 0)");
      ctx.beginPath();
      ctx.arc(0, 0, globeRadius * 1.1, 0, Math.PI * 2);
      ctx.fillStyle = scanGrad;
      ctx.fill();
    } catch {
      // Fallback for browsers without conic gradient
    }
    ctx.restore();

    // Center energy point
    if (isActive) {
      const pulseSize = isSpeaking ? 10 + Math.sin(t * 4) * 3 : isListening ? 8 + Math.sin(t * 2) * 2 : 6;
      const energyGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, pulseSize);
      energyGrad.addColorStop(0, `rgba(0, 212, 255, ${isSpeaking ? 0.9 : 0.6})`);
      energyGrad.addColorStop(0.4, "rgba(0, 212, 255, 0.3)");
      energyGrad.addColorStop(1, "rgba(0, 212, 255, 0)");
      ctx.beginPath();
      ctx.arc(cx, cy, pulseSize, 0, Math.PI * 2);
      ctx.fillStyle = energyGrad;
      ctx.fill();

      ctx.beginPath();
      ctx.arc(cx, cy, 2, 0, Math.PI * 2);
      ctx.fillStyle = "#00d4ff";
      ctx.fill();
    }

    // Floating particles
    if (isActive) {
      const particleCount = isSpeaking ? 40 : 25;
      for (let i = 0; i < particleCount; i++) {
        const angle = (i / particleCount) * Math.PI * 2 + t * (0.15 + (i % 3) * 0.05);
        const dist = globeRadius * (1.05 + Math.sin(t * 0.5 + i * 0.8) * 0.2);
        const px = cx + Math.cos(angle) * dist;
        const py = cy + Math.sin(angle) * dist;
        const alpha = 0.1 + Math.sin(t * 1.5 + i * 0.7) * 0.08;
        const sz = 0.8 + Math.sin(t + i) * 0.4;
        ctx.beginPath();
        ctx.arc(px, py, sz, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(0, 212, 255, ${alpha})`;
        ctx.fill();
      }
    }

    // HUD rings (thin concentric circles)
    if (isActive) {
      for (let i = 1; i <= 3; i++) {
        const ringR = globeRadius * (1.3 + i * 0.15);
        ctx.beginPath();
        ctx.arc(cx, cy, ringR, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(0, 212, 255, ${0.03 - i * 0.008})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      }
    }

    frameRef.current = requestAnimationFrame(draw);
  }, [size, isActive, isListening, isSpeaking, isConnecting]);

  useEffect(() => {
    frameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frameRef.current);
  }, [draw]);

  return (
    <div className="globe-container" style={{ width: size, height: size }}>
      <canvas ref={canvasRef} style={{ width: size, height: size }} />
    </div>
  );
}

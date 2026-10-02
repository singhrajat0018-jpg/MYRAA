/**
 * HolographicEarth — the central MYRAA Core visualization.
 *
 * A stylized rotating Earth rendered on Canvas 2D with:
 * - Luminous surface with geographic linework
 * - Atmospheric glow
 * - Orbital rings
 * - Scanning arcs
 * - Data points / network pulses
 * - Particle accents
 * - Dynamic state-responsive animation
 *
 * No Three.js dependency. Pure Canvas 2D for performance.
 */
import React, { useEffect, useRef, useMemo } from "react";

interface HolographicEarthProps {
  /** MYRAA core state driving animation */
  coreState: string;
  /** Width/height in pixels (square) */
  size?: number;
}

// Simple geographic outlines (simplified continent polylines in lat/lon)
// Each continent is an array of [lon, lat] points
const CONTINENTS: number[][][] = [
  // North America
  [[-130,50],[-120,60],[-100,65],[-80,60],[-70,45],[-80,30],[-100,25],[-120,35],[-130,50]],
  // South America
  [[-80,10],[-70,-5],[-60,-15],[-50,-25],[-55,-35],[-70,-45],[-75,-30],[-80,-10],[-80,10]],
  // Europe
  [[-10,40],[0,50],[10,55],[25,60],[30,50],[20,40],[10,38],[-10,40]],
  // Africa
  [[-15,35],[10,35],[30,30],[40,15],[35,0],[30,-15],[25,-30],[15,-35],[10,-20],[0,5],[-10,10],[-15,35]],
  // Asia
  [[30,50],[50,55],[70,60],[90,55],[110,50],[130,45],[140,35],[130,25],[110,20],[90,25],[70,30],[50,35],[30,50]],
  // Australia
  [[115,-15],[130,-15],[145,-20],[150,-30],[145,-35],[130,-35],[115,-30],[115,-15]],
];

// Convert lat/lon to 3D sphere coordinates, then project to 2D
function latLonTo3D(lat: number, lon: number, radius: number, rotationY: number) {
  const latRad = (lat * Math.PI) / 180;
  const lonRad = ((lon + rotationY) * Math.PI) / 180;

  const x = radius * Math.cos(latRad) * Math.sin(lonRad);
  const y = -radius * Math.sin(latRad);
  const z = radius * Math.cos(latRad) * Math.cos(lonRad);

  return { x, y, z };
}

function project(x: number, y: number, z: number, cx: number, cy: number, fov: number) {
  const scale = fov / (fov + z);
  return { px: cx + x * scale, py: cy + y * scale, scale };
}

export const HolographicEarth: React.FC<HolographicEarthProps> = ({ coreState, size = 400 }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const startTimeRef = useRef(Date.now());
  const stateRef = useRef(coreState);

  // Keep state ref current
  useEffect(() => { stateRef.current = coreState; }, [coreState]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);

    const cx = size / 2;
    const cy = size / 2;
    const earthRadius = size * 0.28;
    const fov = size * 0.8;

    // Pre-generate data points on the sphere
    const dataPoints = Array.from({ length: 40 }, () => ({
      lat: (Math.random() - 0.5) * 140,
      lon: Math.random() * 360 - 180,
      size: Math.random() * 2 + 1,
      pulse: Math.random() * Math.PI * 2,
      speed: Math.random() * 2 + 1,
    }));

    // Network lines (connections between random points)
    const networkLines = Array.from({ length: 15 }, () => ({
      lat1: (Math.random() - 0.5) * 120,
      lon1: Math.random() * 360 - 180,
      lat2: (Math.random() - 0.5) * 120,
      lon2: Math.random() * 360 - 180,
      progress: 0,
      speed: Math.random() * 0.5 + 0.3,
    }));

    // Orbital ring points
    const orbitalRingCount = 120;

    const animate = () => {
      const elapsed = (Date.now() - startTimeRef.current) / 1000;
      const st = stateRef.current;

      // Rotation speed varies by state
      let rotSpeed = 0.15;
      if (st === "thinking") rotSpeed = 0.4;
      else if (st === "executing") rotSpeed = 0.6;
      else if (st === "listening") rotSpeed = 0.25;
      else if (st === "speaking") rotSpeed = 0.3;
      else if (st === "error" || st === "degraded") rotSpeed = 0.05;

      const rotation = elapsed * rotSpeed;

      // Clear
      ctx.clearRect(0, 0, size, size);

      // ── Atmospheric glow ──
      const glowRadius = earthRadius * 1.35;
      const glow = ctx.createRadialGradient(cx, cy, earthRadius * 0.8, cx, cy, glowRadius);
      glow.addColorStop(0, "rgba(34,211,238,0.06)");
      glow.addColorStop(0.5, "rgba(34,211,238,0.03)");
      glow.addColorStop(1, "rgba(34,211,238,0)");
      ctx.fillStyle = glow;
      ctx.fillRect(0, 0, size, size);

      // ── Outer ring glow ──
      ctx.beginPath();
      ctx.arc(cx, cy, earthRadius * 1.15, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(34,211,238,0.08)";
      ctx.lineWidth = 1;
      ctx.stroke();

      // ── Draw Earth sphere (dark fill) ──
      ctx.beginPath();
      ctx.arc(cx, cy, earthRadius, 0, Math.PI * 2);
      const earthGrad = ctx.createRadialGradient(cx - earthRadius * 0.3, cy - earthRadius * 0.3, 0, cx, cy, earthRadius);
      earthGrad.addColorStop(0, "rgba(10,20,35,0.95)");
      earthGrad.addColorStop(0.7, "rgba(5,12,25,0.98)");
      earthGrad.addColorStop(1, "rgba(2,5,12,1)");
      ctx.fillStyle = earthGrad;
      ctx.fill();

      // ── Grid lines (latitude) ──
      ctx.strokeStyle = "rgba(34,211,238,0.06)";
      ctx.lineWidth = 0.5;
      for (let lat = -60; lat <= 60; lat += 30) {
        ctx.beginPath();
        let started = false;
        for (let lon = 0; lon <= 360; lon += 3) {
          const p3d = latLonTo3D(lat, lon, earthRadius * 0.99, rotation);
          if (p3d.z < 0) { started = false; continue; }
          const proj = project(p3d.x, p3d.y, p3d.z, cx, cy, fov);
          if (!started) { ctx.moveTo(proj.px, proj.py); started = true; }
          else ctx.lineTo(proj.px, proj.py);
        }
        ctx.stroke();
      }

      // ── Grid lines (longitude) ──
      for (let lon = 0; lon < 360; lon += 30) {
        ctx.beginPath();
        let started = false;
        for (let lat = -90; lat <= 90; lat += 3) {
          const p3d = latLonTo3D(lat, lon, earthRadius * 0.99, rotation);
          if (p3d.z < 0) { started = false; continue; }
          const proj = project(p3d.x, p3d.y, p3d.z, cx, cy, fov);
          if (!started) { ctx.moveTo(proj.px, proj.py); started = true; }
          else ctx.lineTo(proj.px, proj.py);
        }
        ctx.stroke();
      }

      // ── Continent outlines ──
      ctx.strokeStyle = "rgba(34,211,238,0.35)";
      ctx.lineWidth = 1;
      for (const continent of CONTINENTS) {
        ctx.beginPath();
        let started = false;
        for (const [lon, lat] of continent) {
          const p3d = latLonTo3D(lat, lon, earthRadius * 1.001, rotation);
          if (p3d.z < 0) { started = false; continue; }
          const proj = project(p3d.x, p3d.y, p3d.z, cx, cy, fov);
          if (!started) { ctx.moveTo(proj.px, proj.py); started = true; }
          else ctx.lineTo(proj.px, proj.py);
        }
        ctx.closePath();
        ctx.stroke();

        // Subtle fill for visible continents
        ctx.fillStyle = "rgba(34,211,238,0.03)";
        ctx.fill();
      }

      // ── Data points ──
      for (const dp of dataPoints) {
        const p3d = latLonTo3D(dp.lat, dp.lon, earthRadius * 1.002, rotation);
        if (p3d.z < 0) continue;
        const proj = project(p3d.x, p3d.y, p3d.z, cx, cy, fov);
        const pulse = Math.sin(elapsed * dp.speed + dp.pulse) * 0.5 + 0.5;
        const alpha = 0.3 + pulse * 0.5;
        const r = dp.size * proj.scale;

        ctx.beginPath();
        ctx.arc(proj.px, proj.py, r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(34,211,238,${alpha})`;
        ctx.fill();

        // Pulse ring
        if (pulse > 0.7) {
          ctx.beginPath();
          ctx.arc(proj.px, proj.py, r * 2.5, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(34,211,238,${(pulse - 0.7) * 0.6})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }

      // ── Network lines ──
      for (const nl of networkLines) {
        nl.progress += nl.speed * 0.01;
        if (nl.progress > 1) nl.progress = 0;

        const p1 = latLonTo3D(nl.lat1, nl.lon1, earthRadius * 1.003, rotation);
        const p2 = latLonTo3D(nl.lat2, nl.lon2, earthRadius * 1.003, rotation);
        if (p1.z < 0 || p2.z < 0) continue;

        const a = project(p1.x, p1.y, p1.z, cx, cy, fov);
        const b = project(p2.x, p2.y, p2.z, cx, cy, fov);

        // Arc line
        ctx.beginPath();
        ctx.moveTo(a.px, a.py);
        const midX = (a.px + b.px) / 2;
        const midY = (a.py + b.py) / 2 - 15 * a.scale;
        ctx.quadraticCurveTo(midX, midY, b.px, b.py);
        ctx.strokeStyle = "rgba(34,211,238,0.1)";
        ctx.lineWidth = 0.5;
        ctx.stroke();

        // Traveling dot
        const t = nl.progress;
        const dotX = (1 - t) * (1 - t) * a.px + 2 * (1 - t) * t * midX + t * t * b.px;
        const dotY = (1 - t) * (1 - t) * a.py + 2 * (1 - t) * t * midY + t * t * b.py;
        ctx.beginPath();
        ctx.arc(dotX, dotY, 1.5, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(34,211,238,0.6)";
        ctx.fill();
      }

      // ── Orbital ring 1 ──
      const ringTilt1 = 0.3;
      ctx.beginPath();
      for (let i = 0; i <= orbitalRingCount; i++) {
        const angle = (i / orbitalRingCount) * Math.PI * 2;
        const rx = earthRadius * 1.3;
        const ry = earthRadius * 0.4;
        const x = cx + Math.cos(angle) * rx;
        const y = cy + Math.sin(angle) * ry * Math.cos(ringTilt1) + Math.sin(elapsed * 0.1) * 3;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = "rgba(34,211,238,0.12)";
      ctx.lineWidth = 0.8;
      ctx.stroke();

      // ── Orbital ring 2 (tilted) ──
      const ringTilt2 = -0.5;
      ctx.beginPath();
      for (let i = 0; i <= orbitalRingCount; i++) {
        const angle = (i / orbitalRingCount) * Math.PI * 2 + elapsed * 0.05;
        const rx = earthRadius * 1.5;
        const ry = earthRadius * 0.35;
        const x = cx + Math.cos(angle) * rx;
        const y = cy + Math.sin(angle) * ry * Math.cos(ringTilt2);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = "rgba(34,211,238,0.06)";
      ctx.lineWidth = 0.5;
      ctx.stroke();

      // ── Scanning arc ──
      const scanAngle = (elapsed * 0.5) % (Math.PI * 2);
      const scanGrad = ctx.createConicGradient(scanAngle, cx, cy);
      scanGrad.addColorStop(0, "rgba(34,211,238,0.08)");
      scanGrad.addColorStop(0.1, "rgba(34,211,238,0)");
      scanGrad.addColorStop(1, "rgba(34,211,238,0)");
      ctx.beginPath();
      ctx.arc(cx, cy, earthRadius * 1.05, 0, Math.PI * 2);
      ctx.fillStyle = scanGrad;
      ctx.fill();

      // ── Edge highlight (rim light) ──
      ctx.beginPath();
      ctx.arc(cx, cy, earthRadius, -Math.PI * 0.6, -Math.PI * 0.1);
      const rimGrad = ctx.createLinearGradient(cx - earthRadius, cy, cx, cy - earthRadius);
      rimGrad.addColorStop(0, "rgba(34,211,238,0)");
      rimGrad.addColorStop(0.5, "rgba(34,211,238,0.15)");
      rimGrad.addColorStop(1, "rgba(34,211,238,0)");
      ctx.strokeStyle = rimGrad;
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // ── State-specific effects ──
      if (st === "error" || st === "degraded") {
        // Red warning pulse
        const errPulse = Math.sin(elapsed * 3) * 0.5 + 0.5;
        ctx.beginPath();
        ctx.arc(cx, cy, earthRadius * 1.1, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(239,68,68,${errPulse * 0.2})`;
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      if (st === "thinking") {
        // Extra orbital activity
        for (let i = 0; i < 3; i++) {
          const a = elapsed * (1.5 + i * 0.3) + i * 2;
          const r = earthRadius * (1.2 + i * 0.1);
          const px = cx + Math.cos(a) * r;
          const py = cy + Math.sin(a) * r * 0.3;
          ctx.beginPath();
          ctx.arc(px, py, 2, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(34,211,238,${0.4 + Math.sin(elapsed * 4 + i) * 0.3})`;
          ctx.fill();
        }
      }

      if (st === "executing") {
        // Active directional pulse
        const execPulse = (elapsed * 2) % (Math.PI * 2);
        ctx.beginPath();
        ctx.arc(cx, cy, earthRadius * (1.05 + Math.sin(execPulse) * 0.05), 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(34,211,238,0.15)";
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      animRef.current = requestAnimationFrame(animate);
    };

    animRef.current = requestAnimationFrame(animate);

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [size]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: size, height: size }}
      className="block"
    />
  );
};

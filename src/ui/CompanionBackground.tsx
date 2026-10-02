import React, { useRef, useEffect, useCallback } from 'react';

// ============================================================================
// Floating Petal Particle
// ============================================================================

interface Petal {
  x: number;
  y: number;
  size: number;
  speedX: number;
  speedY: number;
  rotation: number;
  rotationSpeed: number;
  opacity: number;
  hue: number;
}

// ============================================================================
// CompanionBackground — cherry-blossom sunset veranda (reference mock)
// Full-bleed scenic backdrop: sky, Mt Fuji, lake, sakura, wooden posts,
// hanging lantern, warm light. Petal canvas on top for life.
// ============================================================================

export const CompanionBackground = React.memo(function CompanionBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const petalsRef = useRef<Petal[]>([]);
  const mouseRef = useRef({ x: 0, y: 0 });
  const rafRef = useRef<number>(0);

  const createPetal = useCallback((w: number, h: number): Petal => ({
    x: Math.random() * w,
    y: -20 - Math.random() * 100,
    size: 3 + Math.random() * 6,
    speedX: -0.35 + Math.random() * 0.7,
    speedY: 0.45 + Math.random() * 0.9,
    rotation: Math.random() * Math.PI * 2,
    rotationSpeed: -0.02 + Math.random() * 0.04,
    opacity: 0.16 + Math.random() * 0.32,
    hue: 325 + Math.random() * 30,
  }), []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener('resize', resize);

    // Pause the animation loop while the window is hidden (CPU/GPU savings).
    let paused = document.hidden;
    const handleVisibility = () => {
      paused = document.hidden;
      if (!paused) {
        lastTime = performance.now();
        rafRef.current = requestAnimationFrame(animate);
      } else {
        cancelAnimationFrame(rafRef.current);
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);

    petalsRef.current = Array.from({ length: 28 }, () =>
      createPetal(window.innerWidth, window.innerHeight),
    );

    const handleMouse = (e: MouseEvent) => {
      mouseRef.current.x = (e.clientX / window.innerWidth - 0.5) * 2;
      mouseRef.current.y = (e.clientY / window.innerHeight - 0.5) * 2;
    };
    window.addEventListener('mousemove', handleMouse);

    let lastTime = 0;
    const animate = (time: number) => {
      const dt = Math.min((time - lastTime) / 16, 3) || 1;
      lastTime = time;
      const cw = window.innerWidth;
      const ch = window.innerHeight;
      ctx.clearRect(0, 0, cw, ch);
      const mx = mouseRef.current.x * 8;
      const my = mouseRef.current.y * 4;
      for (const p of petalsRef.current) {
        p.x += (p.speedX + mx * 0.08) * dt;
        p.y += p.speedY * dt;
        p.rotation += p.rotationSpeed * dt;
        if (p.y > ch + 30 || p.x < -30 || p.x > cw + 30) {
          Object.assign(p, createPetal(cw, ch));
          p.x = Math.random() * cw;
          p.y = -20;
        }
        ctx.save();
        ctx.translate(p.x + mx, p.y + my);
        ctx.rotate(p.rotation);
        ctx.globalAlpha = p.opacity;
        ctx.beginPath();
        ctx.ellipse(0, 0, p.size, p.size * 0.55, 0, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${p.hue}, 75%, 82%, 1)`;
        ctx.fill();
        ctx.beginPath();
        ctx.ellipse(p.size * 0.3, -p.size * 0.1, p.size * 0.5, p.size * 0.24, 0.3, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${p.hue + 10}, 85%, 88%, 0.75)`;
        ctx.fill();
        ctx.restore();
      }
      rafRef.current = requestAnimationFrame(animate);
    };
    if (!document.hidden) {
      rafRef.current = requestAnimationFrame(animate);
    }
    return () => {
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', handleMouse);
      document.removeEventListener('visibilitychange', handleVisibility);
      cancelAnimationFrame(rafRef.current);
    };
  }, [createPetal]);

  return (
    <div className="fixed inset-0 overflow-hidden" style={{ zIndex: 0, background: '#2a1838' }}>
      {/* ── Sky ─────────────────────────────────────────── */}
      <div
        className="absolute inset-0"
        style={{
          background: `
            radial-gradient(ellipse 90% 45% at 68% 62%, rgba(255, 236, 220, 0.85) 0%, rgba(255, 200, 190, 0.35) 34%, transparent 62%),
            radial-gradient(ellipse 55% 32% at 50% 30%, rgba(255, 255, 255, 0.5) 0%, transparent 65%),
            radial-gradient(ellipse 70% 50% at 12% 18%, rgba(255, 170, 205, 0.55) 0%, transparent 60%),
            radial-gradient(ellipse 60% 42% at 88% 12%, rgba(150, 170, 255, 0.5) 0%, transparent 62%),
            linear-gradient(180deg,
              #6f8fe8 0%,
              #9aa8ee 12%,
              #c4aaec 26%,
              #e5aedd 40%,
              #f7b4c8 52%,
              #ffbf9e 63%,
              #ffc9a3 70%,
              #d99a8e 82%,
              #7a5570 100%
            )
          `,
        }}
      />

      {/* ── Soft clouds ─────────────────────────────────── */}
      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice">
        <defs>
          <radialGradient id="cloudPink" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#ffe9f2" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#ffe9f2" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="fujiBody" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fdfbff" />
            <stop offset="28%" stopColor="#dfe6fb" />
            <stop offset="55%" stopColor="#8fa0d8" />
            <stop offset="100%" stopColor="#5a6a9e" />
          </linearGradient>
          <linearGradient id="lakeGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#f7c9d8" />
            <stop offset="35%" stopColor="#b9a4dc" />
            <stop offset="70%" stopColor="#6f86c2" />
            <stop offset="100%" stopColor="#3c4a78" />
          </linearGradient>
          <linearGradient id="woodGrad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#2c1a14" />
            <stop offset="45%" stopColor="#5a3a2c" />
            <stop offset="100%" stopColor="#241310" />
          </linearGradient>
        </defs>

        {/* clouds */}
        <ellipse cx="560" cy="180" rx="220" ry="42" fill="url(#cloudPink)" opacity="0.7" />
        <ellipse cx="1050" cy="120" rx="260" ry="36" fill="#ffffff" opacity="0.5" />
        <ellipse cx="880" cy="260" rx="180" ry="26" fill="#ffe4ee" opacity="0.65" />
        <ellipse cx="300" cy="300" rx="150" ry="22" fill="#ffd6e6" opacity="0.5" />

        {/* distant hills */}
        <path d="M0 560 C 180 520, 340 545, 520 530 C 700 515, 820 470, 1000 480 C 1180 490, 1320 540, 1440 525 L1440 620 L0 620 Z" fill="#7d6a9e" opacity="0.55" />

        {/* Mt Fuji */}
        <g>
          <path
            d="M700 560 L860 330 C866 321 876 321 882 330 L1042 560 C1050 572 1042 585 1028 585 L714 585 C700 585 692 572 700 560 Z"
            fill="url(#fujiBody)"
          />
          {/* snow cap */}
          <path
            d="M860 330 C866 321 876 321 882 330 L918 378 C910 392 898 388 892 398 C884 388 872 394 866 384 C858 394 846 388 840 396 L824 378 Z"
            fill="#ffffff"
            opacity="0.96"
          />
          <path d="M858 352 L892 352 L876 400 Z" fill="#dfe6fb" opacity="0.9" />
        </g>

        {/* town dots */}
        <g fill="#fff6e8" opacity="0.8">
          <circle cx="760" cy="588" r="2.2" /><circle cx="800" cy="592" r="1.8" />
          <circle cx="850" cy="590" r="2" /><circle cx="900" cy="594" r="1.6" />
          <circle cx="950" cy="590" r="2.1" /><circle cx="990" cy="596" r="1.5" />
        </g>

        {/* lake */}
        <rect x="0" y="600" width="1440" height="150" fill="url(#lakeGrad)" opacity="0.95" />
        <ellipse cx="871" cy="640" rx="120" ry="14" fill="#ffffff" opacity="0.35" />
        <ellipse cx="871" cy="665" rx="180" ry="10" fill="#ffd9e6" opacity="0.3" />
        {/* trees on lake edge */}
        <g>
          <ellipse cx="620" cy="600" rx="46" ry="26" fill="#3f5a44" />
          <ellipse cx="680" cy="596" rx="34" ry="22" fill="#4a6a4a" />
          <ellipse cx="1120" cy="602" rx="52" ry="24" fill="#3f5a44" />
          <ellipse cx="1180" cy="598" rx="30" ry="18" fill="#55704f" />
          <rect x="655" y="600" width="6" height="22" fill="#3a2a20" />
          <rect x="1148" y="602" width="7" height="24" fill="#3a2a20" />
        </g>

        {/* veranda floor */}
        <rect x="0" y="740" width="1440" height="160" fill="#3a241c" />
        <rect x="0" y="740" width="1440" height="10" fill="#6b4632" />
        <g stroke="#241512" strokeWidth="2" opacity="0.6">
          <line x1="0" y1="770" x2="1440" y2="770" />
          <line x1="0" y1="800" x2="1440" y2="800" />
          <line x1="0" y1="832" x2="1440" y2="832" />
        </g>
        {/* warm sun streak on floor */}
        <ellipse cx="520" cy="800" rx="320" ry="40" fill="#ffb98a" opacity="0.28" />
      </svg>

      {/* ── Sakura masses (CSS blobs) ───────────────────── */}
      <div className="absolute inset-0 pointer-events-none">
        {/* top canopy */}
        <div style={{
          position: 'absolute', top: '-8%', left: '-4%', width: '62%', height: '34%',
          background: 'radial-gradient(ellipse at 30% 40%, #ffc7de 0%, #f59ec4 34%, #d97fb0 55%, transparent 72%), radial-gradient(ellipse at 65% 25%, #ffd9e8 0%, #f2a8cc 45%, transparent 70%)',
          filter: 'blur(1px)', opacity: 0.95,
        }} />
        <div style={{
          position: 'absolute', top: '-6%', right: '-6%', width: '56%', height: '30%',
          background: 'radial-gradient(ellipse at 60% 40%, #ffc2da 0%, #ee93bd 40%, transparent 72%)',
          filter: 'blur(0.5px)', opacity: 0.95,
        }} />
        {/* left tree trunk + blossoms */}
        <div style={{
          position: 'absolute', top: '6%', left: '13%', width: '26px', height: '62%',
          background: 'linear-gradient(90deg, #241310, #5a3a2c, #241310)',
          borderRadius: 12, opacity: 0.95,
        }} />
        <div style={{
          position: 'absolute', top: '18%', left: '-6%', width: '34%', height: '44%',
          background: 'radial-gradient(ellipse at 45% 35%, #ffd3e4 0%, #f7a9cb 38%, #c97ba8 62%, transparent 74%)',
          filter: 'blur(0.5px)',
        }} />
        {/* blossom dot clusters for texture */}
        <SakuraDots />
      </div>

      {/* ── Wooden frame posts ──────────────────────────── */}
      <div className="absolute inset-0 pointer-events-none">
        <div style={{ position: 'absolute', top: 0, bottom: '12%', left: 0, width: 46, background: 'linear-gradient(90deg, #170c08 0%, #4a2d20 55%, #2c1a12 100%)', boxShadow: '8px 0 30px rgba(0,0,0,0.4)' }} />
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 26, background: 'linear-gradient(180deg, #3c2318, #241310)', opacity: 0.95 }} />
        {/* right post near chat panel */}
        <div style={{ position: 'absolute', top: 0, bottom: '12%', left: '59.5%', width: 22, background: 'linear-gradient(90deg, #1c0e0a, #5a3a2a, #241510)', boxShadow: '6px 0 24px rgba(0,0,0,0.45)' }} />
      </div>

      {/* ── Hanging lantern + plaque ────────────────────── */}
      <div className="absolute pointer-events-none" style={{ top: '2%', left: '66%', width: 90 }}>
        <div style={{ margin: '0 auto', width: 2, height: 46, background: '#1c0e0a' }} />
        <div style={{
          margin: '0 auto', width: 54, height: 54, borderRadius: '50%',
          background: 'radial-gradient(circle at 35% 30%, rgba(255,255,255,0.9) 0%, rgba(160,200,255,0.55) 30%, rgba(90,120,220,0.35) 60%, rgba(40,50,120,0.25) 100%)',
          border: '1.5px solid rgba(60,40,30,0.8)',
          boxShadow: '0 0 24px rgba(150,180,255,0.5), inset 0 0 12px rgba(255,255,255,0.5)',
        }} />
        <div style={{ margin: '2px auto 0', width: 8, height: 10, background: '#2c1a12', borderRadius: 2 }} />
        <div style={{
          margin: '6px auto 0', width: 44, height: 74, borderRadius: 4,
          background: 'linear-gradient(180deg, #f6e3d3, #e8c9b8)',
          border: '1px solid rgba(60,30,20,0.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          writingMode: 'vertical-rl', fontSize: 15, color: '#5a3a3a', letterSpacing: 4,
          boxShadow: '0 4px 14px rgba(0,0,0,0.35)',
        }}>
          またね♡
        </div>
      </div>

      {/* ── Warm sunlight wash + vignette ───────────────── */}
      <div className="absolute inset-0 pointer-events-none" style={{
        background: `
          radial-gradient(ellipse 60% 55% at 42% 58%, rgba(255, 190, 140, 0.28) 0%, transparent 65%),
          linear-gradient(180deg, transparent 55%, rgba(60, 20, 40, 0.22) 82%, rgba(20, 8, 24, 0.5) 100%)
        `,
      }} />
      <div className="absolute inset-0 pointer-events-none" style={{ boxShadow: 'inset 0 0 180px rgba(30, 10, 40, 0.45)' }} />

      {/* ── Foreground leaves bottom-left ───────────────── */}
      <div className="absolute pointer-events-none" style={{ left: '-30px', bottom: '8%', width: 220, height: 220, filter: 'blur(1.5px)', opacity: 0.9 }}>
        <div style={{ position: 'absolute', width: 90, height: 44, borderRadius: '50%', background: '#1d2f1e', transform: 'rotate(-24deg)', left: 20, top: 40 }} />
        <div style={{ position: 'absolute', width: 110, height: 50, borderRadius: '50%', background: '#243a24', transform: 'rotate(-12deg)', left: 60, top: 90 }} />
        <div style={{ position: 'absolute', width: 80, height: 40, borderRadius: '50%', background: '#16241a', transform: 'rotate(18deg)', left: 10, top: 130 }} />
      </div>

      {/* ── Petal canvas ────────────────────────────────── */}
      <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none" style={{ opacity: 0.9 }} />

      <style>{`
        @keyframes sway { 0%,100% { transform: translateX(0); } 50% { transform: translateX(6px); } }
      `}</style>
    </div>
  );
});

// Small deterministic blossom sparkle dots
function SakuraDots() {
  const dots = [
    { l: '6%', t: '8%', s: 9, o: 0.9 }, { l: '10%', t: '14%', s: 7, o: 0.8 },
    { l: '18%', t: '6%', s: 8, o: 0.85 }, { l: '26%', t: '12%', s: 6, o: 0.7 },
    { l: '34%', t: '5%', s: 10, o: 0.9 }, { l: '44%', t: '9%', s: 7, o: 0.75 },
    { l: '52%', t: '4%', s: 8, o: 0.8 }, { l: '60%', t: '10%', s: 6, o: 0.7 },
    { l: '70%', t: '6%', s: 9, o: 0.85 }, { l: '80%', t: '12%', s: 7, o: 0.8 },
    { l: '90%', t: '7%', s: 8, o: 0.85 }, { l: '4%', t: '28%', s: 7, o: 0.7 },
    { l: '12%', t: '34%', s: 9, o: 0.8 }, { l: '22%', t: '30%', s: 6, o: 0.65 },
  ];
  return (
    <>
      {dots.map((d, i) => (
        <div key={i} style={{
          position: 'absolute', left: d.l, top: d.t, width: d.s, height: d.s,
          borderRadius: '50%', background: '#ffe0ec', opacity: d.o,
          boxShadow: '0 0 8px rgba(255, 200, 220, 0.9)',
        }} />
      ))}
    </>
  );
}

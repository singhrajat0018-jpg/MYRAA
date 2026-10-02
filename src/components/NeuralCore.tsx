import React, { useEffect, useRef, useCallback } from "react";

interface NeuralCoreProps {
  state: "disconnected" | "connecting" | "listening" | "speaking" | "thinking" | "executing" | "researching" | "success" | "error" | "idle";
  themeColor: string;
  activeEmotion?: string;
  characterState: "idle" | "thinking" | "talking";
}

export const NeuralCore: React.FC<NeuralCoreProps> = ({
  state,
  themeColor,
  activeEmotion = "idle",
  characterState
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animationRef = useRef<number | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = canvas.width = canvas.offsetWidth;
    let height = canvas.height = canvas.offsetHeight;

    // Generate background particles
    // Performance optimization: reduce particle count
    const particles = Array.from({ length: 20 }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      speed: Math.random() * 0.5 + 0.2,
      size: Math.random() * 2 + 0.5,
      opacity: Math.random() * 0.6 + 0.2,
      colorShift: Math.random() * Math.PI * 2
    }));

    // Neural filament network points
    const filaments = Array.from({ length: 60 }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.2,
      vy: (Math.random() - 0.5) * 0.2,
      life: Math.random() * 100,
      maxLife: Math.random() * 100 + 50,
      connections: Array.from({ length: Math.floor(Math.random() * 2) + 1 }, () => ({
        target: Math.random() * 60,
        strength: Math.random()
      }))
    }));

    // Concentric rings
    const rings = Array.from({ length: 3 }, (_, i) => ({
      radius: 80 + (i * 40),
      segments: Math.floor(Math.random() * 6) + 4,
      rotation: Math.random() * Math.PI * 2,
      speed: (0.2 - i * 0.05) * (Math.random() > 0.5 ? 1 : -1),
      opacity: 0.3 + Math.random() * 0.2,
      brightness: 0.5 + Math.random() * 0.5
    }));

    // Central nucleus
    const nucleus = {
      x: width / 2,
      y: height / 2,
      baseRadius: 15,
      pulse: 0
    };

    // State-based parameters
    const getStateParams = () => {
      switch (state) {
        case "listening":
          return {
            particleActivity: 1.2,
            filamentActivity: 1.1,
            ringActivity: 1.0,
            nucleusPulse: 1.0,
            filamentBrightness: 1.2, // Increased cyan brightness for listening
            ringGaps: 0.3, // Fewer gaps in rings
            pulseIntensity: 1.0
          };
        case "speaking":
          return {
            particleActivity: 1.5,
            filamentActivity: 1.3,
            ringActivity: 1.2,
            nucleusPulse: 1.3,
            filamentBrightness: 1.5, // Bright cyan filaments
            ringGaps: 0.1, // Almost solid rings
            pulseIntensity: 1.5
          };
        case "thinking":
          return {
            particleActivity: 1.3,
            filamentActivity: 1.4, // High internal activity
            ringActivity: 1.3,
            nucleusPulse: 1.2,
            filamentBrightness: 1.3, // White-blue thinking pulses
            ringGaps: 0.2,
            pulseIntensity: 1.3
          };
        case "executing":
          return {
            particleActivity: 1.6, // Outward particles
            filamentActivity: 1.2,
            ringActivity: 1.4, // Strong ring pulses
            nucleusPulse: 1.1,
            filamentBrightness: 1.0,
            ringGaps: 0.15,
            pulseIntensity: 1.4,
            outwardPulse: 0.7 // Outward energy movement
          };
        case "researching":
          return {
            particleActivity: 1.1,
            filamentActivity: 1.1,
            ringActivity: 1.5, // Structured ring activity
            nucleusPulse: 1.0,
            filamentBrightness: 0.9,
            ringGaps: 0.4, // More gaps for data-like movement
            pulseIntensity: 0.9,
            researchPattern: 0.8 // Structured patterns
          };
        case "success":
          return {
            particleActivity: 1.8, // Expanding particles
            filamentActivity: 1.6, // Bright filaments
            ringActivity: 1.8, // Ring synchronization
            nucleusPulse: 2.0, // Big pulse
            filamentBrightness: 1.8,
            ringGaps: 0.05, // Nearly solid
            pulseIntensity: 2.0,
            successExpansion: 0.9 // Expanding energy
          };
        case "error":
          return {
            particleActivity: 0.9,
            filamentActivity: 0.8, // Reduced activity
            ringActivity: 0.9,
            nucleusPulse: 0.7,
            filamentBrightness: 0.6,
            ringGaps: 0.5,
            pulseIntensity: 0.6,
            errorFlash: 0.3 // Brief red tint (only for genuine errors)
          };
        case "connecting":
          return {
            particleActivity: 0.8,
            filamentActivity: 0.9,
            ringActivity: 1.1, // glitchy
            nucleusPulse: 0.8,
            filamentBrightness: 0.7,
            ringGaps: 0.6,
            pulseIntensity: 0.5,
            connectingGlitch: 0.9
          };
        default: // disconnected/idle
          return {
            particleActivity: 0.6,
            filamentActivity: 0.7,
            ringActivity: 0.8,
            nucleusPulse: 0.7,
            filamentBrightness: 0.8,
            ringGaps: 0.5,
            pulseIntensity: 0.6
          };
      }
    };

    const stateParams = getStateParams();

    const handleResize = () => {
      width = canvas.width = canvas.offsetWidth;
      height = canvas.height = canvas.offsetHeight;
    };

    window.addEventListener("resize", handleResize);

    // Moved drawing functions outside the render loop to avoid redefinition on every frame
    const drawFilament = (x1: number, y1: number, x2: number, y2: number, intensity: number, brightness: number) => {
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      // Electric cyan to white-blue gradient based on brightness
      const hueShift = brightness > 1.2 ? -10 : 0; // Shift toward white for brighter filaments
      const cyanIntensity = Math.min(0.8, intensity * 0.6 * brightness);
      ctx.strokeStyle = `rgba(0, 255, 255, ${cyanIntensity})`; // cyan
      ctx.lineWidth = intensity * 0.5 + 0.5;
      ctx.stroke();
    };

    const drawParticle = (x: number, y: number, size: number, opacity: number, hueShift: number = 0, activity: number = 1.0) => {
      ctx.beginPath();
      ctx.arc(x, y, size * activity, 0, Math.PI * 2);
      // Electric cyan to white-blue gradient
      const baseHue = 180 + hueShift; // Cyan base
      const lightness = 80 + opacity * 15 * activity;
      const alpha = opacity * 0.8 * activity;

      const gradient = ctx.createRadialGradient(x, y, 0, x, y, size * activity);
      gradient.addColorStop(0, `hsla(${baseHue}, 100%, ${lightness}%, ${alpha})`);
      gradient.addColorStop(1, `hsla(${baseHue}, 100%, ${Math.min(95, lightness + 5)}%, ${alpha * 0.3})`);
      ctx.fillStyle = gradient;
      ctx.fill();
    };

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      const time = performance.now() * 0.001;

      // Update and draw background particles
      particles.forEach(p => {
        p.y -= p.speed * stateParams.particleActivity;
        p.x += Math.sin(p.y * 0.01 + p.colorShift) * 0.3;

        // Outward movement for executing state
        if (state === "executing" && stateParams.outwardPulse) {
          const centerX = width / 2;
          const centerY = height / 2;
          const dx = p.x - centerX;
          const dy = p.y - centerY;
          const distance = Math.sqrt(dx * dx + dy * dy);
          if (distance > 10) {
            p.x += (dx / distance) * stateParams.outwardPulse * 0.5;
            p.y += (dy / distance) * stateParams.outwardPulse * 0.5;
          }
        }

        // Expanding particles for success
        if (state === "success" && stateParams.successExpansion) {
          const centerX = width / 2;
          const centerY = height / 2;
          const dx = p.x - centerX;
          const dy = p.y - centerY;
          const distance = Math.sqrt(dx * dx + dy * dy);
          const maxDistance = Math.max(width, height) * 0.5;
          if (distance < maxDistance) {
            p.x += (dx / distance) * stateParams.successExpansion * 0.3;
            p.y += (dy / distance) * stateParams.successExpansion * 0.3;
          }
        }

        if (p.y < -10) {
          p.y = height + Math.random() * 20;
          p.x = Math.random() * width;
        }

        drawParticle(p.x, p.y, p.size, p.opacity * stateParams.particleActivity, p.colorShift, 1.0);
      });

      // Update and draw filaments
      filaments.forEach(f => {
        // Update position with slight drift
        f.x += f.vx * stateParams.filamentActivity;
        f.y += f.vy * stateParams.filamentActivity;

        // Boundary checking
        if (f.x < 0 || f.x > width || f.y < 0 || f.y > height) {
          f.x = Math.random() * width;
          f.y = Math.random() * height;
        }

        // Life cycle
        f.life = (f.life + 0.5) % f.maxLife;
        const lifeIntensity = f.life / f.maxLife;

        // Draw connections
        f.connections.forEach(conn => {
          const target = filaments[Math.floor(conn.target)];
          const intensity = lifeIntensity * conn.strength * stateParams.filamentActivity;
          drawFilament(f.x, f.y, target.x, target.y, intensity, stateParams.filamentBrightness);
        });
      });

      // Update and draw rings
      rings.forEach(ring => {
        ring.rotation += ring.speed * 0.01 * stateParams.ringActivity;

        // Glitch effect for connecting state
        if (state === "connecting" && stateParams.connectingGlitch && Math.random() > stateParams.connectingGlitch) {
          ring.rotation += (Math.random() - 0.5) * 0.5;
        }

        const segments = ring.segments;
        const segmentAngle = (Math.PI * 2) / segments;

        for (let i = 0; i < segments; i++) {
          // Some rings have gaps/breaks based on state
          if (Math.random() > stateParams.ringGaps) continue; // Skip some segments for broken effect

          const angle1 = i * segmentAngle + ring.rotation;
          const angle2 = (i + 1) * segmentAngle + ring.rotation;

          // Some segments are arcs or dotted
          const useArc = Math.random() > 0.3;
          const useDotted = Math.random() > 0.8;

          // Calculate center coordinates once
          const centerX = width / 2;
          const centerY = height / 2;

          if (!useArc && !useDotted) {
            // Solid segment
            const x1 = centerX + Math.cos(angle1) * ring.radius;
            const y1 = centerY + Math.sin(angle1) * ring.radius;
            const x2 = centerX + Math.cos(angle2) * ring.radius;
            const y2 = centerY + Math.sin(angle2) * ring.radius;

            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.strokeStyle = `rgba(0, 255, 255, ${ring.opacity * ring.brightness * stateParams.ringActivity * stateParams.pulseIntensity})`;
            ctx.lineWidth = ring.brightness * 0.5 + 0.5;
            ctx.stroke();
          } else if (useDotted) {
            // Dotted segment
            const steps = 5;
            for (let j = 0; j < steps; j++) {
              const t = j / steps;
              const angle = angle1 + (angle2 - angle1) * t;
              const x = centerX + Math.cos(angle) * ring.radius;
              const y = centerY + Math.sin(angle) * ring.radius;

              if (Math.random() > 0.5) { // Only draw some dots
                drawParticle(x, y, 1.5, ring.opacity * ring.brightness * stateParams.ringActivity * stateParams.pulseIntensity * 0.7);
              }
            }
          }
        }
      });

      // Draw central nucleus
      nucleus.pulse = Math.sin(time * 0.5) * 0.3 + 0.7;
      const pulseRadius = nucleus.baseRadius * (0.7 + nucleus.pulse * 0.3 * stateParams.nucleusPulse);

      // Outer glow
      const glowGradient = ctx.createRadialGradient(
        nucleus.x, nucleus.y, 0,
        nucleus.x, nucleus.y, pulseRadius * 3
      );
      glowGradient.addColorStop(0, "rgba(255, 255, 255, 0.1)");
      glowGradient.addColorStop(0.5, "rgba(0, 255, 255, 0.05)");
      glowGradient.addColorStop(1, "rgba(0, 255, 255, 0)");

      // Add success expansion effect
      if (state === "success" && stateParams.successExpansion) {
        ctx.fillStyle = glowGradient;
        ctx.fillRect(0, 0, width, height);
      } else {
        ctx.fillStyle = glowGradient;
        ctx.fillRect(0, 0, width, height);
      }

      // Inner nucleus with state-based colors
      const nucleusGradient = ctx.createRadialGradient(
        nucleus.x, nucleus.y, 0,
        nucleus.x, nucleus.y, pulseRadius
      );

      // Base nucleus color (white-blue)
      let innerColor1 = "hsla(180, 100%, 95%, 0.9)";
      let innerColor2 = "hsla(180, 100%, 80%, 0.7)";
      let innerColor3 = "hsla(180, 100%, 60%, 0.2)";

      // State-based modifications
      if (state === "thinking") {
        // Brighter white-blue for thinking
        innerColor1 = "hsla(180, 100%, 98%, 0.95)";
        innerColor2 = "hsla(180, 100%, 85%, 0.8)";
        innerColor3 = "hsla(180, 100%, 65%, 0.3)";
      } else if (state === "success") {
        // Intense white-blue expanding to cyan for success
        innerColor1 = "hsla(180, 100%, 99%, 0.98)";
        innerColor2 = "hsla(180, 100%, 90%, 0.85)";
        innerColor3 = "hsla(180, 100%, 70%, 0.4)";
      } else if (state === "error") {
        // Dark red nucleus for error (brief)
        innerColor1 = "hsla(0, 80%, 70%, 0.7)";
        innerColor2 = "hsla(0, 80%, 50%, 0.5)";
        innerColor3 = "hsla(0, 80%, 30%, 0.1)";
      } else if (state === "executing") {
        // Electric cyan tint for executing
        innerColor1 = "hsla(180, 100%, 90%, 0.8)";
        innerColor2 = "hsla(180, 100%, 70%, 0.6)";
        innerColor3 = "hsla(180, 100%, 50%, 0.2)";
      }

      nucleusGradient.addColorStop(0, innerColor1);
      nucleusGradient.addColorStop(0.7, innerColor2);
      nucleusGradient.addColorStop(1, innerColor3);
      ctx.fillStyle = nucleusGradient;
      ctx.beginPath();
      ctx.arc(nucleus.x, nucleus.y, pulseRadius, 0, Math.PI * 2);
      ctx.fill();

      // Energy pulses from nucleus (occasional)
      if (Math.random() > 0.98) {
        const pulseCount = Math.floor(Math.random() * 3) + 1;
        for (let i = 0; i < pulseCount; i++) {
          const angle = Math.random() * Math.PI * 2;
          const length = Math.random() * 100 + 50;
          const x1 = nucleus.x + Math.cos(angle) * pulseRadius;
          const y1 = nucleus.y + Math.sin(angle) * pulseRadius;
          const x2 = nucleus.x + Math.cos(angle) * (pulseRadius + length);
          const y2 = nucleus.y + Math.sin(angle) * (pulseRadius + length);

          ctx.beginPath();
          ctx.moveTo(x1, y1);
          ctx.lineTo(x2, y2);
          ctx.strokeStyle = `rgba(255, 255, 255, ${0.3 + Math.random() * 0.4})`;
          ctx.lineWidth = 1 + Math.random() * 2;
          ctx.stroke();
        }
      }

      // Error flash effect (brief red tint)
      if (state === "error" && stateParams.errorFlash) {
        ctx.fillStyle = `rgba(255, 0, 0, ${stateParams.errorFlash * 0.2})`;
        ctx.fillRect(0, 0, width, height);
      }

      animationRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener("resize", handleResize);
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [state, themeColor, activeEmotion, characterState]);

  return (
    <div className="absolute inset-0 w-full h-full pointer-events-none">
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" />
    </div>
  );
};
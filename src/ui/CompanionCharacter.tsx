import React, { useMemo, useRef, useEffect } from 'react';
import type { AvatarMainState } from '../avatar/contracts';

// ============================================================================
// State → Glow Mapping (warm sunset tints to sit in scenic backdrop)
// ============================================================================

const STATE_AURA: Record<AvatarMainState, { color: string; glow: string; intensity: number }> = {
  IDLE:      { color: 'rgba(255, 190, 160, 0.65)', glow: 'rgba(255, 170, 150, 0.20)', intensity: 1 },
  LISTENING: { color: 'rgba(216, 180, 254, 0.85)', glow: 'rgba(192, 132, 252, 0.28)', intensity: 1.25 },
  THINKING:  { color: 'rgba(167, 139, 250, 0.8)',  glow: 'rgba(139, 92, 246, 0.26)',  intensity: 1.15 },
  WORKING:   { color: 'rgba(255, 200, 130, 0.8)',  glow: 'rgba(255, 180, 100, 0.26)',  intensity: 1.3 },
  SPEAKING:  { color: 'rgba(240, 171, 252, 0.85)', glow: 'rgba(240, 171, 252, 0.28)',  intensity: 1.25 },
  VERIFYING: { color: 'rgba(134, 239, 172, 0.75)', glow: 'rgba(74, 222, 128, 0.22)',   intensity: 1.1 },
  RECOVERY:  { color: 'rgba(255, 190, 120, 0.7)',  glow: 'rgba(255, 170, 0, 0.18)',    intensity: 1 },
  ERROR:     { color: 'rgba(251, 113, 133, 0.75)', glow: 'rgba(251, 113, 133, 0.22)',  intensity: 0.95 },
  RELAXED:   { color: 'rgba(255, 205, 180, 0.55)', glow: 'rgba(255, 190, 160, 0.14)',  intensity: 0.85 },
  SLEEPING:  { color: 'rgba(180, 170, 220, 0.45)', glow: 'rgba(150, 150, 200, 0.10)',  intensity: 0.6 },
};

// ============================================================================
// CompanionCharacter — warm anime portrait (reference: veranda sunset)
// Stylized bust: long dark hair, flower pin, off-shoulder knit, chin on hand.
//
// Living-portrait motion architecture (transform/opacity only, zero per-frame
// React state — blink & gaze are ref-driven schedulers):
//   .mc-torso    breathing              (4.7s, origin bottom)
//   .mc-head     irregular micro-rotate (non-harmonic keyframes, origin neck)
//   .mc-gaze     JS-scheduled saccades  (3.2–8.6s, 900ms ease transition)
//   .mc-lid      JS-scheduled blinks    (2.6–6.8s, ~130ms, 20% double-blink)
//   .mc-mouth    speech oscillation     (SPEAKING only; audio-drivable later
//                without redesign via --mouth-open on this element)
//   .mc-hairside secondary hair sway    (9.7s uneven keyframes)
// ============================================================================

export interface CompanionCharacterProps {
  state: AvatarMainState;
  expression?: string;
}

export const CompanionCharacter = React.memo(function CompanionCharacter({
  state,
}: CompanionCharacterProps) {
  const aura = useMemo(() => STATE_AURA[state] ?? STATE_AURA.IDLE, [state]);
  const svgRef = useRef<SVGSVGElement>(null);
  const gazeRef = useRef<SVGGElement>(null);

  // Irregular human timing — bounded-random intervals, never a fixed loop.
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    let alive = true;
    const timeouts: number[] = [];
    const schedule = (fn: () => void, minMs: number, maxMs: number) => {
      const id = window.setTimeout(() => {
        if (!alive) return;
        fn();
        schedule(fn, minMs, maxMs);
      }, minMs + Math.random() * (maxMs - minMs));
      timeouts.push(id);
    };
    // Blink (with occasional double-blink).
    schedule(() => {
      const svg = svgRef.current;
      if (!svg) return;
      svg.classList.add('mc-blinking');
      timeouts.push(window.setTimeout(() => svg.classList.remove('mc-blinking'), 130));
      if (Math.random() < 0.2) {
        timeouts.push(window.setTimeout(() => {
          if (!alive) return;
          svg.classList.add('mc-blinking');
          timeouts.push(window.setTimeout(() => svg.classList.remove('mc-blinking'), 110));
        }, 300));
      }
    }, 2600, 6800);
    // Gaze micro-saccade (drifts near center often — never a fixed pattern).
    schedule(() => {
      const g = gazeRef.current;
      if (!g) return;
      const dx = (Math.random() * 2 - 1) * 1.4;
      const dy = Math.random() * 1.8 - 0.7;
      g.style.transform = `translate(${dx.toFixed(2)}px, ${dy.toFixed(2)}px)`;
    }, 3200, 8600);
    return () => { alive = false; for (const t of timeouts) clearTimeout(t); };
  }, []);

  return (
    <div className="relative flex items-center justify-center" style={{ width: '100%', height: '100%' }}>
      {/* warm halo behind portrait */}
      <div
        className="absolute rounded-full"
        style={{
          width: '115%', aspectRatio: '1',
          background: `radial-gradient(circle, ${aura.glow} 0%, rgba(255,180,150,0.10) 45%, transparent 70%)`,
          filter: 'blur(30px)',
          transition: 'all 700ms ease',
        }}
      />

      <div style={{ width: '100%', height: '100%' }}>
        <svg
          ref={svgRef}
          data-state={state}
          viewBox="0 0 320 460"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          style={{ width: '100%', height: '100%', filter: `drop-shadow(0 18px 44px rgba(40,10,30,0.45)) drop-shadow(0 0 26px ${aura.color})` }}
        >
          <defs>
            <linearGradient id="mc-skin" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#fff0e2" />
              <stop offset="55%" stopColor="#ffdcc4" />
              <stop offset="100%" stopColor="#f2b79b" />
            </linearGradient>
            <linearGradient id="mc-hair" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#4a2f3d" />
              <stop offset="45%" stopColor="#33202e" />
              <stop offset="100%" stopColor="#1d1219" />
            </linearGradient>
            <linearGradient id="mc-hairHi" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#ff9e9e" stopOpacity="0" />
              <stop offset="55%" stopColor="#ffb98a" stopOpacity="0.55" />
              <stop offset="100%" stopColor="#ffd9c2" stopOpacity="0.75" />
            </linearGradient>
            <linearGradient id="mc-sweater" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#fbf7ff" />
              <stop offset="60%" stopColor="#e9defc" />
              <stop offset="100%" stopColor="#c9b3e8" />
            </linearGradient>
            <radialGradient id="mc-eye" cx="50%" cy="38%" r="65%">
              <stop offset="0%" stopColor="#3b2b4a" />
              <stop offset="45%" stopColor="#6d5aa8" />
              <stop offset="78%" stopColor="#a78bfa" />
              <stop offset="100%" stopColor="#2c2138" />
            </radialGradient>
            <radialGradient id="mc-blush" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#ff9db0" stopOpacity="0.75" />
              <stop offset="100%" stopColor="#ff9db0" stopOpacity="0" />
            </radialGradient>
            <filter id="mc-soft" x="-40%" y="-40%" width="180%" height="180%">
              <feGaussianBlur stdDeviation="6" />
            </filter>
          </defs>

          {/* ── back hair mass ── */}
          <path
            d="M58 148 C50 80 95 28 160 26 C228 24 268 82 262 150 L276 330 C278 380 250 420 160 428 C70 420 42 380 44 330 Z"
            fill="url(#mc-hair)"
          />
          {/* sunset rim on hair */}
          <path
            d="M250 60 C268 100 272 160 276 240"
            stroke="url(#mc-hairHi)" strokeWidth="7" strokeLinecap="round" opacity="0.9"
          />
          <path
            d="M70 90 C58 140 56 200 60 260"
            stroke="#f7a9cb" strokeWidth="4" strokeLinecap="round" opacity="0.45"
          />

          {/* ── torso (breathing group) ── */}
          <g className="mc-torso">
          {/* neck + shoulders */}
          <path d="M138 218 L138 252 C138 262 182 262 182 252 L182 218 Z" fill="url(#mc-skin)" />
          <path d="M138 228 C150 240 170 240 182 228 L182 244 C168 254 152 254 138 244 Z" fill="#e8a583" opacity="0.55" />
          {/* off-shoulder sweater body */}
          <path
            d="M52 330 C60 290 95 268 128 262 L192 262 C228 268 260 292 268 330 L282 430 C282 446 240 456 160 456 C80 456 38 446 38 430 Z"
            fill="url(#mc-sweater)"
          />
          {/* knit ribs */}
          <g stroke="#b9a3dd" strokeWidth="2" opacity="0.5">
            <path d="M78 320 L74 440" /><path d="M100 308 L98 448" />
            <path d="M242 320 L246 440" /><path d="M220 308 L222 448" />
          </g>
          {/* collar shadows */}
          <path d="M118 266 C140 280 180 280 202 266 C196 292 168 304 160 304 C152 304 124 292 118 266 Z" fill="#2c2138" opacity="0.85" />
          {/* black ribbon */}
          <g>
            <path d="M150 330 L160 312 L170 330 L160 348 Z" fill="#241a30" />
            <path d="M160 330 C145 322 132 326 128 338 C140 344 154 340 160 330 Z" fill="#33263f" />
            <path d="M160 330 C175 322 188 326 192 338 C180 344 166 340 160 330 Z" fill="#33263f" />
            <path d="M156 348 L152 380 M164 348 L168 380" stroke="#241a30" strokeWidth="5" strokeLinecap="round" />
          </g>
          {/* sleeve folds */}
          <path d="M52 330 C70 340 78 370 76 400" stroke="#a98fd4" strokeWidth="3" opacity="0.5" fill="none" />
          <path d="M268 330 C250 340 242 370 244 400" stroke="#ff9e7a" strokeWidth="3" opacity="0.45" fill="none" />
          </g>

          {/* ── head (micro-motion group; the hand follows the chin) ── */}
          <g className="mc-head">
          {/* face */}
          <ellipse cx="160" cy="158" rx="62" ry="72" fill="url(#mc-skin)" />
          {/* jaw softening */}
          <path d="M104 170 C112 208 134 228 160 230 C186 228 208 208 216 170 C210 200 188 218 160 218 C132 218 110 200 104 170 Z" fill="#f2b79b" opacity="0.5" />
          {/* blush */}
          <ellipse cx="118" cy="182" rx="16" ry="9" fill="url(#mc-blush)" />
          <ellipse cx="202" cy="182" rx="16" ry="9" fill="url(#mc-blush)" />
          {/* hand under chin (fist) */}
          <g>
            <ellipse cx="132" cy="252" rx="24" ry="28" fill="url(#mc-skin)" />
            <path d="M114 238 C120 232 140 232 148 240" stroke="#d99a7c" strokeWidth="2" opacity="0.7" fill="none" />
            <path d="M112 248 C120 243 142 243 150 249 M112 258 C122 253 142 253 150 259" stroke="#d99a7c" strokeWidth="1.6" opacity="0.6" />
            {/* sleeve cuff over wrist */}
            <path d="M96 300 C100 280 118 268 136 270 L150 292 C138 302 112 310 96 300 Z" fill="url(#mc-sweater)" stroke="#c9b3e8" strokeWidth="1.5" />
            <g stroke="#b9a3dd" strokeWidth="1.6" opacity="0.6">
              <path d="M108 284 L104 300" /><path d="M120 280 L117 298" /><path d="M132 280 L130 296" />
            </g>
          </g>

          {/* ── eyes ── */}
          <g>
            {/* eye whites */}
            <path d="M110 156 C116 144 138 142 146 154 C142 166 116 168 110 156 Z" fill="#ffffff" />
            <path d="M174 154 C182 142 204 144 210 156 C204 168 178 166 174 154 Z" fill="#ffffff" />
            {/* gaze layer — translated by the saccade scheduler */}
            <g ref={gazeRef} className="mc-gaze">
              <ellipse cx="129" cy="155" rx="10.5" ry="12" fill="url(#mc-eye)" />
              <circle cx="129" cy="157" r="4.6" fill="#1c1426" />
              <circle cx="132.5" cy="151" r="3" fill="#ffffff" opacity="0.95" />
              <circle cx="125" cy="160" r="1.4" fill="#ffd9e8" opacity="0.9" />
              <ellipse cx="191" cy="155" rx="10.5" ry="12" fill="url(#mc-eye)" />
              <circle cx="191" cy="157" r="4.6" fill="#1c1426" />
              <circle cx="194.5" cy="151" r="3" fill="#ffffff" opacity="0.95" />
              <circle cx="187" cy="160" r="1.4" fill="#ffd9e8" opacity="0.9" />
            </g>
            {/* lashes */}
            <path d="M108 154 C116 141 140 140 148 152" stroke="#241722" strokeWidth="3.4" strokeLinecap="round" fill="none" />
            <path d="M108 154 L102 150" stroke="#241722" strokeWidth="2.6" strokeLinecap="round" />
            <path d="M172 152 C180 140 204 141 212 154" stroke="#241722" strokeWidth="3.4" strokeLinecap="round" fill="none" />
            <path d="M212 154 L218 150" stroke="#241722" strokeWidth="2.6" strokeLinecap="round" />
            {/* brows */}
            <path d="M110 134 C122 130 138 130 148 135" stroke="#3a2530" strokeWidth="2.6" strokeLinecap="round" opacity="0.8" />
            <path d="M172 135 C182 130 198 130 210 134" stroke="#3a2530" strokeWidth="2.6" strokeLinecap="round" opacity="0.8" />
            {/* eyelids (blink) + closed-eye lash lines */}
            <ellipse className="mc-lid" cx="129" cy="154" rx="15" ry="12" fill="url(#mc-skin)" style={{ transformOrigin: '129px 142px' }} />
            <ellipse className="mc-lid" cx="191" cy="153" rx="15" ry="12" fill="url(#mc-skin)" style={{ transformOrigin: '191px 141px' }} />
            <path className="mc-lash-closed" d="M112 154 C120 160 140 160 147 153" stroke="#241722" strokeWidth="2.4" strokeLinecap="round" fill="none" />
            <path className="mc-lash-closed" d="M174 153 C182 159 202 159 209 152" stroke="#241722" strokeWidth="2.4" strokeLinecap="round" fill="none" />
          </g>
          {/* nose */}
          <path d="M160 168 C159 172 158 174 156 176" stroke="#d99a7c" strokeWidth="1.6" strokeLinecap="round" />
          {/* lips — speech-ready (later audio-drivable via --mouth-open) */}
          <g className="mc-mouth">
            <path d="M150 196 C155 200 165 200 170 196 C166 203 154 203 150 196 Z" fill="#c96a72" opacity="0.85" />
            <path d="M151 196 C156 198.5 164 198.5 169 196" stroke="#8a4450" strokeWidth="1.4" strokeLinecap="round" />
          </g>

            {/* front hair / bangs */}
            <path
              d="M96 120 C98 74 128 44 160 44 C194 44 222 76 224 120 C216 104 208 100 204 108 C200 96 190 92 186 102 C180 90 168 90 164 100 C158 88 146 90 142 100 C136 92 126 96 124 106 C118 102 106 108 96 120 Z"
              fill="url(#mc-hair)"
            />

            {/* flower hairpin */}
            <g transform="translate(222,108)">
            <g>
              <ellipse cx="0" cy="-9" rx="6.5" ry="9" fill="#fff6fa" stroke="#e8c9d8" strokeWidth="1" />
              <ellipse cx="8.5" cy="0" rx="6.5" ry="9" fill="#fff6fa" stroke="#e8c9d8" strokeWidth="1" transform="rotate(72 8.5 0)" />
              <ellipse cx="0" cy="9" rx="6.5" ry="9" fill="#fff6fa" stroke="#e8c9d8" strokeWidth="1" />
              <ellipse cx="-8.5" cy="0" rx="6.5" ry="9" fill="#fff6fa" stroke="#e8c9d8" strokeWidth="1" transform="rotate(72 -8.5 0)" />
              <circle cx="0" cy="0" r="4.4" fill="#ffd98a" stroke="#e8a54b" strokeWidth="1" />
            </g>
            </g>
          </g>

          {/* ── side strands over shoulders (secondary sway group) ── */}
          <g className="mc-hairside">
            <path d="M100 130 C92 190 88 250 96 310 C104 300 110 250 116 190 C118 160 110 140 100 130 Z" fill="url(#mc-hair)" />
            <path d="M220 130 C230 190 236 250 230 316 C254 300 262 240 258 180 C254 150 236 132 220 130 Z" fill="url(#mc-hair)" />
            <path d="M228 150 C238 200 240 260 234 310" stroke="url(#mc-hairHi)" strokeWidth="5" strokeLinecap="round" opacity="0.8" />
            <path d="M96 150 C90 200 90 250 96 296" stroke="#f7a9cb" strokeWidth="2.5" strokeLinecap="round" opacity="0.4" />
          </g>
        </svg>
      </div>

      <style>{`
        /* ── layered living-portrait motion (transform/opacity only) ── */
        .mc-torso { animation: mc-breathe 4.7s ease-in-out infinite; transform-origin: 160px 456px; }
        [data-state="SPEAKING"] .mc-torso, [data-state="LISTENING"] .mc-torso { animation-duration: 3.4s; }
        @keyframes mc-breathe { 0%, 100% { transform: scaleY(1); } 50% { transform: scaleY(1.014); } }

        .mc-head { animation: mc-head-idle 8.3s ease-in-out infinite; transform-origin: 160px 238px; }
        [data-state="LISTENING"] .mc-head { animation: mc-head-attentive 5.9s ease-in-out infinite; }
        [data-state="THINKING"] .mc-head { animation: mc-head-think 7.1s ease-in-out infinite; }
        [data-state="SPEAKING"] .mc-head { animation: mc-head-talk 3.7s ease-in-out infinite; }
        [data-state="WORKING"] .mc-head { animation: mc-head-talk 4.3s ease-in-out infinite; }
        /* Uneven keyframes → no obvious mechanical loop. */
        @keyframes mc-head-idle {
          0%, 100% { transform: rotate(0deg) translateY(0); }
          19% { transform: rotate(0.45deg) translateY(0.5px); }
          43% { transform: rotate(-0.2deg) translateY(0); }
          68% { transform: rotate(0.3deg) translateY(-0.5px); }
          87% { transform: rotate(-0.35deg) translateY(0); }
        }
        @keyframes mc-head-attentive {
          0%, 100% { transform: rotate(0deg) translateY(0); }
          25% { transform: rotate(0.5deg) translateY(-1px); }
          60% { transform: rotate(-0.25deg) translateY(-0.6px); }
        }
        /* Thinking: slow tilt with a held pause. */
        @keyframes mc-head-think {
          0%, 100% { transform: rotate(0deg); }
          30% { transform: rotate(-1.1deg); }
          55% { transform: rotate(-1.05deg); }
          82% { transform: rotate(0.2deg); }
        }
        @keyframes mc-head-talk {
          0%, 100% { transform: rotate(0deg) translateY(0); }
          30% { transform: rotate(0.35deg) translateY(-0.8px); }
          65% { transform: rotate(-0.3deg) translateY(-0.3px); }
        }

        .mc-hairside { animation: mc-hair-sway 9.7s ease-in-out infinite; transform-origin: 160px 128px; }
        @keyframes mc-hair-sway {
          0%, 100% { transform: rotate(0deg); }
          23% { transform: rotate(0.5deg); }
          51% { transform: rotate(-0.4deg); }
          79% { transform: rotate(0.25deg); }
        }

        .mc-gaze { transition: transform 900ms cubic-bezier(0.4, 0, 0.2, 1); }

        .mc-lid { transform: scaleY(0); transition: transform 80ms ease-in; }
        .mc-blinking .mc-lid { transform: scaleY(1); }
        .mc-lash-closed { opacity: 0; transition: opacity 60ms ease-in; }
        .mc-blinking .mc-lash-closed { opacity: 1; }

        /* Speech-ready mouth — later drivable by real audio timing via
           element.style.setProperty('--mouth-open', …) without redesign. */
        .mc-mouth { transform-box: fill-box; transform-origin: center; }
        [data-state="SPEAKING"] .mc-mouth { animation: mc-mouth-talk 0.34s ease-in-out infinite alternate; }
        @keyframes mc-mouth-talk {
          from { transform: scaleY(0.85); }
          to { transform: scaleY(1.3); }
        }

        @media (prefers-reduced-motion: reduce) {
          .mc-torso, .mc-head, .mc-hairside, .mc-mouth, .mc-lid, .mc-gaze, .mc-lash-closed {
            animation: none !important;
            transition: none !important;
          }
        }
      `}</style>
    </div>
  );
});

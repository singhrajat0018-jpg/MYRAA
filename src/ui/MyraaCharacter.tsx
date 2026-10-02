import React, { useMemo } from 'react';
import type { CSSProperties } from 'react';
import type { AvatarMainState } from '../avatar/contracts';
import { CompanionCharacter } from './CompanionCharacter';
import { resolveCharacterArt, useMyraaAssets } from './assets/myraaAssets';

// ============================================================================
// MyraaCharacter — production character asset slot.
//
// When `public/assets/myraa/character/myraa-<state>.webp` exists, the real
// production illustration is rendered with subtle whole-image living motion
// (breathing + irregular micro-sway — transform-only, no image warping).
//
// Flat-raster limitation (documented, not hidden): independent head / eyelid /
// gaze / mouth / hair motion requires LAYERED artwork. This component keeps
// the layer architecture ready (see public/assets/myraa/README.md) but does
// not fake body movement by distorting a single image.
//
// When assets are absent, the code-drawn SVG placeholder is used, which DOES
// have full layered motion (blinks, gaze, breathing, speech mouth).
// ============================================================================

const STATE_AURA: Partial<Record<AvatarMainState, string>> = {
  LISTENING: 'rgba(192, 132, 252, 0.20)',
  SPEAKING: 'rgba(240, 171, 252, 0.20)',
  THINKING: 'rgba(139, 92, 246, 0.18)',
  WORKING: 'rgba(255, 180, 100, 0.18)',
  ERROR: 'rgba(251, 113, 133, 0.18)',
};

export const MyraaCharacter = React.memo(function MyraaCharacter({
  state,
}: {
  state: AvatarMainState;
}) {
  const { status, manifest } = useMyraaAssets();
  const art = status === 'production' ? resolveCharacterArt(manifest, state) : null;

  const aura = useMemo(() => STATE_AURA[state] ?? null, [state]);

  if (!art) {
    // PLACEHOLDER — code-drawn SVG approximation with full layered motion.
    return <CompanionCharacter state={state} />;
  }

  const style: CSSProperties = aura ? { '--myraa-char-aura': aura } as CSSProperties : {};

  return (
    <div className="relative w-full h-full" style={style}>
      {/* Whole-image living motion — subtle, compositor-friendly.
          mc-img-breathe: continuous breathing (non-uniform scale <0.5%).
          mc-img-sway: irregular posture micro-adjustment (uneven keyframes).
          SPEAKING adds a gentle emphasis; reduced-motion disables all. */}
      <img
        src={art}
        alt="MYRAA"
        draggable={false}
        className="mc-img-live absolute inset-0 w-full h-full"
        style={{ objectFit: 'contain', objectPosition: 'center bottom', userSelect: 'none' }}
        data-state={state}
      />
      {aura && (
        <div
          className="absolute inset-x-[12%] bottom-0 h-[45%] pointer-events-none mc-img-aura"
          style={{
            background: 'radial-gradient(ellipse at 50% 100%, var(--myraa-char-aura), transparent 70%)',
            filter: 'blur(18px)',
          }}
        />
      )}
      <style>{`
        .mc-img-live { transform-origin: 50% 88%; will-change: transform; }
        .mc-img-live[data-state="SPEAKING"] { animation-duration: 4.1s; }
        .mc-img-live { animation: mc-img-breathe 5.3s ease-in-out infinite, mc-img-sway 13.7s ease-in-out infinite; }
        @keyframes mc-img-breathe {
          0%, 100% { transform: scale(1, 1); }
          50% { transform: scale(1.002, 1.006); }
        }
        @keyframes mc-img-sway {
          0%, 100% { translate: 0 0; }
          21% { translate: 1.5px 0; }
          47% { translate: -1px 0; }
          74% { translate: 0.5px -1px; }
          91% { translate: -0.5px 0; }
        }
        .mc-img-aura { transition: opacity 900ms ease; animation: mc-img-pulse 5.3s ease-in-out infinite; }
        @keyframes mc-img-pulse { 0%, 100% { opacity: 0.7; } 50% { opacity: 1; } }
        @media (prefers-reduced-motion: reduce) {
          .mc-img-live, .mc-img-aura { animation: none !important; }
        }
      `}</style>
    </div>
  );
});

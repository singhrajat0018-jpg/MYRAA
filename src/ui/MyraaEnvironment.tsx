import React from 'react';
import { CompanionBackground } from './CompanionBackground';
import { useMyraaAssets } from './assets/myraaAssets';

// ============================================================================
// MyraaEnvironment — production environment asset slot.
//
// When `public/assets/myraa/environment/myraa-environment.webp` exists it is
// rendered as the full-bleed scenic plate (with a restrained cinematic
// treatment). Otherwise the code-drawn SVG placeholder scene is used.
// ============================================================================

export const MyraaEnvironment = React.memo(function MyraaEnvironment() {
  const { status, manifest } = useMyraaAssets();

  if (status === 'production' && manifest.environment) {
    return (
      <div className="absolute inset-0 overflow-hidden" style={{ background: '#141020' }}>
        <img
          src={manifest.environment}
          alt=""
          aria-hidden="true"
          draggable={false}
          className="absolute inset-0 w-full h-full"
          style={{ objectFit: 'cover', objectPosition: '38% center', userSelect: 'none' }}
        />
        {/* Cinematic treatment: soft vignette + gentle bottom grounding so UI
            panels stay readable — intentionally restrained, no heavy blur. */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              'linear-gradient(180deg, rgba(20,10,30,0.12) 0%, transparent 30%, transparent 62%, rgba(20,8,24,0.38) 100%)',
            boxShadow: 'inset 0 0 160px rgba(25, 10, 35, 0.35)',
          }}
        />
      </div>
    );
  }

  // PLACEHOLDER — code-drawn SVG approximation, not the final visual design.
  return <CompanionBackground />;
});

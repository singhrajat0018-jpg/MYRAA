// ============================================================================
// MYRAA Production Asset Contract
// ----------------------------------------------------------------------------
// The reference-quality anime character and cinematic Japanese environment DO
// NOT exist in this repository. The code-drawn SVG scene is a PLACEHOLDER.
//
// This module defines the drop-in slots for the real production artwork.
// To install the final visuals, place files in `public/assets/myraa/`:
//
//   public/assets/myraa/
//     character/
//       myraa-idle.webp        (transparent background, required)
//       myraa-listening.webp   (optional — falls back to idle)
//       myraa-thinking.webp    (optional)
//       myraa-speaking.webp    (optional)
//       myraa-working.webp     (optional)
//       myraa-error.webp       (optional)
//     environment/
//       myraa-environment.webp (full-bleed scenic plate, required)
//
// Files are probed at runtime — adding artwork requires NO code change and
// NO rebuild (public/ assets are served as-is). Missing slots fall back to
// the code-drawn placeholder components automatically.
// ============================================================================

import { useEffect, useState } from 'react';
import type { AvatarMainState } from '../../avatar/contracts';

export interface MyraaAssetManifest {
  character: Partial<Record<AvatarMainState, string>>;
  environment: string | null;
}

interface AssetAvailability {
  character: Partial<Record<AvatarMainState, string>>;
  environment: string | null;
  anyFound: boolean;
}

const CHARACTER_SLOTS: Array<{ state: AvatarMainState; file: string }> = [
  { state: 'IDLE', file: 'myraa-idle.webp' },
  { state: 'LISTENING', file: 'myraa-listening.webp' },
  { state: 'THINKING', file: 'myraa-thinking.webp' },
  { state: 'SPEAKING', file: 'myraa-speaking.webp' },
  { state: 'WORKING', file: 'myraa-working.webp' },
  { state: 'ERROR', file: 'myraa-error.webp' },
];

const ENVIRONMENT_URL = '/assets/myraa/environment/myraa-environment.webp';
const characterUrl = (file: string) => `/assets/myraa/character/${file}`;

function probeImage(url: string): Promise<boolean> {
  return new Promise((resolve) => {
    const img = new Image();
    let settled = false;
    const done = (ok: boolean) => {
      if (!settled) {
        settled = true;
        img.onload = img.onerror = null;
        img.src = '';
        resolve(ok);
      }
    };
    img.onload = () => done(img.naturalWidth > 0);
    img.onerror = () => done(false);
    img.src = url;
    // Guard against hung probes (never block UI on a dead asset).
    window.setTimeout(() => done(false), 8000);
  });
}

// Probe once per app session; every consumer shares the result.
let availabilityPromise: Promise<AssetAvailability> | null = null;

function loadAvailability(): Promise<AssetAvailability> {
  if (!availabilityPromise) {
    availabilityPromise = (async () => {
      const envFound = await probeImage(ENVIRONMENT_URL);
      const character: Partial<Record<AvatarMainState, string>> = {};
      let idleFound = false;
      for (const slot of CHARACTER_SLOTS) {
        const url = characterUrl(slot.file);
        // Skip optional state variants if idle itself is missing.
        if (!idleFound && slot.state !== 'IDLE') continue;
        if (await probeImage(url)) {
          character[slot.state] = url;
          if (slot.state === 'IDLE') idleFound = true;
        }
      }
      const anyFound = envFound || idleFound;
      if (!anyFound) {
        console.info(
          '[MYRAA UI] Production artwork not found in /public/assets/myraa — ' +
            'rendering code-drawn placeholder. See public/assets/myraa/README.md ' +
            'for the required asset manifest.',
        );
      }
      return { character, environment: envFound ? ENVIRONMENT_URL : null, anyFound };
    })();
  }
  return availabilityPromise;
}

export type MyraaAssetStatus = 'checking' | 'placeholder' | 'production';

export interface MyraaAssets {
  status: MyraaAssetStatus;
  manifest: MyraaAssetManifest;
}

export function useMyraaAssets(): MyraaAssets {
  const [assets, setAssets] = useState<MyraaAssets>({
    status: 'checking',
    manifest: { character: {}, environment: null },
  });

  useEffect(() => {
    let alive = true;
    loadAvailability().then((avail) => {
      if (!alive) return;
      setAssets({
        status: avail.anyFound ? 'production' : 'placeholder',
        manifest: { character: avail.character, environment: avail.environment },
      });
    });
    return () => {
      alive = false;
    };
  }, []);

  return assets;
}

/** Resolve the best character art for a state (falls back to idle). */
export function resolveCharacterArt(
  manifest: MyraaAssetManifest,
  state: AvatarMainState,
): string | null {
  return (
    manifest.character[state] ??
    manifest.character.IDLE ??
    null
  );
}

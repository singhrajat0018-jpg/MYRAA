# MYRAA Production Artwork — Drop-in Assets

**The code-drawn SVG character/environment currently rendered by the app is a
PLACEHOLDER approximation. The reference-quality artwork does not yet exist in
this repository.** The app is architected so the real artwork can be installed
here without any code change and without a rebuild (Vite serves `public/` as-is).

## Required layout

```
public/assets/myraa/
├── character/
│   ├── myraa-idle.webp        REQUIRED — transparent background (PNG also OK)
│   ├── myraa-listening.webp   optional — falls back to idle
│   ├── myraa-thinking.webp    optional — falls back to idle
│   ├── myraa-speaking.webp    optional — falls back to idle
│   ├── myraa-working.webp     optional — falls back to idle
│   └── myraa-error.webp       optional — falls back to idle
└── environment/
    └── myraa-environment.webp REQUIRED — full-bleed scenic plate (16:9+)
```

## Character art specification (from the approved reference design)

- Detailed mature anime illustration (NOT chibi): long dark-brown hair with
  detailed strands, soft expressive eyes, warm gentle expression
- Light/off-white off-shoulder sweater, dark ribbon detail, small flower hair pin
- Natural human proportions, relaxed companion pose (chin-on-hand or similar)
- **Transparent background** so the character composites onto the environment
- Recommended resolution: ≥ 1200 px tall, WebP with alpha (PNG accepted)

## Environment art specification

- Japanese veranda/balcony, wooden architecture, cherry blossom, lake/valley,
  distant Mount-Fuji-style mountain, warm cinematic lighting
- Full-bleed plate; keep the visual focal point centered-left so the chat
  panel on the right does not cover important scenery
- Recommended: ≥ 2560 px wide WebP

## Layered artwork (optional, enables full living-character animation)

The runtime applies subtle whole-image motion (breathing scale, micro-sway) to
a flat raster. Realistic independent HEAD / EYES / EYELIDS / MOUTH / HAIR /
TORSO motion requires layered assets. If provided, extend
`src/ui/assets/myraaAssets.ts` and `src/ui/MyraaCharacter.tsx` with layer slots:

```
character/layers/
  hair-back.webp, torso.webp, head.webp, eyes.webp,
  eyelids.webp, mouth.webp, hair-front.webp
```

Once any file in this tree exists, the app automatically switches from the
placeholder to the production art on next launch.

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# ── Model Configuration ─────────────────────────────────────
# Centralized model routing for Ollama local-first architecture.
# Based on RTX 3050 4GB benchmark data (2026-08-31):
#
#   MODEL          WARM TTFT   WARM TOTAL   ROLE
#   llama3.2:3b    120ms       1.3s         VOICE_FAST (primary conversation)
#   qwen3:4b       332ms       13.7s        REASONING (complex tasks, coding)
#   gemma3:4b      534ms       1.3s         VISION (screenshots, images)
#   minimax:cloud  unverified  unverified   COMPLEX (cloud reasoning)
#   qwen3.5:4b     N/A         N/A          DISABLED (thinking model, empty on low VRAM)

GENERAL_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")   # Primary voice model
FALLBACK_MODEL = os.getenv("OLLAMA_FALLBACK_MODEL", "qwen3:4b")  # Fallback / reasoning
# Phase 29.8 audit: installed gemma3:4b reports NO vision capability.
# qwen3.5:4b is the only installed vision-capable model — routing vision
# here must never silently degrade to a text-only model.
VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "qwen3.5:4b")
COMPLEX_MODEL = os.getenv("OLLAMA_COMPLEX_MODEL", "minimax-m3:cloud")
LEGACY_MODEL = "qwen3.5:4b"

# Backward compatibility — existing code reads OLLAMA_MODEL
OLLAMA_MODEL = GENERAL_MODEL

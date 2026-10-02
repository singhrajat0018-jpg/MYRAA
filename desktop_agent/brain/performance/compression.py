"""Context compression for reducing token usage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class CompressionResult:
    original: str
    compressed: str
    original_tokens: int
    compressed_tokens: int
    strategy: str

    @property
    def ratio(self) -> float:
        return self.compressed_tokens / self.original_tokens if self.original_tokens else 0.0

    @property
    def saved_tokens(self) -> int:
        return self.original_tokens - self.compressed_tokens


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class ContextCompressor:
    def __init__(self, max_tokens: int = 4096):
        self._max_tokens = max_tokens

    def compress(self, text: str, budget_tokens: Optional[int] = None,
                 preserve_start: bool = True) -> CompressionResult:
        budget = budget_tokens or self._max_tokens
        orig_tokens = estimate_tokens(text)
        if orig_tokens <= budget:
            return CompressionResult(text, text, orig_tokens, orig_tokens, "none")
        target_chars = budget * 4
        if preserve_start:
            compressed = text[:target_chars - 20] + "\n[...compressed...]"
        else:
            compressed = text[-target_chars + 20:] + "\n[...compressed...]"
        comp_tokens = estimate_tokens(compressed)
        return CompressionResult(text, compressed, orig_tokens, comp_tokens, "truncation")

    def compress_screen_description(self, description: str,
                                    max_lines: int = 15) -> CompressionResult:
        orig_tokens = estimate_tokens(description)
        lines = description.strip().split("\n")
        if len(lines) <= max_lines:
            return CompressionResult(description, description, orig_tokens, orig_tokens, "none")
        compressed = "\n".join(lines[:max_lines]) + f"\n[{len(lines) - max_lines} more elements]"
        comp_tokens = estimate_tokens(compressed)
        return CompressionResult(description, compressed, orig_tokens, comp_tokens, "line_limit")

    def compress_conversation(self, messages: list[dict], max_turns: int = 5) -> str:
        if len(messages) <= max_turns:
            return "\n".join(f"{m.get('role','?')}: {m.get('content','')}" for m in messages)
        recent = messages[-max_turns:]
        header = f"[{len(messages) - max_turns} earlier messages omitted]\n"
        return header + "\n".join(f"{m.get('role','?')}: {m.get('content','')}" for m in recent)

    def compress_memory_entries(self, entries: list[dict], max_entries: int = 10) -> str:
        if len(entries) <= max_entries:
            return "\n".join(f"- {e.get('content','')}" for e in entries)
        top = sorted(entries, key=lambda e: e.get("relevance", 0), reverse=True)[:max_entries]
        return "\n".join(f"- {e.get('content','')}" for e in top)

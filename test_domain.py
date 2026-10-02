import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from desktop_agent.brain.ai.ai_manager import AIManager, TaskSignals

def main():
    ai_manager = AIManager()
    text = "send message to john"
    signals = ai_manager._extract_task_signals(text)
    print(f"Text: {text}")
    print(f"Entities: {signals.entities}")
    print(f"Action verbs: {signals.action}")
    print(f"Topic nouns: {signals.topic}")
    print(f"Object nouns: {signals.object}")
    print(f"Requested output nouns: {signals.requested_output}")
    print(f"Modality: {signals.modality}")
    print(f"Freshness: {signals.freshness}")
    print(f"Language: {signals.language}")
    print(f"Tool hints: {signals.tool_hints}")
    print(f"Context: {signals.context}")

    candidates = ai_manager._detect_domain_candidates(signals)
    print(f"\nNumber of domain candidates: {len(candidates)}")
    for c in candidates:
        print(f"Domain: {c.domain.name}, Confidence: {c.confidence:.4f}, Evidence: {c.evidence}")

if __name__ == "__main__":
    main()
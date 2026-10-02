import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from desktop_agent.brain.ai.ai_manager import AIManager

def debug_request(ai_manager, text):
    print(f"\n=== Request: '{text}' ===")
    signals = ai_manager._extract_task_signals(text)
    print(f"Signals:")
    print(f"  entities: {signals.entities}")
    print(f"  action: {signals.action}")
    print(f"  topic: {signals.topic}")
    print(f"  object: {signals.object}")
    print(f"  output: {signals.requested_output}")
    print(f"  modality: {signals.modality}")
    print(f"  freshness: {signals.freshness}")
    print(f"  language: {signals.language}")
    print(f"  tool_hints: {signals.tool_hints}")

    candidates = ai_manager._detect_domain_candidates(signals)
    print(f"\nDomain candidates (sorted by confidence):")
    for c in candidates:
        print(f"  {c.domain.name}: {c.confidence:.4f}")
        print(f"    lexical: {c.lexical_score:.4f}")
        print(f"    entity: {c.entity_score:.4f}")
        print(f"    action: {c.action_fit:.4f}")
        print(f"    topic: {c.topic_fit:.4f}")
        print(f"    object: {c.object_fit:.4f}")
        print(f"    output: {c.output_fit:.4f}")
        print(f"    modality: {c.modality_fit:.4f}")
        print(f"    evidence: {c.evidence}")

def main():
    ai_manager = AIManager()
    requests = [
        "send message to john",
        "make a presentation about ai",
        "website banao",
        "take a screenshot",
        "explain how photosynthesis works",
        "close chrome",
        "create a document for project proposal",
    ]
    for req in requests:
        debug_request(ai_manager, req)

if __name__ == "__main__":
    main()
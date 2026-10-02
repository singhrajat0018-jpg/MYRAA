import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from desktop_agent.brain.ai.ai_manager import AIManager

def main():
    ai_manager = AIManager()
    text = "send message to john"
    # Extract signals first
    signals = ai_manager._extract_task_signals(text)
    # Get domain candidates
    candidates = ai_manager._detect_domain_candidates(signals)
    if not candidates:
        domain = ai_manager.domain.__class__.GENERAL  # Fallback
        domain_confidence = 0.0
    else:
        best = max(candidates, key=lambda x: x.confidence)
        domain = best.domain
        domain_confidence = best.confidence
    print(f"Domain: {domain.name}, Confidence: {domain_confidence}")
    intent, confidence = ai_manager._detect_intent(text, domain, domain_confidence)
    print(f"Intent: {intent.name}, Confidence: {confidence}")

if __name__ == "__main__":
    main()
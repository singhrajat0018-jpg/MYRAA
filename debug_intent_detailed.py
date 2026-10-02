import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from desktop_agent.brain.ai.ai_manager import AIManager

def main():
    ai_manager = AIManager()
    text = "send message to john"
    print(f"Text: {text}")

    # Extract signals
    signals = ai_manager._extract_task_signals(text)
    print(f"Signals: entities={signals.entities}, action={signals.action}, topic={signals.topic}, object={signals.object}, output={signals.requested_output}, modality={signals.modality}")

    # Get domain candidates
    candidates = ai_manager._detect_domain_candidates(signals)
    print(f"\nDomain candidates:")
    for c in candidates:
        print(f"  {c.domain.name}: confidence={c.confidence:.4f}")

    # Select best domain
    best_domain_candidate = max(candidates, key=lambda x: x.confidence)
    domain = best_domain_candidate.domain
    domain_confidence = best_domain_candidate.confidence
    print(f"\nSelected domain: {domain.name} with confidence {domain_confidence:.4f}")

    # Detect intent
    intent, confidence = ai_manager._detect_intent(text, domain, domain_confidence)
    print(f"\nDetected intent: {intent.name} with confidence {confidence:.4f}")

    # Let's also compute the intent scores manually to see what's happening
    text_lower = text.lower()
    intent_scores = {}

    # Step 1: Pattern-based scoring
    for intent_enum, patterns in ai_manager._intent_patterns.items():
        score = 0
        for pattern in patterns:
            if ai_manager._matches_pattern(text_lower, pattern):
                score += 1
        if score > 0:
            normalized_score = score / len(patterns)
            intent_scores[intent_enum] = normalized_score

    print(f"\nIntent scores before domain boost:")
    for intent_enum, score in sorted(intent_scores.items(), key=lambda x: x[1], reverse=True):
        if score > 0:
            print(f"  {intent_enum.name}: {score:.4f}")

    # Step 2: Apply domain-specific intent boost
    if domain in ai_manager._domain_specific_intents_map and domain_confidence > 0.05:
        specific_intents = ai_manager._domain_specific_intents_map[domain]
        boost_factor = 3.0  # Current boost factor
        print(f"\nApplying domain-specific boost for domain {domain.name} with boost_factor {boost_factor}")
        for specific_intent in specific_intents:
            original_score = intent_scores.get(specific_intent, 0.0)
            if original_score > 0:
                boosted_score = original_score * (1.0 + boost_factor * domain_confidence)
            else:
                boosted_score = original_score + (domain_confidence * 0.3)
            intent_scores[specific_intent] = boosted_score
            print(f"  {specific_intent.name}: original={original_score:.4f}, boosted={boosted_score:.4f}")

    print(f"\nIntent scores after domain boost:")
    for intent_enum, score in sorted(intent_scores.items(), key=lambda x: x[1], reverse=True):
        if score > 0:
            print(f"  {intent_enum.name}: {score:.4f}")

    # Select best intent
    if intent_scores:
        best_intent = max(intent_scores, key=intent_scores.get)
        confidence = intent_scores[best_intent]
        print(f"\nBest intent: {best_intent.name} with confidence {confidence:.4f}")
    else:
        print("\nNo intent scores found.")

if __name__ == "__main__":
    main()
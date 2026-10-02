import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from desktop_agent.brain.ai.ai_manager import AIManager

def main():
    ai_manager = AIManager()
    user_prompt = "send message to john"
    system_prompt = ""
    context = {
        'user_prompt': user_prompt,
        'system_prompt': system_prompt,
        'combined_text': f"{system_prompt} {user_prompt}".strip(),
        'task': None
    }
    print(f"Combined text: {context['combined_text']}")
    signals = ai_manager._extract_task_signals(context['combined_text'])
    print(f"Signals: entities={signals.entities}, action={signals.action}, topic={signals.topic}, object={signals.object}, output={signals.requested_output}, modality={signals.modality}")
    domain_candidates = ai_manager._detect_domain_candidates(signals)
    print(f"Number of domain candidates: {len(domain_candidates)}")
    for c in domain_candidates:
        print(f"Domain: {c.domain.name}, Confidence: {c.confidence:.4f}, Evidence: {c.evidence}")
    best_domain_candidate = max(domain_candidates, key=lambda x: x.confidence)
    print(f"Best domain: {best_domain_candidate.domain.name}, Confidence: {best_domain_candidate.confidence:.4f}")

if __name__ == "__main__":
    main()
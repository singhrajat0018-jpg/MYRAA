import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from desktop_agent.brain.ai.ai_manager import AIManager, Intent, Domain

def load_held_out(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def convert_string_to_enum(value, enum_class):
    try:
        return enum_class[value.upper()]
    except KeyError:
        try:
            return enum_class[value]
        except KeyError:
            return list(enum_class)[0]

def main():
    held_out_data = load_held_out("validation_benchmark/held_out.json")
    ai_manager = AIManager()

    wrong_intent = []
    wrong_domain = []

    for i, item in enumerate(held_out_data):
        expected_intent = convert_string_to_enum(item['intent'], Intent)
        expected_domain = convert_string_to_enum(item['domain'], Domain)

        route = ai_manager.route(
            user_prompt=item['request'],
            system_prompt="",
            task=None
        )

        if route.intent != expected_intent:
            wrong_intent.append((i, item['request'], expected_intent, route.intent, route.domain, expected_domain))
        if route.domain != expected_domain:
            wrong_domain.append((i, item['request'], expected_domain, route.domain, route.intent, expected_intent))

    print(f"Total items: {len(held_out_data)}")
    print(f"Wrong intent: {len(wrong_intent)}")
    print(f"Wrong domain: {len(wrong_domain)}")

    # Print first 5 wrong intent cases
    print("\nFirst 5 wrong intent cases:")
    for i, req, exp_int, act_int, act_dom, exp_dom in wrong_intent[:5]:
        print(f"  Request: {req}")
        print(f"    Expected intent: {exp_int.name}, Actual intent: {act_int.name}")
        print(f"    Expected domain: {exp_dom.name}, Actual domain: {act_dom.name}")
        print()

    # Print first 5 wrong domain cases
    print("\nFirst 5 wrong domain cases:")
    for i, req, exp_dom, act_dom, act_int, exp_int in wrong_domain[:5]:
        print(f"  Request: {req}")
        print(f"    Expected domain: {exp_dom.name}, Actual domain: {act_dom.name}")
        print(f"    Expected intent: {exp_int.name}, Actual intent: {act_int.name}")
        print()

if __name__ == "__main__":
    main()
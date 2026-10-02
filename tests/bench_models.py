"""Phase 5 model benchmarks — Ollama/MiniMax-M3, NIM, Gemini."""
import sys, os, time, statistics
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
# Load .env settings first
from desktop_agent.config.settings import *  # noqa

import requests

PROMPTS = {
    'simple': 'Say hello in 3 words.',
    'reasoning': 'If all cats are animals and some animals are fast, are some cats fast? Explain in 2 sentences.',
    'coding': 'Write a Python function to check if a number is prime.',
    'design': 'Design a futuristic bike in 3 sentences.',
    'tool_planning': 'I want to open YouTube and search for AI news. What steps would you take?',
    'research': 'Summarize the key differences between React and Vue in 3 bullet points.',
    'long_context': 'Explain machine learning in detail, covering supervised, unsupervised, and reinforcement learning with examples for each.',
}

NIM_BASE = 'https://integrate.api.nvidia.com/v1'
NIM_MODELS = [
    ('nvidia/nemotron-3-super-120b-a12b', 'Nemotron3Super'),
    ('meta/llama-3.1-8b-instruct', 'Llama31_8B'),
]


def bench_ollama(prompt, timeout=90):
    try:
        from desktop_agent.brain.ai.providers.ollama_provider import OllamaProvider
        p = OllamaProvider()
        if not p.available():
            return None
        start = time.time()
        resp = p.generate('You are MYRAA.', prompt, timeout=timeout)
        elapsed = time.time() - start
        return {'latency': elapsed, 'ok': True, 'tokens': len(resp.split())}
    except Exception as e:
        return {'latency': time.time() - start, 'ok': False, 'error': str(e)[:100]}


def bench_nim(model, prompt, api_key, timeout=60):
    try:
        start = time.time()
        r = requests.post(
            f'{NIM_BASE}/chat/completions',
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'},
            json={
                'model': model,
                'messages': [
                    {'role': 'system', 'content': 'You are MYRAA.'},
                    {'role': 'user', 'content': prompt},
                ],
                'max_tokens': 300,
                'temperature': 0.1,
            },
            timeout=timeout,
        )
        elapsed = time.time() - start
        if r.status_code == 200:
            data = r.json()
            content = data['choices'][0]['message']['content']
            usage = data.get('usage', {})
            return {'latency': elapsed, 'ok': True, 'tokens': len(content.split()),
                    'input_tokens': usage.get('prompt_tokens', 0),
                    'output_tokens': usage.get('completion_tokens', 0)}
        else:
            return {'latency': elapsed, 'ok': False, 'error': f'{r.status_code}: {r.text[:80]}'}
    except Exception as e:
        return {'latency': time.time() - start, 'ok': False, 'error': str(e)[:100]}


def bench_gemini(prompt, timeout=60):
    try:
        from desktop_agent.brain.ai.providers.gemini_provider import GeminiProvider
        p = GeminiProvider()
        if not p.available():
            return None
        start = time.time()
        resp = p.generate('You are MYRAA.', prompt, timeout=timeout)
        elapsed = time.time() - start
        return {'latency': elapsed, 'ok': True, 'tokens': len(resp.split())}
    except Exception as e:
        return {'latency': time.time() - start, 'ok': False, 'error': str(e)[:100]}


def main():
    api_key = os.getenv('NVIDIA_API_KEY', '')
    results = {}

    print('=' * 60)
    print('PHASE 5 MODEL BENCHMARKS')
    print('=' * 60)

    # Ollama
    print('\n--- Ollama / MiniMax-M3 ---')
    for task, prompt in PROMPTS.items():
        r = bench_ollama(prompt)
        if r is None:
            print(f'  {task}: UNAVAILABLE')
        elif r['ok']:
            print(f'  {task}: {r["latency"]:.1f}s, ~{r["tokens"]} tokens')
        else:
            print(f'  {task}: FAILED - {r["error"][:60]}')
        results[f'ollama_{task}'] = r

    # NIM models
    for model_id, model_name in NIM_MODELS:
        print(f'\n--- NIM / {model_name} ---')
        for task, prompt in PROMPTS.items():
            r = bench_nim(model_id, prompt, api_key)
            if r is None:
                print(f'  {task}: UNAVAILABLE')
            elif r['ok']:
                print(f'  {task}: {r["latency"]:.1f}s, ~{r["tokens"]} tokens')
            else:
                print(f'  {task}: FAILED - {r["error"][:60]}')
            results[f'nim_{model_name}_{task}'] = r

    # Gemini
    print('\n--- Gemini ---')
    for task, prompt in list(PROMPTS.items())[:3]:
        r = bench_gemini(prompt)
        if r is None:
            print(f'  {task}: UNAVAILABLE (quota?)')
        elif r['ok']:
            print(f'  {task}: {r["latency"]:.1f}s, ~{r["tokens"]} tokens')
        else:
            print(f'  {task}: FAILED - {r["error"][:60]}')
        results[f'gemini_{task}'] = r

    # Summary table
    print('\n' + '=' * 60)
    print('BENCHMARK SUMMARY')
    print('=' * 60)
    print(f'{"Task":<20} {"Ollama":<15} {"Nemotron3S":<15} {"Llama31_8B":<15} {"Gemini":<15}')
    print('-' * 80)
    for task in PROMPTS:
        vals = []
        for prefix in ['ollama', 'nim_Nemotron3Super', 'nim_Llama31_8B', 'gemini']:
            key = f'{prefix}_{task}'
            r = results.get(key)
            if r is None:
                vals.append('N/A')
            elif r.get('ok'):
                vals.append(f'{r["latency"]:.1f}s')
            else:
                vals.append('FAIL')
        print(f'{task:<20} {vals[0]:<15} {vals[1]:<15} {vals[2]:<15} {vals[3]:<15}')


if __name__ == '__main__':
    main()

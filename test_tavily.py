import os

from desktop_agent.brain.knowledge.intelligence.knowledge_request import KnowledgeRequest
from desktop_agent.brain.knowledge.providers.tavily_provider import TavilyProvider

# Credential sourced from the environment only — never hardcoded/committed.
# Skip the live call when the key is not present.
API_KEY = os.environ.get("TAVILY_API_KEY", "")

if not API_KEY:
    raise SystemExit("TAVILY_API_KEY not set — refusing to run a live Tavily call.")

tavily_provider = TavilyProvider(
    api_key=API_KEY,
)

request = KnowledgeRequest(
    query="Latest NVIDIA AI news",
    realtime=True,
    max_sources=5,
)

result = tavily_provider.search(request)

print("Success:", result.success)
print("Answer:", result.answer)
print("Success:", result.success)
print("Answer:", result.answer)
print("Metadata:", result.metadata)

if result.sources:
    print("\nSources:")
    for source in result.sources:
        print(source.title)
        print(source.url)

print("\nSources:")
for source in result.sources:
    print("-", source.title)
    print(" ", source.url)
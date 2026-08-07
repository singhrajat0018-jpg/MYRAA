from desktop_agent.brain.knowledge.intelligence.knowledge_request import KnowledgeRequest
from desktop_agent.brain.knowledge.providers.tavily_provider import TavilyProvider

# IMPORTANT:
# Replace with your configuration system later.
API_KEY = "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"

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
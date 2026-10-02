"""Quick Phase 6 FastCore classification test."""
import sys
sys.path.insert(0, ".")

from desktop_agent.fastcore.classifier import FastCoreClassifier


def test_weather_classification():
    c = FastCoreClassifier()
    cases = [
        ("weather bata", "weather_task"),
        ("mere yaha mausam kaisa hai", "weather_task"),
        ("Delhi weather", "weather_task"),
        ("kal baarish hogi", "weather_task"),
        ("temperature kitna hai", "weather_task"),
        ("will it rain today", "weather_task"),
        ("aaj baarish hogi", "weather_task"),
        ("weather kaisa hai", "weather_task"),
    ]
    for text, expected in cases:
        r = c.classify(text)
        assert r.task_type.value == expected, f"'{text}' -> {r.task_type.value}, expected {expected}"


def test_news_classification():
    c = FastCoreClassifier()
    cases = [
        ("aaj ki news bata", "news_task"),
        ("latest tech news", "news_task"),
        ("India ki latest news", "news_task"),
        ("AI ki latest news", "news_task"),
        ("what is happening in the world", "news_task"),
        ("latest news", "news_task"),
        ("breaking news", "news_task"),
    ]
    for text, expected in cases:
        r = c.classify(text)
        assert r.task_type.value == expected, f"'{text}' -> {r.task_type.value}, expected {expected}"


def test_existing_classification_unchanged():
    c = FastCoreClassifier()
    cases = [
        ("what is python", "direct_knowledge"),
        ("open notepad", "desktop_action"),
        ("search for python docs", "web_research"),
        ("hello", "conversation"),
        ("good morning", "conversation"),
        ("bye", "conversation"),
        ("write a python script", "coding_task"),
        ("nifty kitna hai", "trading_task"),
    ]
    for text, expected in cases:
        r = c.classify(text)
        assert r.task_type.value == expected, f"'{text}' -> {r.task_type.value}, expected {expected}"


def test_fastcore_latency():
    import time
    c = FastCoreClassifier()
    times = []
    for _ in range(100):
        t0 = time.perf_counter()
        c.classify("what is the weather today")
        times.append((time.perf_counter() - t0) * 1000)
    avg = sum(times) / len(times)
    p50 = sorted(times)[50]
    assert avg < 5.0, f"Average latency {avg:.2f}ms exceeds 5ms target"
    assert p50 < 3.0, f"P50 latency {p50:.2f}ms exceeds 3ms target"


def test_weather_provider_extract_city():
    sys.path.insert(0, ".")
    from desktop_agent.intelligence.weather_provider import WeatherProvider
    wp = WeatherProvider()
    assert wp.extract_city_from_query("Delhi weather").lower() == "delhi"
    assert wp.extract_city_from_query("weather in Mumbai").lower() == "mumbai"
    assert wp.extract_city_from_query("weather bata") is None


def test_news_provider_query_build():
    sys.path.insert(0, ".")
    from desktop_agent.intelligence.news_provider import NewsProvider
    np = NewsProvider()
    q = np._build_query("aaj ki tech news bata")
    assert "news" in q.lower()
    cat = np._extract_category("latest AI news")
    assert cat == "technology"

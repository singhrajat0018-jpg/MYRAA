"""MYRAA Weather Provider — Open-Meteo (free, no API key).

Fetches real-time weather data from Open-Meteo API.
Supports current location (lat/lon), city name fallback, and Hindi/Hinglish queries.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import requests

log = logging.getLogger(__name__)

# WMO weather code mappings
WMO_CODES: Dict[int, str] = {
    0: "Clear Sky", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Foggy", 48: "Rime Fog", 51: "Light Drizzle", 53: "Moderate Drizzle",
    55: "Dense Drizzle", 61: "Slight Rain", 63: "Moderate Rain", 65: "Heavy Rain",
    71: "Slight Snow", 73: "Moderate Snow", 75: "Heavy Snow", 80: "Slight Showers",
    81: "Moderate Showers", 82: "Violent Showers", 95: "Thunderstorm",
    96: "Thunderstorm + Hail", 99: "Thunderstorm + Heavy Hail",
}

WMO_HINDI: Dict[int, str] = {
    0: "Saaf aasmaan", 1: "Zyada tar saaf", 2: "Aadhe baadal", 3: "Baadalon se bhara",
    45: "Kohra", 48: "Kohra", 51: "Halki boondabaanee", 53: "Dheemi boondabaanee",
    55: "Tez boondabaanee", 61: "Halki baarish", 63: "Dheemi baarish", 65: "Bhaari baarish",
    71: "Halki barfbaanee", 73: "Dheemi barfbaanee", 75: "Bhaari barfbaanee",
    80: "Halki bauchhaar", 81: "Dheemi bauchhaar", 82: "Tez bauchhaar",
    95: "Toofaan", 96: "Toofaan + olaa", 99: "Toofaan + bhaari olaa",
}

# City name to coordinates (fallback when geolocation unavailable)
CITY_COORDS: Dict[str, tuple[float, float]] = {
    "delhi": (28.6139, 77.2090),
    "new delhi": (28.6139, 77.2090),
    "mumbai": (19.0760, 72.8777),
    "bangalore": (12.9716, 77.5946),
    "bengaluru": (12.9716, 77.5946),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
    "hyderabad": (17.3850, 78.4867),
    "pune": (18.5204, 73.8567),
    "ahmedabad": (23.0225, 72.5714),
    "jaipur": (26.9124, 75.7873),
    "gurugram": (28.4595, 77.0266),
    "gurgaon": (28.4595, 77.0266),
    "noida": (28.5355, 77.3910),
    "faridabad": (28.4089, 77.3178),
    "ghaziabad": (28.6692, 77.4538),
    "agra": (27.1767, 78.0081),
    "lucknow": (26.8467, 80.9462),
    "kanpur": (26.4499, 80.3319),
    "nagpur": (21.1458, 79.0882),
    "indore": (22.7196, 75.8577),
    "bhopal": (23.2599, 77.4126),
    "patna": (25.6093, 85.1376),
    "raipur": (21.2514, 81.6296),
    "chandigarh": (30.7333, 76.7794),
    "srinagar": (34.0837, 74.7973),
    "dehradun": (30.3165, 78.0322),
    " shimla": (31.1048, 77.1734),
    "manali": (32.2432, 77.1892),
    "goa": (15.2993, 74.1240),
    "coorg": (12.4244, 75.7382),
    "mysore": (12.2958, 76.6394),
    "ooty": (11.4102, 76.6950),
    "kochi": (9.9312, 76.2673),
    "trivandrum": (8.5241, 76.9366),
    "usa": (37.0902, -95.7129),
    "uk": (51.5074, -0.1278),
    "london": (51.5074, -0.1278),
    "new york": (40.7128, -74.0060),
    "san francisco": (37.7749, -122.4194),
    "tokyo": (35.6762, 139.6503),
}


@dataclass
class WeatherData:
    """Structured weather data."""
    temp: Optional[float] = None
    feels_like: Optional[float] = None
    humidity: Optional[int] = None
    wind_speed: Optional[float] = None
    condition: str = "Unknown"
    condition_hindi: str = ""
    icon: str = ""
    lat: float = 0.0
    lon: float = 0.0
    location_name: str = ""
    source: str = "open-meteo"
    timestamp: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "temp": self.temp,
            "feels_like": self.feels_like,
            "humidity": self.humidity,
            "wind_speed": self.wind_speed,
            "condition": self.condition,
            "condition_hindi": self.condition_hindi,
            "icon": self.icon,
            "lat": self.lat,
            "lon": self.lon,
            "location_name": self.location_name,
            "source": self.source,
            "timestamp": self.timestamp,
            "error": self.error,
        }

    def to_natural_response(self, lang: str = "en") -> str:
        """Generate a natural language weather response."""
        if self.error:
            return f"Weather data unavailable: {self.error}"

        if self.temp is None:
            return "Weather data unavailable right now."

        temp_str = f"{round(self.temp)}°C"
        feels_str = f"{round(self.feels_like)}°C" if self.feels_like else ""
        humidity_str = f"{self.humidity}%" if self.humidity else ""
        wind_str = f"{round(self.wind_speed)} km/h" if self.wind_speed else ""

        if lang == "hi" or lang == "hi-en":
            # Hinglish response
            parts = [f"Abhi {self.location_name} mein {temp_str} hai"]
            if self.condition_hindi:
                parts[0] += f", {self.condition_hindi}"
            if feels_str:
                parts.append(f"Lag raha hai {feels_str}")
            if humidity_str:
                parts.append(f"Nami {humidity_str}")
            if wind_str:
                parts.append(f"Hawa {wind_str} ki speed hai")
            return ". ".join(parts) + "."
        else:
            # English response
            parts = [f"Right now in {self.location_name}: {self.condition} at {temp_str}"]
            if feels_str:
                parts.append(f"Feels like {feels_str}")
            if humidity_str:
                parts.append(f"Humidity {humidity_str}")
            if wind_str:
                parts.append(f"Wind {wind_str}")
            return ". ".join(parts) + "."


class WeatherProvider:
    """Fetches weather from Open-Meteo API (free, no key required)."""

    def __init__(self, timeout: int = 5):
        self.timeout = timeout
        self._cache: Dict[str, tuple[float, WeatherData]] = {}
        self._cache_ttl = 300  # 5 minutes

    def _resolve_location(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        city: Optional[str] = None,
    ) -> tuple[float, float, str]:
        """Resolve location from lat/lon or city name."""
        if lat is not None and lon is not None:
            # Find closest city name
            name = self._find_city_name(lat, lon)
            return lat, lon, name

        if city:
            city_lower = city.lower().strip()
            if city_lower in CITY_COORDS:
                lat, lon = CITY_COORDS[city_lower]
                return lat, lon, city.title()
            # Try partial match
            for name, coords in CITY_COORDS.items():
                if city_lower in name or name in city_lower:
                    return coords[0], coords[1], name.title()

        # Default: New Delhi
        return 28.6139, 77.2090, "New Delhi"

    def _find_city_name(self, lat: float, lon: float) -> str:
        """Find the closest named city for given coordinates."""
        best_name = f"{lat:.2f}°N, {lon:.2f}°E"
        best_dist = float("inf")
        for name, (clat, clon) in CITY_COORDS.items():
            dist = ((lat - clat) ** 2 + (lon - clon) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_name = name.title()
        # If very far from any known city, use coordinates
        if best_dist > 2.0:
            best_name = f"{lat:.2f}°N, {lon:.2f}°E"
        return best_name

    def _get_wmo_icon(self, code: int) -> str:
        """Map WMO weather code to emoji icon."""
        icons = {
            0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️",
            45: "🌫️", 48: "🌫️", 51: "🌦️", 53: "🌦️",
            55: "🌧️", 61: "🌧️", 63: "🌧️", 65: "🌧️",
            71: "❄️", 73: "❄️", 75: "❄️", 80: "🌦️",
            81: "🌧️", 82: "⛈️", 95: "⛈️", 96: "⛈️", 99: "⛈️",
        }
        return icons.get(code, "🌤️")

    def fetch(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        city: Optional[str] = None,
    ) -> WeatherData:
        """Fetch current weather from Open-Meteo."""
        resolved_lat, resolved_lon, location_name = self._resolve_location(lat, lon, city)

        # Check cache
        cache_key = f"{resolved_lat:.2f},{resolved_lon:.2f}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_data

        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={resolved_lat}&longitude={resolved_lon}"
                f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
                f"weather_code,wind_speed_10m&timezone=auto"
            )
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            current = data.get("current", {})

            code = current.get("weather_code", 0)
            temp = current.get("temperature_2m")
            feels = current.get("apparent_temperature")
            humidity = current.get("relative_humidity_2m")
            wind = current.get("wind_speed_10m")

            weather = WeatherData(
                temp=temp,
                feels_like=feels,
                humidity=humidity,
                wind_speed=wind,
                condition=WMO_CODES.get(code, "Unknown"),
                condition_hindi=WMO_HINDI.get(code, ""),
                icon=self._get_wmo_icon(code),
                lat=resolved_lat,
                lon=resolved_lon,
                location_name=location_name,
                timestamp=time.time(),
            )

            # Cache
            self._cache[cache_key] = (time.time(), weather)
            return weather

        except requests.Timeout:
            log.warning("[Weather] Timeout fetching from Open-Meteo")
            return WeatherData(
                error="Weather service timed out",
                lat=resolved_lat, lon=resolved_lon,
                location_name=location_name, timestamp=time.time(),
            )
        except Exception as e:
            log.warning("[Weather] Error: %s", e)
            return WeatherData(
                error=str(e)[:200],
                lat=resolved_lat, lon=resolved_lon,
                location_name=location_name, timestamp=time.time(),
            )

    def extract_city_from_query(self, text: str) -> Optional[str]:
        """Extract city name from a weather query."""
        t = text.lower().strip()
        # "Delhi ka weather" / "Delhi weather" / "weather in Delhi"
        patterns = [
            r'(?:weather|mausam|temperature|taapman)\s+(?:of|in|for|ka|ki|ke)?\s*([a-zA-Z\s]+?)(?:\?|$|!|bata|kaisa|hai)',
            r'([a-zA-Z\s]+?)\s+(?:ka|ki|ke)?\s*(?:weather|mausam|temperature|taapman)',
            r'(?:weather|mausam)\s+([a-zA-Z\s]+?)(?:\?|$|!|bata|kaisa|hai)',
        ]
        for pattern in patterns:
            match = re.search(pattern, t)
            if match:
                city = match.group(1).strip()
                # Filter out common non-city words
                skip_words = {'kaisa', 'kaisa', 'bata', 'hai', 'check', 'tell', 'me', 'the', 'a', 'is', 'today', 'kal', 'aaj', 'abhi'}
                city_words = city.split()
                city_words = [w for w in city_words if w not in skip_words and len(w) > 1]
                if city_words:
                    return ' '.join(city_words)
        return None

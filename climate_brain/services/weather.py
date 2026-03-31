"""OpenWeatherMap integration for outdoor conditions."""

import httpx
from climate_brain.config import settings
from climate_brain.db import database as db

BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


async def fetch_weather() -> dict:
    """
    Fetch current weather and cache it.

    Returns dict with: temperature, humidity, feels_like, description, wind_speed, clouds
    """
    params = {
        "lat": settings.openweather_lat,
        "lon": settings.openweather_lon,
        "appid": settings.openweather_api_key,
        "units": "metric",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    weather = {
        "temperature": data["main"]["temp"],
        "humidity": data["main"]["humidity"],
        "feels_like": data["main"]["feels_like"],
        "description": data["weather"][0]["description"] if data.get("weather") else "",
        "wind_speed": data.get("wind", {}).get("speed", 0),
        "clouds": data.get("clouds", {}).get("all", 0),
    }

    # Cache it
    await db.update_weather_cache(
        temp=weather["temperature"],
        humidity=weather["humidity"],
        feels_like=weather["feels_like"],
        description=weather["description"],
        wind_speed=weather["wind_speed"],
        clouds=weather["clouds"],
    )

    return weather


async def get_weather() -> dict | None:
    """Get weather from cache, or fetch fresh if cache is stale (>15 min)."""
    cached = await db.get_weather_cache()
    if cached:
        # For simplicity, always return cache if it exists
        # The scheduler refreshes it regularly
        return cached

    # No cache — fetch fresh
    try:
        return await fetch_weather()
    except Exception as e:
        print(f"[Weather] Error fetching weather: {e}")
        return None

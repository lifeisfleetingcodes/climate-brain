"""Multi-person comfort optimizer.

Given:
  - A room with an AC unit (known capabilities)
  - Current environmental conditions
  - A list of people present
  - Each person's comfort model

Find the AC setting (mode, temperature, fan speed) that minimizes
discomfort across all present occupants.

Supports three strategies:
  - minimax: minimize the worst individual discomfort (fairest)
  - utilitarian: minimize total squared discomfort (average happy)
  - weighted: minimize weighted discomfort (some people get priority)
"""

import json
from datetime import datetime
from climate_brain.models.comfort import predict_comfort
from climate_brain.models.thermal import predict_future_temp
from climate_brain.db import database as db
from climate_brain.config import settings


async def find_optimal_setting(room_id: int) -> dict | None:
    """
    Find the best AC setting for the current moment.

    Returns dict with recommended mode, temperature, fan_speed,
    or None if not enough data/people to optimize.
    """
    # Get current conditions
    ac_unit = await db.get_ac_unit_for_room(room_id)
    if not ac_unit:
        return None

    ac_state = await db.get_ac_state(ac_unit["id"])
    sensor = await db.get_sensor_cache(room_id)
    weather = await db.get_weather_cache()
    present = await db.get_present_people(room_id)

    if not sensor or not weather or not present:
        return None

    # Parse AC capabilities
    caps = json.loads(ac_unit.get("capabilities_json", "{}"))
    available_modes = caps.get("modes", ["cool", "dry", "fan"])
    temp_min = caps.get("temp_min", 16)
    temp_max = caps.get("temp_max", 30)
    temp_step = caps.get("temp_step", 1)
    fan_speeds = caps.get("fan_speeds", ["auto", "low", "medium", "high"])

    current_temp = ac_state.get("temperature", 24) if ac_state else 24
    now = datetime.utcnow()

    # Generate candidate settings to evaluate
    candidates = []

    # Search around current temperature ± search range
    search_range = settings.temp_search_range
    t_low = max(temp_min, current_temp - search_range)
    t_high = min(temp_max, current_temp + search_range)

    for mode in available_modes:
        if mode == "off":
            continue
        for temp in range(t_low, t_high + 1, temp_step):
            for fan in fan_speeds:
                candidates.append({
                    "mode": mode,
                    "temperature": temp,
                    "fan_speed": fan,
                })

    # Also consider turning off
    candidates.append({"mode": "off", "temperature": current_temp, "fan_speed": "auto"})

    if not candidates:
        return None

    # Evaluate each candidate
    best_candidate = None
    best_score = float("inf")

    for candidate in candidates:
        # Predict what indoor temp will be with this setting
        predicted_temp = predict_future_temp(
            room_id=room_id,
            indoor_temp=sensor.get("temperature", 25),
            indoor_humidity=sensor.get("humidity", 60),
            outdoor_temp=weather.get("temperature", 30),
            outdoor_feels_like=weather.get("feels_like", 30),
            ac_mode=candidate["mode"],
            ac_set_temp=candidate["temperature"],
            ac_fan_speed=candidate["fan_speed"],
            hour=now.hour,
            day_of_week=now.weekday(),
            horizon="15min",
        )

        # If no thermal model yet, use the set temperature as a rough proxy
        eval_temp = predicted_temp if predicted_temp is not None else candidate["temperature"]
        eval_humidity = sensor.get("humidity", 60)

        # Get each person's predicted comfort at this setting
        discomforts = []
        for person in present:
            comfort = predict_comfort(
                person_id=person["id"],
                indoor_temp=eval_temp,
                indoor_humidity=eval_humidity,
                outdoor_temp=weather.get("temperature", 30),
                outdoor_feels_like=weather.get("feels_like", 30),
                ac_mode=candidate["mode"],
                ac_set_temp=candidate["temperature"],
                hour=now.hour,
                day_of_week=now.weekday(),
            )

            if comfort is not None:
                discomforts.append(abs(comfort))
            else:
                # No model for this person — skip them
                # (they haven't given enough feedback yet)
                pass

        if not discomforts:
            continue

        # Score this candidate based on optimization strategy
        score = _score_candidate(discomforts)

        if score < best_score:
            best_score = score
            best_candidate = {
                **candidate,
                "predicted_score": score,
                "predicted_temp": predicted_temp,
                "num_people_optimized": len(discomforts),
            }

    return best_candidate


def _score_candidate(discomforts: list[float]) -> float:
    """
    Score a candidate setting based on individual discomfort levels.

    Lower is better. 0 means everyone is perfectly comfortable.
    """
    strategy = settings.optimization_strategy

    if strategy == "minimax":
        # Minimize the worst discomfort — fairest approach
        return max(discomforts)

    elif strategy == "utilitarian":
        # Minimize total squared discomfort
        return sum(d ** 2 for d in discomforts)

    elif strategy == "weighted":
        # Could be extended with per-person weights
        # For now, same as utilitarian
        return sum(d ** 2 for d in discomforts)

    else:
        return max(discomforts)


async def should_adjust(room_id: int, threshold: float = 0.8) -> dict:
    """
    Check if the current AC setting should be adjusted.

    Returns dict with:
      - adjust: bool (should we change something?)
      - reason: str
      - current_discomfort: float (worst individual discomfort now)
      - recommended: dict (the optimal setting if adjust is True)
    """
    present = await db.get_present_people(room_id)
    if not present:
        return {"adjust": False, "reason": "no_people_present"}

    sensor = await db.get_sensor_cache(room_id)
    weather = await db.get_weather_cache()
    ac_unit = await db.get_ac_unit_for_room(room_id)

    if not sensor or not weather or not ac_unit:
        return {"adjust": False, "reason": "missing_data"}

    ac_state = await db.get_ac_state(ac_unit["id"])
    now = datetime.utcnow()

    # Check current discomfort levels
    current_discomforts = []
    for person in present:
        comfort = predict_comfort(
            person_id=person["id"],
            indoor_temp=sensor.get("temperature", 25),
            indoor_humidity=sensor.get("humidity", 60),
            outdoor_temp=weather.get("temperature", 30),
            outdoor_feels_like=weather.get("feels_like", 30),
            ac_mode=ac_state.get("mode", "off") if ac_state else "off",
            ac_set_temp=ac_state.get("temperature", 24) if ac_state else 24,
            hour=now.hour,
            day_of_week=now.weekday(),
        )
        if comfort is not None:
            current_discomforts.append(abs(comfort))

    if not current_discomforts:
        return {"adjust": False, "reason": "no_comfort_models"}

    worst_discomfort = max(current_discomforts)

    if worst_discomfort <= threshold:
        return {
            "adjust": False,
            "reason": "everyone_comfortable",
            "current_discomfort": worst_discomfort,
        }

    # Someone is uncomfortable — find a better setting
    recommended = await find_optimal_setting(room_id)

    if recommended and recommended.get("predicted_score", float("inf")) < worst_discomfort:
        return {
            "adjust": True,
            "reason": "discomfort_detected",
            "current_discomfort": worst_discomfort,
            "recommended": recommended,
        }

    return {
        "adjust": False,
        "reason": "no_better_setting_found",
        "current_discomfort": worst_discomfort,
    }

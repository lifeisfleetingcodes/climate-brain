"""AC Controller — manages state tracking and sends commands."""

import json
from climate_brain.db import database as db
from climate_brain.services import switchbot


async def get_full_room_state(room_id: int) -> dict:
    """Get complete state for a room: AC state, sensor data, weather."""
    ac_unit = await db.get_ac_unit_for_room(room_id)
    ac_state = None
    sensor = None

    if ac_unit:
        ac_state = await db.get_ac_state(ac_unit["id"])
        # Try to read the SwitchBot meter associated with this room
        try:
            caps = json.loads(ac_unit.get("capabilities_json", "{}"))
            meter_id = caps.get("meter_device_id")
            if meter_id:
                reading = await switchbot.get_meter_reading(meter_id)
                if reading.get("temperature") is not None:
                    await db.update_sensor_cache(
                        room_id, reading["temperature"], reading["humidity"]
                    )
        except Exception as e:
            print(f"[AC Controller] Error reading meter for room {room_id}: {e}")

    sensor = await db.get_sensor_cache(room_id)
    weather = await db.get_weather_cache()

    return {
        "room_id": room_id,
        "ac_unit": ac_unit,
        "ac_state": ac_state,
        "sensor": sensor,
        "weather": weather,
    }


async def send_ac_command(room_id: int, mode: str = None, temperature: int = None,
                          fan_speed: str = None, power: str = "on") -> dict:
    """
    Send a command to the AC in a room and update tracked state.

    Returns the updated state.
    """
    ac_unit = await db.get_ac_unit_for_room(room_id)
    if not ac_unit:
        raise ValueError(f"No AC unit registered for room {room_id}")

    current_state = await db.get_ac_state(ac_unit["id"])

    # Merge with current state for any unspecified values
    final_mode = mode or current_state.get("mode", "cool")
    final_temp = temperature or current_state.get("temperature", 24)
    final_fan = fan_speed or current_state.get("fan_speed", "auto")

    if power == "off" or final_mode == "off":
        # Turn off
        await switchbot.turn_off_ac(ac_unit["switchbot_device_id"])
        await db.update_ac_state(ac_unit["id"], mode="off")
        return {"status": "off", "mode": "off"}

    # Send the command
    await switchbot.set_ac(
        device_id=ac_unit["switchbot_device_id"],
        temperature=final_temp,
        mode=final_mode,
        fan_speed=final_fan,
        power="on",
    )

    # Update tracked state
    await db.update_ac_state(
        ac_unit["id"],
        mode=final_mode,
        temperature=final_temp,
        fan_speed=final_fan,
    )

    return {
        "status": "ok",
        "mode": final_mode,
        "temperature": final_temp,
        "fan_speed": final_fan,
    }


async def log_current_climate(room_id: int):
    """Log current conditions for thermal model training."""
    state = await get_full_room_state(room_id)

    sensor = state.get("sensor")
    weather = state.get("weather")
    ac_state = state.get("ac_state")

    if not sensor or not weather:
        return  # Can't log without data

    await db.save_climate_log(
        room_id=room_id,
        indoor_temp=sensor.get("temperature", 0),
        indoor_humidity=sensor.get("humidity", 0),
        outdoor_temp=weather.get("temperature", 0),
        outdoor_humidity=weather.get("humidity", 0),
        outdoor_feels_like=weather.get("feels_like", 0),
        ac_mode=ac_state.get("mode", "off") if ac_state else "off",
        ac_set_temp=ac_state.get("temperature", 24) if ac_state else 24,
        ac_fan_speed=ac_state.get("fan_speed", "auto") if ac_state else "auto",
    )

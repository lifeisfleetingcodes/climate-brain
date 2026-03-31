"""API routes for system status and dashboard data."""

import json
from fastapi import APIRouter
from climate_brain.db import database as db
from climate_brain.services import weather as weather_svc
from climate_brain.services import ac_controller
from climate_brain.models import optimizer
from climate_brain.models import thermal as thermal_model

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status")
async def get_system_status():
    """Get full system status for all rooms."""
    rooms = await db.get_rooms()
    weather = await weather_svc.get_weather()
    feedback_count = await db.get_feedback_count()

    room_statuses = []
    for room in rooms:
        state = await ac_controller.get_full_room_state(room["id"])
        present = await db.get_present_people(room["id"])

        # Check if thermal model exists for this room
        has_thermal = thermal_model.load_thermal_model(room["id"], "15min") is not None

        room_statuses.append({
            "room": room,
            "ac_unit": state.get("ac_unit"),
            "ac_state": state.get("ac_state"),
            "indoor": state.get("sensor"),
            "present_people": present,
            "has_thermal_model": has_thermal,
        })

    return {
        "rooms": room_statuses,
        "weather": weather,
        "total_feedback_points": feedback_count,
    }


@router.get("/status/{room_id}")
async def get_room_status(room_id: int):
    """Get detailed status for a specific room."""
    state = await ac_controller.get_full_room_state(room_id)
    present = await db.get_present_people(room_id)
    weather = await weather_svc.get_weather()

    # Check optimization recommendation
    recommendation = await optimizer.should_adjust(room_id)

    return {
        **state,
        "weather": weather,
        "present_people": present,
        "recommendation": recommendation,
    }


@router.get("/switchbot/devices")
async def list_switchbot_devices():
    """List all SwitchBot devices on the account (for setup)."""
    from climate_brain.services import switchbot
    try:
        devices = await switchbot.get_devices()
        return devices
    except Exception as e:
        return {"error": str(e)}


@router.get("/weather")
async def get_weather():
    """Get current weather data."""
    return await weather_svc.fetch_weather()


@router.get("/history/{room_id}")
async def get_climate_history(room_id: int, limit: int = 200):
    """Get climate log history for a room."""
    return await db.get_climate_logs(room_id, limit)


@router.post("/train/thermal/{room_id}")
async def train_thermal(room_id: int):
    """Manually trigger thermal model training for a room."""
    result = await thermal_model.train_thermal_model(room_id)
    return result

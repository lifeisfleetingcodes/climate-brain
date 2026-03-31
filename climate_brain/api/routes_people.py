"""API routes for people management and comfort feedback."""

from fastapi import APIRouter, HTTPException
from climate_brain.db import database as db
from climate_brain.db.models import PersonCreate, FeedbackCreate
from climate_brain.services import weather as weather_svc
from climate_brain.models import comfort as comfort_model

router = APIRouter(prefix="/api", tags=["people"])


@router.get("/people")
async def list_people():
    """List all active people."""
    return await db.get_people()


@router.post("/people")
async def create_person(person: PersonCreate):
    """Add a household member."""
    return await db.create_person(person.name)


@router.post("/people/{person_id}/presence/{room_id}")
async def set_presence(person_id: int, room_id: int, present: bool = True):
    """Set whether a person is present in a room."""
    await db.set_presence(person_id, room_id, present)
    return {"status": "ok", "person_id": person_id, "room_id": room_id, "present": present}


@router.get("/rooms/{room_id}/presence")
async def get_room_presence(room_id: int):
    """Get who is present in a room."""
    return await db.get_present_people(room_id)


@router.post("/feedback")
async def submit_feedback(feedback: FeedbackCreate):
    """
    Submit comfort feedback from a person.

    The system enriches the feedback with current environmental data
    and uses it to train the person's comfort model.
    """
    # Get current conditions
    sensor = await db.get_sensor_cache(feedback.room_id)
    weather = await weather_svc.get_weather()
    ac_unit = await db.get_ac_unit_for_room(feedback.room_id)
    ac_state = None
    if ac_unit:
        ac_state = await db.get_ac_state(ac_unit["id"])

    # Save enriched feedback
    result = await db.save_feedback(
        person_id=feedback.person_id,
        room_id=feedback.room_id,
        comfort_level=feedback.comfort_level.value,
        indoor_temp=sensor.get("temperature", 0) if sensor else 0,
        indoor_humidity=sensor.get("humidity", 0) if sensor else 0,
        outdoor_temp=weather.get("temperature", 0) if weather else 0,
        outdoor_humidity=weather.get("humidity", 0) if weather else 0,
        outdoor_feels_like=weather.get("feels_like", 0) if weather else 0,
        ac_mode=ac_state.get("mode", "off") if ac_state else "off",
        ac_set_temp=ac_state.get("temperature", 24) if ac_state else 24,
        ac_fan_speed=ac_state.get("fan_speed", "auto") if ac_state else "auto",
    )

    # Retrain this person's comfort model with new data
    trained = await comfort_model.train_comfort_model(feedback.person_id)

    return {
        "feedback": result,
        "model_retrained": trained,
    }


@router.get("/feedback/history/{person_id}")
async def get_feedback_history(person_id: int, limit: int = 50):
    """Get feedback history for a person."""
    all_feedback = await db.get_feedback_for_person(person_id)
    return all_feedback[:limit]


@router.post("/models/retrain")
async def retrain_all():
    """Manually trigger retraining of all comfort models."""
    results = await comfort_model.retrain_all_models()
    return {"retrained": results}

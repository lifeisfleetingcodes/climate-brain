"""API routes for room and AC unit management."""

from fastapi import APIRouter, HTTPException
from climate_brain.db import database as db
from climate_brain.db.models import RoomCreate, ACUnitCreate, ACCommand
from climate_brain.services import ac_controller

router = APIRouter(prefix="/api", tags=["rooms"])


@router.get("/rooms")
async def list_rooms():
    """List all rooms."""
    return await db.get_rooms()


@router.post("/rooms")
async def create_room(room: RoomCreate):
    """Add a new room."""
    return await db.create_room(room.name)


@router.get("/rooms/{room_id}")
async def get_room(room_id: int):
    """Get a room by ID."""
    room = await db.get_room(room_id)
    if not room:
        raise HTTPException(404, "Room not found")
    return room


@router.post("/rooms/{room_id}/ac")
async def register_ac(room_id: int, ac: ACUnitCreate):
    """Register an AC unit in a room."""
    room = await db.get_room(room_id)
    if not room:
        raise HTTPException(404, "Room not found")

    existing = await db.get_ac_unit_for_room(room_id)
    if existing:
        raise HTTPException(400, "Room already has an AC unit. Remove it first.")

    return await db.create_ac_unit(
        room_id=room_id,
        name=ac.name,
        brand=ac.brand,
        model=ac.model,
        switchbot_device_id=ac.switchbot_device_id,
        capabilities=ac.capabilities.model_dump(),
    )


@router.get("/rooms/{room_id}/ac")
async def get_ac(room_id: int):
    """Get the AC unit for a room."""
    ac = await db.get_ac_unit_for_room(room_id)
    if not ac:
        raise HTTPException(404, "No AC unit in this room")
    state = await db.get_ac_state(ac["id"])
    return {"ac_unit": ac, "state": state}


@router.post("/rooms/{room_id}/ac/command")
async def send_command(room_id: int, cmd: ACCommand):
    """Send a manual command to the AC."""
    try:
        result = await ac_controller.send_ac_command(
            room_id=room_id,
            mode=cmd.mode.value if cmd.mode else None,
            temperature=cmd.temperature,
            fan_speed=cmd.fan_speed.value if cmd.fan_speed else None,
        )
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/rooms/{room_id}/ac/off")
async def turn_off(room_id: int):
    """Turn off the AC in a room."""
    try:
        return await ac_controller.send_ac_command(room_id=room_id, power="off")
    except ValueError as e:
        raise HTTPException(400, str(e))

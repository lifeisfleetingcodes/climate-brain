"""Scheduler — the main control loop.

Runs every N minutes and:
1. Refreshes weather data
2. Reads sensor data for all rooms
3. Logs climate data for thermal model training
4. Checks if any room needs AC adjustment
5. Sends commands if needed
6. Periodically retrains models
"""

import json
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from climate_brain.config import settings
from climate_brain.db import database as db
from climate_brain.services import weather as weather_svc
from climate_brain.services import ac_controller
from climate_brain.services import switchbot
from climate_brain.models import optimizer
from climate_brain.models import comfort as comfort_model
from climate_brain.models import thermal as thermal_model

scheduler = AsyncIOScheduler()
_last_thermal_train: datetime | None = None
_last_comfort_train: datetime | None = None


async def control_loop():
    """Main control loop — runs every interval."""
    print(f"[Scheduler] Control loop tick at {datetime.now(timezone.utc).isoformat()}")

    try:
        await weather_svc.fetch_weather()
    except Exception as e:
        print(f"[Scheduler] Weather fetch error: {e}")

    rooms = await db.get_rooms()

    for room in rooms:
        room_id = room["id"]

        try:
            # Read sensor data from SwitchBot meter
            ac_unit = await db.get_ac_unit_for_room(room_id)
            if ac_unit:
                caps = json.loads(ac_unit.get("capabilities_json", "{}"))
                meter_id = caps.get("meter_device_id")
                if meter_id:
                    reading = await switchbot.get_meter_reading(meter_id)
                    if reading.get("temperature") is not None:
                        await db.update_sensor_cache(
                            room_id, reading["temperature"], reading["humidity"]
                        )

            # Log climate data
            await ac_controller.log_current_climate(room_id)

            # Check if adjustment needed
            feedback_count = await db.get_feedback_count()
            if feedback_count >= settings.min_feedback_points:
                result = await optimizer.should_adjust(room_id)

                if result.get("adjust") and result.get("recommended"):
                    rec = result["recommended"]
                    print(
                        f"[Scheduler] Room '{room['name']}': adjusting AC to "
                        f"{rec['mode']} {rec['temperature']}°C fan={rec['fan_speed']} "
                        f"(discomfort: {result.get('current_discomfort', '?'):.2f} -> "
                        f"{rec.get('predicted_score', '?'):.2f})"
                    )
                    await ac_controller.send_ac_command(
                        room_id=room_id,
                        mode=rec["mode"],
                        temperature=rec["temperature"],
                        fan_speed=rec["fan_speed"],
                    )

        except Exception as e:
            print(f"[Scheduler] Error processing room '{room['name']}': {e}")

    await _maybe_retrain_models()


async def _maybe_retrain_models():
    """Retrain models if enough time has passed."""
    global _last_thermal_train, _last_comfort_train
    now = datetime.now(timezone.utc)

    thermal_interval = timedelta(hours=settings.thermal_retrain_hours)
    if _last_thermal_train is None or (now - _last_thermal_train) > thermal_interval:
        print("[Scheduler] Retraining thermal models...")
        rooms = await db.get_rooms()
        for room in rooms:
            try:
                result = await thermal_model.train_thermal_model(room["id"])
                if result.get("model_15min") or result.get("model_30min"):
                    print(f"[Scheduler] Thermal model for '{room['name']}': {result}")
            except Exception as e:
                print(f"[Scheduler] Thermal training error for room {room['id']}: {e}")
        _last_thermal_train = now

    comfort_interval = timedelta(hours=settings.comfort_retrain_hours)
    if _last_comfort_train is None or (now - _last_comfort_train) > comfort_interval:
        print("[Scheduler] Retraining comfort models...")
        try:
            results = await comfort_model.retrain_all_models()
            print(f"[Scheduler] Comfort models retrained: {results}")
        except Exception as e:
            print(f"[Scheduler] Comfort training error: {e}")
        _last_comfort_train = now


def start_scheduler():
    """Start the background scheduler."""
    if not settings.scheduler_enabled:
        print("[Scheduler] Disabled by configuration")
        return

    scheduler.add_job(
        control_loop,
        "interval",
        minutes=settings.control_interval_minutes,
        id="control_loop",
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc),
    )
    scheduler.start()
    print(f"[Scheduler] Started — running every {settings.control_interval_minutes} minutes")


def stop_scheduler():
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("[Scheduler] Stopped")

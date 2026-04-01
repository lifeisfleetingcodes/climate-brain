"""SQLite database setup and operations for ClimateBrain."""

import aiosqlite
import json
from datetime import datetime, timezone
from climate_brain.config import settings


def _db_path() -> str:
    """Get current database path from settings (read at call time, not import time)."""
    return settings.db_path


async def get_db() -> aiosqlite.Connection:
    """Get a database connection."""
    db = await aiosqlite.connect(_db_path())
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    """Initialize database tables."""
    async with aiosqlite.connect(_db_path()) as db:
        await db.executescript(SCHEMA)
        await db.commit()


SCHEMA = """
CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ac_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    brand TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    switchbot_device_id TEXT NOT NULL DEFAULT '',
    capabilities_json TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ac_states (
    ac_id INTEGER PRIMARY KEY REFERENCES ac_units(id) ON DELETE CASCADE,
    mode TEXT NOT NULL DEFAULT 'off',
    temperature INTEGER NOT NULL DEFAULT 24,
    fan_speed TEXT NOT NULL DEFAULT 'auto',
    swing INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ir_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ac_id INTEGER NOT NULL REFERENCES ac_units(id) ON DELETE CASCADE,
    command_name TEXT NOT NULL,
    command_data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ac_id, command_name)
);

CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS room_presence (
    person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    is_present INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (person_id, room_id)
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES people(id),
    room_id INTEGER NOT NULL REFERENCES rooms(id),
    comfort_level INTEGER NOT NULL,
    indoor_temp REAL,
    indoor_humidity REAL,
    outdoor_temp REAL,
    outdoor_humidity REAL,
    outdoor_feels_like REAL,
    ac_mode TEXT,
    ac_set_temp INTEGER,
    ac_fan_speed TEXT,
    hour_of_day INTEGER,
    day_of_week INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS climate_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL REFERENCES rooms(id),
    indoor_temp REAL NOT NULL,
    indoor_humidity REAL NOT NULL,
    outdoor_temp REAL,
    outdoor_humidity REAL,
    outdoor_feels_like REAL,
    ac_mode TEXT,
    ac_set_temp INTEGER,
    ac_fan_speed TEXT,
    hour_of_day INTEGER,
    day_of_week INTEGER,
    indoor_temp_15min REAL,
    indoor_temp_30min REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sensor_cache (
    room_id INTEGER PRIMARY KEY REFERENCES rooms(id),
    temperature REAL,
    humidity REAL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS weather_cache (
    id INTEGER PRIMARY KEY DEFAULT 1,
    temperature REAL,
    humidity REAL,
    feels_like REAL,
    description TEXT DEFAULT '',
    wind_speed REAL DEFAULT 0,
    clouds INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feedback_person ON feedback(person_id);
CREATE INDEX IF NOT EXISTS idx_feedback_room ON feedback(room_id);
CREATE INDEX IF NOT EXISTS idx_climate_logs_room ON climate_logs(room_id);
CREATE INDEX IF NOT EXISTS idx_climate_logs_time ON climate_logs(created_at);
"""


# === Room Operations ===

async def create_room(name: str) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute("INSERT INTO rooms (name) VALUES (?)", (name,))
        await db.commit()
        row = await db.execute_fetchall("SELECT * FROM rooms WHERE id = ?", (cursor.lastrowid,))
        return dict(row[0])
    finally:
        await db.close()


async def get_rooms() -> list[dict]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT * FROM rooms ORDER BY name")
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_room(room_id: int) -> dict | None:
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT * FROM rooms WHERE id = ?", (room_id,))
        return dict(rows[0]) if rows else None
    finally:
        await db.close()


# === AC Unit Operations ===

async def create_ac_unit(room_id: int, name: str, brand: str, model: str,
                         switchbot_device_id: str, capabilities: dict) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO ac_units (room_id, name, brand, model, switchbot_device_id, capabilities_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (room_id, name, brand, model, switchbot_device_id, json.dumps(capabilities))
        )
        ac_id = cursor.lastrowid
        await db.execute(
            "INSERT INTO ac_states (ac_id) VALUES (?)", (ac_id,)
        )
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM ac_units WHERE id = ?", (ac_id,))
        return dict(rows[0])
    finally:
        await db.close()


async def get_ac_unit_for_room(room_id: int) -> dict | None:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM ac_units WHERE room_id = ?", (room_id,)
        )
        return dict(rows[0]) if rows else None
    finally:
        await db.close()


async def get_ac_state(ac_id: int) -> dict | None:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM ac_states WHERE ac_id = ?", (ac_id,)
        )
        return dict(rows[0]) if rows else None
    finally:
        await db.close()


async def update_ac_state(ac_id: int, mode: str = None, temperature: int = None,
                          fan_speed: str = None, swing: bool = None):
    db = await get_db()
    try:
        updates = []
        params = []
        if mode is not None:
            updates.append("mode = ?")
            params.append(mode)
        if temperature is not None:
            updates.append("temperature = ?")
            params.append(temperature)
        if fan_speed is not None:
            updates.append("fan_speed = ?")
            params.append(fan_speed)
        if swing is not None:
            updates.append("swing = ?")
            params.append(1 if swing else 0)
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(ac_id)
            await db.execute(
                f"UPDATE ac_states SET {', '.join(updates)} WHERE ac_id = ?",
                params
            )
            await db.commit()
    finally:
        await db.close()


# === IR Code Operations ===

async def save_ir_code(ac_id: int, command_name: str, command_data: str):
    db = await get_db()
    try:
        await db.execute(
            """INSERT OR REPLACE INTO ir_codes (ac_id, command_name, command_data)
               VALUES (?, ?, ?)""",
            (ac_id, command_name, command_data)
        )
        await db.commit()
    finally:
        await db.close()


async def get_ir_codes(ac_id: int) -> list[dict]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM ir_codes WHERE ac_id = ? ORDER BY command_name", (ac_id,)
        )
        return [dict(r) for r in rows]
    finally:
        await db.close()


# === Person Operations ===

async def create_person(name: str) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO people (name) VALUES (?)", (name,)
        )
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM people WHERE id = ?", (cursor.lastrowid,))
        return dict(rows[0])
    finally:
        await db.close()


async def get_people() -> list[dict]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT * FROM people WHERE is_active = 1 ORDER BY name")
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def set_presence(person_id: int, room_id: int, is_present: bool):
    db = await get_db()
    try:
        await db.execute(
            """INSERT OR REPLACE INTO room_presence (person_id, room_id, is_present, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
            (person_id, room_id, 1 if is_present else 0)
        )
        await db.commit()
    finally:
        await db.close()


async def get_present_people(room_id: int) -> list[dict]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """SELECT p.* FROM people p
               JOIN room_presence rp ON p.id = rp.person_id
               WHERE rp.room_id = ? AND rp.is_present = 1 AND p.is_active = 1""",
            (room_id,)
        )
        return [dict(r) for r in rows]
    finally:
        await db.close()


# === Feedback Operations ===

async def save_feedback(person_id: int, room_id: int, comfort_level: int,
                        indoor_temp: float, indoor_humidity: float,
                        outdoor_temp: float, outdoor_humidity: float,
                        outdoor_feels_like: float, ac_mode: str,
                        ac_set_temp: int, ac_fan_speed: str) -> dict:
    now = datetime.now(timezone.utc)
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO feedback
               (person_id, room_id, comfort_level, indoor_temp, indoor_humidity,
                outdoor_temp, outdoor_humidity, outdoor_feels_like,
                ac_mode, ac_set_temp, ac_fan_speed, hour_of_day, day_of_week)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (person_id, room_id, comfort_level, indoor_temp, indoor_humidity,
             outdoor_temp, outdoor_humidity, outdoor_feels_like,
             ac_mode, ac_set_temp, ac_fan_speed, now.hour, now.weekday())
        )
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM feedback WHERE id = ?", (cursor.lastrowid,))
        return dict(rows[0])
    finally:
        await db.close()


async def get_feedback_for_person(person_id: int) -> list[dict]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM feedback WHERE person_id = ? ORDER BY created_at DESC",
            (person_id,)
        )
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_feedback_count() -> int:
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT COUNT(*) as count FROM feedback")
        return rows[0]["count"]
    finally:
        await db.close()


# === Climate Log Operations ===

async def save_climate_log(room_id: int, indoor_temp: float, indoor_humidity: float,
                           outdoor_temp: float, outdoor_humidity: float,
                           outdoor_feels_like: float, ac_mode: str,
                           ac_set_temp: int, ac_fan_speed: str):
    now = datetime.now(timezone.utc)
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO climate_logs
               (room_id, indoor_temp, indoor_humidity, outdoor_temp, outdoor_humidity,
                outdoor_feels_like, ac_mode, ac_set_temp, ac_fan_speed, hour_of_day, day_of_week)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (room_id, indoor_temp, indoor_humidity, outdoor_temp, outdoor_humidity,
             outdoor_feels_like, ac_mode, ac_set_temp, ac_fan_speed, now.hour, now.weekday())
        )
        await db.commit()
    finally:
        await db.close()


async def get_climate_logs(room_id: int, limit: int = 1000) -> list[dict]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """SELECT * FROM climate_logs WHERE room_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (room_id, limit)
        )
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def backfill_climate_log_targets(room_id: int):
    """Fill in the 15min/30min future temperature for past log entries."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """SELECT id, created_at FROM climate_logs
               WHERE room_id = ? AND indoor_temp_15min IS NULL
               ORDER BY created_at""",
            (room_id,)
        )
        for row in rows:
            log_time = row["created_at"]
            # Find the reading closest to 15 minutes later
            future_15 = await db.execute_fetchall(
                """SELECT indoor_temp FROM climate_logs
                   WHERE room_id = ? AND created_at > datetime(?, '+12 minutes')
                   AND created_at < datetime(?, '+18 minutes')
                   ORDER BY created_at LIMIT 1""",
                (room_id, log_time, log_time)
            )
            future_30 = await db.execute_fetchall(
                """SELECT indoor_temp FROM climate_logs
                   WHERE room_id = ? AND created_at > datetime(?, '+27 minutes')
                   AND created_at < datetime(?, '+33 minutes')
                   ORDER BY created_at LIMIT 1""",
                (room_id, log_time, log_time)
            )
            if future_15:
                await db.execute(
                    "UPDATE climate_logs SET indoor_temp_15min = ? WHERE id = ?",
                    (future_15[0]["indoor_temp"], row["id"])
                )
            if future_30:
                await db.execute(
                    "UPDATE climate_logs SET indoor_temp_30min = ? WHERE id = ?",
                    (future_30[0]["indoor_temp"], row["id"])
                )
        await db.commit()
    finally:
        await db.close()


# === Sensor Cache ===

async def update_sensor_cache(room_id: int, temperature: float, humidity: float):
    db = await get_db()
    try:
        await db.execute(
            """INSERT OR REPLACE INTO sensor_cache (room_id, temperature, humidity, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
            (room_id, temperature, humidity)
        )
        await db.commit()
    finally:
        await db.close()


async def get_sensor_cache(room_id: int) -> dict | None:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM sensor_cache WHERE room_id = ?", (room_id,)
        )
        return dict(rows[0]) if rows else None
    finally:
        await db.close()


# === Weather Cache ===

async def update_weather_cache(temp: float, humidity: float, feels_like: float,
                                description: str, wind_speed: float, clouds: int):
    db = await get_db()
    try:
        await db.execute(
            """INSERT OR REPLACE INTO weather_cache
               (id, temperature, humidity, feels_like, description, wind_speed, clouds, updated_at)
               VALUES (1, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (temp, humidity, feels_like, description, wind_speed, clouds)
        )
        await db.commit()
    finally:
        await db.close()


async def get_weather_cache() -> dict | None:
    db = await get_db()
    try:
        rows = await db.execute_fetchall("SELECT * FROM weather_cache WHERE id = 1")
        return dict(rows[0]) if rows else None
    finally:
        await db.close()

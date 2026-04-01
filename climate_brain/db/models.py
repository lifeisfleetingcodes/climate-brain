"""Data models and Pydantic schemas for ClimateBrain."""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
from enum import Enum


# === Enums ===

class ACMode(str, Enum):
    COOL = "cool"
    HEAT = "heat"
    DRY = "dry"
    FAN = "fan"
    AUTO = "auto"
    OFF = "off"


class FanSpeed(str, Enum):
    AUTO = "auto"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    QUIET = "quiet"
    TURBO = "turbo"


class ComfortLevel(int, Enum):
    FREEZING = -3
    COLD = -2
    SLIGHTLY_COOL = -1
    COMFORTABLE = 0
    SLIGHTLY_WARM = 1
    HOT = 2
    BURNING = 3


# === Room & AC Schemas ===

class RoomCreate(BaseModel):
    name: str = Field(..., example="Master Bedroom")


class Room(BaseModel):
    id: int
    name: str
    created_at: datetime


class ACCapabilities(BaseModel):
    modes: list[ACMode] = [ACMode.COOL, ACMode.HEAT, ACMode.DRY, ACMode.FAN, ACMode.AUTO]
    temp_min: int = 16
    temp_max: int = 30
    temp_step: int = 1
    fan_speeds: list[FanSpeed] = [FanSpeed.AUTO, FanSpeed.LOW, FanSpeed.MEDIUM, FanSpeed.HIGH]
    has_swing: bool = True


class ACUnitCreate(BaseModel):
    name: str = Field(..., example="Daikin FTXM35")
    brand: str = Field(..., example="Daikin")
    model: str = Field(default="", example="FTXM35")
    switchbot_device_id: str = Field(..., description="SwitchBot Hub device ID for this room")
    capabilities: ACCapabilities = ACCapabilities()


class ACUnit(BaseModel):
    id: int
    room_id: int
    name: str
    brand: str
    model: str
    switchbot_device_id: str
    capabilities: ACCapabilities
    created_at: datetime


class ACState(BaseModel):
    """Current known state of an AC unit."""
    mode: ACMode = ACMode.OFF
    temperature: int = 24
    fan_speed: FanSpeed = FanSpeed.AUTO
    swing: bool = True


class ACCommand(BaseModel):
    """Command to send to an AC unit."""
    mode: Optional[ACMode] = None
    temperature: Optional[int] = None
    fan_speed: Optional[FanSpeed] = None
    swing: Optional[bool] = None


# === Person Schemas ===

class PersonCreate(BaseModel):
    name: str = Field(..., example="Hanindyo")
    is_active: bool = True


class Person(BaseModel):
    id: int
    name: str
    is_active: bool
    created_at: datetime


# === Feedback ===

class FeedbackCreate(BaseModel):
    person_id: int
    room_id: int
    comfort_level: ComfortLevel


class Feedback(BaseModel):
    id: int
    person_id: int
    room_id: int
    comfort_level: ComfortLevel
    indoor_temp: float
    indoor_humidity: float
    outdoor_temp: float
    outdoor_humidity: float
    outdoor_feels_like: float
    ac_mode: ACMode
    ac_set_temp: int
    ac_fan_speed: FanSpeed
    hour_of_day: int
    day_of_week: int
    created_at: datetime


# === Sensor & Weather Data ===

class IndoorReading(BaseModel):
    room_id: int
    temperature: float
    humidity: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WeatherData(BaseModel):
    temperature: float
    humidity: float
    feels_like: float
    description: str = ""
    wind_speed: float = 0.0
    clouds: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# === Climate Log (for thermal model training) ===

class ClimateLog(BaseModel):
    room_id: int
    indoor_temp: float
    indoor_humidity: float
    outdoor_temp: float
    outdoor_humidity: float
    outdoor_feels_like: float
    ac_mode: str
    ac_set_temp: int
    ac_fan_speed: str
    hour_of_day: int
    day_of_week: int
    # Target: what indoor temp was 15 and 30 min later
    indoor_temp_15min: Optional[float] = None
    indoor_temp_30min: Optional[float] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# === Status / Dashboard ===

class RoomStatus(BaseModel):
    room: Room
    ac_unit: Optional[ACUnit] = None
    ac_state: ACState = ACState()
    indoor_temp: Optional[float] = None
    indoor_humidity: Optional[float] = None
    weather: Optional[WeatherData] = None
    present_people: list[Person] = []
    last_adjustment: Optional[datetime] = None


class SystemStatus(BaseModel):
    rooms: list[RoomStatus]
    weather: Optional[WeatherData] = None
    scheduler_running: bool = False
    total_feedback_points: int = 0
    thermal_model_trained: bool = False

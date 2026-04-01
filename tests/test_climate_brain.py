"""Tests for ClimateBrain — comfort model, thermal model, and optimizer."""

import pytest
import asyncio
import os
import sys

# Ensure we can import the package
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from climate_brain.db.models import ComfortLevel


# === Unit tests for comfort scoring ===

class TestComfortModel:
    """Test the comfort learning pipeline with synthetic data."""

    def test_comfort_level_values(self):
        assert ComfortLevel.FREEZING.value == -3
        assert ComfortLevel.COMFORTABLE.value == 0
        assert ComfortLevel.BURNING.value == 3

    def test_comfort_levels_are_symmetric(self):
        """Cold side and hot side should mirror each other."""
        assert abs(ComfortLevel.FREEZING.value) == abs(ComfortLevel.BURNING.value)
        assert abs(ComfortLevel.COLD.value) == abs(ComfortLevel.HOT.value)
        assert abs(ComfortLevel.SLIGHTLY_COOL.value) == abs(ComfortLevel.SLIGHTLY_WARM.value)

    def test_mode_encoding(self):
        from climate_brain.models.comfort import _safe_encode_mode
        assert isinstance(_safe_encode_mode("cool"), int)
        assert isinstance(_safe_encode_mode("unknown_mode"), int)  # Should not crash

    def test_feature_encoding(self):
        from climate_brain.models.comfort import _encode_features
        rows = [
            {
                "indoor_temp": 26.5,
                "indoor_humidity": 65,
                "outdoor_temp": 33,
                "outdoor_feels_like": 37,
                "ac_mode": "cool",
                "ac_set_temp": 24,
                "hour_of_day": 14,
                "day_of_week": 2,
            }
        ]
        X = _encode_features(rows)
        assert X.shape == (1, 8)
        assert X[0][0] == 26.5  # indoor_temp

    def test_feature_encoding_missing_fields(self):
        """Should use defaults for missing fields."""
        from climate_brain.models.comfort import _encode_features
        rows = [{}]  # Empty dict — all defaults
        X = _encode_features(rows)
        assert X.shape == (1, 8)

    def test_predict_without_model_returns_none(self):
        from climate_brain.models.comfort import predict_comfort
        result = predict_comfort(
            person_id=99999,
            indoor_temp=25, indoor_humidity=60,
            outdoor_temp=30, outdoor_feels_like=33,
            ac_mode="cool", ac_set_temp=24,
            hour=14, day_of_week=2,
        )
        assert result is None


class TestThermalModel:
    """Test the thermal response model."""

    def test_predict_without_model_returns_none(self):
        from climate_brain.models.thermal import predict_future_temp
        result = predict_future_temp(
            room_id=99999,
            indoor_temp=26, indoor_humidity=60,
            outdoor_temp=33, outdoor_feels_like=37,
            ac_mode="cool", ac_set_temp=24, ac_fan_speed="auto",
            hour=14, day_of_week=2,
        )
        assert result is None

    def test_safe_encode_unknown_mode(self):
        from climate_brain.models.thermal import _safe_encode, _mode_encoder
        result = _safe_encode(_mode_encoder, "nonexistent")
        assert result == 0


class TestOptimizer:
    """Test the multi-person optimization logic."""

    def test_minimax_scoring(self):
        from climate_brain.models.optimizer import _score_candidate
        from climate_brain.config import settings
        settings.optimization_strategy = "minimax"

        # Person A discomfort=0.5, Person B discomfort=2.0
        score = _score_candidate([0.5, 2.0])
        assert score == 2.0  # Worst individual

    def test_utilitarian_scoring(self):
        from climate_brain.models.optimizer import _score_candidate
        from climate_brain.config import settings
        settings.optimization_strategy = "utilitarian"

        score = _score_candidate([0.5, 2.0])
        assert score == pytest.approx(0.25 + 4.0)  # Sum of squares

    def test_all_comfortable_scores_zero(self):
        from climate_brain.models.optimizer import _score_candidate
        from climate_brain.config import settings
        settings.optimization_strategy = "minimax"

        score = _score_candidate([0.0, 0.0, 0.0])
        assert score == 0.0


class TestSwitchBotMappings:
    """Test SwitchBot API value mappings."""

    def test_mode_map_coverage(self):
        from climate_brain.services.switchbot import MODE_MAP
        for mode in ["auto", "cool", "dry", "fan", "heat"]:
            assert mode in MODE_MAP

    def test_fan_map_coverage(self):
        from climate_brain.services.switchbot import FAN_MAP
        for fan in ["auto", "low", "medium", "high"]:
            assert fan in FAN_MAP

    def test_mode_map_is_reversible(self):
        from climate_brain.services.switchbot import MODE_MAP, MODE_MAP_REVERSE
        for k, v in MODE_MAP.items():
            assert MODE_MAP_REVERSE[v] == k


class TestDataModels:
    """Test Pydantic data models."""

    def test_ac_capabilities_defaults(self):
        from climate_brain.db.models import ACCapabilities
        caps = ACCapabilities()
        assert 16 <= caps.temp_min <= caps.temp_max <= 30
        assert len(caps.modes) > 0
        assert len(caps.fan_speeds) > 0

    def test_ac_command_optional_fields(self):
        from climate_brain.db.models import ACCommand
        cmd = ACCommand()
        assert cmd.mode is None
        assert cmd.temperature is None

    def test_feedback_create_validation(self):
        from climate_brain.db.models import FeedbackCreate, ComfortLevel
        fb = FeedbackCreate(person_id=1, room_id=1, comfort_level=ComfortLevel.HOT)
        assert fb.comfort_level.value == 2

    def test_room_create(self):
        from climate_brain.db.models import RoomCreate
        r = RoomCreate(name="Test Room")
        assert r.name == "Test Room"


class TestConfig:
    """Test configuration loading."""

    def test_default_config(self):
        from climate_brain.config import Settings
        s = Settings()
        assert s.port == 8000
        assert s.control_interval_minutes == 5
        assert s.optimization_strategy in ["minimax", "utilitarian", "weighted"]
        assert s.temp_search_range > 0


# === Integration test with in-memory DB ===

class TestDatabaseIntegration:
    """Test database operations with a temporary database."""

    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        """Use a temporary database for each test."""
        from climate_brain.config import settings
        settings.db_path = str(tmp_path / "test.db")

    @pytest.mark.asyncio
    async def test_create_and_get_room(self):
        from climate_brain.db.database import init_db, create_room, get_rooms
        await init_db()
        room = await create_room("Test Room")
        assert room["name"] == "Test Room"
        rooms = await get_rooms()
        assert len(rooms) == 1

    @pytest.mark.asyncio
    async def test_create_person(self):
        from climate_brain.db.database import init_db, create_person, get_people
        await init_db()
        person = await create_person("Alice")
        assert person["name"] == "Alice"
        people = await get_people()
        assert len(people) == 1

    @pytest.mark.asyncio
    async def test_save_and_get_feedback(self):
        from climate_brain.db.database import (
            init_db, create_room, create_person,
            save_feedback, get_feedback_for_person, get_feedback_count
        )
        await init_db()
        room = await create_room("Bedroom")
        person = await create_person("Bob")

        fb = await save_feedback(
            person_id=person["id"], room_id=room["id"], comfort_level=2,
            indoor_temp=27.5, indoor_humidity=70,
            outdoor_temp=33, outdoor_humidity=80, outdoor_feels_like=37,
            ac_mode="cool", ac_set_temp=24, ac_fan_speed="auto",
        )
        assert fb["comfort_level"] == 2

        history = await get_feedback_for_person(person["id"])
        assert len(history) == 1

        count = await get_feedback_count()
        assert count == 1

    @pytest.mark.asyncio
    async def test_sensor_cache(self):
        from climate_brain.db.database import (
            init_db, create_room, update_sensor_cache, get_sensor_cache
        )
        await init_db()
        room = await create_room("Living Room")
        await update_sensor_cache(room["id"], 25.5, 65)
        cached = await get_sensor_cache(room["id"])
        assert cached["temperature"] == 25.5
        assert cached["humidity"] == 65

    @pytest.mark.asyncio
    async def test_weather_cache(self):
        from climate_brain.db.database import (
            init_db, update_weather_cache, get_weather_cache
        )
        await init_db()
        await update_weather_cache(33.0, 80, 37.5, "haze", 3.5, 40)
        cached = await get_weather_cache()
        assert cached["temperature"] == 33.0
        assert cached["feels_like"] == 37.5

    @pytest.mark.asyncio
    async def test_presence(self):
        from climate_brain.db.database import (
            init_db, create_room, create_person,
            set_presence, get_present_people
        )
        await init_db()
        room = await create_room("Office")
        p1 = await create_person("Charlie")
        p2 = await create_person("Diana")

        await set_presence(p1["id"], room["id"], True)
        await set_presence(p2["id"], room["id"], True)

        present = await get_present_people(room["id"])
        assert len(present) == 2

        await set_presence(p1["id"], room["id"], False)
        present = await get_present_people(room["id"])
        assert len(present) == 1
        assert present[0]["name"] == "Diana"

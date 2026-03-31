"""Room thermal response model.

Predicts what the indoor temperature will be in 15 and 30 minutes,
given current conditions and AC settings. This allows the system to
make proactive adjustments before anyone gets uncomfortable.

Features:
  - indoor_temp (current)
  - indoor_humidity (current)
  - outdoor_temp
  - outdoor_feels_like
  - ac_mode (encoded)
  - ac_set_temp
  - ac_fan_speed (encoded)
  - hour_of_day
  - day_of_week

Target:
  - indoor_temp at t+15min
  - indoor_temp at t+30min
"""

import pickle
import numpy as np
from pathlib import Path
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder
from climate_brain.db import database as db

MODEL_DIR = Path("trained_models")
MODEL_DIR.mkdir(exist_ok=True)

_thermal_models: dict[str, GradientBoostingRegressor] = {}

_mode_encoder = LabelEncoder()
_mode_encoder.fit(["off", "cool", "heat", "dry", "fan", "auto"])

_fan_encoder = LabelEncoder()
_fan_encoder.fit(["auto", "low", "medium", "high", "quiet", "turbo"])


def _safe_encode(encoder: LabelEncoder, value: str) -> int:
    try:
        return int(encoder.transform([value])[0])
    except ValueError:
        return 0


def _extract_features(rows: list[dict]) -> np.ndarray:
    features = []
    for r in rows:
        features.append([
            r.get("indoor_temp", 25),
            r.get("indoor_humidity", 60),
            r.get("outdoor_temp", 30),
            r.get("outdoor_feels_like", 30),
            _safe_encode(_mode_encoder, r.get("ac_mode", "off")),
            r.get("ac_set_temp", 24),
            _safe_encode(_fan_encoder, r.get("ac_fan_speed", "auto")),
            r.get("hour_of_day", 12),
            r.get("day_of_week", 0),
        ])
    return np.array(features)


async def train_thermal_model(room_id: int) -> dict:
    """
    Train thermal response models (15min and 30min) for a room.

    Returns dict with training status and sample counts.
    """
    # First, backfill targets from historical data
    await db.backfill_climate_log_targets(room_id)

    logs = await db.get_climate_logs(room_id, limit=5000)

    # Filter to rows that have future temperature data
    logs_15 = [r for r in logs if r.get("indoor_temp_15min") is not None]
    logs_30 = [r for r in logs if r.get("indoor_temp_30min") is not None]

    results = {"room_id": room_id, "model_15min": False, "model_30min": False}

    if len(logs_15) >= 20:
        X = _extract_features(logs_15)
        y = np.array([r["indoor_temp_15min"] for r in logs_15])
        model = GradientBoostingRegressor(
            n_estimators=min(200, len(logs_15) * 3),
            max_depth=4,
            learning_rate=0.1,
            random_state=42,
        )
        model.fit(X, y)
        key = f"thermal_{room_id}_15min"
        _thermal_models[key] = model
        with open(MODEL_DIR / f"{key}.pkl", "wb") as f:
            pickle.dump(model, f)
        results["model_15min"] = True
        results["samples_15min"] = len(logs_15)

    if len(logs_30) >= 20:
        X = _extract_features(logs_30)
        y = np.array([r["indoor_temp_30min"] for r in logs_30])
        model = GradientBoostingRegressor(
            n_estimators=min(200, len(logs_30) * 3),
            max_depth=4,
            learning_rate=0.1,
            random_state=42,
        )
        model.fit(X, y)
        key = f"thermal_{room_id}_30min"
        _thermal_models[key] = model
        with open(MODEL_DIR / f"{key}.pkl", "wb") as f:
            pickle.dump(model, f)
        results["model_30min"] = True
        results["samples_30min"] = len(logs_30)

    return results


def load_thermal_model(room_id: int, horizon: str = "15min") -> GradientBoostingRegressor | None:
    key = f"thermal_{room_id}_{horizon}"
    if key in _thermal_models:
        return _thermal_models[key]
    model_path = MODEL_DIR / f"{key}.pkl"
    if model_path.exists():
        with open(model_path, "rb") as f:
            model = pickle.load(f)
        _thermal_models[key] = model
        return model
    return None


def predict_future_temp(room_id: int, indoor_temp: float, indoor_humidity: float,
                        outdoor_temp: float, outdoor_feels_like: float,
                        ac_mode: str, ac_set_temp: int, ac_fan_speed: str,
                        hour: int, day_of_week: int,
                        horizon: str = "15min") -> float | None:
    """
    Predict what indoor temperature will be in 15 or 30 minutes.

    Returns predicted temperature, or None if no model trained yet.
    """
    model = load_thermal_model(room_id, horizon)
    if model is None:
        return None

    features = np.array([[
        indoor_temp,
        indoor_humidity,
        outdoor_temp,
        outdoor_feels_like,
        _safe_encode(_mode_encoder, ac_mode),
        ac_set_temp,
        _safe_encode(_fan_encoder, ac_fan_speed),
        hour,
        day_of_week,
    ]])

    return float(model.predict(features)[0])

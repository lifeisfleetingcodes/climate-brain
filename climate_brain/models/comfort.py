"""Per-person comfort learning model.

Each person gets their own model that learns the mapping:
  (indoor_temp, indoor_humidity, outdoor_temp, outdoor_feels_like,
   ac_mode, ac_set_temp, hour_of_day, day_of_week) → comfort_level

The comfort_level is on a scale from -3 (freezing) to +3 (burning),
where 0 is comfortable.
"""

import pickle
import numpy as np
from pathlib import Path
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder
from climate_brain.db import database as db

MODEL_DIR = Path("trained_models")
MODEL_DIR.mkdir(exist_ok=True)

# Cache trained models in memory
_comfort_models: dict[int, GradientBoostingRegressor] = {}
_mode_encoder = LabelEncoder()
_mode_encoder.fit(["off", "cool", "heat", "dry", "fan", "auto"])


def _encode_features(rows: list[dict]) -> np.ndarray:
    """Convert feedback rows into feature matrix."""
    features = []
    for r in rows:
        mode_encoded = _safe_encode_mode(r.get("ac_mode", "off"))
        features.append([
            r.get("indoor_temp", 25),
            r.get("indoor_humidity", 60),
            r.get("outdoor_temp", 30),
            r.get("outdoor_feels_like", r.get("outdoor_temp", 30)),
            mode_encoded,
            r.get("ac_set_temp", 24),
            r.get("hour_of_day", 12),
            r.get("day_of_week", 0),
        ])
    return np.array(features)


def _safe_encode_mode(mode: str) -> int:
    """Encode AC mode string to integer."""
    try:
        return int(_mode_encoder.transform([mode])[0])
    except ValueError:
        return 0  # default to 'off'


async def train_comfort_model(person_id: int) -> bool:
    """
    Train (or retrain) the comfort model for a specific person.

    Returns True if a model was trained, False if not enough data.
    """
    feedback_rows = await db.get_feedback_for_person(person_id)

    if len(feedback_rows) < 5:
        return False  # Need at least a few data points

    X = _encode_features(feedback_rows)
    y = np.array([r["comfort_level"] for r in feedback_rows])

    model = GradientBoostingRegressor(
        n_estimators=min(100, len(feedback_rows) * 5),
        max_depth=3,
        learning_rate=0.1,
        random_state=42,
    )
    model.fit(X, y)

    # Cache in memory
    _comfort_models[person_id] = model

    # Save to disk
    model_path = MODEL_DIR / f"comfort_person_{person_id}.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    return True


def load_comfort_model(person_id: int) -> GradientBoostingRegressor | None:
    """Load a trained comfort model from memory or disk."""
    if person_id in _comfort_models:
        return _comfort_models[person_id]

    model_path = MODEL_DIR / f"comfort_person_{person_id}.pkl"
    if model_path.exists():
        with open(model_path, "rb") as f:
            model = pickle.load(f)
        _comfort_models[person_id] = model
        return model

    return None


def predict_comfort(person_id: int, indoor_temp: float, indoor_humidity: float,
                    outdoor_temp: float, outdoor_feels_like: float,
                    ac_mode: str, ac_set_temp: int,
                    hour: int, day_of_week: int) -> float | None:
    """
    Predict a person's comfort level given environmental conditions.

    Returns a float from ~-3 to ~+3 where 0 is comfortable.
    Returns None if no model is available.
    """
    model = load_comfort_model(person_id)
    if model is None:
        return None

    features = np.array([[
        indoor_temp,
        indoor_humidity,
        outdoor_temp,
        outdoor_feels_like,
        _safe_encode_mode(ac_mode),
        ac_set_temp,
        hour,
        day_of_week,
    ]])

    return float(model.predict(features)[0])


async def retrain_all_models():
    """Retrain comfort models for all active people."""
    people = await db.get_people()
    results = {}
    for person in people:
        trained = await train_comfort_model(person["id"])
        results[person["name"]] = trained
    return results

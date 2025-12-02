# utils/risk_model.py
import os
import numpy as np
import joblib

MODEL_PATH = os.path.join("models", "oscc_risk_model.pkl")
_model = None


def load_risk_model():
    """Lazy-load the risk model from disk."""
    global _model
    if _model is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Risk model file not found at {MODEL_PATH}")
        _model = joblib.load(MODEL_PATH)
    return _model


def compute_risk_from_features(feature_vector: np.ndarray) -> float:
    """
    feature_vector: 1D numpy array in correct order.
    Returns OSCC probability (0–1).
    """
    model = load_risk_model()
    prob = model.predict_proba(feature_vector.reshape(1, -1))[0, 1]
    return float(prob)

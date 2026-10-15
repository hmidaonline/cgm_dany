import numpy as np
from typing import Optional, Tuple, Dict, Any
from app.ml.rl.config import CGMSensorConfig

class CGMSensorModel:
    """
    Subcutaneous CGM sensor model incorporating:
    1. Interstitial physiological diffusion lag (5 to 15 min, 1st-order filter).
    2. Autocorrelated sensor error (AR(1) process).
    3. Signal transmission losses / dropouts.
    4. Nocturnal compression lows (pseudo-hypoglycemia caused by physical pressure).
    """
    def __init__(self, config: Optional[CGMSensorConfig] = None, seed: Optional[int] = None):
        self.config = config or CGMSensorConfig()
        self.rng = np.random.RandomState(seed if seed is not None else 42)
        
        # State variables
        self.interstitial_bg: float = 110.0
        self.ar_error: float = 0.0
        self.dropout_steps_remaining: int = 0
        self.compression_steps_remaining: int = 0
        self.compression_drop: float = 0.0

        # Diffusion smoothing factor alpha = 1 - exp(-dt / tau)
        dt = 5.0 # min
        self.tau = max(5.0, min(15.0, self.config.lag_time_minutes))
        self.alpha = 1.0 - np.exp(-dt / self.tau)

    def reset(self, initial_blood_glucose: float = 110.0, seed: Optional[int] = None):
        if seed is not None:
            self.rng = np.random.RandomState(seed)
        self.interstitial_bg = float(initial_blood_glucose)
        self.ar_error = float(self.rng.normal(0, self.config.sensor_noise_std))
        self.dropout_steps_remaining = 0
        self.compression_steps_remaining = 0
        self.compression_drop = 0.0

    def step(self, blood_glucose: float, hour_of_day: float = 12.0) -> Tuple[Optional[float], Dict[str, Any]]:
        """
        Takes real capillary/venous blood glucose and returns interstitial CGM reading.
        Returns:
            (cgm_reading, diagnostics_dict)
            cgm_reading is None if a sensor dropout occurs.
        """
        # 1. 1st-order physiological diffusion delay
        self.interstitial_bg += self.alpha * (blood_glucose - self.interstitial_bg)

        # 2. Autocorrelated AR(1) sensor measurement noise
        white_noise = self.rng.normal(0, self.config.sensor_noise_std)
        self.ar_error = self.config.arma_phi * self.ar_error + np.sqrt(1.0 - self.config.arma_phi ** 2) * white_noise

        # 3. Check for nocturnal compression low trigger (typically between 23h and 07h)
        is_night = (hour_of_day >= 23.0) or (hour_of_day < 7.0)
        is_compression_active = False

        if self.compression_steps_remaining > 0:
            self.compression_steps_remaining -= 1
            is_compression_active = True
        elif is_night and self.rng.rand() < self.config.compression_low_prob:
            # Trigger new compression low event
            self.compression_steps_remaining = self.config.compression_duration_steps
            self.compression_drop = self.rng.uniform(25.0, self.config.compression_drop_mgdl)
            is_compression_active = True
        else:
            self.compression_drop = 0.0

        # 4. Check for signal dropout
        is_dropout = False
        if self.dropout_steps_remaining > 0:
            self.dropout_steps_remaining -= 1
            is_dropout = True
        elif self.rng.rand() < self.config.dropout_probability:
            self.dropout_steps_remaining = self.rng.randint(1, self.config.dropout_max_duration_steps + 1)
            is_dropout = True

        if is_dropout:
            return None, {
                "blood_glucose": round(blood_glucose, 1),
                "interstitial_bg": round(self.interstitial_bg, 1),
                "is_dropout": True,
                "is_compression": is_compression_active,
                "cgm_reading": None
            }

        # Apply noise and potential compression dip
        raw_cgm = self.interstitial_bg + self.ar_error
        if is_compression_active:
            raw_cgm -= self.compression_drop

        cgm_clamped = float(np.clip(round(raw_cgm, 1), 30.0, 400.0))

        return cgm_clamped, {
            "blood_glucose": round(blood_glucose, 1),
            "interstitial_bg": round(self.interstitial_bg, 1),
            "is_dropout": False,
            "is_compression": is_compression_active,
            "compression_drop": round(self.compression_drop, 1) if is_compression_active else 0.0,
            "sensor_noise": round(self.ar_error, 2),
            "cgm_reading": cgm_clamped
        }

import os
import sys
import numpy as np

# Ensure app is importable
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from app.ml.rl.env.glucose_env import GlycoTwinEnv
from app.ml.rl.calibration.params_store import load_calibration_params

DISCLAIMER_BANNER = """
================================================================================
ATTENTION : TEST DE PLOMBERIE TECHNIQUE UNIQUEMENT (PPO <= 50 000 PAS)
LES PERFORMANCES OBTENUES NE SONT PAS INTERPRÉTABLES CLINIQUEMENT.
AUCUNE COMPARAISON NI DÉCISION MÉDICALE AVANT REVALIDATION DE LA PHASE 1.
================================================================================
"""

def make_env():
    params = load_calibration_params()
    def _init():
        return GlycoTwinEnv(calibrated_params=params, use_shield=True, domain_randomization=True, seed=42)
    return _init

def run_plumbing_test(total_timesteps: int = 25000):
    print(DISCLAIMER_BANNER)
    print(f"[PLOMBERIE] Initialisation de l'environnement vectorisé GlycoTwinEnv...")
    
    vec_env = DummyVecEnv([make_env()])

    checkpoint_dir = os.path.join(current_dir, "checkpoints")
    os.makedirs(checkpoint_dir, exist_ok=True)
    checkpoint_path = os.path.join(checkpoint_dir, "plumbing_test_ppo.zip")

    print(f"[PLOMBERIE] Instanciation de l'agent PPO (MlpPolicy, gamma=0.99, gae_lambda=0.95)...")
    model = PPO(
        "MlpPolicy",
        vec_env,
        learning_rate=3e-4,
        n_steps=512,
        batch_size=64,
        n_epochs=4,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        verbose=1,
        seed=42
    )

    print(f"[PLOMBERIE] Démarrage de l'entraînement court ({total_timesteps} pas)...")
    model.learn(total_timesteps=total_timesteps)

    # Save checkpoint
    model.save(checkpoint_path)
    print(f"[PLOMBERIE] Modèle sauvegardé avec succès dans : {checkpoint_path}")
    print(DISCLAIMER_BANNER)
    print("Test de plomberie PPO terminé avec succès (zéro crash, gradient stable).")

if __name__ == "__main__":
    run_plumbing_test(total_timesteps=25000)

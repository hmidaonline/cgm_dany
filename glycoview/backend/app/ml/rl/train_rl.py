import os
import sys
import json
import time
import numpy as np
import scipy.stats as stats
import torch
from typing import Dict, Any, List, Tuple, Optional

# Stable Baselines3
from stable_baselines3 import PPO, SAC
from stable_baselines3.common.vec_env import DummyVecEnv, VecFrameStack, VecNormalize
from stable_baselines3.common.callbacks import BaseCallback

# Local project imports
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.ml.rl.env.glucose_env import GlycoTwinEnv
from app.ml.rl.env.residual_env import ResidualGlycoTwinEnv
from app.ml.rl.evaluate_baselines import compute_episode_metrics, aggregate_distribution

def make_residual_env(seed: int, is_training: bool = True, alpha: float = 0.50):
    def _init():
        return ResidualGlycoTwinEnv(
            alpha=alpha,
            is_training=is_training,
            use_shield=True,
            domain_randomization=True,
            episode_steps=288,
            seed=seed
        )
    return _init

def train_ppo(total_timesteps: int = 60000, seed: int = 42) -> Tuple[PPO, VecNormalize]:
    print(f"\n=======================================================")
    print(f"ENTRAÎNEMENT RESIDUAL PPO (+ VecFrameStack=6, VecNormalize)")
    print(f"Total timesteps: {total_timesteps} | Seed: {seed}")
    print(f"=======================================================")
    
    # Vectorized environment with Frame Stacking and Normalization
    venv = DummyVecEnv([make_residual_env(seed=5000 + i, is_training=True) for i in range(1)])
    venv = VecFrameStack(venv, n_stack=6)
    venv = VecNormalize(venv, norm_obs=True, norm_reward=False, clip_obs=10.0)

    model = PPO(
        policy="MlpPolicy",
        env=venv,
        learning_rate=3e-4,
        n_steps=576,        # 2 full days per rollout update
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.005,     # Slight exploration bonus
        verbose=1,
        seed=seed
    )

    # Initialize last layer weights near 0 (w ~ N(0, 1e-3))
    print("[Residual Policy Init] Setting PPO action_net weights ~ N(0, 1e-3)...")
    model.policy.action_net.weight.data.normal_(0.0, 1e-3)
    model.policy.action_net.bias.data.zero_()

    t0 = time.time()
    model.learn(total_timesteps=total_timesteps)
    print(f"PPO training finished in {time.time() - t0:.1f}s.")

    # Save model and normalization stats
    ckpt_dir = os.path.join(current_dir, "checkpoints")
    os.makedirs(ckpt_dir, exist_ok=True)
    model.save(os.path.join(ckpt_dir, "residual_ppo_model"))
    venv.save(os.path.join(ckpt_dir, "residual_ppo_vecnormalize.pkl"))
    return model, venv

def train_sac(total_timesteps: int = 50000, seed: int = 42) -> Tuple[SAC, VecNormalize]:
    print(f"\n=======================================================")
    print(f"ENTRAÎNEMENT RESIDUAL SAC (+ VecNormalize)")
    print(f"Total timesteps: {total_timesteps} | Seed: {seed}")
    print(f"=======================================================")

    venv = DummyVecEnv([make_residual_env(seed=7000 + i, is_training=True) for i in range(1)])
    venv = VecNormalize(venv, norm_obs=True, norm_reward=False, clip_obs=10.0)

    model = SAC(
        policy="MlpPolicy",
        env=venv,
        learning_rate=3e-4,
        buffer_size=50000,
        learning_starts=576,
        batch_size=128,
        tau=0.005,
        gamma=0.99,
        ent_coef="auto",
        verbose=1,
        seed=seed
    )

    # Initialize policy actor mu weights near 0 (w ~ N(0, 1e-3))
    print("[Residual Policy Init] Setting SAC actor mu weights ~ N(0, 1e-3)...")
    model.policy.actor.mu.weight.data.normal_(0.0, 1e-3)
    model.policy.actor.mu.bias.data.zero_()

    t0 = time.time()
    model.learn(total_timesteps=total_timesteps)
    print(f"SAC training finished in {time.time() - t0:.1f}s.")

    ckpt_dir = os.path.join(current_dir, "checkpoints")
    model.save(os.path.join(ckpt_dir, "residual_sac_model"))
    venv.save(os.path.join(ckpt_dir, "residual_sac_vecnormalize.pkl"))
    return model, venv

def evaluate_residual_agent(
    model: Any,
    norm_env: Optional[VecNormalize],
    is_stacked: bool,
    seeds: List[int],
    scenario_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Evaluates a trained residual RL policy deterministically over explicit seeds."""
    if norm_env is not None:
        norm_env.training = False
        norm_env.norm_reward = False

    ep_metrics = []

    for seed in seeds:
        env = ResidualGlycoTwinEnv(
            alpha=0.50,
            is_training=False,
            use_shield=True,
            domain_randomization=True,
            episode_steps=288,
            seed=seed
        )

        options = {"scenario_type": scenario_type} if scenario_type else None
        obs, info = env.reset(seed=seed, options=options)

        # Buffer for frame stacking if needed
        history_obs = [obs.copy()] * 6 if is_stacked else None

        cgm_hist = [float(info["initial_cgm"])]
        rewards_hist = []
        shield_count = 0

        for step in range(288):
            if is_stacked:
                # Shape: (1, 54)
                stacked_obs = np.concatenate(history_obs, axis=0).reshape(1, -1)
                if norm_env is not None:
                    norm_obs = norm_env.normalize_obs(stacked_obs)
                else:
                    norm_obs = stacked_obs
                action, _ = model.predict(norm_obs, deterministic=True)
                action = action[0] # Extract batch dim
            else:
                raw_obs = obs.reshape(1, -1)
                if norm_env is not None:
                    norm_obs = norm_env.normalize_obs(raw_obs)
                else:
                    norm_obs = raw_obs
                action, _ = model.predict(norm_obs, deterministic=True)
                action = action[0]

            obs, reward, terminated, truncated, info = env.step(action)

            if is_stacked:
                history_obs.append(obs.copy())
                history_obs.pop(0)

            cgm_hist.append(info["cgm_reading"])
            rewards_hist.append(reward)
            if info["shield"]["triggered"]:
                shield_count += 1

            if terminated or truncated:
                break

        m = compute_episode_metrics(cgm_hist, rewards_hist, shield_count, len(rewards_hist))
        ep_metrics.append(m)

    return ep_metrics

def run_phase4_experiment():
    print("\n" + "=" * 80)
    print("LANCEMENT OFFICIEL DE LA PHASE 4 : ENTRAÎNEMENT ET ÉVALUATION RL RÉSIDUEL")
    print("=" * 80)

    # 1. Train PPO and SAC
    ppo_model, ppo_norm = train_ppo(total_timesteps=60000, seed=42)
    sac_model, sac_norm = train_sac(total_timesteps=50000, seed=42)

    # Load baseline results for direct paired comparison
    base_file = os.path.join(current_dir, "baselines_evaluation_results.json")
    with open(base_file, "r", encoding="utf-8") as f:
        baseline_data = json.load(f)

    # 2. Banc A Evaluation on exact 200 test seeds (1000 - 1199)
    print("\n[Évaluation Banc A] Évaluation sur les 200 graines de test appariées (1000 à 1199)...")
    test_seeds_a = [1000 + i for i in range(200)]

    ppo_a_eps = evaluate_residual_agent(ppo_model, ppo_norm, is_stacked=True, seeds=test_seeds_a)
    sac_a_eps = evaluate_residual_agent(sac_model, sac_norm, is_stacked=False, seeds=test_seeds_a)

    # Summarize Banc A
    summary_ppo_a = {k: aggregate_distribution([e[k] for e in ppo_a_eps]) for k in ppo_a_eps[0].keys()}
    summary_sac_a = {k: aggregate_distribution([e[k] for e in sac_a_eps]) for k in sac_a_eps[0].keys()}

    # Pairwise Wilcoxon tests against Oref0 (+Shield)
    print("\n[Tests Statistiques de Wilcoxon] Comparaison appariée vs Oref0 (+Shield) sur N=200...")
    # Re-extract Oref0 Banc A per-episode values
    # In evaluate_baselines.py, let's run Oref0 on exact seeds or extract if saved
    oref0_eps = []
    from app.ml.rl.baselines.controllers import Oref0HeuristicPolicy
    pol_oref = Oref0HeuristicPolicy()
    for s in test_seeds_a:
        env_o = GlycoTwinEnv(domain_randomization=True, use_shield=True, episode_steps=288, seed=s)
        obs, info = env_o.reset()
        pol_oref.reset()
        cgm_h = [float(info["initial_cgm"])]
        rew_h = []
        sc_c = 0
        for _ in range(288):
            a, _ = pol_oref.predict(obs)
            obs, r, term, trunc, inf = env_o.step(a)
            cgm_h.append(inf["cgm_reading"])
            rew_h.append(r)
            if inf["shield"]["triggered"]: sc_c += 1
            if term or trunc: break
        oref0_eps.append(compute_episode_metrics(cgm_h, rew_h, sc_c, len(rew_h)))

    wilcoxon_phase4 = {}
    for comp_name, comp_eps in [("Residual_PPO_vs_Oref0", ppo_a_eps), ("Residual_SAC_vs_Oref0", sac_a_eps)]:
        wilcoxon_phase4[comp_name] = {}
        for metric in ["tir_70_180", "tight_tir_70_140", "tbr_under_70", "bgri", "cumulative_reward"]:
            vals_comp = [e[metric] for e in comp_eps]
            vals_oref = [e[metric] for e in oref0_eps]
            diff = np.array(vals_comp) - np.array(vals_oref)
            if np.all(diff == 0):
                w_stat, p_val = 0.0, 1.0
            else:
                res = stats.wilcoxon(vals_comp, vals_oref)
                w_stat, p_val = float(res.statistic), float(res.pvalue)

            wilcoxon_phase4[comp_name][metric] = {
                "mean_diff": round(float(np.mean(diff)), 2),
                "statistic": round(w_stat, 1),
                "p_value": p_val,
                "significant": p_val < 0.05
            }

    # 3. Banc B Evaluation on 5 Stress Scenarios (50 seeds: 2000 - 2049)
    print("\n[Évaluation Banc B] Évaluation sur les 5 scénarios de stress dédiés...")
    stress_scenarios = [
        {"type": "forgotten_bolus", "label": "1. Bolus Oublié (Repas 60g)"},
        {"type": "high_fat_meal", "label": "2. Repas Gras / Absorption Retardée (T_max=110m)"},
        {"type": "exercise", "label": "3. Exercice Physique (+50% ISF / Captation GLUT4)"},
        {"type": "carb_undercounting", "label": "4. Sous-estimation Glucides (-40%)"},
        {"type": "carb_overestimation", "label": "5. Surestimation Glucides (+40% Bolus / Overdosage)"}
    ]
    test_seeds_b = [2000 + i for i in range(50)]
    results_b_phase4: Dict[str, Any] = {}

    for sc in stress_scenarios:
        s_type = sc["type"]
        s_label = sc["label"]
        results_b_phase4[s_type] = {"label": s_label, "controllers": {}}

        # PPO
        ppo_stress_eps = evaluate_residual_agent(ppo_model, ppo_norm, is_stacked=True, seeds=test_seeds_b, scenario_type=s_type)
        summary_ppo_stress = {k: aggregate_distribution([e[k] for e in ppo_stress_eps]) for k in ["tir_70_180", "tbr_under_70", "tbr_under_54", "tar_over_180", "bgri", "cumulative_reward"]}
        results_b_phase4[s_type]["controllers"]["Residual_PPO_WithShield"] = summary_ppo_stress

        # SAC
        sac_stress_eps = evaluate_residual_agent(sac_model, sac_norm, is_stacked=False, seeds=test_seeds_b, scenario_type=s_type)
        summary_sac_stress = {k: aggregate_distribution([e[k] for e in sac_stress_eps]) for k in ["tir_70_180", "tbr_under_70", "tbr_under_54", "tar_over_180", "bgri", "cumulative_reward"]}
        results_b_phase4[s_type]["controllers"]["Residual_SAC_WithShield"] = summary_sac_stress

    # Assemble and save phase 4 results
    phase4_output = {
        "banc_a_residual_results": {
            "Residual_PPO_WithShield": summary_ppo_a,
            "Residual_SAC_WithShield": summary_sac_a
        },
        "wilcoxon_vs_oref0": wilcoxon_phase4,
        "banc_b_stress_tests": results_b_phase4
    }

    out_file = os.path.join(current_dir, "phase4_evaluation_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(phase4_output, f, indent=2)

    print(f"\nPhase 4 terminée avec succès. Résultats sauvegardés dans : {out_file}")
    return phase4_output

if __name__ == "__main__":
    run_phase4_experiment()

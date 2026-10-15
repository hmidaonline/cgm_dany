import os
import sys
import json
import math
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple
from scipy import stats

# Ensure app is importable
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.data.pipeline import get_processed_dataframe
from app.ml.rl.env.glucose_env import GlycoTwinEnv
from app.ml.rl.rewards import ClinicalRewardCalculator
from app.ml.rl.baselines.controllers import (
    OpenLoopBolusWizardPolicy,
    PIDControllerPolicy,
    Oref0HeuristicPolicy
)

def kovatchev_indices(bg_series: np.ndarray) -> Tuple[float, float, float]:
    """Computes LBGI, HBGI, and BGRI according to Kovatchev et al."""
    bg = np.clip(bg_series, 20.0, 500.0)
    f = 1.509 * ((np.log(bg) ** 1.084) - 5.381)
    risk = 10.0 * (f ** 2)
    lbgi = float(np.mean(np.where(f < 0, risk, 0.0)))
    hbgi = float(np.mean(np.where(f > 0, risk, 0.0)))
    bgri = lbgi + hbgi
    return round(lbgi, 2), round(hbgi, 2), round(bgri, 2)

def compute_episode_metrics(cgm_history: List[float], rewards_history: List[float], shield_triggers: int, total_steps: int) -> Dict[str, float]:
    cgms = np.array(cgm_history, dtype=float)
    mean_g = float(np.mean(cgms))
    std_g = float(np.std(cgms))
    cv_pct = float((std_g / mean_g) * 100.0) if mean_g > 0 else 0.0

    tir = float(np.mean((cgms >= 70.0) & (cgms <= 180.0)) * 100.0)
    tight_tir = float(np.mean((cgms >= 70.0) & (cgms <= 140.0)) * 100.0)
    tbr_70 = float(np.mean(cgms < 70.0) * 100.0)
    tbr_54 = float(np.mean(cgms < 54.0) * 100.0)
    tar_180 = float(np.mean(cgms > 180.0) * 100.0)
    tar_250 = float(np.mean(cgms > 250.0) * 100.0)

    lbgi, hbgi, bgri = kovatchev_indices(cgms)
    cum_reward = float(sum(rewards_history))
    shield_pct = float((shield_triggers / max(1, total_steps)) * 100.0)

    return {
        "mean_g": mean_g,
        "cv_pct": cv_pct,
        "tir_70_180": tir,
        "tight_tir_70_140": tight_tir,
        "tbr_under_70": tbr_70,
        "tbr_under_54": tbr_54,
        "tar_over_180": tar_180,
        "tar_over_250": tar_250,
        "lbgi": lbgi,
        "hbgi": hbgi,
        "bgri": bgri,
        "cumulative_reward": cum_reward,
        "shield_activation_pct": shield_pct
    }

def aggregate_distribution(values: List[float]) -> Dict[str, Any]:
    arr = np.array(values, dtype=float)
    mean = float(np.mean(arr))
    std = float(np.std(arr))
    median = float(np.median(arr))
    p25 = float(np.percentile(arr, 25))
    p75 = float(np.percentile(arr, 75))
    p5 = float(np.percentile(arr, 5)) # 5th percentile / CVaR worst case

    return {
        "mean": round(mean, 2),
        "std": round(std, 2),
        "median": round(median, 2),
        "iqr_low": round(p25, 2),
        "iqr_high": round(p75, 2),
        "cvar_p5": round(p5, 2),
        "formatted_mean_sd": f"{mean:.1f} ± {std:.1f}",
        "formatted_median_iqr": f"{median:.1f} [{p25:.1f} - {p75:.1f}]",
        "formatted_p5": f"{p5:.1f}"
    }

def run_evaluation():
    print("=" * 85)
    print("PHASE 3 : ÉVALUATION STATISTIQUE RIGOUREUSE DES BASELINES (IN SILICO APPARIÉ)")
    print("=" * 85)

    # 1. Historical In Vivo Reference (14 days from MongoDB)
    print("\n[1] Extraction de la Référence Historique Observée (In Vivo - AAPS réel)...")
    df_raw = get_processed_dataframe(since="2026-10-01")
    real_sgv = df_raw['sgv'].dropna().values
    r_mean = float(np.mean(real_sgv))
    r_std = float(np.std(real_sgv))
    r_cv = float((r_std / r_mean) * 100.0)
    r_tir = float(np.mean((real_sgv >= 70.0) & (real_sgv <= 180.0)) * 100.0)
    r_ttir = float(np.mean((real_sgv >= 70.0) & (real_sgv <= 140.0)) * 100.0)
    r_tbr70 = float(np.mean(real_sgv < 70.0) * 100.0)
    r_tbr54 = float(np.mean(real_sgv < 54.0) * 100.0)
    r_tar180 = float(np.mean(real_sgv > 180.0) * 100.0)
    r_tar250 = float(np.mean(real_sgv > 250.0) * 100.0)
    r_lbgi, r_hbgi, r_bgri = kovatchev_indices(real_sgv)

    in_vivo_ref = {
        "mean_g": round(r_mean, 1),
        "cv_pct": round(r_cv, 1),
        "tir_70_180": round(r_tir, 1),
        "tight_tir_70_140": round(r_ttir, 1),
        "tbr_under_70": round(r_tbr70, 1),
        "tbr_under_54": round(r_tbr54, 1),
        "tar_over_180": round(r_tar180, 1),
        "tar_over_250": round(r_tar250, 1),
        "lbgi": r_lbgi,
        "hbgi": r_hbgi,
        "bgri": r_bgri
    }
    print(f"  • Référence Réelle In Vivo ({len(real_sgv)} points = ~14 jours) :")
    print(f"    TIR 70-180: {r_tir:.1f}% | Tight TIR: {r_ttir:.1f}% | TBR < 70: {r_tbr70:.1f}% | TBR < 54: {r_tbr54:.1f}% | TAR > 180: {r_tar180:.1f}% | Moyenne: {r_mean:.1f} mg/dL | CV: {r_cv:.1f}% | BGRI: {r_bgri:.2f}")

    # -------------------------------------------------------------------------
    # BANC A : 200 épisodes de 24h avec Domain Randomization standard
    # -------------------------------------------------------------------------
    print("\n[2] Banc d'Essai A : 200 épisodes appariés de 24h avec Domain Randomization...")
    n_episodes_a = 200
    seeds_a = [1000 + i for i in range(n_episodes_a)]

    configs_a = [
        {"name": "OpenLoop_BolusWizard", "use_shield": True, "policy_cls": OpenLoopBolusWizardPolicy},
        {"name": "PID_Controller_WithShield", "use_shield": True, "policy_cls": PIDControllerPolicy},
        {"name": "PID_Controller_NoShield", "use_shield": False, "policy_cls": PIDControllerPolicy},
        {"name": "Oref0_Heuristic_WithShield", "use_shield": True, "policy_cls": Oref0HeuristicPolicy},
        {"name": "Oref0_Heuristic_NoShield", "use_shield": False, "policy_cls": Oref0HeuristicPolicy},
    ]

    results_a: Dict[str, List[Dict[str, float]]] = {c["name"]: [] for c in configs_a}

    for ep_idx, seed in enumerate(seeds_a):
        if (ep_idx + 1) % 50 == 0:
            print(f"  -> Progression Banc A : {ep_idx + 1} / {n_episodes_a} épisodes terminés...")

        for cfg in configs_a:
            env = GlycoTwinEnv(domain_randomization=True, use_shield=cfg["use_shield"], episode_steps=288, seed=seed)
            pol = cfg["policy_cls"]()
            obs, info = env.reset(seed=seed, options={"scenario_type": "standard_day"})
            pol.reset()

            cgm_hist = [float(info["initial_cgm"])]
            rewards_hist = []
            shield_count = 0

            for step in range(288):
                act, _ = pol.predict(obs)
                obs, reward, terminated, truncated, info = env.step(act)
                cgm_hist.append(info["cgm_reading"])
                rewards_hist.append(reward)
                if info["shield"]["triggered"]:
                    shield_count += 1
                if terminated or truncated:
                    break

            ep_metric = compute_episode_metrics(cgm_hist, rewards_hist, shield_count, len(rewards_hist))
            results_a[cfg["name"]].append(ep_metric)

    # Aggregate Banc A distributions
    summary_a = {}
    for cfg_name, ep_list in results_a.items():
        summary_a[cfg_name] = {}
        for m_key in ep_list[0].keys():
            m_vals = [e[m_key] for e in ep_list]
            summary_a[cfg_name][m_key] = aggregate_distribution(m_vals)

    # -------------------------------------------------------------------------
    # TESTS STATISTIQUES SUR LES 200 GRAINES COMMUNES DU BANC A
    # -------------------------------------------------------------------------
    print("\n[3] Calcul des tests statistiques d'hypothèse (Wilcoxon signé par paires, N=200)...")
    wilcoxon_tests = {}
    pairs_to_compare = [
        ("Oref0_Heuristic_WithShield", "OpenLoop_BolusWizard"),
        ("Oref0_Heuristic_WithShield", "PID_Controller_WithShield"),
        ("PID_Controller_WithShield", "OpenLoop_BolusWizard"),
        ("Oref0_Heuristic_WithShield", "Oref0_Heuristic_NoShield"),
        ("PID_Controller_WithShield", "PID_Controller_NoShield")
    ]

    for model_a, model_b in pairs_to_compare:
        wilcoxon_tests[f"{model_a}_vs_{model_b}"] = {}
        for metric_name in ["tir_70_180", "tbr_under_70", "cumulative_reward"]:
            vals_a = [e[metric_name] for e in results_a[model_a]]
            vals_b = [e[metric_name] for e in results_a[model_b]]
            diff = np.array(vals_a) - np.array(vals_b)
            if np.all(diff == 0):
                w_stat, p_val = 0.0, 1.0
            else:
                res = stats.wilcoxon(vals_a, vals_b)
                w_stat, p_val = float(res.statistic), float(res.pvalue)

            wilcoxon_tests[f"{model_a}_vs_{model_b}"][metric_name] = {
                "mean_diff": round(float(np.mean(diff)), 2),
                "statistic": round(w_stat, 1),
                "p_value": p_val,
                "significant": p_val < 0.001
            }

    # -------------------------------------------------------------------------
    # BANC B : 5 SCÉNARIOS DE STRESS DÉDIÉS (50 épisodes par scénario)
    # -------------------------------------------------------------------------
    print("\n[4] Banc d'Essai B : Scénarios de Stress Dédiés (50 épisodes x 5 scénarios)...")
    stress_scenarios = [
        {"type": "forgotten_bolus", "label": "1. Bolus Oublié (Repas 60g)"},
        {"type": "high_fat_meal", "label": "2. Repas Gras / Absorption Retardée (T_max=110m)"},
        {"type": "exercise", "label": "3. Exercice Physique (+50% ISF / Captation GLUT4)"},
        {"type": "carb_undercounting", "label": "4. Sous-estimation Glucides (-40%)"},
        {"type": "carb_overestimation", "label": "5. Surestimation Glucides (+40% Bolus / Overdosage)"}
    ]

    controllers_b = [
        {"name": "OpenLoop_BolusWizard", "use_shield": True, "policy_cls": OpenLoopBolusWizardPolicy},
        {"name": "PID_Controller_WithShield", "use_shield": True, "policy_cls": PIDControllerPolicy},
        {"name": "Oref0_Heuristic_WithShield", "use_shield": True, "policy_cls": Oref0HeuristicPolicy}
    ]

    results_b: Dict[str, Dict[str, Dict[str, Any]]] = {}
    seeds_b = [2000 + i for i in range(50)]

    for sc in stress_scenarios:
        s_type = sc["type"]
        s_label = sc["label"]
        results_b[s_type] = {"label": s_label, "controllers": {}}

        for c_info in controllers_b:
            c_name = c_info["name"]
            c_ep_metrics = []

            for seed in seeds_b:
                env = GlycoTwinEnv(domain_randomization=True, use_shield=c_info["use_shield"], episode_steps=288, seed=seed)
                pol = c_info["policy_cls"]()
                obs, info = env.reset(seed=seed, options={"scenario_type": s_type})
                
                # Special customization for high_fat_meal: T_max = 110 min
                if s_type == "high_fat_meal":
                    env.patient.carb_t_max = 110.0

                pol.reset()
                cgm_hist = [float(info["initial_cgm"])]
                rewards_hist = []
                shield_count = 0

                for step in range(288):
                    act, _ = pol.predict(obs)
                    obs, reward, terminated, truncated, info = env.step(act)
                    cgm_hist.append(info["cgm_reading"])
                    rewards_hist.append(reward)
                    if info["shield"]["triggered"]:
                        shield_count += 1
                    if terminated or truncated:
                        break

                m = compute_episode_metrics(cgm_hist, rewards_hist, shield_count, len(rewards_hist))
                c_ep_metrics.append(m)

            # Summarize over 50 seeds
            c_summary = {}
            for k in ["tir_70_180", "tbr_under_70", "tbr_under_54", "tar_over_180", "bgri", "cumulative_reward"]:
                vals = [e[k] for e in c_ep_metrics]
                c_summary[k] = aggregate_distribution(vals)
            results_b[s_type]["controllers"][c_name] = c_summary

    # Assemble complete phase 3 output
    phase3_output = {
        "in_vivo_reference": in_vivo_ref,
        "banc_a_nominal": summary_a,
        "wilcoxon_tests": wilcoxon_tests,
        "banc_b_stress_tests": results_b
    }

    out_file = os.path.join(current_dir, "baselines_evaluation_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(phase3_output, f, indent=2)

    print(f"\nÉvaluation Phase 3 terminée avec succès. Résultats bruts dans : {out_file}")
    return phase3_output

if __name__ == "__main__":
    run_evaluation()

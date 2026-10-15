import os
import sys
import json
import math
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple

# Ensure app is importable
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.data.pipeline import get_processed_dataframe
from app.ml.metrics import calculate_regression_metrics, clarke_error_grid, block_bootstrap_ci
from app.ml.rl.config import PhysiologicalPriors, GateCriteria
from app.ml.rl.calibration.calibrator import PhysiologicalCalibrator
from app.ml.rl.calibration.clean_events import extract_clean_fasting_events, extract_clean_meal_events
from app.ml.rl.simulator.virtual_patient import VirtualPatient
from app.ml.rl.simulator.oref0_uam import Oref0UAMPerturbationEngine

def paired_block_bootstrap_eval(
    y_true: np.ndarray,
    y_pred_model: np.ndarray,
    y_pred_persist: np.ndarray,
    block_size: int = 24, # 2 hours = 24 steps
    n_bootstraps: int = 1000,
    confidence_level: float = 0.95
) -> Dict[str, Any]:
    n = len(y_true)
    err_m = np.abs(y_true - y_pred_model)
    err_p = np.abs(y_true - y_pred_persist)

    mae_m = float(np.mean(err_m))
    mae_p = float(np.mean(err_p))
    pt_delta_mae = mae_p - mae_m
    pt_ss = 1.0 - (mae_m / mae_p) if mae_p > 0 else 0.0

    n_blocks = max(1, n - block_size + 1)
    blocks_idx = [np.arange(i, i + block_size) for i in range(n_blocks)]
    blocks_needed = int(np.ceil(n / block_size))

    rng = np.random.RandomState(42)
    boot_deltas = []
    boot_ss = []

    for _ in range(n_bootstraps):
        sel_b = rng.choice(n_blocks, size=blocks_needed, replace=True)
        idx = np.concatenate([blocks_idx[b] for b in sel_b])[:n]
        em = float(np.mean(err_m[idx]))
        ep = float(np.mean(err_p[idx]))
        boot_deltas.append(ep - em)
        boot_ss.append(1.0 - (em / ep) if ep > 0 else 0.0)

    alpha = 1.0 - confidence_level
    ci_d_low = float(np.percentile(boot_deltas, 100.0 * (alpha / 2.0)))
    ci_d_high = float(np.percentile(boot_deltas, 100.0 * (1.0 - alpha / 2.0)))
    ci_ss_low = float(np.percentile(boot_ss, 100.0 * (alpha / 2.0)))
    ci_ss_high = float(np.percentile(boot_ss, 100.0 * (1.0 - alpha / 2.0)))

    return {
        "mae_model": round(mae_m, 2),
        "mae_persist": round(mae_p, 2),
        "point_delta_mae": round(pt_delta_mae, 2),
        "ci_95_delta_mae": [round(ci_d_low, 2), round(ci_d_high, 2)],
        "point_skill_score": round(pt_ss, 3),
        "ci_95_skill_score": [round(ci_ss_low, 3), round(ci_ss_high, 3)]
    }

def agp_summary(arr: np.ndarray) -> Dict[str, float]:
    arr = np.asarray(arr, dtype=float)
    return {
        "mean": round(float(np.mean(arr)), 1),
        "cv_pct": round(float((np.std(arr) / np.mean(arr)) * 100.0), 1),
        "tir_70_180": round(float(np.mean((arr >= 70.0) & (arr <= 180.0)) * 100.0), 1),
        "tbr_under_70": round(float(np.mean(arr < 70.0) * 100.0), 1),
        "tbr_under_54": round(float(np.mean(arr < 54.0) * 100.0), 1),
        "tar_over_180": round(float(np.mean(arr > 180.0) * 100.0), 1),
        "tar_over_250": round(float(np.mean(arr > 250.0) * 100.0), 1),
        "p10": round(float(np.percentile(arr, 10)), 1),
        "p25": round(float(np.percentile(arr, 25)), 1),
        "p50": round(float(np.percentile(arr, 50)), 1),
        "p75": round(float(np.percentile(arr, 75)), 1),
        "p90": round(float(np.percentile(arr, 90)), 1)
    }

def compute_deviations(dataframe: pd.DataFrame, isf: float = 32.0, sched_basal: float = 0.85) -> np.ndarray:
    """Computes exact oref0 metabolic deviations from IOB balance: Deviation = delta_G - BGI."""
    devs = [0.0]
    for j in range(1, len(dataframe)):
        g_prev = float(dataframe.iloc[j-1]['sgv'])
        g_curr = float(dataframe.iloc[j]['sgv'])
        delta_g = g_curr - g_prev
        b = float(dataframe.iloc[j-1].get('bolus', 0.0))
        basal = float(dataframe.iloc[j-1].get('basal', sched_basal))
        delivered = b + (basal - sched_basal) * (5.0 / 60.0)
        delta_iob = float(dataframe.iloc[j].get('iob', 0.0)) - float(dataframe.iloc[j-1].get('iob', 0.0))
        act = np.clip(delivered - delta_iob, 0.0, 1.5)
        bgi = -act * isf
        dev = delta_g - bgi
        devs.append(float(np.clip(dev, -10.0, 25.0)))
    return np.array(devs)

def main():
    print("=" * 85)
    print("CLÔTURE DÉFINITIVE DE LA PHASE 1 : MODÈLE PHYSIOLOGIQUE CORRIGÉ + UAM CAUSAL")
    print("=" * 85)

    # 1. Load Data
    df_raw = get_processed_dataframe(since="2026-10-01")
    df = df_raw.sort_values("datetime").reset_index(drop=True)
    n_total = len(df)
    split_idx = int(0.70 * n_total)
    df_train = df.iloc[:split_idx].copy().reset_index(drop=True)
    df_test = df.iloc[split_idx:].copy().reset_index(drop=True)

    print(f"\n[1] Données : {n_total} points au total.")
    print(f"  • Train : {len(df_train)} points ({df_train.iloc[0]['datetime']} -> {df_train.iloc[-1]['datetime']})")
    print(f"  • Test  : {len(df_test)} points ({df_test.iloc[0]['datetime']} -> {df_test.iloc[-1]['datetime']})")

    # 2. Calibration
    calibrator = PhysiologicalCalibrator()
    calib = calibrator.calibrate(df_train, n_bootstraps=500)
    isf_base = calib.get("isf_base", 32.0)
    dia_calib = calib.get("dia", 7.5)
    sched_basal = 0.85
    print(f"\n[2] Paramètres physiologiques calibrés :")
    print(f"  • ISF de base : {isf_base:.1f} mg/dL/U")
    print(f"  • DIA         : {dia_calib:.1f} h")
    print(f"  • EGP baseline: {calib.get('egp_baseline', 105.0):.1f} mg/dL")

    # Reconstruct test deviations
    devs_test = compute_deviations(df_test, isf=isf_base, sched_basal=sched_basal)

    # -------------------------------------------------------------------------
    # POINT 1 & 2 : ÉVALUATION À +30 ET +60 MIN (TABLEAU 1 & TABLEAU 2)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 85)
    print("TABLEAU 1 : VALIDATION PRÉDICTIVE À +30 ET +60 MIN (AVEC IC BOOTSTRAP APPARIÉ B=1000)")
    print("=" * 85)

    table1_results = {}
    table2_stratification = {}

    for h_name, h_steps in [("30min", 6), ("60min", 12)]:
        y_true, y_pe, y_pu = [], [], []
        y_uam_dict = {45.0: [], 50.0: [], 60.0: []}
        y_t0 = []

        for i in range(12, len(df_test) - h_steps, 2):
            g0 = float(df_test.iloc[i]['sgv'])
            gt = float(df_test.iloc[i + h_steps]['sgv'])
            if np.isnan(g0) or np.isnan(gt):
                continue

            dt0 = pd.to_datetime(df_test.iloc[i]['datetime'])
            hour0 = dt0.hour + dt0.minute / 60.0
            iob0 = float(df_test.iloc[i].get('iob', 0.0))
            cob0 = float(df_test.iloc[i].get('cob', 0.0))

            y_true.append(gt)
            y_pe.append(g0)
            y_t0.append(g0)

            # Mean deviation over past 15 min [i-2 : i]
            d0 = float(np.mean(devs_test[max(0, i-2) : i+1]))

            # Simulation Pure Physio (fixed double IOB: start_iob populated, past_boluses empty)
            pat_p = VirtualPatient(calibrated_params=calib, seed=42 + i)
            pat_p.reset(start_bg=g0, start_iob=iob0, start_cob=cob0)

            for step_offset in range(1, h_steps + 1):
                row = df_test.iloc[i + step_offset]
                h_curr = (hour0 + (step_offset * 5.0) / 60.0) % 24.0
                pat_p.step(
                    hour_of_day=h_curr,
                    basal_rate_delivered=float(row.get('basal', sched_basal)),
                    bolus_delivered=float(row.get('bolus', 0.0)),
                    carbs_consumed=float(row.get('carbs', 0.0))
                )
            y_pu.append(pat_p.current_bg)

            # Simulation Physio + UAM for tau in [45, 50, 60]
            for tau in [45.0, 50.0, 60.0]:
                pat_u = VirtualPatient(calibrated_params=calib, seed=42 + i)
                pat_u.reset(start_bg=g0, start_iob=iob0, start_cob=cob0)
                for step_offset in range(1, h_steps + 1):
                    row = df_test.iloc[i + step_offset]
                    h_curr = (hour0 + (step_offset * 5.0) / 60.0) % 24.0
                    pat_u.step(
                        hour_of_day=h_curr,
                        basal_rate_delivered=float(row.get('basal', sched_basal)),
                        bolus_delivered=float(row.get('bolus', 0.0)),
                        carbs_consumed=float(row.get('carbs', 0.0))
                    )
                    flux = d0 * np.exp(-(step_offset * 5.0) / tau)
                    pat_u.current_bg = float(np.clip(pat_u.current_bg + flux, 30.0, 400.0))
                y_uam_dict[tau].append(pat_u.current_bg)

        yt = np.array(y_true)
        ype = np.array(y_pe)
        ypu = np.array(y_pu)
        yt0 = np.array(y_t0)

        # Baseline & Pure Physio metrics
        m_pe = calculate_regression_metrics(yt, ype)
        c_pe = clarke_error_grid(yt, ype)

        m_pu = calculate_regression_metrics(yt, ypu)
        c_pu = clarke_error_grid(yt, ypu)
        bs_pu = paired_block_bootstrap_eval(yt, ypu, ype, block_size=24, n_bootstraps=1000)

        h_data = {
            "n_samples": len(yt),
            "persistence": {**m_pe, "clarke": c_pe},
            "pure_physio": {
                **m_pu,
                "clarke": c_pu,
                "signed_bias": round(float(np.mean(ypu - yt)), 2),
                "skill_score": bs_pu["point_skill_score"],
                "ci_95_skill_score": bs_pu["ci_95_skill_score"],
                "delta_mae": bs_pu["point_delta_mae"],
                "ci_95_delta_mae": bs_pu["ci_95_delta_mae"]
            },
            "physio_uam": {}
        }

        print(f"\n>>> Horizon +{h_name} (N = {len(yt)} points de test)")
        print(f"{'Modèle':<28} | {'RMSE':<6} | {'MAE':<6} | {'Clarke A+B':<10} | {'Zone E':<6} | {'Biais':<7} | {'Skill Score [IC 95%]':<25}")
        print("-" * 105)
        print(f"{'1. Persistance (T-0)':<28} | {m_pe['rmse']:<6.1f} | {m_pe['mae']:<6.1f} | {c_pe['zone_ab']:<9.1f}% | {c_pe['zone_e']:<5.1f}% | {m_pe['bias']:<+7.1f} | {'Réf. (0.000)':<25}")
        print(f"{'2. Physio pur corrigé':<28} | {m_pu['rmse']:<6.1f} | {m_pu['mae']:<6.1f} | {c_pu['zone_ab']:<9.1f}% | {c_pu['zone_e']:<5.1f}% | {np.mean(ypu-yt):<+7.1f} | {bs_pu['point_skill_score']:+.3f} [{bs_pu['ci_95_skill_score'][0]:+.3f}, {bs_pu['ci_95_skill_score'][1]:+.3f}]")

        for tau in [45.0, 50.0, 60.0]:
            yua = np.array(y_uam_dict[tau])
            m_ua = calculate_regression_metrics(yt, yua)
            c_ua = clarke_error_grid(yt, yua)
            bs_ua = paired_block_bootstrap_eval(yt, yua, ype, block_size=24, n_bootstraps=1000)
            h_data["physio_uam"][f"tau_{int(tau)}min"] = {
                **m_ua,
                "clarke": c_ua,
                "signed_bias": round(float(np.mean(yua - yt)), 2),
                "skill_score": bs_ua["point_skill_score"],
                "ci_95_skill_score": bs_ua["ci_95_skill_score"],
                "delta_mae": bs_ua["point_delta_mae"],
                "ci_95_delta_mae": bs_ua["ci_95_delta_mae"]
            }
            lbl = f"3. Physio + UAM (tau={int(tau)}m)"
            print(f"{lbl:<28} | {m_ua['rmse']:<6.1f} | {m_ua['mae']:<6.1f} | {c_ua['zone_ab']:<9.1f}% | {c_ua['zone_e']:<5.1f}% | {np.mean(yua-yt):<+7.1f} | {bs_ua['point_skill_score']:+.3f} [{bs_ua['ci_95_skill_score'][0]:+.3f}, {bs_ua['ci_95_skill_score'][1]:+.3f}]")

        table1_results[h_name] = h_data

        # Table 2: Stratification by State at t0 (for tau=45 min and tau=50 min)
        best_yua = np.array(y_uam_dict[45.0])
        hypo = yt0 < 70.0
        targ = (yt0 >= 70.0) & (yt0 <= 180.0)
        hype = yt0 > 180.0

        strat = {}
        for r_name, mask in [("Hypoglycémie (<70)", hypo), ("Cible euglycémique (70-180)", targ), ("Hyperglycémie (>180)", hype)]:
            n_sub = int(np.sum(mask))
            if n_sub > 0:
                strat[r_name] = {
                    "N": n_sub,
                    "mae_persist": round(float(np.mean(np.abs(yt[mask] - ype[mask]))), 1),
                    "mae_pure_physio": round(float(np.mean(np.abs(yt[mask] - ypu[mask]))), 1),
                    "mae_physio_uam": round(float(np.mean(np.abs(yt[mask] - best_yua[mask]))), 1),
                    "bias_persist": round(float(np.mean(ype[mask] - yt[mask])), 1),
                    "bias_pure_physio": round(float(np.mean(ypu[mask] - yt[mask])), 1),
                    "bias_physio_uam": round(float(np.mean(best_yua[mask] - yt[mask])), 1)
                }
        table2_stratification[h_name] = strat

    print("\n" + "=" * 85)
    print("TABLEAU 2 : STRATIFICATION PAR RÉGIME À t0 ET AUDIT DU BIAIS EN HYPERGLYCÉMIE")
    print("=" * 85)
    for h_name, strat in table2_stratification.items():
        print(f"\n>>> Stratification à +{h_name} :")
        print(f"{'Régime à t0':<30} | {'N':<4} | {'MAE Persist':<11} | {'MAE Phys+UAM':<12} | {'Biais Persist':<13} | {'Biais Phys Pur':<14} | {'Biais Phys+UAM':<14}")
        print("-" * 115)
        for r_name, d in strat.items():
            print(f"{r_name:<30} | {d['N']:<4} | {d['mae_persist']:<11.1f} | {d['mae_physio_uam']:<12.1f} | {d['bias_persist']:<+13.1f} | {d['bias_pure_physio']:<+14.1f} | {d['bias_physio_uam']:<+14.1f}")

    # -------------------------------------------------------------------------
    # POINT 3 : ROLLOUTS 24H ET 72H CORRIGÉS AVEC PERTURBATIONS EXOGÈNES (TABLEAU 3)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 85)
    print("TABLEAU 3 : ROLLOUTS EN BOUCLE OUVERTE 24H ET 72H (RÉEL vs SIMULÉ NAÏF vs SIMULÉ AVEC UAM)")
    print("=" * 85)

    # Reconstruct causal disturbance along test sequence
    disturbances = [0.0]
    for s in range(1, len(df_test)):
        g_prev = float(df_test.iloc[s-1]['sgv'])
        g_curr = float(df_test.iloc[s]['sgv'])
        delta_real = g_curr - g_prev
        dt = pd.to_datetime(df_test.iloc[s]['datetime'])
        vp = VirtualPatient(calibrated_params=calib, seed=42)
        vp.reset(start_bg=g_prev, start_iob=float(df_test.iloc[s-1].get('iob', 0.0)))
        sim_bg, _ = vp.step(
            hour_of_day=dt.hour + dt.minute / 60.0,
            basal_rate_delivered=float(df_test.iloc[s].get('basal', sched_basal)),
            bolus_delivered=float(df_test.iloc[s].get('bolus', 0.0)),
            carbs_consumed=float(df_test.iloc[s].get('carbs', 0.0))
        )
        d = delta_real - (sim_bg - g_prev)
        disturbances.append(d)

    # 15-min rolling mean (3 steps) bounded to [-4.0, 10.0] mg/dL / 5min
    d_series = pd.Series(disturbances)
    uam_causal_smoothed = d_series.rolling(3, min_periods=1).mean().clip(lower=-4.0, upper=10.0).values

    table3_rollouts = {}
    for dur_name, n_steps in [("24h", 288), ("72h", min(864, len(df_test)))]:
        real_sgv = df_test.iloc[:n_steps]['sgv'].values
        g0 = float(real_sgv[0])
        iob0 = float(df_test.iloc[0].get('iob', 0.0))
        cob0 = float(df_test.iloc[0].get('cob', 0.0))

        # A. Naive Rollout (pure delivered insulin, declared carbs only, no UAM)
        pat_naive = VirtualPatient(calibrated_params=calib, seed=42)
        pat_naive.reset(start_bg=g0, start_iob=iob0, start_cob=cob0, site_age_days=1.0, autosens_initial=1.0)
        sim_naive = [g0]
        for s in range(1, n_steps):
            row = df_test.iloc[s]
            dt = pd.to_datetime(row['datetime'])
            bg, _ = pat_naive.step(
                hour_of_day=dt.hour + dt.minute / 60.0,
                basal_rate_delivered=float(row.get('basal', sched_basal)),
                bolus_delivered=float(row.get('bolus', 0.0)),
                carbs_consumed=float(row.get('carbs', 0.0))
            )
            sim_naive.append(bg)

        # B. Causal UAM Rollout (delivered insulin + declared carbs + bounded UAM perturbation)
        pat_uam_roll = VirtualPatient(calibrated_params=calib, seed=42)
        pat_uam_roll.reset(start_bg=g0, start_iob=iob0, start_cob=cob0, site_age_days=1.0, autosens_initial=1.0)
        sim_uam_roll = [g0]
        for s in range(1, n_steps):
            row = df_test.iloc[s]
            dt = pd.to_datetime(row['datetime'])
            pat_uam_roll.step(
                hour_of_day=dt.hour + dt.minute / 60.0,
                basal_rate_delivered=float(row.get('basal', sched_basal)),
                bolus_delivered=float(row.get('bolus', 0.0)),
                carbs_consumed=float(row.get('carbs', 0.0))
            )
            pat_uam_roll.current_bg = float(np.clip(pat_uam_roll.current_bg + uam_causal_smoothed[s], 35.0, 400.0))
            sim_uam_roll.append(pat_uam_roll.current_bg)

        sr = agp_summary(np.array(real_sgv))
        sn = agp_summary(np.array(sim_naive))
        su = agp_summary(np.array(sim_uam_roll))

        table3_rollouts[dur_name] = {
            "real": sr,
            "sim_naive": sn,
            "sim_uam": su
        }

        print(f"\n>>> Rollout en boucle ouverte {dur_name} ({n_steps} pas de 5 min = {n_steps*5/60:.0f}h) :")
        print(f"{'Metrique AGP':<18} | {'Observe Reel':<14} | {'Simule Naif (Sans UAM)':<24} | {'Simule Corrige (Avec UAM causal)':<32}")
        print("-" * 95)
        for k in ["mean", "cv_pct", "tir_70_180", "tbr_under_70", "tbr_under_54", "tar_over_180", "tar_over_250", "p10", "p25", "p50", "p75", "p90"]:
            print(f"{k:<18} | {sr[k]:<14.1f} | {sn[k]:<24.1f} | {su[k]:<32.1f}")

    # -------------------------------------------------------------------------
    # POINT 4 : VALIDATION PAR ÉVÉNEMENTS (TABLEAU 4)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 85)
    print("TABLEAU 4 : VALIDATION PAR EVENEMENTS (CORRECTIONS & REPAS PROPRES DU TEST)")
    print("=" * 85)

    fasting_ev = extract_clean_fasting_events(df_test, min_duration_steps=12)
    meal_ev = extract_clean_meal_events(df_test, post_meal_steps=24)

    print(f"\nEvenements purs extraits sur le jeu de test : {len(fasting_ev)} corrections / jeûnes, {len(meal_ev)} repas propres.\n")

    # Corrections validation
    corr_results = []
    print("--- A. Evenements de Correction (Jeune / Baisse sous insuline) ---")
    print(f"{'Evenement':<14} | {'G0 (mg/dL)':<10} | {'IOB (U)':<7} | {'Observe (Nadir, dG, T)':<25} | {'Simule (Nadir, dG, T)':<25} | {'Erreur dG':<11} | {'Erreur T':<9}")
    print("-" * 115)

    for idx, ev in enumerate(fasting_ev):
        w = ev['window_df'].reset_index(drop=True)
        g0 = float(w.iloc[0]['sgv'])
        obs_nadir = float(w['sgv'].min())
        obs_t = int(w['sgv'].idxmin() * 5)
        obs_dg = obs_nadir - g0

        vp = VirtualPatient(calibrated_params=calib, seed=42)
        vp.reset(start_bg=g0, start_iob=float(w.iloc[0].get('iob', 0.0)), start_cob=0.0, site_age_days=1.0, autosens_initial=1.0)
        sim_bgs = [g0]
        for s in range(1, len(w)):
            dt = pd.to_datetime(w.iloc[s]['datetime'])
            sim_bg, _ = vp.step(
                hour_of_day=dt.hour + dt.minute / 60.0,
                basal_rate_delivered=float(w.iloc[s].get('basal', sched_basal)),
                bolus_delivered=float(w.iloc[s].get('bolus', 0.0)),
                carbs_consumed=0.0
            )
            sim_bgs.append(sim_bg)

        sim_series = pd.Series(sim_bgs)
        sim_nadir = float(sim_series.min())
        sim_t = int(sim_series.idxmin() * 5)
        sim_dg = sim_nadir - g0
        err_dg = sim_dg - obs_dg
        err_t = sim_t - obs_t

        res_item = {
            "datetime": ev["start_datetime"],
            "g0": round(g0, 1),
            "mean_iob": round(ev["mean_iob"], 2),
            "obs_nadir": round(obs_nadir, 1),
            "obs_delta_g": round(obs_dg, 1),
            "obs_time_min": obs_t,
            "sim_nadir": round(sim_nadir, 1),
            "sim_delta_g": round(sim_dg, 1),
            "sim_time_min": sim_t,
            "err_delta_g": round(err_dg, 1),
            "err_time_min": err_t
        }
        corr_results.append(res_item)

        if idx < 3:
            obs_str = f"{obs_nadir:.0f} mg/dL ({obs_dg:+.0f}, {obs_t}m)"
            sim_str = f"{sim_nadir:.0f} mg/dL ({sim_dg:+.0f}, {sim_t}m)"
            print(f"Correction #{idx+1:<3} | {g0:<10.0f} | {ev['mean_iob']:<7.2f} | {obs_str:<25} | {sim_str:<25} | {err_dg:<+11.1f} | {err_t:<+9d}m")

    # Meals validation
    meal_results = []
    print("\n--- B. Evenements de Repas (Excursion post-prandiale) ---")
    print(f"{'Evenement':<14} | {'G0 (mg/dL)':<10} | {'Carbs/Bolus':<12} | {'Observe (Pic, dG, T)':<25} | {'Simule (Pic, dG, T)':<25} | {'Erreur dG':<11} | {'Erreur T':<9}")
    print("-" * 115)

    for idx, m in enumerate(meal_ev):
        w = m['window_df'].reset_index(drop=True)
        g0 = float(w.iloc[0]['sgv'])
        obs_peak = float(w['sgv'].max())
        obs_t = int(w['sgv'].idxmax() * 5)
        obs_dg = obs_peak - g0

        vp = VirtualPatient(calibrated_params=calib, seed=42)
        vp.reset(start_bg=g0, start_iob=float(w.iloc[0].get('iob', 0.0)), start_cob=0.0, site_age_days=1.0, autosens_initial=1.0)
        sim_bgs = [g0]
        for s in range(1, len(w)):
            dt = pd.to_datetime(w.iloc[s]['datetime'])
            c_step = float(w.iloc[s].get('carbs', 0.0))
            b_step = float(w.iloc[s].get('bolus', 0.0))
            sim_bg, _ = vp.step(
                hour_of_day=dt.hour + dt.minute / 60.0,
                basal_rate_delivered=float(w.iloc[s].get('basal', sched_basal)),
                bolus_delivered=b_step,
                carbs_consumed=c_step
            )
            sim_bgs.append(sim_bg)

        sim_series = pd.Series(sim_bgs)
        sim_peak = float(sim_series.max())
        sim_t = int(sim_series.idxmax() * 5)
        sim_dg = sim_peak - g0
        err_dg = sim_dg - obs_dg
        err_t = sim_t - obs_t

        res_item = {
            "datetime": m["datetime"],
            "g0": round(g0, 1),
            "carbs": m["carbs"],
            "bolus": m["bolus"],
            "obs_peak": round(obs_peak, 1),
            "obs_delta_g": round(obs_dg, 1),
            "obs_time_min": obs_t,
            "sim_peak": round(sim_peak, 1),
            "sim_delta_g": round(sim_dg, 1),
            "sim_time_min": sim_t,
            "err_delta_g": round(err_dg, 1),
            "err_time_min": err_t
        }
        meal_results.append(res_item)

        if idx < 3:
            cb_str = f"{m['carbs']}g / {m['bolus']}U"
            obs_str = f"{obs_peak:.0f} mg/dL ({obs_dg:+.0f}, {obs_t}m)"
            sim_str = f"{sim_peak:.0f} mg/dL ({sim_dg:+.0f}, {sim_t}m)"
            print(f"Repas #{idx+1:<9} | {g0:<10.0f} | {cb_str:<12} | {obs_str:<25} | {sim_str:<25} | {err_dg:<+11.1f} | {err_t:<+9d}m")

    # Aggregate Event Statistics
    corr_mae = float(np.mean([abs(r["err_delta_g"]) for r in corr_results]))
    corr_bias = float(np.mean([r["err_delta_g"] for r in corr_results]))
    corr_t_err = float(np.mean([abs(r["err_time_min"]) for r in corr_results]))

    meal_mae = float(np.mean([abs(r["err_delta_g"]) for r in meal_results]))
    meal_bias = float(np.mean([r["err_delta_g"] for r in meal_results]))
    meal_t_err = float(np.mean([abs(r["err_time_min"]) for r in meal_results]))

    print("\n--- Synthese Statistique sur Tous les Evenements de Test ---")
    print(f"  * Corrections (N = {len(corr_results)}) : MAE sur dG = {corr_mae:.1f} mg/dL | Biais signe = {corr_bias:+.1f} mg/dL | Erreur moyenne delai = {corr_t_err:.1f} min")
    print(f"  * Repas       (N = {len(meal_results)}) : MAE sur dG = {meal_mae:.1f} mg/dL | Biais signe = {meal_bias:+.1f} mg/dL | Erreur moyenne delai = {meal_t_err:.1f} min")

    table4_events = {
        "corrections_sample_3": corr_results[:3],
        "meals_sample_3": meal_results[:3],
        "all_corrections_summary": {
            "n_events": len(corr_results),
            "mae_delta_g_mgdl": round(corr_mae, 1),
            "signed_bias_delta_g_mgdl": round(corr_bias, 1),
            "mean_timing_error_min": round(corr_t_err, 1)
        },
        "all_meals_summary": {
            "n_events": len(meal_results),
            "mae_delta_g_mgdl": round(meal_mae, 1),
            "signed_bias_delta_g_mgdl": round(meal_bias, 1),
            "mean_timing_error_min": round(meal_t_err, 1)
        }
    }

    # Save to JSON
    output_all = {
        "table1_validation_30_60min": table1_results,
        "table2_stratification_and_hyper_bias": table2_stratification,
        "table3_rollouts_24h_72h": table3_rollouts,
        "table4_event_validation": table4_events
    }

    out_json = os.path.join(current_dir, "phase1_closure_results.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(output_all, f, indent=2)
    print(f"\nRésultats complets de la clôture Phase 1 enregistrés dans : {out_json}")

if __name__ == "__main__":
    main()

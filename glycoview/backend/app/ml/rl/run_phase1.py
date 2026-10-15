import os
import sys
import json
import pandas as pd
import numpy as np

# Ensure app is importable
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.data.pipeline import get_processed_dataframe
from app.ml.rl.calibration.calibrator import PhysiologicalCalibrator
from app.ml.rl.calibration.validator import DigitalTwinValidator
from app.ml.rl.calibration.params_store import save_calibration_params

def run_phase1_pipeline():
    print("=" * 80)
    print("PHASE 1 (REVISÉE) : CALIBRATION PHYSIOLOGIQUE & VALIDATION HYBRIDE STRICTE")
    print("=" * 80)

    # 1. Load historical data from MongoDB
    print("\n[1/4] Extraction des données historiques réelles...")
    df_raw = get_processed_dataframe(since="2026-10-01")
    if df_raw.empty:
        raise RuntimeError("Aucune donnée disponible dans MongoDB.")

    df = df_raw.sort_values("datetime").reset_index(drop=True)
    n_total = len(df)
    print(f"Total points 5-min disponibles : {n_total} (du {df.iloc[0]['datetime']} au {df.iloc[-1]['datetime']})")

    # 2. Chronological Split (70% train / 30% test)
    split_idx = int(0.70 * n_total)
    df_train = df.iloc[:split_idx].copy().reset_index(drop=True)
    df_test = df.iloc[split_idx:].copy().reset_index(drop=True)

    print(f"\n[2/4] Découpage chronologique strict :")
    print(f"  • Train (Calibration 70%) : {len(df_train)} points ({df_train.iloc[0]['datetime']} -> {df_train.iloc[-1]['datetime']})")
    print(f"  • Test (Validation 30%)   : {len(df_test)} points ({df_test.iloc[0]['datetime']} -> {df_test.iloc[-1]['datetime']})")

    # 3. Calibration
    print("\n[3/4] Calibration compacte avec priors AAPS & Block Bootstrap (B=500)...")
    calibrator = PhysiologicalCalibrator()
    calib_results = calibrator.calibrate(df_train, n_bootstraps=500)

    # Save calibrated params
    saved_path = save_calibration_params(calib_results)
    print(f"  -> Paramètres sauvegardés dans : {saved_path}")
    print(f"  • DIA fixé à                     : {calib_results['dia']} h")
    print(f"  • EGP homéostatique sain fixé à  : {calib_results['egp_baseline']} mg/dL")
    print(f"  • Événements jeûne pur extraits  : {calib_results['n_fasting_events_extracted']}")
    print(f"  • Repas isolés propres extraits  : {calib_results['n_meal_events_extracted']}")

    print("\n  Détail des paramètres calibrés et distributions bootstrap :")
    for pname, pinfo in calib_results["diagnostics"].items():
        bound_warn = " [ATTENTION: SUR BORNE]" if pinfo["at_boundary"] else ""
        print(f"    - {pname:14}: {pinfo['point_estimate']:4.1f} (Prior: {pinfo['prior']:4.1f}) | {pinfo['status']} (N={pinfo['n_events']}) | IC 95%: [{pinfo['ci_95'][0]}, {pinfo['ci_95'][1]}]{bound_warn}")
        print(f"      Distribution brute: p2.5={pinfo['raw_distribution']['p2_5']}, p25={pinfo['raw_distribution']['p25']}, p50={pinfo['raw_distribution']['p50']}, p75={pinfo['raw_distribution']['p75']}, p97.5={pinfo['raw_distribution']['p97_5']}")

    # 4. Open-Loop Validation with Hybrid Architecture
    print("\n[4/4] Validation prospective en boucle ouverte (Jumeau Hybride vs Persistance vs Physio)...")
    validator = DigitalTwinValidator(calibrated_params=calib_results)
    val_results = validator.validate(df_train, df_test, step_stride=2)

    # Print validation table
    print("\n" + "-" * 80)
    print("RÉSULTATS DE VALIDATION À +30 MIN ET +60 MIN (Test Set)")
    print("-" * 80)
    for h in ["30min", "60min"]:
        data = val_results["horizons"][h]
        hyb = data["hybrid"]
        phy = data["pure_physio"]
        pe = data["persistence"]
        print(f"\n>>> Horizon +{h} (N = {data['n_samples']} évaluations) :")
        print(f"  • Jumeau HYBRIDE      : MAE = {hyb['mae']:5.2f} mg/dL | RMSE = {hyb['rmse']:5.2f} | MARD = {hyb['mard']:4.1f}% | Skill Score = {hyb['skill_score_vs_persist']:+.3f} | Clarke A+B = {hyb['clarke']['zone_ab']}% (A: {hyb['clarke']['zone_a']}%, B: {hyb['clarke']['zone_b']}%, E: {hyb['clarke']['zone_e']}%)")
        print(f"  • Jumeau PHYSIO PUR   : MAE = {phy['mae']:5.2f} mg/dL | RMSE = {phy['rmse']:5.2f} | MARD = {phy['mard']:4.1f}% | Skill Score = {phy['skill_score_vs_persist']:+.3f} | Clarke A+B = {phy['clarke']['zone_ab']}% (E: {phy['clarke']['zone_e']}%)")
        print(f"  • Persistance (T-0)   : MAE = {pe['mae']:5.2f} mg/dL | RMSE = {pe['rmse']:5.2f} | MARD = {pe['mard']:4.1f}% | Clarke A+B = {pe['clarke']['zone_ab']}%")
        
        diff = data["delta_mae_gain_vs_persist"]
        print(f"  • Gain MAE vs Persist : {diff['mean_gain']:+.2f} mg/dL (IC 95%: [{diff['ci_95'][0]}, {diff['ci_95'][1]}])")
        
        print(f"  • Biais Signé Global  : {hyb['signed_bias']:+.2f} mg/dL")
        print(f"  • Biais Signé par Régime : Hypo={hyb['signed_bias_by_regime']['hypo']:+.2f} | Cible={hyb['signed_bias_by_regime']['target']:+.2f} | Hyper={hyb['signed_bias_by_regime']['hyper']:+.2f}")
        print(f"  • Biais Signé par Heure  : Nuit={hyb['signed_bias_by_hour']['night_00h_06h']} | Matin={hyb['signed_bias_by_hour']['morning_06h_12h']} | Midi={hyb['signed_bias_by_hour']['afternoon_12h_18h']} | Soir={hyb['signed_bias_by_hour']['evening_18h_24h']}")
        print(f"  • MAE par Régime : Hypo={hyb['mae_by_regime']['hypo']} (Persist: {pe['mae_by_regime']['hypo']}) | Cible={hyb['mae_by_regime']['target']} (Persist: {pe['mae_by_regime']['target']}) | Hyper={hyb['mae_by_regime']['hyper']} (Persist: {pe['mae_by_regime']['hyper']})")

    # Gate Criteria Check
    print("\n" + "=" * 80)
    print("VÉRIFICATION DES CRITÈRES FIXÉS A PRIORI (GATE CRITERIA) :")
    print("=" * 80)
    for crit_name, cinfo in val_results["gate_checks"].items():
        status = "PASSED" if cinfo["passed"] else "FAILED"
        print(f"  • {crit_name:25}: Valeur = {cinfo['value']} (Cible: {cinfo['target']}) -> [{status}]")

    print(f"\nDECISION FINALE PHASE 1 : {'ACCEPTÉE' if val_results['is_acceptable'] else 'NON ACCEPTÉE'}")
    print("=" * 80)

    # Save detailed validation output
    report_path = os.path.join(current_dir, "validation_results.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(val_results, f, indent=2)

    return calib_results, val_results

if __name__ == "__main__":
    run_phase1_pipeline()

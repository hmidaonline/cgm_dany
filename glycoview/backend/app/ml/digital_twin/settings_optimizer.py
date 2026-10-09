import numpy as np
import pandas as pd
from typing import Dict, List, Any

from app.ml.features import prepare_ml_dataset
from app.ml.digital_twin.model import DigitalTwinModel

def analyze_user_settings(
    df_raw: pd.DataFrame,
    twin_model: DigitalTwinModel
) -> Dict[str, Any]:
    """
    Analyzes historical pump/loop settings (Basal, ISF, CR) by 3-hour time blocks.
    Evaluates whether settings are optimal, under-dosed, or over-dosed with confidence levels.
    """
    df_feat, feature_cols, target_cols = prepare_ml_dataset(df_raw)
    
    if df_feat.empty or len(df_feat) < 50:
        return {"status": "error", "message": "Données insuffisantes pour l'analyse des réglages."}

    data = df_feat.copy()
    if 'datetime' in data.columns:
        data['hour'] = pd.to_datetime(data['datetime']).dt.hour
    else:
        data['hour'] = 12

    time_blocks_analysis = []

    block_labels = [
        "00h00 - 03h00 (Nuit profonde)",
        "03h00 - 06h00 (Fin de nuit / Aube)",
        "06h00 - 09h00 (Petit déjeuner / Réveil)",
        "09h00 - 12h00 (Matinée)",
        "12h00 - 15h00 (Déjeuner)",
        "15h00 - 18h00 (Après-midi)",
        "18h00 - 21h00 (Dîner)",
        "21h00 - 24h00 (Début de nuit)"
    ]

    for block_idx in range(8):
        start_h, end_h = block_idx * 3, (block_idx + 1) * 3
        sub = data[(data['hour'] >= start_h) & (data['hour'] < end_h)]
        
        current_isf = twin_model.isf_by_block.get(block_idx, 40.0)
        current_cr = twin_model.cr_by_block.get(block_idx, 10.0)
        current_basal = twin_model.basal_by_block.get(block_idx, 0.8)

        if sub.empty:
            time_blocks_analysis.append({
                "block_id": block_idx,
                "label": block_labels[block_idx],
                "time_range": f"{start_h:02d}h00 - {end_h:02d}h00",
                "isf_estimated": current_isf,
                "cr_estimated": current_cr,
                "basal_estimated": current_basal,
                "status_basal": "Données insuffisantes",
                "status_isf": "Données insuffisantes",
                "confidence": "Faible",
                "recommendation_note": "Conserver les réglages actuels et accumuler plus de données."
            })
            continue

        mean_sgv = float(sub['sgv'].mean())
        pct_tbr = float((sub['sgv'] < 70).mean() * 100.0)
        pct_tar = float((sub['sgv'] > 180).mean() * 100.0)

        # Basal evaluation logic
        fasting_sub = sub[(sub['cob'] < 2.0) & (sub['iob'] < 0.8)]
        if not fasting_sub.empty and 'sgv_diff_15' in fasting_sub.columns:
            fasting_trend = float(fasting_sub['sgv_diff_15'].mean())
            if fasting_trend > 4.0:
                basal_status = "Basale sous-dosée (tendance à la hausse à jeun)"
                basal_note = "La glycémie monte à jeun dans ce créneau. Piste à discuter avec l'équipe médicale : légère hausse du débit basal."
            elif fasting_trend < -4.0 or pct_tbr > 5.0:
                basal_status = "Basale sur-dosée (tendance à la baisse ou hypos)"
                basal_note = "La glycémie a tendance à chuter à jeun. Piste à discuter : diminution prudente de la basale."
            else:
                basal_status = "Basale bien adaptée (glycémie stable à jeun)"
                basal_note = "Le débit basal actuel maintient la glycémie stable."
        else:
            basal_status = "Basale généralement adaptée"
            basal_note = "Absence de dérive significative observée à jeun."

        # ISF & CR evaluation logic
        if pct_tbr > 8.0:
            isf_status = "Sensibilité potentiellement sous-estimée (ISF trop fort)"
            cr_status = "Ratio glucides potentiellement trop fort"
        elif pct_tar > 25.0:
            isf_status = "Sensibilité surestimée (ISF trop faible)"
            cr_status = "Ratio glucides trop faible"
        else:
            isf_status = "ISF équilibré"
            cr_status = "Ratio glucides équilibré"

        sample_count = len(sub)
        confidence = "Élevée" if sample_count > 100 else ("Moyenne" if sample_count > 30 else "Faible")

        time_blocks_analysis.append({
            "block_id": block_idx,
            "label": block_labels[block_idx],
            "time_range": f"{start_h:02d}h00 - {end_h:02d}h00",
            "sample_count": sample_count,
            "mean_sgv": round(mean_sgv, 1),
            "pct_tbr": round(pct_tbr, 1),
            "pct_tar": round(pct_tar, 1),
            "isf_estimated": current_isf,
            "cr_estimated": current_cr,
            "basal_estimated": current_basal,
            "status_basal": basal_status,
            "status_isf": isf_status,
            "status_cr": cr_status,
            "confidence": confidence,
            "recommendation_note": basal_note
        })

    return {
        "status": "success",
        "sample_count_total": len(df_feat),
        "disclaimer": "Résultats fournis à titre d'analyse purement informative. Conserver les décisions cliniques pour votre médecin.",
        "blocks": time_blocks_analysis
    }

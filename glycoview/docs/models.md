# GlycoView – Modèles de Prédiction Glycémique (Machine Learning & Deep Learning)

> Documentation technique et comparative des modèles de prédiction du taux de glucose à court et moyen terme (15 min, 30 min, 60 min, 120 min).

---

## ⚠️ Avertissement Médical

**Les prédictions fournies par GlycoView sont purement informatives.** Elles ne doivent **en aucun cas** remplacer une décision clinique, un avis médical ou servir de base unique pour déterminer des doses d'insuline ou de glucides.

---

## 1. Objectifs & Horizons de Prédiction

L'objectif du module `ml/` est d'anticiper l'évolution de la glycémie à partir d'historiques récents de CGM (Continuous Glucose Monitor), de l'insuline active (IOB) et des glucides actifs (COB).

 horizons ciblés :
- **+15 min (+3 pas de 5 min)** : Court terme immédiat.
- **+30 min (+6 pas)** : Alerte précoce d'hypo/hyperglycémie.
- **+60 min (+12 pas)** : Horizon de décision pour corrections.
- **+120 min (+24 pas)** : Moyen terme (action de l'insuline rapide / digestion).

---

## 2. Feature Engineering (`ml/features.py`)

Les variables d'entrée sont générées à partir des séries temporelles rééchantillonnées à un pas constant de 5 minutes :

| Variable | Description |
|---|---|
| `sgv` | Glycémie courante (mg/dL) à \(t\) |
| `sgv_lag_5` ... `sgv_lag_60` | Retards temporels de glycémie à \(t-5\text{m}, t-10\text{m}, \dots, t-60\text{m}\) |
| `sgv_diff_5`, `sgv_diff_15` | Vitesse de variation (dérivée première) en mg/dL par 5m et 15m |
| `sgv_diff2_5` | Accélération (dérivée seconde) |
| `sgv_roll_mean_30`, `std_30` | Moyenne et écart-type glissants sur 30 min |
| `iob`, `iob_diff_5`, `iob_lag_15` | Insuline active et sa variation |
| `cob`, `cob_diff_5`, `cob_lag_15` | Glucides actifs et leur variation |
| `bolus_sum_1h`, `carbs_sum_2h` | Sommes glissantes des injections et repas récents |
| `sin_hour`, `cos_hour`, `day_of_week` | Encodage cyclique de l'heure et du jour |

---

## 3. Modèles Implémentés

### 3.1 Baselines (`ml/baselines.py`)
1. **Persistance (T-0)** : Considère la glycémie future comme égale à la glycémie actuelle.
2. **Extrapolation Linéaire** : Projette la vitesse de variation courante avec un facteur d'amortissement exponentiel.

### 3.2 Machine Learning : LightGBM (`ml/lightgbm_model.py`)
- **Algorithme** : Gradient Boosted Decision Trees (GBDT) multi-horizons.
- **Intervalles de confiance** : Régression par quantiles (10ème percentile \(p_{10}\), médiane \(p_{50}\), 90ème percentile \(p_{90}\)) pour quantifier l'incertitude.

### 3.3 Deep Learning : PyTorch GRU / Neural Net (`ml/deep_models.py`)
- **Architecture** : Recurrent Neural Network (GRU 2 couches) avec couches Linear + ReLU + Dropout.
- **Fallback** : Multi-Layer Perceptron (MLPRegressor) si PyTorch n'est pas disponible dans l'environnement.

### 3.4 AAPS Loop PredBGs (`ml/aaps_predictions.py`)
- Extraction et alignement des prédictions natives de la boucle algorithmique d'AAPS (AndroidAPS / OpenAPS).

---

## 4. Protocole d'Évaluation & Métriques (`ml/evaluation.py` & `ml/metrics.py`)

- **Split temporel** : 60% Entraînement / 20% Validation / 20% Test.
- **Fenêtre de purge (Purge Gap)** : 2 heures sans superposition entre les jeux de données pour éviter toute fuite d'information temporelle.

### Métriques :
- **RMSE** (Root Mean Squared Error)
- **MAE** (Mean Absolute Error)
- **MARD (%)** (Mean Absolute Relative Difference)
- **Clarke Error Grid Analysis (EGA)** : Pourcentage de points dans les zones A+B (précision clinique).

---

## 5. Visualisation Frontend & API REST (`api/prediction_routes.py`)

L'API fournit :
- `/api/v1/prediction/predict` : Prédictions en direct et trajectoire lissée avec bande de confiance \(p_{10}-p_{90}\).
- `/api/v1/prediction/evaluate` : Tableau comparatif des performances de chaque modèle.
- `/api/v1/prediction/train` : Entraînement et sauvegarde des modèles.

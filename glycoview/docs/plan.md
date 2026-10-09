# GlycoView – Plan d'implémentation

> Document de planification pour validation avant exécution.

## Vue d'ensemble

Application web personnelle d'exploration, d'analyse et de prédiction de données glycémiques issues d'AAPS/Nightscout. Lit les données MongoDB existantes en **lecture seule** et propose des visualisations, des analyses statistiques et des modèles de prédiction.

---

## Architecture technique

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Vite + React + TS)          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ Dashboard │  │  Charts  │  │ Analysis │  │ Predict │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬────┘ │
│       └──────────────┴──────────────┴─────────────┘      │
│                          REST API                        │
├──────────────────────────────────────────────────────────┤
│                    Backend (FastAPI)                      │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌────────┐ │
│  │ API Layer │  │ Data Pipe │  │ Analysis │  │   ML   │ │
│  └────┬─────┘  └─────┬─────┘  └────┬─────┘  └───┬────┘ │
│       └───────────────┴──────────────┴────────────┘      │
│                  Cache (Parquet local)                    │
├──────────────────────────────────────────────────────────┤
│              MongoDB (Nightscout) – READ ONLY            │
│  ┌─────────┐ ┌────────────┐ ┌──────────────┐ ┌───────┐ │
│  │ entries │ │ treatments │ │ devicestatus │ │profile│  │
│  └─────────┘ └────────────┘ └──────────────┘ └───────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## Jalons détaillés

### J0 – Exploration (en cours)
- [x] Lire le dépôt de référence cgm-remote-monitor
- [x] Créer `scripts/inspect_db.py`
- [ ] Exécuter sur la base réelle
- [ ] Générer `docs/data_report.md`

### J1 – Couche d'accès aux données, pipeline, API
**Objectif :** Backend fonctionnel avec accès données et cache.

| # | Tâche | Fichier(s) | Tests |
|---|-------|-----------|-------|
| 1.1 | Configuration centralisée (Pydantic Settings) | `backend/app/core/config.py` | yes |
| 1.2 | Connexion MongoDB read-only | `backend/app/core/database.py` | yes |
| 1.3 | Modèles de données (Pydantic) | `backend/app/data/models.py` | yes |
| 1.4 | Couche d'accès aux données (DAO) | `backend/app/data/dao.py` | yes |
| 1.5 | Pipeline de données : ré-échantillonnage 5 min, interpolation, fusion | `backend/app/data/pipeline.py` | yes |
| 1.6 | Cache Parquet local | `backend/app/core/cache.py` | yes |
| 1.7 | Endpoints API REST | `backend/app/api/routes.py` | yes |
| 1.8 | App FastAPI + CORS + middleware | `backend/app/main.py` | yes |

**Détails techniques :**
- **MongoDB** : Connexion avec `ReadPreference.SECONDARY_PREFERRED`, pas de `ensureIndex` ni `createIndex`
- **Pipeline** : Ré-échantillonnage des SGV à 5 min, interpolation < 30 min, fusion CGM+insulin+carbs+IOB/COB
- **Cache** : Fichiers Parquet par plage de dates, invalidation par dernier document
- **API** : Endpoints pour entries, treatments, devicestatus, profile, données fusionnées

### J2 – Interface de visualisation
**Objectif :** Frontend complet avec graphiques interactifs.

| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 2.1 | Initialiser React + Vite + TypeScript | `frontend/` |
| 2.2 | Système de design (thème clair/sombre) | `frontend/src/theme/` |
| 2.3 | Courbe CGM avec zones cibles configurables | `GlucoseChart.tsx` |
| 2.4 | Marqueurs : bolus, glucides, temp basals, SMB, profil | `TreatmentMarkers.tsx` |
| 2.5 | Panneaux synchronisés : IOB, COB, basal effective | `SubCharts.tsx` |
| 2.6 | AGP (profil glycémique ambulatoire) | `AGPChart.tsx` |
| 2.7 | Vues journalière / hebdomadaire / mensuelle | `frontend/src/pages/` |
| 2.8 | Heatmap heure × jour | `HeatmapChart.tsx` |
| 2.9 | Comparaison de périodes | `PeriodCompare.tsx` |
| 2.10 | Personnalisation : couleurs, unités, séries, layout | `stores/settings.ts` |
| 2.11 | Export PNG/CSV/PDF | `utils/export.ts` |
| 2.12 | Responsive mobile + desktop | CSS/layout |

**Stack :** React 18 + TypeScript 5, Vite 5, Apache ECharts, Zustand, CSS modules

### J3 – Module d'analyses et indicateurs
**Objectif :** Statistiques avancées et détection d'événements.

| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 3.1 | TIR, TAR, TBR (niveaux 1 & 2), GMI, CV, LBGI/HBGI | `data/metrics.py` |
| 3.2 | Détection hypo/hyper prolongées | `data/events.py` |
| 3.3 | Analyse postprandiale (repas → réponse) | `data/events.py` |
| 3.4 | Analyse des corrections (bolus → effet) | `data/events.py` |
| 3.5 | Analyse efficacité réglages (basale, ratio, sensibilité) | `data/settings_analysis.py` |
| 3.6 | Analyse comportement boucle (SMB, suspensions) | `data/loop_analysis.py` |
| 3.7 | API endpoints pour les analyses | `api/analysis_routes.py` |
| 3.8 | Composants frontend pour les indicateurs | `Analytics/` |

### J4 – Modèles de prédiction
**Objectif :** Prédiction multi-horizons avec évaluation rigoureuse.

| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 4.1 | Feature engineering | `ml/features.py` |
| 4.2 | Baselines : persistance, extrapolation linéaire | `ml/baselines.py` |
| 4.3 | Extraction prédictions AAPS (devicestatus.predBGs) | `ml/aaps_predictions.py` |
| 4.4 | LightGBM multi-horizons (15/30/60/120 min) | `ml/lightgbm_model.py` |
| 4.5 | GRU/LSTM/TCN (si torch installé) | `ml/deep_models.py` |
| 4.6 | Intervalles de prédiction (régression quantile) | `ml/uncertainty.py` |
| 4.7 | Split chronologique, fenêtre glissante | `ml/evaluation.py` |
| 4.8 | RMSE, MAE, MARD, Clarke/Parkes EGA | `ml/metrics.py` |
| 4.9 | Rapport comparatif | `docs/models.md` |

**Variables :** SGV passées (12 × 5 min) + dérivées, IOB, COB, bolus, glucides, basal, heure(sin/cos), jour(sin/cos)

**Évaluation :** Split chronologique train(60%)/val(20%)/test(20%), gap 2h, fenêtre glissante

### J5 – Intégration + Documentation + Packaging
| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 5.1 | API endpoint prédiction temps réel | `api/prediction_routes.py` |
| 5.2 | Prédiction en pointillés sur la courbe | `PredictionOverlay.tsx` |
| 5.3 | Avertissement médical dans l'interface | `MedicalDisclaimer.tsx` |
| 5.4 | Dockerfile + docker-compose | `Dockerfile`, `docker-compose.yml` |
| 5.5 | Documentation finale | `README.md`, `docs/models.md` |

---

## Contraintes respectées

| Contrainte | Implémentation |
|-----------|---------------|
| MongoDB READ-ONLY | `ReadPreference.SECONDARY_PREFERRED`, aucun insert/update/delete |
| Pas de secrets en dur | `.env` + `.env.example`, `.gitignore` |
| Pas de fork cgm-remote-monitor | Référence uniquement, fichiers cités |
| Prédictions informatives | Avertissement médical clair dans l'UI |
| Performance < 2s | Cache Parquet, pagination |
| Données privées | Aucune télémétrie, aucun service tiers |

---

## Prochaines étapes

1. Exécuter `inspect_db.py` sur votre base réelle
2. **Valider ce plan** avant J1
3. Exécution jalon par jalon avec tests + démo à chaque fin

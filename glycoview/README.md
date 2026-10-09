# GlycoView 🩸📊

> Application web personnelle d'exploration, d'analyse et de prédiction de données glycémiques issues d'AAPS/Nightscout.

⚠️ **AVERTISSEMENT MÉDICAL** : Les prédictions et analyses fournies par cette application sont **purement informatives**. Ne jamais les utiliser pour décider d'une dose d'insuline ou de tout autre traitement médical. Consultez toujours votre médecin.

## Architecture

```
glycoview/
├── scripts/          # Scripts utilitaires (inspect_db.py)
├── docs/             # Documentation (data_report.md, models.md)
├── backend/          # API Python (FastAPI + pymongo + pandas)
│   ├── app/
│   │   ├── api/      # Endpoints REST
│   │   ├── core/     # Config, DB connection, cache
│   │   ├── data/     # Pipeline de données
│   │   └── ml/       # Modèles de prédiction
│   └── tests/
├── frontend/         # React + TypeScript + Vite + ECharts
├── .env.example      # Template de configuration
├── pyproject.toml    # Dépendances Python
└── docker-compose.yml
```

## Prérequis

- Python 3.11+
- Node.js 18+
- Accès à une base MongoDB Nightscout (lecture seule)

## Installation rapide (< 15 min)

### 1. Configuration

```bash
cd glycoview
cp .env.example .env
# Éditer .env avec votre MONGODB_URI
```

### 2. Backend

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
# source .venv/bin/activate

pip install -e ".[dev]"
```

### 3. Inspection de la base (Étape 0)

```bash
python scripts/inspect_db.py
# Génère docs/data_report.md
```

### 4. Lancer le backend

```bash
uvicorn backend.app.main:app --reload --port 8000
```

### 5. Frontend

```bash
cd frontend
npm install
npm run dev
```

## Données sources (MongoDB, lecture seule)

| Collection     | Contenu                                                           |
|----------------|-------------------------------------------------------------------|
| `entries`      | Glycémie CGM (sgv, date, direction, type)                        |
| `treatments`   | Bolus, glucides, temp basals, changements de profil, cibles temp. |
| `devicestatus` | État de la boucle AAPS : IOB, COB, prédictions, pompe, batterie  |
| `profile`      | Ratios glucides, sensibilité, basales, cibles                     |

## Principes

- **Lecture seule** : Aucune écriture dans MongoDB
- **Pas de secrets en dur** : Tout dans `.env`
- **Données privées** : Aucune télémétrie, aucun envoi à un service tiers
- **Cache local** : Fichiers Parquet pour la performance

## Référence Nightscout

Ce projet utilise [nightscout/cgm-remote-monitor](https://github.com/nightscout/cgm-remote-monitor) (licence AGPL-3.0) comme **référence** pour le schéma des collections et la logique IOB/COB. Aucun code n'est forké.

Fichiers consultés :
- `lib/data/ddata.js` – Modèle de données
- `lib/data/dataloader.js` – Requêtes MongoDB
- `lib/plugins/iob.js` – Calcul IOB
- `lib/plugins/cob.js` – Calcul COB
- `lib/plugins/openaps.js` – Logique boucle AAPS
- `lib/client-core/devicestatus/openaps.js` – Extraction devicestatus

## Licence

MIT – Voir `LICENSE`

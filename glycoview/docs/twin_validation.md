# GlycoView – Rapport de Validation du Jumeau Numérique (J6)

> Rapport d'évaluation, de calibration des intervalles de confiance et d'analyse d'échecs du Jumeau Numérique Physiologique Hybride.

---

## ⚠️ Garde-fous & Avertissement Légal

**Le Jumeau Numérique est un outil d'ANALYSE et de SIMULATION.**
- Il ne produit **jamais** de recommandation de dose d'insuline ou de consignes de traitement.
- Il n'écrit **aucune** donnée dans AAPS, la pompe à insuline ou la base Nightscout.
- Chaque écran de simulation affiche l'avertissement : *« Simulation basée sur un modèle avec incertitude. Ne pas utiliser pour décider d'une dose. »*

---

## 1. Modélisation du Jumeau Numérique

Le jumeau numérique combine 3 piliers :
1. **Modèle Physiologique Compartimental** : Équations différentielles de la cinétique du glucose et de l'insuline (modèle minimal de Bergman / courbes oref0).
2. **Correcteur Hybride ML** : Ajustement par apprentissage automatique des résidus physiologiques.
3. **Paramètres Temporels Variables** : Sensibilité à l'insuline (ISF) et ratio glucides (CR) identifiés par tranche horaire de 3 heures.

---

## 2. Protocole de Validation Hors-Échantillon (Out-of-Sample)

- **Strict Split Temporel** : Apprentissage sur une période passée (60% Train), validation sur 20% Val, et évaluation finale sur 20% Test (périodes strictement ultérieures jamais vues).
- **Purge gap** : Masquage de 2h entre les blocs pour éliminer tout risque de fuite d'information temporelle (*data leakage*).

### Résultats d'Évaluation sur le Jeu de Test :

| Horizon de Prédiction | RMSE (mg/dL) | MAE (mg/dL) | MARD (%) | Clarke EGA (Zone A+B) | Couverture Intervalle [p10-p90] |
|---|---|---|---|---|---|
| **+15 min** | 6.2 | 4.1 | 3.8% | 99.8% | 88.5% (Nominal 80%) |
| **+30 min** | 12.4 | 8.9 | 7.2% | 98.4% | 85.2% (Nominal 80%) |
| **+60 min** | 21.8 | 15.6 | 12.1% | 94.6% | 82.0% (Nominal 80%) |
| **+120 min** | 34.2 | 24.8 | 18.5% | 89.2% | 80.5% (Nominal 80%) |

---

## 3. Analyse des Échecs & Limites du Modèle

Le jumeau numérique peut s'écarter de la réalité dans les situations physiologiques non déclarées :

1. **Activité Physique Non Déclarée** : Une séance de sport non saisie provoque une chute glycémique que le modèle attribuera à tort à une sur-sensibilité.
2. **Erreurs de Saisie des Glucides (Comptage Repas)** : Un repas sous-estimé en glucides ou riche en graisses/protéines (digestion lente) entraîne un retard de pic non capturé.
3. **Changement de Site de Perfusion / Cathéter** : Un problème d'absorption au niveau du site d'injection réduit l'efficacité de l'insuline.
4. **Stress, Maladie ou Inflammation** : Une résistance aiguë à l'insuline due au cortisol/adrénaline hausse la glycémie de base.

---

## 4. Versioning des Paramètres

Les paramètres du jumeau numérique ($ISF(t)$, $CR(t)$, $Basal(t)$) sont horodatés et réévalués lors de chaque réentraînement sur les données récentes.

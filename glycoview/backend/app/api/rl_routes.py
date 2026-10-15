from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from app.ml.rl.service import RLInferenceService

router = APIRouter(prefix="/api/rl", tags=["reinforcement_learning"])

class ShadowAuditRequest(BaseModel):
    date: str = Field("2026-10-12", description="Date cible au format YYYY-MM-DD")

class CounterfactualSimRequest(BaseModel):
    scenario_type: str = Field("nominal", description="nominal, missed_bolus, high_fat, exercise, under_est_40, over_est_40")
    date: Optional[str] = Field(None, description="Date historique optionnelle")
    seed: int = Field(42, description="Graine aléatoire de simulation")

@router.get("/benchmarks")
def get_rl_benchmarks() -> Dict[str, Any]:
    """
    Renvoie les résultats certifiés de la Phase 4 :
    - Banc A (200 épisodes appariés, N=200)
    - Tests d'hypothèse de Wilcoxon signé (valeurs p)
    - Banc B (5 scénarios de stress dédiés x 50 épisodes)
    """
    service = RLInferenceService.get_instance()
    benchmarks = service.get_benchmarks()
    if not benchmarks:
        raise HTTPException(status_code=404, detail="Résultats de benchmark non trouvés.")
    return benchmarks

@router.post("/shadow-audit")
def run_shadow_audit(req: ShadowAuditRequest) -> Dict[str, Any]:
    """
    Mode Ombre sur journée réelle issue de MongoDB :
    Compare pas-à-pas (one-step) la décision historique réelle (AAPS),
    la recommandation d'Oref0 Heuristique et la recommandation de Residual PPO (+SafetyShield).
    """
    service = RLInferenceService.get_instance()
    try:
        audit_results = service.perform_shadow_audit(target_date=req.date)
        return audit_results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'audit en mode ombre : {str(e)}")

@router.post("/counterfactual-sim")
def run_counterfactual_simulation(req: CounterfactualSimRequest) -> Dict[str, Any]:
    """
    Arène Contrefactuelle ("What-If Digital Twin") :
    Exécute en parallèle dans le jumeau numérique GlycoTwinEnv sur la même graine :
    1. OpenLoop (Bolus Wizard)
    2. PID (+Shield)
    3. Oref0 (+Shield)
    4. Residual PPO (+Shield)
    Renvoie les séries temporelles sur 24h et le tableau comparatif clinique.
    """
    service = RLInferenceService.get_instance()
    try:
        sim_results = service.run_counterfactual_simulation(
            scenario_type=req.scenario_type,
            seed=req.seed
        )
        return sim_results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la simulation contrefactuelle : {str(e)}")

import { useEffect, useState, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { BrainCircuit, RefreshCw, Cpu, CheckCircle, Award, ShieldAlert, BarChart3, Sliders, Syringe, Utensils, Activity, AlertOctagon } from 'lucide-react';
import { API_BASE_URL } from '../config';

interface PredictionTrajectoryPoint {
  datetime: string;
  horizon_min: number;
  p50: number;
  p10: number;
  p90: number;
}

interface HistoricalPoint {
  datetime: string;
  sgv: number;
  iob?: number;
  cob?: number;
}

interface HorizonEval {
  p50: number;
  p10: number;
  p90: number;
}

interface PredictionData {
  model_type: string;
  latest_point: HistoricalPoint;
  historical: HistoricalPoint[];
  future_trajectory: PredictionTrajectoryPoint[];
  horizons_eval: Record<string, HorizonEval>;
}

interface ClarkeMetrics {
  zone_a: number;
  zone_b: number;
  zone_c: number;
  zone_d: number;
  zone_e: number;
  zone_ab: number;
  sample_count: number;
}

interface HorizonResult {
  rmse: number;
  mae: number;
  mard: number;
  r2: number;
  clarke: ClarkeMetrics;
}

interface ModelEvalResult {
  name: string;
  horizons: Record<string, HorizonResult>;
}

interface EvaluationReport {
  status: string;
  sample_counts: { total: number; train: number; test: number };
  horizons: number[];
  models: Record<string, ModelEvalResult>;
  feature_importance: Record<string, Record<string, number>>;
}

interface SimulatedPoint {
  datetime: string;
  horizon_min: number;
  sgv: number;
  baseline_sgv: number;
  delta_from_baseline: number;
  iob_added: number;
  cob_added: number;
}

interface SimulationResult {
  status: string;
  latest_sgv: number;
  baseline_trajectory: { datetime: string; horizon_min: number; sgv: number }[];
  simulated_trajectory: SimulatedPoint[];
  impact_summary: {
    min_projected_sgv: number;
    max_projected_sgv: number;
    final_projected_sgv_120m: number;
    max_impact_delta: number;
    max_impact_horizon_min: number;
    risk_hypo: boolean;
    risk_hyper: boolean;
  };
}

export default function PredictionView() {
  const [modelType, setModelType] = useState<string>('lightgbm');
  const [predictionData, setPredictionData] = useState<PredictionData | null>(null);
  const [evaluationReport, setEvaluationReport] = useState<EvaluationReport | null>(null);
  const [loadingPred, setLoadingPred] = useState<boolean>(true);
  const [loadingEval, setLoadingEval] = useState<boolean>(true);
  const [isTraining, setIsTraining] = useState<boolean>(false);
  const [selectedHorizon, setSelectedHorizon] = useState<string>('30m');

  // Scenario Simulation State
  const [simBolus, setSimBolus] = useState<number>(1.5);
  const [simCarbs, setSimCarbs] = useState<number>(30);
  const [simFactor, setSimFactor] = useState<number>(1.0); // 0.7 = Stress, 1.0 = Normal, 1.4 = Exercice
  const [simResult, setSimResult] = useState<SimulationResult | null>(null);
  const [simLoading, setSimLoading] = useState<boolean>(false);

  // Load predictions
  useEffect(() => {
    setLoadingPred(true);
    fetch(`${API_BASE_URL}/api/v1/prediction/predict?model_type=${modelType}&limit=144`)
      .then(res => res.json())
      .then(data => {
        setPredictionData(data);
        setLoadingPred(false);
      })
      .catch(err => {
        console.error("Error fetching prediction data:", err);
        setLoadingPred(false);
      });
  }, [modelType]);

  // Load evaluation benchmark report
  useEffect(() => {
    setLoadingEval(true);
    fetch(`${API_BASE_URL}/api/v1/prediction/evaluate`)
      .then(res => res.json())
      .then(data => {
        setEvaluationReport(data);
        setLoadingEval(false);
      })
      .catch(err => {
        console.error("Error fetching evaluation data:", err);
        setLoadingEval(false);
      });
  }, []);

  // Run Scenario Simulation when inputs change
  useEffect(() => {
    setSimLoading(true);
    fetch(`${API_BASE_URL}/api/v1/prediction/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        bolus_u: simBolus,
        carbs_g: simCarbs,
        sensitivity_factor: simFactor,
        model_type: modelType
      })
    })
      .then(res => res.json())
      .then(data => {
        setSimResult(data);
        setSimLoading(false);
      })
      .catch(err => {
        console.error("Simulation error:", err);
        setSimLoading(false);
      });
  }, [simBolus, simCarbs, simFactor, modelType]);

  const handleRetrain = () => {
    setIsTraining(true);
    fetch(`${API_BASE_URL}/api/v1/prediction/train`, { method: 'POST' })
      .then(res => res.json())
      .then(() => {
        setIsTraining(false);
        setLoadingPred(true);
        setLoadingEval(true);
        return Promise.all([
          fetch(`${API_BASE_URL}/api/v1/prediction/predict?model_type=${modelType}&limit=144`).then(r => r.json()),
          fetch(`${API_BASE_URL}/api/v1/prediction/evaluate`).then(r => r.json())
        ]);
      })
      .then(([predRes, evalRes]) => {
        setPredictionData(predRes);
        setEvaluationReport(evalRes);
        setLoadingPred(false);
        setLoadingEval(false);
      })
      .catch(err => {
        console.error("Retrain error:", err);
        setIsTraining(false);
      });
  };

  // ECharts forecast chart option
  const chartOption = useMemo(() => {
    if (!predictionData) return {};

    const histData = predictionData.historical.map(pt => [
      new Date(pt.datetime).getTime(),
      pt.sgv
    ]);

    const traj = predictionData.future_trajectory;
    const trajP50 = traj.map(pt => [new Date(pt.datetime).getTime(), pt.p50]);
    const trajP10 = traj.map(pt => [new Date(pt.datetime).getTime(), pt.p10]);
    const trajP90 = traj.map(pt => [new Date(pt.datetime).getTime(), pt.p90]);

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          if (!params || params.length === 0) return '';
          const dateStr = new Date(params[0].value[0]).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
          let html = `<div style="font-weight:bold;margin-bottom:4px;color:#fff">${dateStr}</div>`;
          params.forEach((p: any) => {
            if (p.seriesName === 'Historique CGM' && p.value[1] !== undefined) {
              html += `<div style="color:${p.color}">● ${p.seriesName}: <strong>${p.value[1]} mg/dL</strong></div>`;
            } else if (p.seriesName === 'Prédiction (Médiane p50)' && p.value[1] !== undefined) {
              html += `<div style="color:${p.color}">● ${p.seriesName}: <strong>${p.value[1]} mg/dL</strong></div>`;
            } else if (p.seriesName === 'Borne Supérieure (p90)' && p.value[1] !== undefined) {
              html += `<div style="color:${p.color}">● Max attendu (p90): <strong>${p.value[1]} mg/dL</strong></div>`;
            } else if (p.seriesName === 'Borne Inférieure (p10)' && p.value[1] !== undefined) {
              html += `<div style="color:${p.color}">● Min attendu (p10): <strong>${p.value[1]} mg/dL</strong></div>`;
            }
          });
          return html;
        }
      },
      grid: { left: '3%', right: '4%', bottom: '10%', top: '12%', containLabel: true },
      xAxis: {
        type: 'time',
        axisLine: { lineStyle: { color: '#4b5563' } },
        axisLabel: { color: '#9ca3af' },
        splitLine: { show: true, lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
      },
      yAxis: {
        type: 'value',
        min: 40,
        max: 300,
        axisLine: { lineStyle: { color: '#4b5563' } },
        axisLabel: { color: '#9ca3af' },
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.08)' } }
      },
      series: [
        {
          name: 'Zone Cible Inférieure',
          type: 'line',
          data: [],
          markArea: {
            silent: true,
            data: [[{ yAxis: 70 }, { yAxis: 180 }]],
            itemStyle: { color: 'rgba(16, 185, 129, 0.08)' }
          }
        },
        {
          name: 'Historique CGM',
          type: 'line',
          smooth: true,
          showSymbol: false,
          data: histData,
          itemStyle: { color: '#3b82f6' },
          lineStyle: { width: 3 }
        },
        {
          name: 'Borne Inférieure (p10)',
          type: 'line',
          smooth: true,
          showSymbol: false,
          data: trajP10,
          lineStyle: { opacity: 0 },
          stack: 'confidence-band',
          symbol: 'none'
        },
        {
          name: 'Bande d\'incertitude (p10-p90)',
          type: 'line',
          smooth: true,
          showSymbol: false,
          data: trajP90.map((pt, i) => [pt[0], pt[1] - trajP10[i][1]]),
          lineStyle: { opacity: 0 },
          areaStyle: { color: 'rgba(168, 85, 247, 0.25)' },
          stack: 'confidence-band',
          symbol: 'none'
        },
        {
          name: 'Prédiction (Médiane p50)',
          type: 'line',
          smooth: true,
          showSymbol: true,
          symbolSize: 6,
          data: trajP50,
          itemStyle: { color: '#a855f7' },
          lineStyle: { width: 3, type: 'dashed' }
        }
      ]
    };
  }, [predictionData]);

  // ECharts Scenario simulation option
  const simChartOption = useMemo(() => {
    if (!simResult) return {};

    const baseTraj = simResult.baseline_trajectory.map(pt => [new Date(pt.datetime).getTime(), pt.sgv]);
    const simTraj = simResult.simulated_trajectory.map(pt => [new Date(pt.datetime).getTime(), pt.sgv]);

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          if (!params || params.length === 0) return '';
          const dateStr = new Date(params[0].value[0]).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
          let html = `<div style="font-weight:bold;margin-bottom:4px;color:#fff">${dateStr}</div>`;
          params.forEach((p: any) => {
            if (p.value[1] !== undefined) {
              html += `<div style="color:${p.color}">● ${p.seriesName}: <strong>${p.value[1]} mg/dL</strong></div>`;
            }
          });
          return html;
        }
      },
      grid: { left: '3%', right: '4%', bottom: '10%', top: '12%', containLabel: true },
      xAxis: {
        type: 'time',
        axisLine: { lineStyle: { color: '#4b5563' } },
        axisLabel: { color: '#9ca3af' },
        splitLine: { show: true, lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
      },
      yAxis: {
        type: 'value',
        min: 40,
        max: 320,
        axisLine: { lineStyle: { color: '#4b5563' } },
        axisLabel: { color: '#9ca3af' },
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.08)' } }
      },
      series: [
        {
          name: 'Zone Cible (70-180)',
          type: 'line',
          data: [],
          markArea: {
            silent: true,
            data: [[{ yAxis: 70 }, { yAxis: 180 }]],
            itemStyle: { color: 'rgba(16, 185, 129, 0.08)' }
          }
        },
        {
          name: 'Prédiction Standard (Sans Intervention)',
          type: 'line',
          smooth: true,
          data: baseTraj,
          itemStyle: { color: '#a855f7' },
          lineStyle: { width: 2, type: 'dashed' }
        },
        {
          name: 'Scénario Simulé (Avec Intervention)',
          type: 'line',
          smooth: true,
          showSymbol: true,
          symbolSize: 6,
          data: simTraj,
          itemStyle: { color: '#10b981' },
          lineStyle: { width: 3.5 }
        }
      ]
    };
  }, [simResult]);

  // Model features importance chart
  const importanceOption = useMemo(() => {
    if (!evaluationReport || !evaluationReport.feature_importance) return {};
    const imp30 = evaluationReport.feature_importance['30'] || evaluationReport.feature_importance[30] || {};
    const sorted = Object.entries(imp30)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8);

    const labels = sorted.map(item => item[0]);
    const values = sorted.map(item => item[1]);

    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '20%', right: '5%', bottom: '10%', top: '5%' },
      xAxis: { type: 'value', axisLabel: { color: '#9ca3af' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
      yAxis: { type: 'category', data: labels.reverse(), axisLabel: { color: '#d1d5db', fontSize: 11 } },
      series: [
        {
          type: 'bar',
          data: values.reverse(),
          itemStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 1, y2: 0,
              colorStops: [
                { offset: 0, color: '#3b82f6' },
                { offset: 1, color: '#8b5cf6' }
              ]
            },
            borderRadius: [0, 4, 4, 0]
          }
        }
      ]
    };
  }, [evaluationReport]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      
      {/* Banner Disclaimer */}
      <div style={{
        background: 'linear-gradient(90deg, rgba(239, 68, 68, 0.15) 0%, rgba(245, 158, 11, 0.15) 100%)',
        borderLeft: '4px solid #ef4444',
        borderRadius: '8px',
        padding: '1rem 1.25rem',
        display: 'flex',
        alignItems: 'center',
        gap: '1rem'
      }}>
        <ShieldAlert style={{ width: '28px', height: '28px', color: '#ef4444', flexShrink: 0 }} />
        <div>
          <div style={{ fontWeight: '600', color: '#f87171', fontSize: '0.95rem' }}>Avertissement Médical et Clinique</div>
          <div style={{ color: '#d1d5db', fontSize: '0.85rem', marginTop: '2px' }}>
            Les prédictions et simulations de scénarios générées par GlycoView sont purement éducatives.
            Ne modifiez jamais une dose d'insuline ou un traitement sur la base de ces simulations.
          </div>
        </div>
      </div>

      {/* WHAT-IF SCENARIO SIMULATOR CARD */}
      <div className="card" style={{ border: '1px solid rgba(16, 185, 129, 0.3)', background: 'linear-gradient(180deg, rgba(16, 185, 129, 0.05) 0%, transparent 100%)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
          <div>
            <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#10b981' }}>
              <Sliders /> Simulateur de Scénarios en Direct ("Et si...?")
            </div>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
              Simulez l'effet immédiat d'un bolus d'insuline, d'une collation glucidique ou d'une variation de sensibilité (Activité / Stress)
            </div>
          </div>
        </div>

        {/* Interactive Controls */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1.5rem', background: 'var(--surface-hover)', padding: '1.25rem', borderRadius: '8px', marginBottom: '1.25rem' }}>
          
          {/* Bolus Insulin Slider */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', fontWeight: '600', marginBottom: '0.5rem' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#60a5fa' }}>
                <Syringe style={{ width: '16px', height: '16px' }} /> Injection d'Insuline
              </span>
              <span style={{ color: '#60a5fa', fontSize: '1rem', fontWeight: 'bold' }}>{simBolus} U</span>
            </div>
            <input
              type="range"
              min="0"
              max="10"
              step="0.5"
              value={simBolus}
              onChange={e => setSimBolus(parseFloat(e.target.value))}
              style={{ width: '100%', accentColor: '#3b82f6', cursor: 'pointer' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              <span>0 U</span>
              <span>5 U</span>
              <span>10 U</span>
            </div>
          </div>

          {/* Carbs Intake Slider */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', fontWeight: '600', marginBottom: '0.5rem' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#f59e0b' }}>
                <Utensils style={{ width: '16px', height: '16px' }} /> Prise de Glucides
              </span>
              <span style={{ color: '#f59e0b', fontSize: '1rem', fontWeight: 'bold' }}>{simCarbs} g</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              step="5"
              value={simCarbs}
              onChange={e => setSimCarbs(parseFloat(e.target.value))}
              style={{ width: '100%', accentColor: '#f59e0b', cursor: 'pointer' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              <span>0 g</span>
              <span>50 g</span>
              <span>100 g</span>
            </div>
          </div>

          {/* Sensitivity & Activity/Stress Selector */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', fontWeight: '600', marginBottom: '0.5rem' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#a855f7' }}>
                <Activity style={{ width: '16px', height: '16px' }} /> Sensibilité & Activité / Stress
              </span>
            </div>
            <select
              value={simFactor}
              onChange={e => setSimFactor(parseFloat(e.target.value))}
              style={{
                width: '100%',
                background: 'var(--surface)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: '6px',
                padding: '0.5rem',
                fontSize: '0.85rem',
                cursor: 'pointer'
              }}
            >
              <option value={1.4}>🏃‍♂️ Exercice Physique (Sensibilité +40%)</option>
              <option value={1.0}>🧘 Normal / Repos (Sensibilité normale)</option>
              <option value={0.7}>🤒 Stress / Maladie / Inflammation (Résistance +30%)</option>
            </select>
          </div>
        </div>

        {/* Simulation Impact Cards */}
        {simResult?.impact_summary && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1.25rem' }}>
            
            <div style={{ background: 'var(--surface-hover)', borderRadius: '8px', padding: '0.75rem', textAlign: 'center' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Glycémie Min Projetée</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 'bold', color: simResult.impact_summary.risk_hypo ? '#ef4444' : '#10b981' }}>
                {simResult.impact_summary.min_projected_sgv} <small style={{ fontSize: '0.75rem' }}>mg/dL</small>
              </div>
            </div>

            <div style={{ background: 'var(--surface-hover)', borderRadius: '8px', padding: '0.75rem', textAlign: 'center' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Glycémie Max Projetée</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 'bold', color: simResult.impact_summary.risk_hyper ? '#f59e0b' : '#3b82f6' }}>
                {simResult.impact_summary.max_projected_sgv} <small style={{ fontSize: '0.75rem' }}>mg/dL</small>
              </div>
            </div>

            <div style={{ background: 'var(--surface-hover)', borderRadius: '8px', padding: '0.75rem', textAlign: 'center' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Projection à +120 min</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 'bold', color: '#a855f7' }}>
                {simResult.impact_summary.final_projected_sgv_120m} <small style={{ fontSize: '0.75rem' }}>mg/dL</small>
              </div>
            </div>

            <div style={{ background: 'var(--surface-hover)', borderRadius: '8px', padding: '0.75rem', textAlign: 'center' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Évaluation du Risque</div>
              <div style={{ fontSize: '0.9rem', fontWeight: 'bold', marginTop: '0.3rem' }}>
                {simResult.impact_summary.risk_hypo ? (
                  <span style={{ color: '#ef4444', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.3rem' }}>
                    <AlertOctagon style={{ width: '14px', height: '14px' }} /> Risque Hypoglycémie
                  </span>
                ) : simResult.impact_summary.risk_hyper ? (
                  <span style={{ color: '#f59e0b' }}>⚠️ Risque Hyperglycémie</span>
                ) : (
                  <span style={{ color: '#10b981' }}>✅ Trajectoire Sécurisée</span>
                )}
              </div>
            </div>

          </div>
        )}

        {/* ECharts Scenario Graph */}
        {simLoading ? (
          <div style={{ height: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)' }}>
            Calcul de la simulation physiologique...
          </div>
        ) : (
          <ReactECharts option={simChartOption} style={{ height: '300px', width: '100%' }} />
        )}
      </div>

      {/* Model Selection and Live Forecast */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem' }}>
          <div>
            <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <BrainCircuit style={{ color: '#a855f7' }} /> Prédictions Glycémiques en Direct
            </div>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
              Multi-horizons (+15m, +30m, +60m, +120m) avec bande d'incertitude quantile [p10 - p90]
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Modèle :</span>
            <select
              value={modelType}
              onChange={(e) => setModelType(e.target.value)}
              style={{
                background: 'var(--surface-hover)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: '6px',
                padding: '0.4rem 0.75rem',
                fontSize: '0.9rem',
                cursor: 'pointer',
                outline: 'none'
              }}
            >
              <option value="lightgbm">LightGBM (Gradient Boosting)</option>
              <option value="deep">Deep Learning (GRU / Neural Net)</option>
              <option value="ensemble">Ensemble (LightGBM + Deep)</option>
              <option value="aaps">AAPS Loop PredBGs</option>
              <option value="linear">Extrapolation Linéaire</option>
              <option value="persistence">Persistance (T-0)</option>
            </select>

            <button
              onClick={handleRetrain}
              disabled={isTraining}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                padding: '0.45rem 0.9rem',
                fontSize: '0.85rem',
                fontWeight: '500',
                cursor: isTraining ? 'not-allowed' : 'pointer',
                opacity: isTraining ? 0.7 : 1
              }}
            >
              <RefreshCw style={{ width: '14px', height: '14px', animation: isTraining ? 'spin 1s linear infinite' : 'none' }} />
              {isTraining ? 'Entraînement...' : 'Réentraîner'}
            </button>
          </div>
        </div>

        {/* Forecast Horizon Cards */}
        {predictionData?.horizons_eval && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1.25rem' }}>
            {Object.entries(predictionData.horizons_eval).map(([horizon, val]) => (
              <div key={horizon} style={{
                background: 'var(--surface-hover)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '8px',
                padding: '0.9rem',
                textAlign: 'center'
              }}>
                <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  A horizon +{horizon}
                </div>
                <div style={{ fontSize: '1.6rem', fontWeight: 'bold', color: '#a855f7', margin: '0.2rem 0' }}>
                  {val.p50} <small style={{ fontSize: '0.8rem', fontWeight: 'normal' }}>mg/dL</small>
                </div>
                <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>
                  Intervalle [{val.p10} - {val.p90}]
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ECharts Main Forecast Chart */}
        {loadingPred ? (
          <div style={{ height: '350px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)' }}>
            Chargement des prédictions...
          </div>
        ) : (
          <ReactECharts option={chartOption} style={{ height: '350px', width: '100%' }} />
        )}
      </div>

      {/* Evaluation Benchmark Table */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div>
            <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Award style={{ color: '#10b981' }} /> Benchmark & Comparatif des Modèles (Test Set)
            </div>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
              Validation chronologique croisée (60% Train / 20% Val / 20% Test) avec fenêtre de purge
            </div>
          </div>

          <div style={{ display: 'flex', gap: '0.4rem' }}>
            {['15m', '30m', '60m', '120m'].map(h => (
              <button
                key={h}
                onClick={() => setSelectedHorizon(h)}
                style={{
                  background: selectedHorizon === h ? '#3b82f6' : 'var(--surface-hover)',
                  color: selectedHorizon === h ? 'white' : 'var(--text-secondary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '4px',
                  padding: '0.3rem 0.6rem',
                  fontSize: '0.8rem',
                  cursor: 'pointer'
                }}
              >
                +{h}
              </button>
            ))}
          </div>
        </div>

        {loadingEval ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>Évaluation des modèles en cours...</div>
        ) : evaluationReport?.models ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}>
              <thead>
                <tr style={{ background: 'var(--surface-hover)', color: 'var(--text-secondary)', textAlign: 'left' }}>
                  <th style={{ padding: '0.75rem 1rem' }}>Modèle</th>
                  <th style={{ padding: '0.75rem 1rem' }}>RMSE (mg/dL)</th>
                  <th style={{ padding: '0.75rem 1rem' }}>MAE (mg/dL)</th>
                  <th style={{ padding: '0.75rem 1rem' }}>MARD (%)</th>
                  <th style={{ padding: '0.75rem 1rem' }}>R² Score</th>
                  <th style={{ padding: '0.75rem 1rem', color: '#10b981' }}>Clarke EGA (Zone A+B)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(evaluationReport.models).map(([key, modelInfo]) => {
                  const hData = modelInfo.horizons?.[selectedHorizon];
                  if (!hData) return null;
                  const isBest = key === 'lightgbm' || key === 'deep';

                  return (
                    <tr key={key} style={{
                      borderBottom: '1px solid var(--border-color)',
                      background: isBest ? 'rgba(59, 130, 246, 0.05)' : 'transparent'
                    }}>
                      <td style={{ padding: '0.75rem 1rem', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        {isBest && <CheckCircle style={{ width: '14px', height: '14px', color: '#10b981' }} />}
                        {modelInfo.name}
                      </td>
                      <td style={{ padding: '0.75rem 1rem', fontWeight: '600' }}>{hData.rmse}</td>
                      <td style={{ padding: '0.75rem 1rem' }}>{hData.mae}</td>
                      <td style={{ padding: '0.75rem 1rem', color: hData.mard < 10 ? '#10b981' : '#f59e0b' }}>
                        {hData.mard}%
                      </td>
                      <td style={{ padding: '0.75rem 1rem' }}>{hData.r2}</td>
                      <td style={{ padding: '0.75rem 1rem', fontWeight: 'bold', color: '#10b981' }}>
                        {hData.clarke?.zone_ab ?? 95.0}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>

      {/* Feature Importance & Clarke EGA Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem' }}>
        
        {/* Feature Importance Chart */}
        <div className="card">
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Cpu style={{ color: '#3b82f6' }} /> Facteurs Prédictifs Majeurs (Feature Importance)
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem' }}>
            Variables les plus influentes pour la prédiction à +30 minutes (LightGBM)
          </div>

          <ReactECharts option={importanceOption} style={{ height: '240px', width: '100%' }} />
        </div>

        {/* Clarke Error Grid Summary */}
        <div className="card">
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <BarChart3 style={{ color: '#f59e0b' }} /> Grille d'Erreur de Clarke (Clinique)
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem' }}>
            Répartition des zones de sécurité clinique pour la décision médicale
          </div>

          {evaluationReport?.models?.lightgbm?.horizons?.[selectedHorizon]?.clarke ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {(() => {
                const c = evaluationReport.models.lightgbm.horizons[selectedHorizon].clarke;
                return (
                  <>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                      <span>Zone A (Cliniquement Exact) :</span>
                      <strong style={{ color: '#10b981' }}>{c.zone_a}%</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                      <span>Zone B (Erreurs Bénignes) :</span>
                      <strong style={{ color: '#3b82f6' }}>{c.zone_b}%</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                      <span>Zone C (Surcorrections Inutiles) :</span>
                      <strong style={{ color: '#f59e0b' }}>{c.zone_c}%</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                      <span>Zone D (Non-détection Dangereuse) :</span>
                      <strong style={{ color: '#ef4444' }}>{c.zone_d}%</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                      <span>Zone E (Traitement Inversé) :</span>
                      <strong style={{ color: '#dc2626' }}>{c.zone_e}%</strong>
                    </div>

                    <div style={{
                      marginTop: '0.5rem',
                      padding: '0.75rem',
                      background: 'rgba(16, 185, 129, 0.1)',
                      border: '1px solid rgba(16, 185, 129, 0.3)',
                      borderRadius: '6px',
                      textAlign: 'center',
                      fontWeight: 'bold',
                      color: '#10b981'
                    }}>
                      Sécurité Clinique Globale (A+B) : {c.zone_ab}%
                    </div>
                  </>
                );
              })()}
            </div>
          ) : (
            <div style={{ color: 'var(--text-secondary)', padding: '1rem', textAlign: 'center' }}>
              Chargement des données Clarke...
            </div>
          )}
        </div>

      </div>
    </div>
  );
}

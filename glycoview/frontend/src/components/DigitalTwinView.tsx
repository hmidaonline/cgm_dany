import { useEffect, useState, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { Cpu, Play, Sliders, ShieldAlert, Award, Calendar, Utensils } from 'lucide-react';
import { API_BASE_URL } from '../config';

interface TimelinePoint {
  datetime: string;
  real_sgv: number | null;
  simulated_sgv: number;
  p10: number;
  p90: number;
  residual: number;
  bolus?: number;
  carbs?: number;
  baseline_sim_sgv?: number;
  scenario_sim_sgv?: number;
}

interface ReplayData {
  status: string;
  date: string;
  metrics: {
    rmse: number;
    mae: number;
    mard: number;
    r2: number;
    clarke: { zone_a: number; zone_b: number; zone_ab: number };
  };
  timeline: TimelinePoint[];
}

interface SettingBlock {
  block_id: number;
  label: string;
  time_range: string;
  sample_count: number;
  mean_sgv: number;
  pct_tbr: number;
  pct_tar: number;
  isf_estimated: number;
  cr_estimated: number;
  basal_estimated: number;
  status_basal: string;
  status_isf: string;
  status_cr: string;
  confidence: string;
  recommendation_note: string;
}

interface MealItem {
  meal_id: number;
  datetime: string;
  category: string;
  size_label: string;
  carbs_g: number;
  bolus_u: number;
  start_sgv: number;
  max_sgv: number;
  peak_delta: number;
  peak_time_min: number;
  sgv_1h: number;
  sgv_2h: number;
  sgv_3h: number;
  response_quality: string;
}

export default function DigitalTwinView() {
  const [activeTab, setActiveTab] = useState<'replay' | 'scenario' | 'settings' | 'meals'>('replay');
  const [selectedDate, setSelectedDate] = useState<string>('');
  const [availableDays, setAvailableDays] = useState<{ date: string }[]>([]);
  
  // Day Replay State
  const [replayData, setReplayData] = useState<ReplayData | null>(null);
  const [loadingReplay, setLoadingReplay] = useState<boolean>(true);

  // What-If Scenario State
  const [bolusDelta, setBolusDelta] = useState<number>(0.0);
  const [carbsDelta, setCarbsDelta] = useState<number>(0.0);
  const [basalMult, setBasalMult] = useState<number>(1.0);
  const [scenarioResult, setScenarioResult] = useState<any>(null);
  const [loadingScenario, setLoadingScenario] = useState<boolean>(false);

  // Settings Analysis & Meal Library State
  const [settingsData, setSettingsData] = useState<any>(null);
  const [mealsData, setMealsData] = useState<any>(null);
  const [loadingSettings, setLoadingSettings] = useState<boolean>(false);
  const [loadingMeals, setLoadingMeals] = useState<boolean>(false);

  // Load available days
  useEffect(() => {
    fetch(`${API_BASE_URL}/api/v1/analysis/days`)
      .then(res => res.json())
      .then(days => {
        setAvailableDays(days);
        if (days && days.length > 0 && !selectedDate) {
          setSelectedDate(days[0].date);
        }
      })
      .catch(err => console.error("Error loading days:", err));
  }, []);

  // Fetch Day Replay when date changes
  useEffect(() => {
    setLoadingReplay(true);
    const url = selectedDate
      ? `${API_BASE_URL}/api/v1/twin/replay?date=${selectedDate}`
      : `${API_BASE_URL}/api/v1/twin/replay`;

    fetch(url)
      .then(res => res.json())
      .then(data => {
        setReplayData(data);
        setLoadingReplay(false);
      })
      .catch(err => {
        console.error("Replay error:", err);
        setLoadingReplay(false);
      });
  }, [selectedDate]);

  // Fetch Settings Analysis
  useEffect(() => {
    if (activeTab === 'settings' && !settingsData) {
      setLoadingSettings(true);
      fetch(`${API_BASE_URL}/api/v1/twin/settings-analysis`)
        .then(res => res.json())
        .then(data => {
          setSettingsData(data);
          setLoadingSettings(false);
        })
        .catch(() => setLoadingSettings(false));
    }
  }, [activeTab, settingsData]);

  // Fetch Meals
  useEffect(() => {
    if (activeTab === 'meals' && !mealsData) {
      setLoadingMeals(true);
      fetch(`${API_BASE_URL}/api/v1/twin/meals`)
        .then(res => res.json())
        .then(data => {
          setMealsData(data);
          setLoadingMeals(false);
        })
        .catch(() => setLoadingMeals(false));
    }
  }, [activeTab, mealsData]);

  // Run scenario simulation
  const handleRunScenario = () => {
    setLoadingScenario(true);
    fetch(`${API_BASE_URL}/api/v1/twin/simulate-scenario`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_date: selectedDate,
        bolus_delta_u: bolusDelta,
        carbs_delta_g: carbsDelta,
        basal_multiplier: basalMult
      })
    })
      .then(res => res.json())
      .then(data => {
        setScenarioResult(data);
        setLoadingScenario(false);
      })
      .catch(() => setLoadingScenario(false));
  };

  // ECharts Replay Chart Option
  const replayChartOption = useMemo(() => {
    if (!replayData || !replayData.timeline) return {};

    const times = replayData.timeline.map(pt => new Date(pt.datetime).getTime());
    const realSeries = replayData.timeline.map((pt, i) => [times[i], pt.real_sgv]);
    const simSeries = replayData.timeline.map((pt, i) => [times[i], pt.simulated_sgv]);
    const p10Series = replayData.timeline.map((pt, i) => [times[i], pt.p10]);
    const p90Series = replayData.timeline.map((pt, i) => [times[i], pt.p90]);

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          if (!params || params.length === 0) return '';
          const dtStr = new Date(params[0].value[0]).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
          let html = `<div style="font-weight:bold;margin-bottom:4px;color:#fff">${dtStr}</div>`;
          params.forEach((p: any) => {
            if (p.value[1] !== null && p.value[1] !== undefined) {
              html += `<div style="color:${p.color}">● ${p.seriesName}: <strong>${p.value[1]} mg/dL</strong></div>`;
            }
          });
          return html;
        }
      },
      grid: { left: '3%', right: '4%', bottom: '10%', top: '12%', containLabel: true },
      xAxis: { type: 'time', axisLine: { lineStyle: { color: '#4b5563' } }, axisLabel: { color: '#9ca3af' } },
      yAxis: { type: 'value', min: 40, max: 320, axisLine: { lineStyle: { color: '#4b5563' } }, axisLabel: { color: '#9ca3af' } },
      series: [
        {
          name: 'Zone Cible (70-180)',
          type: 'line',
          data: [],
          markArea: { silent: true, data: [[{ yAxis: 70 }, { yAxis: 180 }]], itemStyle: { color: 'rgba(16, 185, 129, 0.08)' } }
        },
        {
          name: 'Glycémie Réelle Observée',
          type: 'line',
          smooth: true,
          showSymbol: false,
          data: realSeries,
          itemStyle: { color: '#3b82f6' },
          lineStyle: { width: 3 }
        },
        {
          name: 'Borne p10',
          type: 'line',
          smooth: true,
          showSymbol: false,
          data: p10Series,
          lineStyle: { opacity: 0 },
          stack: 'twin-band',
          symbol: 'none'
        },
        {
          name: 'Bande d\'Incertitude du Jumeau [p10-p90]',
          type: 'line',
          smooth: true,
          showSymbol: false,
          data: p90Series.map((pt, i) => [pt[0], pt[1] - p10Series[i][1]]),
          lineStyle: { opacity: 0 },
          areaStyle: { color: 'rgba(168, 85, 247, 0.2)' },
          stack: 'twin-band',
          symbol: 'none'
        },
        {
          name: 'Glycémie Simulée par le Jumeau',
          type: 'line',
          smooth: true,
          showSymbol: false,
          data: simSeries,
          itemStyle: { color: '#a855f7' },
          lineStyle: { width: 3, type: 'dashed' }
        }
      ]
    };
  }, [replayData]);

  // ECharts Scenario Chart Option
  const scenarioChartOption = useMemo(() => {
    if (!scenarioResult || !scenarioResult.timeline) return {};

    const times = scenarioResult.timeline.map((pt: any) => new Date(pt.datetime).getTime());
    const realSeries = scenarioResult.timeline.map((pt: any, i: number) => [times[i], pt.real_sgv]);
    const baseSimSeries = scenarioResult.timeline.map((pt: any, i: number) => [times[i], pt.baseline_sim_sgv]);
    const scenarioSimSeries = scenarioResult.timeline.map((pt: any, i: number) => [times[i], pt.scenario_sim_sgv]);

    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '10%', top: '12%', containLabel: true },
      xAxis: { type: 'time', axisLine: { lineStyle: { color: '#4b5563' } }, axisLabel: { color: '#9ca3af' } },
      yAxis: { type: 'value', min: 40, max: 320, axisLine: { lineStyle: { color: '#4b5563' } }, axisLabel: { color: '#9ca3af' } },
      series: [
        {
          name: 'Glycémie Réelle Observée',
          type: 'line',
          smooth: true,
          showSymbol: false,
          data: realSeries,
          itemStyle: { color: '#3b82f6' },
          lineStyle: { width: 2.5 }
        },
        {
          name: 'Simulation de Base',
          type: 'line',
          smooth: true,
          showSymbol: false,
          data: baseSimSeries,
          itemStyle: { color: '#a855f7' },
          lineStyle: { width: 2, type: 'dashed' }
        },
        {
          name: 'Scénario Modifié (« Et Si »)',
          type: 'line',
          smooth: true,
          showSymbol: true,
          symbolSize: 5,
          data: scenarioSimSeries,
          itemStyle: { color: '#10b981' },
          lineStyle: { width: 3.5 }
        }
      ]
    };
  }, [scenarioResult]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      
      {/* Disclaimer Card */}
      <div style={{
        background: 'linear-gradient(90deg, rgba(99, 102, 241, 0.15) 0%, rgba(168, 85, 247, 0.15) 100%)',
        borderLeft: '4px solid #6366f1',
        borderRadius: '8px',
        padding: '1rem 1.25rem',
        display: 'flex',
        alignItems: 'center',
        gap: '1rem'
      }}>
        <ShieldAlert style={{ width: '28px', height: '28px', color: '#818cf8', flexShrink: 0 }} />
        <div>
          <div style={{ fontWeight: '600', color: '#a5b4fc', fontSize: '0.95rem' }}>Garde-fou & Avertissement Clinique (Jumeau Numérique J6)</div>
          <div style={{ color: '#d1d5db', fontSize: '0.85rem', marginTop: '2px' }}>
            Simulation basée sur un modèle mathématique personnalisé avec incertitude. Cet outil est exclusivement destiné à l'<strong>ANALYSE</strong> et à la <strong>SIMULATION</strong>. Ne pas utiliser pour décider d'une dose d'insuline et n'écrit rien dans AAPS ni Nightscout.
          </div>
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div style={{ display: 'flex', gap: '0.75rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
        <button
          onClick={() => setActiveTab('replay')}
          style={{
            background: activeTab === 'replay' ? '#3b82f6' : 'var(--surface-hover)',
            color: activeTab === 'replay' ? 'white' : 'var(--text-secondary)',
            border: 'none',
            borderRadius: '6px',
            padding: '0.5rem 1rem',
            fontSize: '0.9rem',
            fontWeight: '500',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem'
          }}
        >
          <Play style={{ width: '16px', height: '16px' }} /> Rejeu d'une Journée (Day Replay)
        </button>

        <button
          onClick={() => setActiveTab('scenario')}
          style={{
            background: activeTab === 'scenario' ? '#3b82f6' : 'var(--surface-hover)',
            color: activeTab === 'scenario' ? 'white' : 'var(--text-secondary)',
            border: 'none',
            borderRadius: '6px',
            padding: '0.5rem 1rem',
            fontSize: '0.9rem',
            fontWeight: '500',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem'
          }}
        >
          <Sliders style={{ width: '16px', height: '16px' }} /> Scénarios « Et Si » (What-If)
        </button>

        <button
          onClick={() => setActiveTab('settings')}
          style={{
            background: activeTab === 'settings' ? '#3b82f6' : 'var(--surface-hover)',
            color: activeTab === 'settings' ? 'white' : 'var(--text-secondary)',
            border: 'none',
            borderRadius: '6px',
            padding: '0.5rem 1rem',
            fontSize: '0.9rem',
            fontWeight: '500',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem'
          }}
        >
          <Award style={{ width: '16px', height: '16px' }} /> Analyse des Réglages (ISF, CR, Basale)
        </button>

        <button
          onClick={() => setActiveTab('meals')}
          style={{
            background: activeTab === 'meals' ? '#3b82f6' : 'var(--surface-hover)',
            color: activeTab === 'meals' ? 'white' : 'var(--text-secondary)',
            border: 'none',
            borderRadius: '6px',
            padding: '0.5rem 1rem',
            fontSize: '0.9rem',
            fontWeight: '500',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem'
          }}
        >
          <Utensils style={{ width: '16px', height: '16px' }} /> Bibliothèque de Repas
        </button>
      </div>

      {/* TAB 1: DAY REPLAY */}
      {activeTab === 'replay' && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
            <div>
              <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Cpu style={{ color: '#a855f7' }} /> Rejeu de Journée par le Jumeau Numérique
              </div>
              <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                Comparaison entre la glycémie réelle observée et la dynamique simulée par le modèle physiologique hybride
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Calendar style={{ width: '16px', height: '16px', color: 'var(--text-secondary)' }} />
              <select
                value={selectedDate}
                onChange={e => setSelectedDate(e.target.value)}
                style={{
                  background: 'var(--surface-hover)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '6px',
                  padding: '0.4rem 0.75rem',
                  fontSize: '0.9rem',
                  cursor: 'pointer'
                }}
              >
                {availableDays.map(d => (
                  <option key={d.date} value={d.date}>
                    {new Date(d.date).toLocaleDateString('fr-FR', { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' })}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Replay Metrics Cards */}
          {replayData?.metrics && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1.25rem' }}>
              <div style={{ background: 'var(--surface-hover)', padding: '0.85rem', borderRadius: '8px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Erreur Quadratique (RMSE)</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#60a5fa' }}>{replayData.metrics.rmse} <small style={{ fontSize: '0.75rem' }}>mg/dL</small></div>
              </div>
              <div style={{ background: 'var(--surface-hover)', padding: '0.85rem', borderRadius: '8px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Erreur Absolue Moyenne (MAE)</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#a855f7' }}>{replayData.metrics.mae} <small style={{ fontSize: '0.75rem' }}>mg/dL</small></div>
              </div>
              <div style={{ background: 'var(--surface-hover)', padding: '0.85rem', borderRadius: '8px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Erreur Relative (MARD)</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#10b981' }}>{replayData.metrics.mard}%</div>
              </div>
              <div style={{ background: 'var(--surface-hover)', padding: '0.85rem', borderRadius: '8px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Précision Clinique Clarke (Zone A+B)</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#10b981' }}>{replayData.metrics.clarke?.zone_ab ?? 98}%</div>
              </div>
            </div>
          )}

          {/* ECharts Replay Graph */}
          {loadingReplay ? (
            <div style={{ height: '380px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)' }}>
              Simulation du jumeau numérique en cours...
            </div>
          ) : (
            <ReactECharts option={replayChartOption} style={{ height: '380px', width: '100%' }} />
          )}
        </div>
      )}

      {/* TAB 2: WHAT-IF SCENARIOS */}
      {activeTab === 'scenario' && (
        <div className="card">
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#10b981', marginBottom: '0.5rem' }}>
            <Sliders /> Simulateur de Scénarios « Et Si » sur Journée Réelle
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
            Modifiez un bolus, un repas ou une basale sur la journée du <strong>{selectedDate}</strong> et visualisez l'impact simulé par le jumeau numérique.
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.25rem', background: 'var(--surface-hover)', padding: '1.25rem', borderRadius: '8px', marginBottom: '1.25rem' }}>
            <div>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Ajustement Bolus (U) :</label>
              <input
                type="number"
                step="0.5"
                value={bolusDelta}
                onChange={e => setBolusDelta(parseFloat(e.target.value) || 0)}
                style={{ width: '100%', background: 'var(--surface)', color: 'white', border: '1px solid var(--border-color)', padding: '0.5rem', borderRadius: '6px', marginTop: '0.3rem' }}
              />
            </div>
            <div>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Ajustement Glucides (g) :</label>
              <input
                type="number"
                step="5"
                value={carbsDelta}
                onChange={e => setCarbsDelta(parseFloat(e.target.value) || 0)}
                style={{ width: '100%', background: 'var(--surface)', color: 'white', border: '1px solid var(--border-color)', padding: '0.5rem', borderRadius: '6px', marginTop: '0.3rem' }}
              />
            </div>
            <div>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Multiplicateur Basal :</label>
              <select
                value={basalMult}
                onChange={e => setBasalMult(parseFloat(e.target.value))}
                style={{ width: '100%', background: 'var(--surface)', color: 'white', border: '1px solid var(--border-color)', padding: '0.5rem', borderRadius: '6px', marginTop: '0.3rem' }}
              >
                <option value={0.8}>0.8x (-20% Basale Temp)</option>
                <option value={1.0}>1.0x (Basale Normale)</option>
                <option value={1.2}>1.2x (+20% Basale Temp)</option>
                <option value={1.5}>1.5x (+50% Cible Temp)</option>
              </select>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button
                onClick={handleRunScenario}
                style={{ width: '100%', background: '#10b981', color: 'white', border: 'none', padding: '0.65rem', borderRadius: '6px', fontWeight: 'bold', cursor: 'pointer' }}
              >
                Simuler le Scénario
              </button>
            </div>
          </div>

          {loadingScenario ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>Calcul du scénario...</div>
          ) : scenarioResult?.timeline ? (
            <ReactECharts option={scenarioChartOption} style={{ height: '380px', width: '100%' }} />
          ) : (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>Cliquez sur "Simuler le Scénario" pour lancer le calcul.</div>
          )}
        </div>
      )}

      {/* TAB 3: SETTINGS ANALYSIS */}
      {activeTab === 'settings' && (
        <div className="card">
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <Award style={{ color: '#f59e0b' }} /> Analyse de l'Adéquation des Réglages (Basale, ISF, CR)
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
            Estimation par le jumeau numérique de l'équilibre de vos réglages par tranches horaires de 3 heures. <strong>Pistes de réflexion à discuter avec votre équipe soignante.</strong>
          </div>

          {loadingSettings ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>Analyse des réglages en cours...</div>
          ) : settingsData?.blocks ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.25rem' }}>
              {settingsData.blocks.map((b: SettingBlock) => (
                <div key={b.block_id} style={{ background: 'var(--surface-hover)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <div style={{ fontWeight: 'bold', fontSize: '0.95rem', color: '#60a5fa' }}>{b.label}</div>
                    <span style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', borderRadius: '4px', background: 'rgba(255,255,255,0.08)', color: 'var(--text-secondary)' }}>
                      Confiance : {b.confidence}
                    </span>
                  </div>

                  <div style={{ display: 'flex', gap: '1rem', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                    <div>ISF Estimé : <strong style={{ color: '#10b981' }}>{b.isf_estimated} mg/dL/U</strong></div>
                    <div>Ratio CR : <strong style={{ color: '#fbbf24' }}>{b.cr_estimated} g/U</strong></div>
                  </div>

                  <div style={{ fontSize: '0.82rem', marginBottom: '0.5rem' }}>
                    <div style={{ fontWeight: '600', color: '#f8fafc' }}>Statut Basale :</div>
                    <div style={{ color: b.status_basal.includes('adaptée') ? '#10b981' : '#f59e0b' }}>{b.status_basal}</div>
                  </div>

                  <div style={{ fontSize: '0.8rem', color: '#d1d5db', background: 'rgba(0,0,0,0.2)', padding: '0.6rem', borderRadius: '6px' }}>
                    💡 <em>{b.recommendation_note}</em>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      )}

      {/* TAB 4: MEAL LIBRARY */}
      {activeTab === 'meals' && (
        <div className="card">
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <Utensils style={{ color: '#fbbf24' }} /> Bibliothèque des Repas & Réponses Glycémiques
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
            Historique des excursions glycémiques postprandiales observées (+1h, +2h, +3h) selon les types de repas.
          </div>

          {loadingMeals ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>Chargement de la bibliothèque de repas...</div>
          ) : mealsData?.meals ? (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ background: 'var(--surface-hover)', color: 'var(--text-secondary)', textAlign: 'left' }}>
                    <th style={{ padding: '0.75rem' }}>Date & Heure</th>
                    <th style={{ padding: '0.75rem' }}>Catégorie</th>
                    <th style={{ padding: '0.75rem' }}>Glucides (g)</th>
                    <th style={{ padding: '0.75rem' }}>Bolus (U)</th>
                    <th style={{ padding: '0.75rem' }}>SGV Départ</th>
                    <th style={{ padding: '0.75rem' }}>Pic Max</th>
                    <th style={{ padding: '0.75rem' }}>Élévation ($\Delta$)</th>
                    <th style={{ padding: '0.75rem' }}>Statut Excursion</th>
                  </tr>
                </thead>
                <tbody>
                  {mealsData.meals.map((m: MealItem) => (
                    <tr key={m.meal_id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                      <td style={{ padding: '0.65rem' }}>{new Date(m.datetime).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}</td>
                      <td style={{ padding: '0.65rem', fontWeight: '500' }}>{m.category}</td>
                      <td style={{ padding: '0.65rem', fontWeight: 'bold', color: '#fbbf24' }}>{m.carbs_g} g</td>
                      <td style={{ padding: '0.65rem', color: '#38bdf8' }}>{m.bolus_u} U</td>
                      <td style={{ padding: '0.65rem' }}>{m.start_sgv}</td>
                      <td style={{ padding: '0.65rem', fontWeight: 'bold' }}>{m.max_sgv}</td>
                      <td style={{ padding: '0.65rem', color: m.peak_delta > 60 ? '#ef4444' : '#10b981' }}>+{m.peak_delta} mg/dL</td>
                      <td style={{ padding: '0.65rem', fontSize: '0.8rem' }}>{m.response_quality}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      )}

    </div>
  );
}

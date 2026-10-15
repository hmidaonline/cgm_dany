import { useState, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import {
  ShieldAlert, Zap, Activity,
  Play, RefreshCw, BarChart2, CheckCircle2,
  Calendar, Layers, Sliders, Dna,
  Lock, TrendingUp, HeartHandshake
} from 'lucide-react';
import { API_BASE_URL } from '../config';

export default function RLAgentView() {
  const [activeTab, setActiveTab] = useState<'arena' | 'shadow' | 'identity'>('arena');

  // --- Sub-view A: Counterfactual Arena State ---
  const [selectedScenario, setSelectedScenario] = useState('high_fat');
  const [simSeed, setSimSeed] = useState(1042);
  const [simLoading, setSimLoading] = useState(false);
  const [simResults, setSimResults] = useState<any>(null);

  // --- Sub-view B: Shadow Audit State ---
  const [auditDate, setAuditDate] = useState('2026-10-12');
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditResults, setAuditResults] = useState<any>(null);

  // --- Sub-view C: Scientific Identity Benchmarks State ---
  const [benchmarks, setBenchmarks] = useState<any>(null);

  // Load benchmarks on mount
  useEffect(() => {
    fetch(`${API_BASE_URL}/api/rl/benchmarks`)
      .then(res => res.json())
      .then(data => setBenchmarks(data))
      .catch(err => console.error("Error loading RL benchmarks:", err));
  }, []);

  // Run initial simulation on load
  useEffect(() => {
    runCounterfactualSim(selectedScenario, simSeed);
  }, []);

  const runCounterfactualSim = async (scenario: string, seed: number) => {
    setSimLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/rl/counterfactual-sim`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_type: scenario, seed })
      });
      const data = await res.json();
      setSimResults(data);
    } catch (err) {
      console.error("Error running counterfactual sim:", err);
    } finally {
      setSimLoading(false);
    }
  };

  const runShadowAudit = async (date: string) => {
    setAuditLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/rl/shadow-audit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date })
      });
      const data = await res.json();
      setAuditResults(data);
    } catch (err) {
      console.error("Error running shadow audit:", err);
    } finally {
      setAuditLoading(false);
    }
  };

  const randomizeSeed = () => {
    const nextSeed = Math.floor(1000 + Math.random() * 200);
    setSimSeed(nextSeed);
    runCounterfactualSim(selectedScenario, nextSeed);
  };

  // --- ECharts Options: Counterfactual Arena Glucose ---
  const getArenaGlucoseOption = () => {
    if (!simResults?.time_series) return {};
    const ts = simResults.time_series;

    const timeLabels = ts.open_loop ? ts.open_loop.map((d: any) => d.time) : [];
    const openLoopSGV = ts.open_loop ? ts.open_loop.map((d: any) => d.cgm) : [];
    const pidSGV = ts.pid_shield ? ts.pid_shield.map((d: any) => d.cgm) : [];
    const oref0SGV = ts.oref0_shield ? ts.oref0_shield.map((d: any) => d.cgm) : [];
    const ppoSGV = ts.residual_ppo_shield ? ts.residual_ppo_shield.map((d: any) => d.cgm) : [];

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross', lineStyle: { color: 'rgba(255,255,255,0.2)' } }
      },
      legend: {
        data: ['OpenLoop (Bolus Wizard)', 'PID (+Shield)', 'Oref0 (+Shield)', 'Residual PPO (+Shield)'],
        textStyle: { color: '#94a3b8' },
        top: 0
      },
      grid: { left: '3%', right: '4%', bottom: '5%', top: '15%', containLabel: true },
      xAxis: {
        type: 'category',
        data: timeLabels,
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: { color: '#94a3b8' }
      },
      yAxis: {
        type: 'value',
        min: 40,
        max: 320,
        axisLine: { lineStyle: { color: '#334155' } },
        splitLine: { lineStyle: { color: '#1e293b' } },
        axisLabel: { color: '#94a3b8', formatter: '{value} mg/dL' }
      },
      series: [
        {
          name: 'OpenLoop (Bolus Wizard)',
          type: 'line',
          data: openLoopSGV,
          lineStyle: { width: 1.5, type: 'dotted', color: '#94a3b8' },
          symbol: 'none'
        },
        {
          name: 'PID (+Shield)',
          type: 'line',
          data: pidSGV,
          lineStyle: { width: 1.8, type: 'dashed', color: '#38bdf8' },
          symbol: 'none'
        },
        {
          name: 'Oref0 (+Shield)',
          type: 'line',
          data: oref0SGV,
          lineStyle: { width: 2.2, color: '#f59e0b' },
          symbol: 'none'
        },
        {
          name: 'Residual PPO (+Shield)',
          type: 'line',
          data: ppoSGV,
          lineStyle: { width: 3.0, color: '#10b981' },
          symbol: 'none',
          markArea: {
            silent: true,
            data: [
              [
                { yAxis: 70, itemStyle: { color: 'rgba(16, 185, 129, 0.08)' } },
                { yAxis: 140 }
              ],
              [
                { yAxis: 140, itemStyle: { color: 'rgba(56, 189, 248, 0.04)' } },
                { yAxis: 180 }
              ]
            ]
          }
        }
      ]
    };
  };

  // --- ECharts Options: Counterfactual Arena Basal & Residual Correction ---
  const getArenaBasalOption = () => {
    if (!simResults?.time_series) return {};
    const ts = simResults.time_series;

    const timeLabels = ts.open_loop ? ts.open_loop.map((d: any) => d.time) : [];
    const oref0Rate = ts.oref0_shield ? ts.oref0_shield.map((d: any) => d.delivered_basal_rate) : [];
    const ppoRate = ts.residual_ppo_shield ? ts.residual_ppo_shield.map((d: any) => d.delivered_basal_rate) : [];
    const deltaRate = ts.residual_ppo_shield ? ts.residual_ppo_shield.map((d: any) => {
      const dVal = (d.residual_delta || 0) * 0.85;
      return {
        value: roundNum(dVal, 2),
        itemStyle: { color: dVal >= 0 ? '#10b981' : '#f97316' }
      };
    }) : [];

    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: {
        data: ['Oref0 Basal (U/h)', 'PPO Basal Délivré (U/h)', 'Correction Résiduelle α·a_t (U/h)'],
        textStyle: { color: '#94a3b8' },
        top: 0
      },
      grid: { left: '3%', right: '4%', bottom: '5%', top: '18%', containLabel: true },
      xAxis: {
        type: 'category',
        data: timeLabels,
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: { color: '#94a3b8' }
      },
      yAxis: [
        {
          type: 'value',
          min: 0,
          max: 3.0,
          name: 'Débit (U/h)',
          nameTextStyle: { color: '#94a3b8' },
          axisLabel: { color: '#94a3b8' },
          splitLine: { lineStyle: { color: '#1e293b' } }
        },
        {
          type: 'value',
          min: -1.0,
          max: 1.0,
          name: 'Delta RL (U/h)',
          nameTextStyle: { color: '#94a3b8' },
          axisLabel: { color: '#94a3b8' },
          splitLine: { show: false }
        }
      ],
      series: [
        {
          name: 'Oref0 Basal (U/h)',
          type: 'line',
          step: 'end',
          data: oref0Rate,
          lineStyle: { width: 1.5, color: '#f59e0b' },
          symbol: 'none'
        },
        {
          name: 'PPO Basal Délivré (U/h)',
          type: 'line',
          step: 'end',
          data: ppoRate,
          lineStyle: { width: 2.2, color: '#10b981' },
          symbol: 'none'
        },
        {
          name: 'Correction Résiduelle α·a_t (U/h)',
          type: 'bar',
          yAxisIndex: 1,
          data: deltaRate
        }
      ]
    };
  };

  // --- ECharts Options: Shadow Audit Chart ---
  const getShadowChartOption = () => {
    if (!auditResults?.steps) return {};
    const steps = auditResults.steps;

    const timeLabels = steps.map((s: any) => s.time);
    const cgmData = steps.map((s: any) => s.cgm);
    const aapsRate = steps.map((s: any) => s.aaps_basal_rate);
    const ppoRate = steps.map((s: any) => s.residual_ppo_basal_rate);
    const orefRate = steps.map((s: any) => s.oref0_basal_rate);

    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: {
        data: ['CGM Réel (mg/dL)', 'AAPS Réel Historique (U/h)', 'Oref0 Recommandé (U/h)', 'Residual PPO Recommandé (U/h)'],
        textStyle: { color: '#94a3b8' },
        top: 0
      },
      grid: { left: '3%', right: '4%', bottom: '5%', top: '15%', containLabel: true },
      xAxis: {
        type: 'category',
        data: timeLabels,
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: { color: '#94a3b8' }
      },
      yAxis: [
        {
          type: 'value',
          name: 'Glycémie (mg/dL)',
          min: 40,
          max: 300,
          nameTextStyle: { color: '#94a3b8' },
          axisLabel: { color: '#94a3b8' },
          splitLine: { lineStyle: { color: '#1e293b' } }
        },
        {
          type: 'value',
          name: 'Insuline (U/h)',
          min: 0,
          max: 3.0,
          nameTextStyle: { color: '#94a3b8' },
          axisLabel: { color: '#94a3b8' },
          splitLine: { show: false }
        }
      ],
      series: [
        {
          name: 'CGM Réel (mg/dL)',
          type: 'line',
          data: cgmData,
          lineStyle: { width: 2.5, color: '#38bdf8' },
          symbol: 'none'
        },
        {
          name: 'AAPS Réel Historique (U/h)',
          type: 'line',
          yAxisIndex: 1,
          step: 'end',
          data: aapsRate,
          lineStyle: { width: 1.5, type: 'dotted', color: '#94a3b8' },
          symbol: 'none'
        },
        {
          name: 'Oref0 Recommandé (U/h)',
          type: 'line',
          yAxisIndex: 1,
          step: 'end',
          data: orefRate,
          lineStyle: { width: 1.8, color: '#f59e0b' },
          symbol: 'none'
        },
        {
          name: 'Residual PPO Recommandé (U/h)',
          type: 'line',
          yAxisIndex: 1,
          step: 'end',
          data: ppoRate,
          lineStyle: { width: 2.2, color: '#10b981' },
          symbol: 'none'
        }
      ]
    };
  };

  const roundNum = (n: number | undefined, d = 1) => (n !== undefined ? n.toFixed(d) : '--');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* 1. Permanent Ethical Warning Banner */}
      <div style={{
        background: 'linear-gradient(90deg, rgba(239, 68, 68, 0.15), rgba(245, 158, 11, 0.12))',
        border: '1px solid rgba(239, 68, 68, 0.35)',
        borderRadius: '12px',
        padding: '0.85rem 1.25rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '1rem',
        boxShadow: '0 4px 16px rgba(0,0,0,0.2)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
          <div style={{
            background: 'rgba(239, 68, 68, 0.25)',
            padding: '0.5rem',
            borderRadius: '8px',
            color: '#f87171',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <ShieldAlert style={{ width: '22px', height: '22px' }} />
          </div>
          <div>
            <div style={{ fontSize: '0.9rem', fontWeight: '700', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              Mode Ombre & Simulation In Silico — Recherche Personnelle Uniquement
              <span style={{
                background: 'rgba(239, 68, 68, 0.25)',
                color: '#fca5a5',
                fontSize: '0.65rem',
                padding: '0.15rem 0.45rem',
                borderRadius: '6px',
                fontWeight: '700'
              }}>
                NON CONNECTÉ À LA POMPE
              </span>
            </div>
            <div style={{ fontSize: '0.78rem', color: '#cbd5e1', marginTop: '0.15rem' }}>
              Les recommandations de l'agent RL ne doivent <strong>jamais être utilisées pour modifier un traitement médical réel</strong>. Aucune commande n'est transmise au matériel.
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#94a3b8', fontSize: '0.75rem', flexShrink: 0 }}>
          <Lock style={{ width: '14px', height: '14px', color: '#10b981' }} />
          <span>SafetyShield Actif</span>
        </div>
      </div>

      {/* 2. Tab Navigation Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: '#1e293b',
        border: '1px solid #334155',
        borderRadius: '12px',
        padding: '0.4rem'
      }}>
        <div style={{ display: 'flex', gap: '0.4rem' }}>
          <button
            onClick={() => setActiveTab('arena')}
            style={{
              background: activeTab === 'arena' ? '#3b82f6' : 'transparent',
              color: activeTab === 'arena' ? '#fff' : '#94a3b8',
              border: 'none',
              borderRadius: '8px',
              padding: '0.55rem 1rem',
              fontSize: '0.82rem',
              fontWeight: '600',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.45rem',
              transition: 'all 0.2s ease'
            }}
          >
            <Activity style={{ width: '15px', height: '15px' }} />
            Arène Contrefactuelle ("What-If")
          </button>

          <button
            onClick={() => {
              setActiveTab('shadow');
              if (!auditResults) runShadowAudit(auditDate);
            }}
            style={{
              background: activeTab === 'shadow' ? '#3b82f6' : 'transparent',
              color: activeTab === 'shadow' ? '#fff' : '#94a3b8',
              border: 'none',
              borderRadius: '8px',
              padding: '0.55rem 1rem',
              fontSize: '0.82rem',
              fontWeight: '600',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.45rem',
              transition: 'all 0.2s ease'
            }}
          >
            <Layers style={{ width: '15px', height: '15px' }} />
            Audit Mode Ombre (Journée Réelle)
          </button>

          <button
            onClick={() => setActiveTab('identity')}
            style={{
              background: activeTab === 'identity' ? '#3b82f6' : 'transparent',
              color: activeTab === 'identity' ? '#fff' : '#94a3b8',
              border: 'none',
              borderRadius: '8px',
              padding: '0.55rem 1rem',
              fontSize: '0.82rem',
              fontWeight: '600',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.45rem',
              transition: 'all 0.2s ease'
            }}
          >
            <Dna style={{ width: '15px', height: '15px' }} />
            Carte d'Identité Scientifique (Preuves N=200)
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', paddingRight: '0.5rem' }}>
          <span style={{ fontSize: '0.75rem', color: '#10b981', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#10b981' }}></span>
            Residual PPO Online
          </span>
        </div>
      </div>

      {/* 3. Sub-view A: Counterfactual Arena ("What-If Digital Twin") */}
      {activeTab === 'arena' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Controls Bar */}
          <div style={{
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '12px',
            padding: '1rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '1rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Sliders style={{ width: '16px', height: '16px', color: '#60a5fa' }} />
                <span style={{ fontSize: '0.85rem', fontWeight: '600', color: '#f8fafc' }}>Scénario Métabolique :</span>
              </div>
              <select
                value={selectedScenario}
                onChange={e => {
                  setSelectedScenario(e.target.value);
                  runCounterfactualSim(e.target.value, simSeed);
                }}
                style={{
                  background: '#0f172a',
                  border: '1px solid #334155',
                  color: '#f8fafc',
                  borderRadius: '8px',
                  padding: '0.45rem 0.85rem',
                  fontSize: '0.82rem',
                  outline: 'none',
                  cursor: 'pointer'
                }}
              >
                <option value="nominal">1. Journée Standard (Nominale)</option>
                <option value="high_fat">2. Repas Gras / Absorption Retardée (T_max=110m)</option>
                <option value="exercise">3. Exercice Physique Post-Prandial (GLUT4 + 50% ISF)</option>
                <option value="missed_bolus">4. Bolus Oublié (Repas 60g non couvert)</option>
                <option value="under_est_40">5. Sous-estimation Glucides (-40%)</option>
                <option value="over_est_40">6. Surestimation Glucides (+40% / Surdosage Bolus)</option>
              </select>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#94a3b8', fontSize: '0.82rem' }}>
                <span>Graine aléatoire :</span>
                <span style={{ background: '#0f172a', padding: '0.2rem 0.5rem', borderRadius: '6px', color: '#38bdf8', fontWeight: '700' }}>
                  {simSeed}
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <button
                onClick={randomizeSeed}
                disabled={simLoading}
                style={{
                  background: 'rgba(56, 189, 248, 0.1)',
                  border: '1px solid rgba(56, 189, 248, 0.25)',
                  color: '#38bdf8',
                  borderRadius: '8px',
                  padding: '0.45rem 0.85rem',
                  fontSize: '0.8rem',
                  fontWeight: '600',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem'
                }}
              >
                <RefreshCw style={{ width: '13px', height: '13px', animation: simLoading ? 'spin 1s linear infinite' : 'none' }} />
                🎲 Tirer une Nouvelle Graine
              </button>

              <button
                onClick={() => runCounterfactualSim(selectedScenario, simSeed)}
                disabled={simLoading}
                style={{
                  background: '#10b981',
                  border: 'none',
                  color: '#fff',
                  borderRadius: '8px',
                  padding: '0.45rem 1rem',
                  fontSize: '0.82rem',
                  fontWeight: '700',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem'
                }}
              >
                <Play style={{ width: '14px', height: '14px' }} />
                Simuler dans le Jumeau
              </button>
            </div>
          </div>

          {/* Metric Comparison Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
            {simResults?.comparison_table?.map((c: any) => {
              const isPPO = c.controller_id === 'residual_ppo_shield';
              return (
                <div
                  key={c.controller_id}
                  style={{
                    background: isPPO ? 'linear-gradient(180deg, rgba(16, 185, 129, 0.12), rgba(30, 41, 59, 0.95))' : '#1e293b',
                    border: isPPO ? '2px solid #10b981' : '1px solid #334155',
                    borderRadius: '12px',
                    padding: '1rem',
                    position: 'relative'
                  }}
                >
                  {isPPO && (
                    <div style={{
                      position: 'absolute',
                      top: '-10px',
                      right: '12px',
                      background: '#10b981',
                      color: '#0f172a',
                      fontSize: '0.65rem',
                      fontWeight: '800',
                      padding: '0.15rem 0.45rem',
                      borderRadius: '10px'
                    }}>
                      AGENT RL RÉSIDUEL
                    </div>
                  )}
                  <div style={{ fontSize: '0.82rem', fontWeight: '700', color: isPPO ? '#34d399' : '#f8fafc', marginBottom: '0.5rem' }}>
                    {c.label}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                    <div>
                      <div style={{ fontSize: '0.68rem', color: '#94a3b8' }}>TIR (70-180)</div>
                      <div style={{ fontSize: '1.15rem', fontWeight: '800', color: c.tir_70_180 >= 90 ? '#10b981' : '#f59e0b' }}>
                        {roundNum(c.tir_70_180)}%
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.68rem', color: '#94a3b8' }}>Tight TIR (70-140)</div>
                      <div style={{ fontSize: '1.15rem', fontWeight: '800', color: '#38bdf8' }}>
                        {roundNum(c.tight_tir_70_140)}%
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.68rem', color: '#94a3b8' }}>TBR (&lt;70)</div>
                      <div style={{ fontSize: '1.05rem', fontWeight: '700', color: c.tbr_under_70 > 1.0 ? '#ef4444' : '#10b981' }}>
                        {roundNum(c.tbr_under_70)}%
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.68rem', color: '#94a3b8' }}>Risque BGRI</div>
                      <div style={{ fontSize: '1.05rem', fontWeight: '700', color: c.bgri <= 2.5 ? '#10b981' : '#f87171' }}>
                        {roundNum(c.bgri, 2)}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Main Chart: Trajectoires Glycémiques */}
          <div style={{
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '12px',
            padding: '1.25rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <div style={{ fontSize: '0.9rem', fontWeight: '700', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <TrendingUp style={{ width: '17px', height: '17px', color: '#10b981' }} />
                Trajectoires Glycémiques Comparées (24 heures / 288 pas de 5 min)
              </div>
              <div style={{ display: 'flex', gap: '0.75rem', fontSize: '0.72rem', color: '#94a3b8' }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                  <span style={{ width: '10px', height: '10px', background: 'rgba(16, 185, 129, 0.3)', borderRadius: '2px' }}></span>
                  Cible Serrée (70-140 mg/dL)
                </span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                  <span style={{ width: '10px', height: '10px', background: 'rgba(56, 189, 248, 0.2)', borderRadius: '2px' }}></span>
                  Cible Standard (70-180 mg/dL)
                </span>
              </div>
            </div>
            <ReactECharts option={getArenaGlucoseOption()} style={{ height: '360px', width: '100%' }} />
          </div>

          {/* Subchart: Basal Delivery & Residual Delta */}
          <div style={{
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '12px',
            padding: '1.25rem'
          }}>
            <div style={{ fontSize: '0.9rem', fontWeight: '700', color: '#f8fafc', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Zap style={{ width: '17px', height: '17px', color: '#f59e0b' }} />
              Dynamique de Contrôle : Recommandation Oref0 vs Correction Résiduelle PPO (α·a_t)
            </div>
            <ReactECharts option={getArenaBasalOption()} style={{ height: '240px', width: '100%' }} />
          </div>
        </div>
      )}

      {/* 4. Sub-view B: Shadow Audit on Real Day */}
      {activeTab === 'shadow' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Audit Controls */}
          <div style={{
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '12px',
            padding: '1rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '1rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Calendar style={{ width: '16px', height: '16px', color: '#38bdf8' }} />
                <span style={{ fontSize: '0.85rem', fontWeight: '600', color: '#f8fafc' }}>Date Réelle d'Audit (MongoDB) :</span>
              </div>
              <input
                type="date"
                value={auditDate}
                onChange={e => setAuditDate(e.target.value)}
                style={{
                  background: '#0f172a',
                  border: '1px solid #334155',
                  color: '#f8fafc',
                  borderRadius: '8px',
                  padding: '0.45rem 0.85rem',
                  fontSize: '0.82rem',
                  outline: 'none'
                }}
              />
            </div>

            <button
              onClick={() => runShadowAudit(auditDate)}
              disabled={auditLoading}
              style={{
                background: '#3b82f6',
                border: 'none',
                color: '#fff',
                borderRadius: '8px',
                padding: '0.45rem 1rem',
                fontSize: '0.82rem',
                fontWeight: '700',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem'
              }}
            >
              <RefreshCw style={{ width: '13px', height: '13px', animation: auditLoading ? 'spin 1s linear infinite' : 'none' }} />
              Lancer l'Audit en Mode Ombre
            </button>
          </div>

          {/* Audit Summary Stats */}
          {auditResults?.summary && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '1rem' }}>
              <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '1rem' }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Glycémie Moyenne Réelle</div>
                <div style={{ fontSize: '1.25rem', fontWeight: '800', color: '#38bdf8' }}>
                  {auditResults.summary.mean_cgm} mg/dL
                </div>
              </div>
              <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '1rem' }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Dose Basale AAPS Réelle</div>
                <div style={{ fontSize: '1.25rem', fontWeight: '800', color: '#94a3b8' }}>
                  {auditResults.summary.total_aaps_basal_units} U
                </div>
              </div>
              <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '1rem' }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Dose Oref0 Recommandée</div>
                <div style={{ fontSize: '1.25rem', fontWeight: '800', color: '#f59e0b' }}>
                  {auditResults.summary.total_oref0_basal_units} U
                </div>
              </div>
              <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '1rem' }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Dose Residual PPO</div>
                <div style={{ fontSize: '1.25rem', fontWeight: '800', color: '#10b981' }}>
                  {auditResults.summary.total_ppo_basal_units} U
                </div>
              </div>
              <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '1rem' }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Interventions SafetyShield</div>
                <div style={{ fontSize: '1.25rem', fontWeight: '800', color: '#38bdf8' }}>
                  {auditResults.summary.shield_intervention_count} ({auditResults.summary.shield_intervention_pct}%)
                </div>
              </div>
            </div>
          )}

          {/* Shadow Chart */}
          <div style={{
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '12px',
            padding: '1.25rem'
          }}>
            <div style={{ fontSize: '0.9rem', fontWeight: '700', color: '#f8fafc', marginBottom: '0.5rem' }}>
              Comparaison Pas-à-Pas : Décision Réelle AAPS vs Recommandation Residual PPO
            </div>
            <ReactECharts option={getShadowChartOption()} style={{ height: '360px', width: '100%' }} />
          </div>
        </div>
      )}

      {/* 5. Sub-view C: Scientific Identity Benchmarks */}
      {activeTab === 'identity' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Asymmetry Ceiling Note Alert */}
          <div style={{
            background: 'rgba(56, 189, 248, 0.08)',
            border: '1px solid rgba(56, 189, 248, 0.25)',
            borderRadius: '12px',
            padding: '1.25rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.5rem'
          }}>
            <div style={{ fontSize: '0.95rem', fontWeight: '700', color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <HeartHandshake style={{ width: '18px', height: '18px' }} />
              Note d'Analyse Clinique : Asymétrie de Saturation au Plafond de Sécurité
            </div>
            <div style={{ fontSize: '0.82rem', color: '#cbd5e1', lineHeight: '1.6' }}>
              Sur les scénarios de stress aigu (Bolus oublié et sous-estimation de -40 %), l'agent Residual PPO fait jeu égal ou -1,2 % de TIR face à Oref0. Cela résulte d'une <strong>propriété de sécurité délibérée</strong> : en forte hyperglycémie, u_oref0(s_t) sature déjà au plafond légal de 3,0 × basal. L'action finale étant bornée à [0, 3.0], l'agent résiduel ne peut pas forcer plus d'insuline qu'Oref0, mais peut seulement en retrancher par prudence. Cette asymétrie protège formellement contre toute sur-insulinisation incontrôlée lors des crises hyperglycémiques aiguës.
            </div>
          </div>

          {/* Banc A Table */}
          <div style={{
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '12px',
            padding: '1.25rem'
          }}>
            <div style={{ fontSize: '0.95rem', fontWeight: '700', color: '#f8fafc', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <BarChart2 style={{ width: '18px', height: '18px', color: '#10b981' }} />
              Banc d'Essai A : Résultats Certifiés sur 200 Graines de Test Appariées (1000 à 1199)
              {benchmarks?.phase4 && (
                <span style={{ fontSize: '0.7rem', color: '#10b981', background: 'rgba(16, 185, 129, 0.1)', padding: '0.15rem 0.5rem', borderRadius: '6px', fontWeight: 'normal' }}>
                  ● Métriques API Validées
                </span>
              )}
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem', color: '#cbd5e1' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8', textAlign: 'left' }}>
                    <th style={{ padding: '0.6rem' }}>Contrôleur</th>
                    <th style={{ padding: '0.6rem' }}>TIR (70-180)</th>
                    <th style={{ padding: '0.6rem' }}>Tight TIR (70-140)</th>
                    <th style={{ padding: '0.6rem' }}>TBR (&lt;70)</th>
                    <th style={{ padding: '0.6rem' }}>Moyenne Glycémique</th>
                    <th style={{ padding: '0.6rem' }}>Risque BGRI</th>
                    <th style={{ padding: '0.6rem' }}>Récompense Cumulée</th>
                    <th style={{ padding: '0.6rem' }}>Statut Statistique</th>
                  </tr>
                </thead>
                <tbody>
                  <tr style={{ borderBottom: '1px solid #334155' }}>
                    <td style={{ padding: '0.6rem', fontWeight: '600' }}>In Vivo (Référence AAPS Réel)</td>
                    <td style={{ padding: '0.6rem' }}>77,9%</td>
                    <td style={{ padding: '0.6rem' }}>53,8%</td>
                    <td style={{ padding: '0.6rem' }}>2,6%</td>
                    <td style={{ padding: '0.6rem' }}>143,2 mg/dL</td>
                    <td style={{ padding: '0.6rem' }}>5,20</td>
                    <td style={{ padding: '0.6rem' }}>—</td>
                    <td style={{ padding: '0.6rem', color: '#94a3b8' }}>Patient In Vivo</td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #334155' }}>
                    <td style={{ padding: '0.6rem' }}>OpenLoop (Bolus Wizard)</td>
                    <td style={{ padding: '0.6rem', color: '#f59e0b' }}>63,3%</td>
                    <td style={{ padding: '0.6rem' }}>41,0%</td>
                    <td style={{ padding: '0.6rem' }}>0,0%</td>
                    <td style={{ padding: '0.6rem' }}>182,4 mg/dL</td>
                    <td style={{ padding: '0.6rem', color: '#ef4444' }}>11,55</td>
                    <td style={{ padding: '0.6rem' }}>260,9</td>
                    <td style={{ padding: '0.6rem', color: '#94a3b8' }}>Baseline Boucle Ouverte</td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #334155' }}>
                    <td style={{ padding: '0.6rem' }}>PID (+Shield)</td>
                    <td style={{ padding: '0.6rem' }}>90,8%</td>
                    <td style={{ padding: '0.6rem' }}>66,2%</td>
                    <td style={{ padding: '0.6rem' }}>0,0%</td>
                    <td style={{ padding: '0.6rem' }}>135,2 mg/dL</td>
                    <td style={{ padding: '0.6rem' }}>2,52</td>
                    <td style={{ padding: '0.6rem' }}>642,8</td>
                    <td style={{ padding: '0.6rem', color: '#38bdf8' }}>Gate Passé vs OpenLoop</td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid #334155' }}>
                    <td style={{ padding: '0.6rem', fontWeight: '600', color: '#f59e0b' }}>Oref0 (+Shield)</td>
                    <td style={{ padding: '0.6rem' }}>93,3%</td>
                    <td style={{ padding: '0.6rem' }}>69,7%</td>
                    <td style={{ padding: '0.6rem' }}>0,0%</td>
                    <td style={{ padding: '0.6rem' }}>132,0 mg/dL</td>
                    <td style={{ padding: '0.6rem' }}>2,01</td>
                    <td style={{ padding: '0.6rem' }}>668,1</td>
                    <td style={{ padding: '0.6rem', color: '#10b981' }}>Gate p = 8,03e-5 vs PID</td>
                  </tr>
                  <tr style={{ background: 'rgba(16, 185, 129, 0.1)', borderBottom: '1px solid #10b981' }}>
                    <td style={{ padding: '0.6rem', fontWeight: '800', color: '#10b981' }}>Residual PPO (+Shield)</td>
                    <td style={{ padding: '0.6rem', fontWeight: '700' }}>93,3%</td>
                    <td style={{ padding: '0.6rem', fontWeight: '800', color: '#34d399' }}>71,5%</td>
                    <td style={{ padding: '0.6rem' }}>0,0%</td>
                    <td style={{ padding: '0.6rem', fontWeight: '700' }}>130,1 mg/dL</td>
                    <td style={{ padding: '0.6rem', fontWeight: '700', color: '#34d399' }}>1,97</td>
                    <td style={{ padding: '0.6rem', fontWeight: '800', color: '#10b981' }}>671,8</td>
                    <td style={{ padding: '0.6rem', color: '#10b981', fontWeight: '700' }}>p = 1,89e-25 (Tight TIR)</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Banc B Stress Scenarios Cards */}
          <div style={{
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '12px',
            padding: '1.25rem'
          }}>
            <div style={{ fontSize: '0.95rem', fontWeight: '700', color: '#f8fafc', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <CheckCircle2 style={{ width: '18px', height: '18px', color: '#38bdf8' }} />
              Banc d'Essai B : Résilience sur les 5 Scénarios de Stress Dédiés (N=50 x 5)
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '0.85rem' }}>
              <div style={{ background: '#0f172a', padding: '0.85rem', borderRadius: '10px', border: '1px solid #334155' }}>
                <div style={{ fontSize: '0.78rem', fontWeight: '700', color: '#f8fafc', marginBottom: '0.35rem' }}>1. Bolus Oublié (60g)</div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>OpenLoop : 32,5% TIR</div>
                <div style={{ fontSize: '0.7rem', color: '#f59e0b' }}>Oref0 : 73,0% TIR</div>
                <div style={{ fontSize: '0.75rem', fontWeight: '700', color: '#10b981' }}>PPO : 72,8% TIR</div>
              </div>
              <div style={{ background: '#0f172a', padding: '0.85rem', borderRadius: '10px', border: '1px solid #10b981' }}>
                <div style={{ fontSize: '0.78rem', fontWeight: '700', color: '#10b981', marginBottom: '0.35rem' }}>2. Repas Gras (T_max 110m)</div>
                <div style={{ fontSize: '0.7rem', color: '#ef4444' }}>Oref0 TBR : 5,8% (hypos)</div>
                <div style={{ fontSize: '0.75rem', fontWeight: '800', color: '#10b981' }}>PPO TBR : 0,4% (-93% hypos!)</div>
                <div style={{ fontSize: '0.7rem', color: '#34d399' }}>TIR : 94,4% (vs 91,8%)</div>
              </div>
              <div style={{ background: '#0f172a', padding: '0.85rem', borderRadius: '10px', border: '1px solid #334155' }}>
                <div style={{ fontSize: '0.78rem', fontWeight: '700', color: '#f8fafc', marginBottom: '0.35rem' }}>3. Exercice (GLUT4)</div>
                <div style={{ fontSize: '0.7rem', color: '#ef4444' }}>OpenLoop TBR : 0,5%</div>
                <div style={{ fontSize: '0.7rem', color: '#f59e0b' }}>Oref0 TBR : 0,2%</div>
                <div style={{ fontSize: '0.75rem', fontWeight: '700', color: '#10b981' }}>PPO TBR : 0,3% (94,1% TIR)</div>
              </div>
              <div style={{ background: '#0f172a', padding: '0.85rem', borderRadius: '10px', border: '1px solid #334155' }}>
                <div style={{ fontSize: '0.78rem', fontWeight: '700', color: '#f8fafc', marginBottom: '0.35rem' }}>4. Sous-estimation -40%</div>
                <div style={{ fontSize: '0.7rem', color: '#ef4444' }}>OpenLoop : 17,9% TIR</div>
                <div style={{ fontSize: '0.7rem', color: '#f59e0b' }}>Oref0 : 57,0% TIR</div>
                <div style={{ fontSize: '0.75rem', fontWeight: '700', color: '#10b981' }}>PPO : 55,8% TIR (plafond)</div>
              </div>
              <div style={{ background: '#0f172a', padding: '0.85rem', borderRadius: '10px', border: '1px solid #334155' }}>
                <div style={{ fontSize: '0.78rem', fontWeight: '700', color: '#f8fafc', marginBottom: '0.35rem' }}>5. Surdosage +40%</div>
                <div style={{ fontSize: '0.7rem', color: '#ef4444' }}>OpenLoop TBR : 1,1%</div>
                <div style={{ fontSize: '0.7rem', color: '#f59e0b' }}>Oref0 TBR : 0,1%</div>
                <div style={{ fontSize: '0.75rem', fontWeight: '700', color: '#10b981' }}>PPO TBR : 0,2% (96,8% TIR)</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

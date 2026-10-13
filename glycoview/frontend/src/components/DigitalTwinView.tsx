import { useEffect, useState, useMemo, useCallback } from 'react';
import ReactECharts from 'echarts-for-react';
import {
  Cpu, Play, Sliders, ShieldAlert, Award, Calendar, Utensils,
  TrendingUp, TrendingDown, Target, AlertTriangle, CheckCircle2,
  Activity, Zap, Heart, Clock, BarChart3, Gauge,
  Flame, Droplets, Beaker, RefreshCw, Info, Plus, Trash2, CalendarDays, FileText
} from 'lucide-react';
import { API_BASE_URL } from '../config';

/* ─────────────────────── Interfaces ─────────────────────── */

export interface PlannedMeal {
  id: string;
  time: string;
  label: string;
  carbs: number;
  bolus: number;
  speed: 'fast' | 'normal' | 'slow';
}

export interface PlannedDayResult {
  status: string;
  summary: {
    tir: number;
    tbr: number;
    tar: number;
    mean_sgv: number;
    min_sgv: number;
    max_sgv: number;
    total_bolus: number;
    total_carbs: number;
    max_iob?: number;
    max_cob?: number;
  };
  timeline: {
    datetime: string;
    step: number;
    hour_str: string;
    simulated_sgv: number;
    p10: number;
    p90: number;
    bolus: number;
    carbs: number;
    iob?: number;
    cob?: number;
  }[];
}

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
  delta_from_baseline?: number;
  is_event_point?: boolean;
  iob?: number;
  cob?: number;
  real_iob?: number;
  real_cob?: number;
  simulated_iob?: number;
  simulated_cob?: number;
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

/* ─────────────────────── Styles ─────────────────────── */

const glassCard: React.CSSProperties = {
  background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.95) 100%)',
  backdropFilter: 'blur(20px)',
  border: '1px solid rgba(148, 163, 184, 0.12)',
  borderRadius: '16px',
  padding: '1.5rem',
  boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.05)',
  transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
  position: 'relative' as const,
  overflow: 'hidden',
};

const glassCardHover = {
  ...glassCard,
  border: '1px solid rgba(148, 163, 184, 0.2)',
  boxShadow: '0 12px 40px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.08)',
};

const shimmerKeyframes = `
@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 0 0 rgba(99, 102, 241, 0.4); }
  50% { box-shadow: 0 0 20px 4px rgba(99, 102, 241, 0.15); }
}
@keyframes spin-slow {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
@keyframes gradient-shift {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
`;

/* ─────────────────────── Sub-Components ─────────────────────── */

function MetricGauge({ label, value, unit, color, icon: Icon, subtitle, maxValue = 100 }: {
  label: string; value: number; unit: string; color: string; icon: any;
  subtitle?: string; maxValue?: number;
}) {
  const percentage = Math.min((value / maxValue) * 100, 100);
  const circumference = 2 * Math.PI * 38;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  return (
    <div style={{
      ...glassCard,
      padding: '1.25rem',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: '0.5rem',
      animation: 'fadeInUp 0.5s ease-out both',
    }}>
      <div style={{ position: 'relative', width: '90px', height: '90px' }}>
        <svg width="90" height="90" viewBox="0 0 90 90" style={{ transform: 'rotate(-90deg)' }}>
          <circle cx="45" cy="45" r="38" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
          <circle
            cx="45" cy="45" r="38" fill="none"
            stroke={color} strokeWidth="6" strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            style={{ transition: 'stroke-dashoffset 1.5s cubic-bezier(0.4, 0, 0.2, 1)' }}
          />
        </svg>
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon style={{ width: '22px', height: '22px', color, opacity: 0.9 }} />
        </div>
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: '1.5rem', fontWeight: '700', color, lineHeight: 1.1 }}>
          {value}<span style={{ fontSize: '0.7rem', fontWeight: '400', opacity: 0.8, marginLeft: '2px' }}>{unit}</span>
        </div>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '2px', lineHeight: 1.2 }}>{label}</div>
        {subtitle && (
          <div style={{ fontSize: '0.65rem', color: 'rgba(148, 163, 184, 0.6)', marginTop: '1px' }}>{subtitle}</div>
        )}
      </div>
    </div>
  );
}

function AnimatedTab({ active, onClick, icon: Icon, label, accentColor }: {
  active: boolean; onClick: () => void; icon: any; label: string; accentColor: string;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        position: 'relative',
        background: active
          ? `linear-gradient(135deg, ${accentColor}22, ${accentColor}11)`
          : 'transparent',
        color: active ? '#f8fafc' : 'var(--text-secondary)',
        border: active ? `1px solid ${accentColor}55` : '1px solid transparent',
        borderRadius: '12px',
        padding: '0.65rem 1.15rem',
        fontSize: '0.85rem',
        fontWeight: active ? '600' : '500',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        backdropFilter: active ? 'blur(8px)' : 'none',
        overflow: 'hidden',
      }}
      onMouseEnter={e => {
        if (!active) e.currentTarget.style.background = 'rgba(255,255,255,0.04)';
      }}
      onMouseLeave={e => {
        if (!active) e.currentTarget.style.background = 'transparent';
      }}
    >
      <Icon style={{
        width: '16px', height: '16px',
        color: active ? accentColor : 'var(--text-secondary)',
        transition: 'color 0.3s ease'
      }} />
      {label}
      {active && (
        <div style={{
          position: 'absolute', bottom: 0, left: '15%', right: '15%', height: '2px',
          background: `linear-gradient(90deg, transparent, ${accentColor}, transparent)`,
          borderRadius: '1px',
        }} />
      )}
    </button>
  );
}

function StatusBadge({ status, type }: { status: string; type: 'success' | 'warning' | 'danger' | 'info' }) {
  const colors = {
    success: { bg: 'rgba(16, 185, 129, 0.12)', text: '#34d399', border: 'rgba(16, 185, 129, 0.3)' },
    warning: { bg: 'rgba(245, 158, 11, 0.12)', text: '#fbbf24', border: 'rgba(245, 158, 11, 0.3)' },
    danger: { bg: 'rgba(239, 68, 68, 0.12)', text: '#f87171', border: 'rgba(239, 68, 68, 0.3)' },
    info: { bg: 'rgba(99, 102, 241, 0.12)', text: '#818cf8', border: 'rgba(99, 102, 241, 0.3)' },
  };
  const c = colors[type];
  return (
    <span style={{
      background: c.bg, color: c.text, border: `1px solid ${c.border}`,
      padding: '0.2rem 0.65rem', borderRadius: '20px', fontSize: '0.72rem', fontWeight: '600',
      display: 'inline-flex', alignItems: 'center', gap: '0.3rem',
    }}>
      {type === 'success' && <CheckCircle2 style={{ width: '11px', height: '11px' }} />}
      {type === 'warning' && <AlertTriangle style={{ width: '11px', height: '11px' }} />}
      {type === 'danger' && <AlertTriangle style={{ width: '11px', height: '11px' }} />}
      {type === 'info' && <Info style={{ width: '11px', height: '11px' }} />}
      {status}
    </span>
  );
}

function LoadingSpinner({ message }: { message: string }) {
  return (
    <div style={{
      height: '380px', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', gap: '1rem',
    }}>
      <div style={{ position: 'relative', width: '48px', height: '48px' }}>
        <div style={{
          position: 'absolute', inset: 0,
          border: '3px solid rgba(99, 102, 241, 0.15)',
          borderTopColor: '#6366f1',
          borderRadius: '50%',
          animation: 'spin-slow 1s linear infinite',
        }} />
        <div style={{
          position: 'absolute', inset: '6px',
          border: '3px solid rgba(168, 85, 247, 0.15)',
          borderBottomColor: '#a855f7',
          borderRadius: '50%',
          animation: 'spin-slow 1.5s linear infinite reverse',
        }} />
      </div>
      <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', fontWeight: '500' }}>
        {message}
      </div>
    </div>
  );
}

/* ─────────────────────── Main Component ─────────────────────── */

export default function DigitalTwinView() {
  const [activeTab, setActiveTab] = useState<'replay' | 'planned' | 'scenario' | 'settings' | 'meals' | 'protocol'>('planned');
  const [selectedDate, setSelectedDate] = useState<string>('');
  const [availableDays, setAvailableDays] = useState<{ date: string }[]>([]);
  
  // Planned Day Simulation State (Programmer une journée)
  const [plannedStartSgv, setPlannedStartSgv] = useState<number>(110);
  const [plannedBasalRate, setPlannedBasalRate] = useState<number>(0.85);
  const [plannedStress, setPlannedStress] = useState<number>(1.0);
  const [plannedMeals, setPlannedMeals] = useState<PlannedMeal[]>([
    { id: '1', time: '07:30', label: 'Petit-déjeuner', carbs: 45, bolus: 5.0, speed: 'normal' },
    { id: '2', time: '12:30', label: 'Déjeuner', carbs: 65, bolus: 6.5, speed: 'normal' },
    { id: '3', time: '19:30', label: 'Dîner', carbs: 55, bolus: 6.0, speed: 'normal' },
  ]);
  const [plannedResult, setPlannedResult] = useState<PlannedDayResult | null>(null);
  const [loadingPlanned, setLoadingPlanned] = useState<boolean>(false);

  // Clinical Research Protocol Benchmark State (Hôpital Militaire Oued Eddahab)
  const [protocolData, setProtocolData] = useState<any>(null);
  const [loadingProtocol, setLoadingProtocol] = useState<boolean>(false);

  // Day Replay State
  const [replayData, setReplayData] = useState<ReplayData | null>(null);
  const [loadingReplay, setLoadingReplay] = useState<boolean>(true);

  // What-If Scenario State
  const [eventTimeStr, setEventTimeStr] = useState<string>('12:00');
  const [bolusDelta, setBolusDelta] = useState<number>(0.0);
  const [carbsDelta, setCarbsDelta] = useState<number>(0.0);
  const [carbSpeed, setCarbSpeed] = useState<string>('normal');
  const [basalMult, setBasalMult] = useState<number>(1.0);
  const [isfOverride, setIsfOverride] = useState<string>('');
  const [stressFactor, setStressFactor] = useState<number>(1.0);
  const [scenarioResult, setScenarioResult] = useState<any>(null);
  const [loadingScenario, setLoadingScenario] = useState<boolean>(false);

  // Settings Analysis & Meal Library State
  const [settingsData, setSettingsData] = useState<any>(null);
  const [mealsData, setMealsData] = useState<any>(null);
  const [loadingSettings, setLoadingSettings] = useState<boolean>(false);
  const [loadingMeals, setLoadingMeals] = useState<boolean>(false);

  // Hover States
  const [hoveredCard, setHoveredCard] = useState<number | null>(null);
  const [hoveredMeal, setHoveredMeal] = useState<number | null>(null);

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

  // Clinical Research Protocol Benchmark (AAPS-DT Pilot v1.0)
  const handleRunProtocolBenchmark = useCallback(() => {
    setLoadingProtocol(true);
    fetch(`${API_BASE_URL}/api/v1/twin/protocol-benchmark`)
      .then(res => res.json())
      .then(data => {
        setProtocolData(data);
        setLoadingProtocol(false);
      })
      .catch(() => setLoadingProtocol(false));
  }, []);

  useEffect(() => {
    if (activeTab === 'protocol' && !protocolData && !loadingProtocol) {
      handleRunProtocolBenchmark();
    }
  }, [activeTab, protocolData, loadingProtocol, handleRunProtocolBenchmark]);

  // Run Planned Day Simulation
  const handleRunPlannedDay = useCallback(() => {
    setLoadingPlanned(true);
    fetch(`${API_BASE_URL}/api/v1/twin/simulate-planned-day`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        start_sgv: plannedStartSgv,
        basal_rate: plannedBasalRate,
        stress_factor: plannedStress,
        meals: plannedMeals.map(m => ({
          time: m.time,
          label: m.label,
          carbs: m.carbs,
          bolus: m.bolus,
          speed: m.speed,
        }))
      })
    })
      .then(res => res.json())
      .then(data => {
        setPlannedResult(data);
        setLoadingPlanned(false);
      })
      .catch(() => setLoadingPlanned(false));
  }, [plannedStartSgv, plannedBasalRate, plannedStress, plannedMeals]);

  // Auto-run planned simulation on tab switch if not yet loaded
  useEffect(() => {
    if (activeTab === 'planned' && !plannedResult) {
      handleRunPlannedDay();
    }
  }, [activeTab, plannedResult, handleRunPlannedDay]);

  // Run scenario simulation
  const handleRunScenario = useCallback(() => {
    setLoadingScenario(true);
    fetch(`${API_BASE_URL}/api/v1/twin/simulate-scenario`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_date: selectedDate,
        event_time_str: eventTimeStr,
        bolus_delta_u: bolusDelta,
        carbs_delta_g: carbsDelta,
        carb_speed: carbSpeed,
        isf_override: isfOverride ? parseFloat(isfOverride) : null,
        basal_multiplier: basalMult,
        stress_activity_factor: stressFactor
      })
    })
      .then(res => res.json())
      .then(data => {
        setScenarioResult(data);
        setLoadingScenario(false);
      })
      .catch(() => setLoadingScenario(false));
  }, [selectedDate, eventTimeStr, bolusDelta, carbsDelta, carbSpeed, basalMult, isfOverride, stressFactor]);

  /* ─────────────────────── ECharts: Replay Chart ─────────────────────── */
  const replayChartOption = useMemo(() => {
    if (!replayData || !replayData.timeline) return {};

    const times = replayData.timeline.map(pt => new Date(pt.datetime).getTime());
    const realSeries = replayData.timeline.map((pt, i) => [times[i], pt.real_sgv]);
    const simSeries = replayData.timeline.map((pt, i) => [times[i], pt.simulated_sgv]);
    const p10Series = replayData.timeline.map((pt, i) => [times[i], pt.p10]);
    const p90Series = replayData.timeline.map((pt, i) => [times[i], pt.p90]);
    const simIobSeries = replayData.timeline.map((pt, i) => [times[i], pt.simulated_iob ?? 0]);
    const simCobSeries = replayData.timeline.map((pt, i) => [times[i], pt.simulated_cob ?? 0]);

    // Build bolus markers
    const bolusMarkers = replayData.timeline
      .filter(pt => (pt.bolus ?? 0) > 0.1)
      .map(pt => ({
        coord: [new Date(pt.datetime).getTime(), pt.real_sgv ?? pt.simulated_sgv],
        value: pt.bolus,
        symbol: 'triangle',
        symbolSize: Math.min(8 + (pt.bolus ?? 0) * 3, 20),
        itemStyle: { color: '#38bdf8' },
        label: {
          show: true,
          formatter: `${pt.bolus}U`,
          position: 'bottom',
          fontSize: 9,
          color: '#38bdf8',
          fontWeight: 'bold' as const,
        }
      }));

    // Build carb markers
    const carbMarkers = replayData.timeline
      .filter(pt => (pt.carbs ?? 0) > 2)
      .map(pt => ({
        coord: [new Date(pt.datetime).getTime(), pt.real_sgv ?? pt.simulated_sgv],
        value: pt.carbs,
        symbol: 'circle',
        symbolSize: Math.min(8 + (pt.carbs ?? 0) * 0.3, 22),
        itemStyle: { color: '#fbbf24' },
        label: {
          show: true,
          formatter: `${pt.carbs}g`,
          position: 'top',
          fontSize: 9,
          color: '#fbbf24',
          fontWeight: 'bold' as const,
        }
      }));

    return {
      backgroundColor: 'transparent',
      animation: true,
      animationDuration: 1500,
      animationEasing: 'cubicOut',
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: 'rgba(99, 102, 241, 0.3)',
        borderRadius: 12,
        padding: [12, 16],
        textStyle: { fontSize: 12, color: '#f8fafc' },
        formatter: (params: any) => {
          if (!params || params.length === 0) return '';
          const dtStr = new Date(params[0].value[0]).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
          let html = `<div style="font-weight:700;margin-bottom:8px;color:#e2e8f0;font-size:13px">${dtStr}</div>`;
          params.forEach((p: any) => {
            if (p.value[1] !== null && p.value[1] !== undefined && p.seriesName !== 'Borne p10' && p.seriesName !== 'Bande d\'Incertitude' && p.seriesName !== 'Zone Cible') {
              const isIob = p.seriesName.includes('IOB');
              const isCob = p.seriesName.includes('COB');
              const unit = isIob ? ' U' : isCob ? ' g' : ' mg/dL';
              const valStr = isIob ? Number(p.value[1]).toFixed(2) : isCob ? Number(p.value[1]).toFixed(1) : Math.round(p.value[1]);
              html += `<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin:3px 0">
                <div style="display:flex;align-items:center;gap:6px">
                  <span style="width:8px;height:8px;border-radius:50%;background:${p.color};display:inline-block"></span>
                  <span style="color:#94a3b8;font-size:12px">${p.seriesName}:</span>
                </div>
                <span style="color:#f8fafc;font-weight:600;font-size:12px">${valStr}${unit}</span>
              </div>`;
            }
          });
          return html;
        }
      },
      legend: {
        data: ['Glycémie Réelle', 'Simulation Jumeau', 'IOB Jumeau (U)', 'COB Jumeau (g)'],
        top: 0,
        textStyle: { color: '#94a3b8', fontSize: 11 },
        itemGap: 16,
        icon: 'roundRect',
        itemWidth: 14,
        itemHeight: 3,
      },
      grid: { left: '3%', right: '4%', bottom: '12%', top: '12%', containLabel: true },
      dataZoom: [{
        type: 'inside',
        start: 0,
        end: 100,
      }, {
        type: 'slider',
        height: 24,
        bottom: 4,
        borderColor: 'transparent',
        backgroundColor: 'rgba(255,255,255,0.03)',
        fillerColor: 'rgba(99, 102, 241, 0.15)',
        handleStyle: { color: '#6366f1', borderColor: '#6366f1' },
        textStyle: { color: '#64748b', fontSize: 10 },
        dataBackground: {
          lineStyle: { color: 'rgba(99, 102, 241, 0.3)' },
          areaStyle: { color: 'rgba(99, 102, 241, 0.08)' },
        },
      }],
      xAxis: {
        type: 'time',
        axisLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.15)' } },
        axisLabel: { color: '#64748b', fontSize: 10, formatter: '{HH}:{mm}' },
        splitLine: { show: true, lineStyle: { color: 'rgba(148, 163, 184, 0.06)' } },
      },
      yAxis: [
        {
          type: 'value',
          min: 40,
          max: 320,
          axisLine: { show: false },
          axisLabel: { color: '#64748b', fontSize: 10 },
          splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.06)', type: 'dashed' } },
        },
        {
          type: 'value',
          name: 'IOB (U) / COB (g)',
          position: 'right',
          min: 0,
          max: (value: any) => Math.max(8, Math.ceil(value.max * 1.15)),
          axisLine: { show: false },
          axisLabel: { color: '#94a3b8', fontSize: 10, formatter: '{value}' },
          splitLine: { show: false },
        }
      ],
      series: [
        // Target Zone (70-180)
        {
          name: 'Zone Cible',
          type: 'line',
          data: [],
          markArea: {
            silent: true,
            data: [[{ yAxis: 70 }, { yAxis: 180 }]],
            itemStyle: { color: 'rgba(16, 185, 129, 0.06)' },
          },
          markLine: {
            silent: true,
            symbol: 'none',
            lineStyle: { color: 'rgba(239, 68, 68, 0.3)', type: 'dashed', width: 1 },
            data: [
              { yAxis: 70, label: { formatter: '70', position: 'insideEndTop', color: '#f87171', fontSize: 9 } },
              { yAxis: 180, label: { formatter: '180', position: 'insideEndTop', color: '#fbbf24', fontSize: 9 } },
            ]
          }
        },
        // Real glucose line
        {
          name: 'Glycémie Réelle',
          type: 'line',
          smooth: 0.4,
          showSymbol: false,
          data: realSeries,
          itemStyle: { color: '#3b82f6' },
          lineStyle: {
            width: 3,
            shadowColor: 'rgba(59, 130, 246, 0.3)',
            shadowBlur: 8,
            shadowOffsetY: 4,
          },
          markPoint: {
            data: [...bolusMarkers, ...carbMarkers],
            animation: true,
          }
        },
        // p10 bound
        {
          name: 'Borne p10',
          type: 'line',
          smooth: 0.4,
          showSymbol: false,
          data: p10Series,
          lineStyle: { opacity: 0 },
          stack: 'twin-band',
          symbol: 'none',
        },
        // Uncertainty band p10-p90
        {
          name: 'Bande d\'Incertitude',
          type: 'line',
          smooth: 0.4,
          showSymbol: false,
          data: p90Series.map((pt, i) => [pt[0], (pt[1] as number) - (p10Series[i][1] as number)]),
          lineStyle: { opacity: 0 },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(168, 85, 247, 0.20)' },
                { offset: 1, color: 'rgba(168, 85, 247, 0.04)' },
              ]
            }
          },
          stack: 'twin-band',
          symbol: 'none',
        },
        // Simulated glucose line
        {
          name: 'Simulation Jumeau',
          type: 'line',
          smooth: 0.4,
          showSymbol: false,
          data: simSeries,
          itemStyle: { color: '#a855f7' },
          lineStyle: {
            width: 2.5,
            type: [8, 4],
            shadowColor: 'rgba(168, 85, 247, 0.25)',
            shadowBlur: 6,
          },
        },
        // Simulated IOB line
        {
          name: 'IOB Jumeau (U)',
          type: 'line',
          yAxisIndex: 1,
          smooth: 0.35,
          showSymbol: false,
          data: simIobSeries,
          itemStyle: { color: '#38bdf8' },
          lineStyle: { width: 2, type: 'dashed' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(56, 189, 248, 0.15)' },
                { offset: 1, color: 'rgba(56, 189, 248, 0.01)' }
              ]
            }
          }
        },
        // Simulated COB line
        {
          name: 'COB Jumeau (g)',
          type: 'line',
          yAxisIndex: 1,
          smooth: 0.35,
          showSymbol: false,
          data: simCobSeries,
          itemStyle: { color: '#fbbf24' },
          lineStyle: { width: 2, type: 'dotted' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(251, 191, 36, 0.15)' },
                { offset: 1, color: 'rgba(251, 191, 36, 0.01)' }
              ]
            }
          }
        }
      ]
    };
  }, [replayData]);

  /* ─────────────────────── ECharts: Scenario Chart ─────────────────────── */
  const scenarioChartOption = useMemo(() => {
    if (!scenarioResult || !scenarioResult.timeline) return {};

    const times = scenarioResult.timeline.map((pt: any) => new Date(pt.datetime).getTime());
    const realSeries = scenarioResult.timeline.map((pt: any, i: number) => [times[i], pt.real_sgv]);
    const baseSimSeries = scenarioResult.timeline.map((pt: any, i: number) => [times[i], pt.baseline_sim_sgv]);
    const scenarioSimSeries = scenarioResult.timeline.map((pt: any, i: number) => [times[i], pt.scenario_sim_sgv]);
    const iobSeries = scenarioResult.timeline.map((pt: any, i: number) => [times[i], pt.simulated_iob ?? 0]);
    const cobSeries = scenarioResult.timeline.map((pt: any, i: number) => [times[i], pt.simulated_cob ?? 0]);

    // Event marker
    const eventPoint = scenarioResult.timeline.find((pt: any) => pt.is_event_point);

    return {
      backgroundColor: 'transparent',
      animation: true,
      animationDuration: 1200,
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: 'rgba(16, 185, 129, 0.3)',
        borderRadius: 12,
        padding: [12, 16],
        textStyle: { fontSize: 12, color: '#f8fafc' },
        formatter: (params: any) => {
          if (!params || params.length === 0) return '';
          const dtStr = new Date(params[0].value[0]).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
          let html = `<div style="font-weight:700;margin-bottom:8px;color:#e2e8f0;font-size:13px">⏱ ${dtStr}</div>`;
          params.forEach((p: any) => {
            if (p.value[1] !== null && p.value[1] !== undefined && p.seriesName !== 'Zone Cible') {
              const isIob = p.seriesName.includes('IOB');
              const isCob = p.seriesName.includes('COB');
              const unit = isIob ? ' U' : isCob ? ' g' : ' mg/dL';
              const valStr = isIob ? Number(p.value[1]).toFixed(2) : isCob ? Number(p.value[1]).toFixed(1) : Math.round(p.value[1]);
              html += `<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin:3px 0">
                <div style="display:flex;align-items:center;gap:6px">
                  <span style="width:8px;height:8px;border-radius:50%;background:${p.color};display:inline-block"></span>
                  <span style="color:#94a3b8;font-size:12px">${p.seriesName}:</span>
                </div>
                <span style="color:#f8fafc;font-weight:600;font-size:12px">${valStr}${unit}</span>
              </div>`;
            }
          });
          // Show delta if scenario series exists
          const baseVal = params.find((p: any) => p.seriesName === 'Simulation de Base')?.value?.[1];
          const scenVal = params.find((p: any) => p.seriesName === 'Scénario Modifié')?.value?.[1];
          if (baseVal != null && scenVal != null) {
            const delta = Math.round(scenVal - baseVal);
            const color = delta > 0 ? '#fbbf24' : delta < 0 ? '#38bdf8' : '#10b981';
            html += `<div style="margin-top:6px;padding-top:6px;border-top:1px solid rgba(255,255,255,0.1);color:${color};font-weight:600;font-size:12px">
              Δ Impact : ${delta > 0 ? '+' : ''}${delta} mg/dL
            </div>`;
          }
          return html;
        }
      },
      legend: {
        data: ['Glycémie Réelle', 'Simulation de Base', 'Scénario Modifié', 'IOB Ajouté (U)', 'COB Ajouté (g)'],
        top: 0,
        textStyle: { color: '#94a3b8', fontSize: 11 },
        itemGap: 16,
        icon: 'roundRect',
        itemWidth: 14,
        itemHeight: 3,
      },
      grid: { left: '3%', right: '4%', bottom: '12%', top: '12%', containLabel: true },
      dataZoom: [{
        type: 'inside',
        start: 0,
        end: 100,
      }, {
        type: 'slider',
        height: 24,
        bottom: 4,
        borderColor: 'transparent',
        backgroundColor: 'rgba(255,255,255,0.03)',
        fillerColor: 'rgba(16, 185, 129, 0.15)',
        handleStyle: { color: '#10b981', borderColor: '#10b981' },
        textStyle: { color: '#64748b', fontSize: 10 },
      }],
      xAxis: {
        type: 'time',
        axisLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.15)' } },
        axisLabel: { color: '#64748b', fontSize: 10, formatter: '{HH}:{mm}' },
        splitLine: { show: true, lineStyle: { color: 'rgba(148, 163, 184, 0.06)' } },
      },
      yAxis: [
        {
          type: 'value',
          min: 40,
          max: 320,
          axisLine: { show: false },
          axisLabel: { color: '#64748b', fontSize: 10 },
          splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.06)', type: 'dashed' } },
        },
        {
          type: 'value',
          name: 'IOB (U) / COB (g)',
          position: 'right',
          min: 0,
          max: (value: any) => Math.max(6, Math.ceil(value.max * 1.15)),
          axisLine: { show: false },
          axisLabel: { color: '#94a3b8', fontSize: 10, formatter: '{value}' },
          splitLine: { show: false },
        }
      ],
      series: [
        // Target Zone
        {
          name: 'Zone Cible',
          type: 'line',
          data: [],
          markArea: {
            silent: true,
            data: [[{ yAxis: 70 }, { yAxis: 180 }]],
            itemStyle: { color: 'rgba(16, 185, 129, 0.06)' },
          },
        },
        // Real SGV
        {
          name: 'Glycémie Réelle',
          type: 'line',
          smooth: 0.4,
          showSymbol: false,
          data: realSeries,
          itemStyle: { color: '#3b82f6' },
          lineStyle: { width: 2 },
        },
        // Baseline simulation
        {
          name: 'Simulation de Base',
          type: 'line',
          smooth: 0.4,
          showSymbol: false,
          data: baseSimSeries,
          itemStyle: { color: '#a855f7' },
          lineStyle: { width: 2, type: [8, 4] },
        },
        // Scenario modified
        {
          name: 'Scénario Modifié',
          type: 'line',
          smooth: 0.4,
          showSymbol: false,
          data: scenarioSimSeries,
          itemStyle: { color: '#10b981' },
          lineStyle: {
            width: 3.5,
            shadowColor: 'rgba(16, 185, 129, 0.4)',
            shadowBlur: 10,
            shadowOffsetY: 3,
          },
          markPoint: eventPoint ? {
            data: [{
              coord: [new Date(eventPoint.datetime).getTime(), eventPoint.scenario_sim_sgv],
              symbol: 'pin',
              symbolSize: 36,
              itemStyle: { color: '#f59e0b' },
              label: { show: true, formatter: '⚡', fontSize: 14 }
            }]
          } : undefined,
        },
        // Simulated IOB line
        {
          name: 'IOB Ajouté (U)',
          type: 'line',
          yAxisIndex: 1,
          smooth: 0.35,
          showSymbol: false,
          data: iobSeries,
          itemStyle: { color: '#38bdf8' },
          lineStyle: { width: 2, type: 'dashed' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(56, 189, 248, 0.15)' },
                { offset: 1, color: 'rgba(56, 189, 248, 0.01)' }
              ]
            }
          }
        },
        // Simulated COB line
        {
          name: 'COB Ajouté (g)',
          type: 'line',
          yAxisIndex: 1,
          smooth: 0.35,
          showSymbol: false,
          data: cobSeries,
          itemStyle: { color: '#fbbf24' },
          lineStyle: { width: 2, type: 'dotted' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(251, 191, 36, 0.15)' },
                { offset: 1, color: 'rgba(251, 191, 36, 0.01)' }
              ]
            }
          }
        }
      ]
    };
  }, [scenarioResult]);

  /* ─────────────────────── ECharts: Planned Day Chart ─────────────────────── */
  const plannedChartOption = useMemo(() => {
    if (!plannedResult || !plannedResult.timeline) return {};

    const times = plannedResult.timeline.map(pt => new Date(pt.datetime).getTime());
    const simSeries = plannedResult.timeline.map((pt, i) => [times[i], pt.simulated_sgv]);
    const p10Series = plannedResult.timeline.map((pt, i) => [times[i], pt.p10]);
    const p90Series = plannedResult.timeline.map((pt, i) => [times[i], pt.p90]);
    const iobSeries = plannedResult.timeline.map((pt, i) => [times[i], pt.iob ?? 0]);
    const cobSeries = plannedResult.timeline.map((pt, i) => [times[i], pt.cob ?? 0]);

    // Bolus Markers
    const bolusMarkers = plannedResult.timeline
      .filter(pt => (pt.bolus ?? 0) > 0.05)
      .map(pt => ({
        coord: [new Date(pt.datetime).getTime(), pt.simulated_sgv],
        value: pt.bolus,
        symbol: 'triangle',
        symbolSize: Math.min(10 + (pt.bolus ?? 0) * 2.5, 24),
        itemStyle: { color: '#38bdf8' },
        label: {
          show: true,
          formatter: `${pt.bolus}U`,
          position: 'bottom',
          fontSize: 10,
          color: '#38bdf8',
          fontWeight: 'bold' as const,
        }
      }));

    // Carb Markers
    const carbMarkers = plannedResult.timeline
      .filter(pt => (pt.carbs ?? 0) > 2)
      .map(pt => ({
        coord: [new Date(pt.datetime).getTime(), pt.simulated_sgv],
        value: pt.carbs,
        symbol: 'circle',
        symbolSize: Math.min(10 + (pt.carbs ?? 0) * 0.25, 24),
        itemStyle: { color: '#fbbf24' },
        label: {
          show: true,
          formatter: `${pt.carbs}g`,
          position: 'top',
          fontSize: 10,
          color: '#fbbf24',
          fontWeight: 'bold' as const,
        }
      }));

    return {
      backgroundColor: 'transparent',
      animation: true,
      animationDuration: 1200,
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: 'rgba(99, 102, 241, 0.3)',
        borderRadius: 12,
        padding: [12, 16],
        textStyle: { fontSize: 12, color: '#f8fafc' },
        formatter: (params: any) => {
          if (!params || params.length === 0) return '';
          const date = new Date(params[0].value[0]);
          const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
          let html = `<div style="font-weight:700;margin-bottom:6px;color:#a5b4fc">${timeStr}</div>`;
          const sgvVal = params.find((p: any) => p.seriesName === 'Glycémie Simulée')?.value?.[1];
          if (sgvVal != null) {
            const color = sgvVal < 70 ? '#f87171' : sgvVal > 180 ? '#fbbf24' : '#34d399';
            html += `<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin:3px 0">
              <span style="color:#94a3b8">Glycémie Prévue:</span>
              <span style="color:${color};font-weight:700;font-size:14px">${Math.round(sgvVal)} mg/dL</span>
            </div>`;
          }
          const iobVal = params.find((p: any) => p.seriesName === 'IOB Actif (U)')?.value?.[1];
          const cobVal = params.find((p: any) => p.seriesName === 'COB Actif (g)')?.value?.[1];
          if (iobVal != null && iobVal > 0.02) {
            html += `<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin:2px 0">
              <span style="color:#38bdf8;font-size:12px">💉 IOB Actif:</span>
              <span style="color:#38bdf8;font-weight:600;font-size:12px">${Number(iobVal).toFixed(2)} U</span>
            </div>`;
          }
          if (cobVal != null && cobVal > 0.2) {
            html += `<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin:2px 0">
              <span style="color:#fbbf24;font-size:12px">🍞 COB Actif:</span>
              <span style="color:#fbbf24;font-weight:600;font-size:12px">${Number(cobVal).toFixed(1)} g</span>
            </div>`;
          }
          return html;
        }
      },
      legend: {
        data: ['Zone Cible (70-180)', 'Bande Incertitude (p10-p90)', 'Glycémie Simulée', 'IOB Actif (U)', 'COB Actif (g)'],
        top: 0,
        textStyle: { color: '#94a3b8', fontSize: 11 },
        itemGap: 16,
        icon: 'roundRect',
        itemWidth: 14,
        itemHeight: 3,
      },
      grid: { left: '3%', right: '4%', bottom: '12%', top: '14%', containLabel: true },
      dataZoom: [{
        type: 'inside', start: 0, end: 100,
      }, {
        type: 'slider',
        height: 24,
        bottom: 4,
        borderColor: 'transparent',
        backgroundColor: 'rgba(255,255,255,0.03)',
        fillerColor: 'rgba(99, 102, 241, 0.15)',
        handleStyle: { color: '#6366f1', borderColor: '#6366f1' },
        textStyle: { color: '#64748b', fontSize: 10 },
      }],
      xAxis: {
        type: 'time',
        axisLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.15)' } },
        axisLabel: { color: '#64748b', fontSize: 10, formatter: '{HH}:{mm}' },
        splitLine: { show: true, lineStyle: { color: 'rgba(148, 163, 184, 0.06)' } },
      },
      yAxis: [
        {
          type: 'value',
          min: 40,
          max: 300,
          axisLine: { show: false },
          axisLabel: { color: '#64748b', fontSize: 10 },
          splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.06)', type: 'dashed' } },
        },
        {
          type: 'value',
          name: 'IOB (U) / COB (g)',
          position: 'right',
          min: 0,
          max: (value: any) => Math.max(10, Math.ceil(value.max * 1.15)),
          axisLine: { show: false },
          axisLabel: { color: '#94a3b8', fontSize: 10, formatter: '{value}' },
          splitLine: { show: false },
        }
      ],
      series: [
        {
          name: 'Zone Cible (70-180)',
          type: 'line',
          data: [],
          markArea: {
            silent: true,
            data: [[{ yAxis: 70 }, { yAxis: 180 }]],
            itemStyle: { color: 'rgba(16, 185, 129, 0.06)' },
          },
        },
        {
          name: 'Bande Incertitude (p10-p90)',
          type: 'line',
          data: p90Series,
          lineStyle: { opacity: 0 },
          stack: 'confidence-band',
          symbol: 'none',
        },
        {
          name: 'Bande Incertitude (p10-p90)',
          type: 'line',
          data: p10Series.map((pt, i) => [pt[0], (p90Series[i][1] as number) - (pt[1] as number)]),
          lineStyle: { opacity: 0 },
          areaStyle: {
            color: 'rgba(99, 102, 241, 0.12)',
          },
          stack: 'confidence-band',
          symbol: 'none',
        },
        {
          name: 'Glycémie Simulée',
          type: 'line',
          smooth: 0.35,
          showSymbol: false,
          data: simSeries,
          itemStyle: { color: '#818cf8' },
          lineStyle: {
            width: 3.5,
            color: '#818cf8',
            shadowColor: 'rgba(129, 140, 248, 0.5)',
            shadowBlur: 10,
            shadowOffsetY: 2,
          },
          markPoint: {
            data: [...bolusMarkers, ...carbMarkers],
          },
        },
        {
          name: 'IOB Actif (U)',
          type: 'line',
          yAxisIndex: 1,
          smooth: 0.35,
          showSymbol: false,
          data: iobSeries,
          itemStyle: { color: '#38bdf8' },
          lineStyle: { width: 2, type: 'dashed' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(56, 189, 248, 0.20)' },
                { offset: 1, color: 'rgba(56, 189, 248, 0.01)' }
              ]
            }
          }
        },
        {
          name: 'COB Actif (g)',
          type: 'line',
          yAxisIndex: 1,
          smooth: 0.35,
          showSymbol: false,
          data: cobSeries,
          itemStyle: { color: '#fbbf24' },
          lineStyle: { width: 2 },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(251, 191, 36, 0.18)' },
                { offset: 1, color: 'rgba(251, 191, 36, 0.01)' }
              ]
            }
          }
        }
      ]
    };
  }, [plannedResult]);

  /* ─────────────────────── Render ─────────────────────── */
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <style>{shimmerKeyframes}</style>

      {/* ─── Disclaimer Banner ─── */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(168, 85, 247, 0.08) 50%, rgba(59, 130, 246, 0.08) 100%)',
        border: '1px solid rgba(99, 102, 241, 0.2)',
        borderRadius: '14px',
        padding: '1rem 1.5rem',
        display: 'flex',
        alignItems: 'center',
        gap: '1rem',
        animation: 'pulse-glow 3s ease-in-out infinite',
        position: 'relative',
        overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
          background: 'linear-gradient(90deg, transparent, rgba(99, 102, 241, 0.05), transparent)',
          animation: 'shimmer 3s infinite',
          pointerEvents: 'none',
        }} />
        <div style={{
          background: 'linear-gradient(135deg, #6366f1, #a855f7)',
          borderRadius: '10px',
          padding: '0.5rem',
          display: 'flex',
          flexShrink: 0,
        }}>
          <ShieldAlert style={{ width: '22px', height: '22px', color: '#fff' }} />
        </div>
        <div>
          <div style={{ fontWeight: '600', color: '#c7d2fe', fontSize: '0.9rem' }}>
            Garde-fou & Avertissement Clinique
          </div>
          <div style={{ color: '#94a3b8', fontSize: '0.8rem', marginTop: '2px', lineHeight: 1.5 }}>
            Simulation basée sur un modèle mathématique personnalisé avec incertitude. Outil exclusivement destiné à
            l'<strong style={{ color: '#a5b4fc' }}>ANALYSE</strong> et à la <strong style={{ color: '#a5b4fc' }}>SIMULATION</strong>.
            Ne pas utiliser pour décider d'une dose d'insuline. N'écrit rien dans AAPS ni Nightscout.
          </div>
        </div>
      </div>

      {/* ─── Tab Navigation ─── */}
      <div style={{
        display: 'flex',
        gap: '0.5rem',
        padding: '0.5rem',
        background: 'rgba(15, 23, 42, 0.5)',
        borderRadius: '14px',
        border: '1px solid rgba(148, 163, 184, 0.08)',
        flexWrap: 'wrap',
      }}>
        <AnimatedTab active={activeTab === 'planned'} onClick={() => setActiveTab('planned')}
          icon={CalendarDays} label="Programmer une Journée" accentColor="#818cf8" />
        <AnimatedTab active={activeTab === 'protocol'} onClick={() => setActiveTab('protocol')}
          icon={FileText} label="Protocole AAPS-DT (Hôpital Militaire)" accentColor="#38bdf8" />
        <AnimatedTab active={activeTab === 'replay'} onClick={() => setActiveTab('replay')}
          icon={Play} label="Rejeu de Journée" accentColor="#6366f1" />
        <AnimatedTab active={activeTab === 'scenario'} onClick={() => setActiveTab('scenario')}
          icon={Sliders} label="Scénarios « Et Si »" accentColor="#10b981" />
        <AnimatedTab active={activeTab === 'settings'} onClick={() => setActiveTab('settings')}
          icon={Award} label="Analyse des Réglages" accentColor="#f59e0b" />
        <AnimatedTab active={activeTab === 'meals'} onClick={() => setActiveTab('meals')}
          icon={Utensils} label="Bibliothèque de Repas" accentColor="#f43f5e" />
      </div>

      {/* ════════════════════ TAB 0: PROGRAMMER UNE JOURNÉE ════════════════════ */}
      {activeTab === 'planned' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', animation: 'fadeInUp 0.4s ease-out' }}>
          {/* Header */}
          <div style={{
            ...glassCard,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            flexWrap: 'wrap', gap: '1rem',
            padding: '1.25rem 1.5rem',
          }}>
            <div>
              <div style={{
                display: 'flex', alignItems: 'center', gap: '0.6rem',
                fontSize: '1.15rem', fontWeight: '700', color: '#e2e8f0',
              }}>
                <div style={{
                  background: 'linear-gradient(135deg, #818cf8, #c084fc)',
                  borderRadius: '8px', padding: '0.4rem', display: 'flex',
                }}>
                  <CalendarDays style={{ width: '18px', height: '18px', color: '#fff' }} />
                </div>
                Programmer une Journée Complète
              </div>
              <div style={{ color: '#64748b', fontSize: '0.82rem', marginTop: '0.3rem', marginLeft: '2.5rem' }}>
                Entrez vos repas (glucides), bolus et débit basal pour visualiser en direct la courbe glycémique 24h projetée par le Jumeau Numérique
              </div>
            </div>

            <button
              onClick={handleRunPlannedDay}
              disabled={loadingPlanned}
              style={{
                background: loadingPlanned
                  ? 'rgba(99, 102, 241, 0.3)'
                  : 'linear-gradient(135deg, #6366f1, #a855f7)',
                color: 'white',
                border: 'none',
                padding: '0.65rem 1.25rem',
                borderRadius: '10px',
                fontWeight: '700',
                cursor: loadingPlanned ? 'wait' : 'pointer',
                fontSize: '0.88rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                boxShadow: '0 4px 15px rgba(99, 102, 241, 0.3)',
                transition: 'all 0.3s ease',
              }}
            >
              {loadingPlanned ? (
                <RefreshCw style={{ width: '15px', height: '15px', animation: 'spin-slow 1s linear infinite' }} />
              ) : (
                <Play style={{ width: '15px', height: '15px' }} />
              )}
              {loadingPlanned ? 'Simulation en cours...' : 'Calculer la Simulation'}
            </button>
          </div>

          {/* Configuration: Paramètres de base (Glycémie initiale, Débit basal, Activité physique) */}
          <div style={{
            ...glassCard,
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '1.25rem',
            padding: '1.25rem',
          }}>
            {/* Glycémie initiale à 00:00 */}
            <div>
              <label style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <Activity style={{ width: '13px', height: '13px', color: '#818cf8' }} />Glycémie Initiale à 00h00
              </label>
              <div style={{ position: 'relative', marginTop: '0.35rem' }}>
                <input
                  type="number"
                  value={plannedStartSgv}
                  onChange={e => setPlannedStartSgv(parseFloat(e.target.value) || 100)}
                  style={{
                    width: '100%', background: 'rgba(15, 23, 42, 0.6)',
                    color: '#e2e8f0', border: '1px solid rgba(148, 163, 184, 0.15)',
                    padding: '0.55rem 0.75rem', borderRadius: '10px',
                    fontSize: '0.88rem', outline: 'none',
                  }}
                />
                <span style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', fontSize: '0.75rem', color: '#64748b' }}>mg/dL</span>
              </div>
            </div>

            {/* Débit Basal Programmé */}
            <div>
              <label style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <Gauge style={{ width: '13px', height: '13px', color: '#38bdf8' }} />Débit Basal Moyen
              </label>
              <div style={{ position: 'relative', marginTop: '0.35rem' }}>
                <input
                  type="number" step="0.05"
                  value={plannedBasalRate}
                  onChange={e => setPlannedBasalRate(parseFloat(e.target.value) || 0.85)}
                  style={{
                    width: '100%', background: 'rgba(15, 23, 42, 0.6)',
                    color: '#e2e8f0', border: '1px solid rgba(148, 163, 184, 0.15)',
                    padding: '0.55rem 0.75rem', borderRadius: '10px',
                    fontSize: '0.88rem', outline: 'none',
                  }}
                />
                <span style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', fontSize: '0.75rem', color: '#64748b' }}>U/h</span>
              </div>
            </div>

            {/* État de Stress / Exercice */}
            <div>
              <label style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <Heart style={{ width: '13px', height: '13px', color: '#f43f5e' }} />Activité / Stress
              </label>
              <select
                value={plannedStress}
                onChange={e => setPlannedStress(parseFloat(e.target.value))}
                style={{
                  width: '100%', background: 'rgba(15, 23, 42, 0.6)',
                  color: '#e2e8f0', border: '1px solid rgba(148, 163, 184, 0.15)',
                  padding: '0.55rem 0.75rem', borderRadius: '10px', marginTop: '0.35rem',
                  fontSize: '0.85rem', cursor: 'pointer', outline: 'none',
                }}
              >
                <option value={0.7} style={{ background: '#1e293b' }}>🤒 Stress / Maladie (−30% Sensibilité)</option>
                <option value={0.85} style={{ background: '#1e293b' }}>😟 Stress Léger (−15% Sensibilité)</option>
                <option value={1.0} style={{ background: '#1e293b' }}>😌 Normal / Repos (1.0x)</option>
                <option value={1.25} style={{ background: '#1e293b' }}>🚶 Marche Modérée (+25% Sensibilité)</option>
                <option value={1.5} style={{ background: '#1e293b' }}>🏃 Sport Intense (+50% Sensibilité)</option>
              </select>
            </div>
          </div>

          {/* Liste des Événements: Repas (Glucides) & Bolus d'insuline */}
          <div style={{ ...glassCard, padding: '1.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: '600', color: '#e2e8f0', fontSize: '0.95rem' }}>
                <Utensils style={{ width: '16px', height: '16px', color: '#fbbf24' }} />
                Programme des Repas et Bolus ({plannedMeals.length})
              </div>
              <button
                onClick={() => {
                  const newId = String(Date.now());
                  setPlannedMeals(prev => [
                    ...prev,
                    { id: newId, time: '16:00', label: 'Collation', carbs: 20, bolus: 2.0, speed: 'normal' }
                  ]);
                }}
                style={{
                  background: 'rgba(16, 185, 129, 0.12)',
                  color: '#34d399',
                  border: '1px solid rgba(16, 185, 129, 0.25)',
                  borderRadius: '8px',
                  padding: '0.4rem 0.85rem',
                  fontSize: '0.78rem',
                  fontWeight: '600',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
              >
                <Plus style={{ width: '13px', height: '13px' }} />
                Ajouter un Repas / Bolus
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {plannedMeals.map((meal, index) => (
                <div
                  key={meal.id}
                  style={{
                    background: 'rgba(15, 23, 42, 0.5)',
                    border: '1px solid rgba(148, 163, 184, 0.1)',
                    borderRadius: '12px',
                    padding: '0.85rem 1rem',
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr)) 40px',
                    gap: '0.75rem',
                    alignItems: 'center',
                  }}
                >
                  {/* Heure */}
                  <div>
                    <label style={{ fontSize: '0.7rem', color: '#64748b' }}>Heure</label>
                    <input
                      type="time"
                      value={meal.time}
                      onChange={e => {
                        const val = e.target.value;
                        setPlannedMeals(prev => prev.map((m, i) => i === index ? { ...m, time: val } : m));
                      }}
                      style={{
                        width: '100%', background: 'rgba(30, 41, 59, 0.8)',
                        color: '#f8fafc', border: '1px solid rgba(148, 163, 184, 0.15)',
                        padding: '0.45rem 0.6rem', borderRadius: '8px', fontSize: '0.85rem',
                      }}
                    />
                  </div>

                  {/* Intitulé */}
                  <div>
                    <label style={{ fontSize: '0.7rem', color: '#64748b' }}>Intitulé</label>
                    <input
                      type="text"
                      value={meal.label}
                      onChange={e => {
                        const val = e.target.value;
                        setPlannedMeals(prev => prev.map((m, i) => i === index ? { ...m, label: val } : m));
                      }}
                      style={{
                        width: '100%', background: 'rgba(30, 41, 59, 0.8)',
                        color: '#f8fafc', border: '1px solid rgba(148, 163, 184, 0.15)',
                        padding: '0.45rem 0.6rem', borderRadius: '8px', fontSize: '0.85rem',
                      }}
                    />
                  </div>

                  {/* Glucides */}
                  <div>
                    <label style={{ fontSize: '0.7rem', color: '#fbbf24', display: 'flex', alignItems: 'center', gap: '3px' }}>
                      <Flame style={{ width: '11px', height: '11px' }} /> Glucides (g)
                    </label>
                    <input
                      type="number" step="5" min="0"
                      value={meal.carbs}
                      onChange={e => {
                        const val = parseFloat(e.target.value) || 0;
                        setPlannedMeals(prev => prev.map((m, i) => i === index ? { ...m, carbs: val } : m));
                      }}
                      style={{
                        width: '100%', background: 'rgba(30, 41, 59, 0.8)',
                        color: '#fbbf24', fontWeight: '700', border: '1px solid rgba(251, 191, 36, 0.25)',
                        padding: '0.45rem 0.6rem', borderRadius: '8px', fontSize: '0.85rem',
                      }}
                    />
                  </div>

                  {/* Bolus */}
                  <div>
                    <label style={{ fontSize: '0.7rem', color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '3px' }}>
                      <Droplets style={{ width: '11px', height: '11px' }} /> Bolus (U)
                    </label>
                    <input
                      type="number" step="0.5" min="0"
                      value={meal.bolus}
                      onChange={e => {
                        const val = parseFloat(e.target.value) || 0;
                        setPlannedMeals(prev => prev.map((m, i) => i === index ? { ...m, bolus: val } : m));
                      }}
                      style={{
                        width: '100%', background: 'rgba(30, 41, 59, 0.8)',
                        color: '#38bdf8', fontWeight: '700', border: '1px solid rgba(56, 189, 248, 0.25)',
                        padding: '0.45rem 0.6rem', borderRadius: '8px', fontSize: '0.85rem',
                      }}
                    />
                  </div>

                  {/* Vitesse de digestion */}
                  <div>
                    <label style={{ fontSize: '0.7rem', color: '#64748b' }}>Digestion</label>
                    <select
                      value={meal.speed}
                      onChange={e => {
                        const val = e.target.value as 'fast' | 'normal' | 'slow';
                        setPlannedMeals(prev => prev.map((m, i) => i === index ? { ...m, speed: val } : m));
                      }}
                      style={{
                        width: '100%', background: 'rgba(30, 41, 59, 0.8)',
                        color: '#f8fafc', border: '1px solid rgba(148, 163, 184, 0.15)',
                        padding: '0.45rem 0.4rem', borderRadius: '8px', fontSize: '0.8rem',
                      }}
                    >
                      <option value="fast">⚡ Rapide (Jus)</option>
                      <option value="normal">🍽 Normal</option>
                      <option value="slow">🍕 Lent (Gras)</option>
                    </select>
                  </div>

                  {/* Bouton Supprimer */}
                  <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '14px' }}>
                    <button
                      onClick={() => {
                        if (plannedMeals.length > 1) {
                          setPlannedMeals(prev => prev.filter((_, i) => i !== index));
                        }
                      }}
                      disabled={plannedMeals.length <= 1}
                      title="Supprimer ce repas"
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: plannedMeals.length <= 1 ? '#475569' : '#f87171',
                        cursor: plannedMeals.length <= 1 ? 'not-allowed' : 'pointer',
                        padding: '0.35rem',
                        display: 'flex',
                        borderRadius: '6px',
                      }}
                    >
                      <Trash2 style={{ width: '16px', height: '16px' }} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Indicateurs Clés de la Simulation (TIR, Hypo, Hyper, SGV Moyenne) */}
          {plannedResult?.summary && (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '1rem',
              animation: 'fadeInUp 0.5s ease-out',
            }}>
              {/* TIR */}
              <div style={{ ...glassCard, padding: '1.25rem', textAlign: 'center' }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Temps dans la Cible (TIR)</div>
                <div style={{ fontSize: '1.8rem', fontWeight: '800', color: '#34d399', marginTop: '0.2rem' }}>
                  {plannedResult.summary.tir}%
                </div>
                <div style={{ fontSize: '0.68rem', color: '#64748b' }}>Cible 70 - 180 mg/dL</div>
              </div>

              {/* Hypo TBR */}
              <div style={{
                ...glassCard, padding: '1.25rem', textAlign: 'center',
                borderColor: plannedResult.summary.tbr > 4 ? 'rgba(239, 68, 68, 0.4)' : 'rgba(148, 163, 184, 0.12)'
              }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Temps Sous la Cible (TBR)</div>
                <div style={{
                  fontSize: '1.8rem', fontWeight: '800',
                  color: plannedResult.summary.tbr > 4 ? '#f87171' : '#10b981',
                  marginTop: '0.2rem'
                }}>
                  {plannedResult.summary.tbr}%
                </div>
                <div style={{ fontSize: '0.68rem', color: '#64748b' }}>&lt; 70 mg/dL (Seuil hypo: 4%)</div>
              </div>

              {/* Hyper TAR */}
              <div style={{ ...glassCard, padding: '1.25rem', textAlign: 'center' }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Temps Au-dessus (TAR)</div>
                <div style={{
                  fontSize: '1.8rem', fontWeight: '800',
                  color: plannedResult.summary.tar > 25 ? '#fbbf24' : '#10b981',
                  marginTop: '0.2rem'
                }}>
                  {plannedResult.summary.tar}%
                </div>
                <div style={{ fontSize: '0.68rem', color: '#64748b' }}>&gt; 180 mg/dL</div>
              </div>

              {/* SGV Moyenne */}
              <div style={{ ...glassCard, padding: '1.25rem', textAlign: 'center' }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Glycémie Moyenne Prévue</div>
                <div style={{ fontSize: '1.8rem', fontWeight: '800', color: '#818cf8', marginTop: '0.2rem' }}>
                  {plannedResult.summary.mean_sgv}
                  <span style={{ fontSize: '0.7rem', fontWeight: '400', opacity: 0.7 }}> mg/dL</span>
                </div>
                <div style={{ fontSize: '0.68rem', color: '#64748b' }}>
                  Min: {plannedResult.summary.min_sgv} | Max: {plannedResult.summary.max_sgv}
                </div>
              </div>

              {/* Cumul Doses & Pharmacocinétique */}
              <div style={{ ...glassCard, padding: '1.25rem', textAlign: 'center' }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Doses & Pics Actifs</div>
                <div style={{ display: 'flex', justifyContent: 'space-around', alignItems: 'center', marginTop: '0.35rem' }}>
                  <div>
                    <div style={{ fontSize: '1rem', fontWeight: '700', color: '#fbbf24' }}>{plannedResult.summary.total_carbs}g</div>
                    <div style={{ fontSize: '0.65rem', color: '#94a3b8' }}>Pic COB : <strong style={{ color: '#fbbf24' }}>{plannedResult.summary.max_cob ?? '--'}g</strong></div>
                  </div>
                  <div style={{ width: '1px', height: '24px', background: 'rgba(255,255,255,0.1)' }}></div>
                  <div>
                    <div style={{ fontSize: '1rem', fontWeight: '700', color: '#38bdf8' }}>{plannedResult.summary.total_bolus}U</div>
                    <div style={{ fontSize: '0.65rem', color: '#94a3b8' }}>Pic IOB : <strong style={{ color: '#38bdf8' }}>{plannedResult.summary.max_iob ?? '--'}U</strong></div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Graphique de la Courbe Glycémique Simulée sur 24h */}
          <div style={glassCard}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
              <div style={{ fontSize: '0.95rem', fontWeight: '700', color: '#e2e8f0' }}>
                Courbe Glycémique Simulée (00h00 - 23h55) & Pharmacocinétique IOB/COB
              </div>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <span>Événements : <span style={{ color: '#38bdf8', fontWeight: '700' }}>▲ Bolus</span> | <span style={{ color: '#fbbf24', fontWeight: '700' }}>● Repas</span></span>
                <span>Pharmacocinétique : <span style={{ color: '#38bdf8', fontWeight: '700' }}>--- IOB (U)</span> | <span style={{ color: '#fbbf24', fontWeight: '700' }}>━ COB (g)</span></span>
              </div>
            </div>

            {loadingPlanned ? (
              <LoadingSpinner message="Calcul de la simulation 24h en cours..." />
            ) : plannedResult?.timeline ? (
              <ReactECharts option={plannedChartOption} style={{ height: '420px', width: '100%' }} />
            ) : (
              <div style={{ height: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b' }}>
                Aucune simulation calculée
              </div>
            )}
          </div>
        </div>
      )}

      {/* ════════════════════ TAB PROTOCOLE: AAPS-DT PILOT (HÔPITAL MILITAIRE) ════════════════════ */}
      {activeTab === 'protocol' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', animation: 'fadeInUp 0.4s ease-out' }}>
          {/* Header Protocole */}
          <div style={{
            ...glassCard,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            flexWrap: 'wrap', gap: '1rem',
            padding: '1.25rem 1.5rem',
            borderLeft: '4px solid #38bdf8',
          }}>
            <div>
              <div style={{
                display: 'flex', alignItems: 'center', gap: '0.6rem',
                fontSize: '1.15rem', fontWeight: '700', color: '#e2e8f0',
              }}>
                <div style={{
                  background: 'linear-gradient(135deg, #0284c7, #38bdf8)',
                  borderRadius: '8px', padding: '0.4rem', display: 'flex',
                }}>
                  <FileText style={{ width: '18px', height: '18px', color: '#fff' }} />
                </div>
                Protocole Clinique AAPS-DT Pilot v1.0
                <span style={{
                  fontSize: '0.72rem', background: 'rgba(56, 189, 248, 0.15)',
                  color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.3)',
                  padding: '0.15rem 0.55rem', borderRadius: '12px', fontWeight: '600'
                }}>
                  12 Octobre 2026
                </span>
              </div>
              <div style={{ color: '#94a3b8', fontSize: '0.82rem', marginTop: '0.35rem', marginLeft: '2.5rem' }}>
                <strong style={{ color: '#cbd5e1' }}>Hôpital Militaire Oued Eddahab - Agadir</strong> | Patient : <strong style={{ color: '#34d399' }}>Ahmed DANY</strong> | Investigateur Principal : <strong style={{ color: '#38bdf8' }}>Médecin Commandant Lhoussaine Abainou</strong>
              </div>
            </div>

            <button
              onClick={handleRunProtocolBenchmark}
              disabled={loadingProtocol}
              style={{
                background: loadingProtocol
                  ? 'rgba(56, 189, 248, 0.3)'
                  : 'linear-gradient(135deg, #0284c7, #0284c7)',
                color: 'white',
                border: 'none',
                padding: '0.65rem 1.25rem',
                borderRadius: '10px',
                fontWeight: '700',
                cursor: loadingProtocol ? 'wait' : 'pointer',
                fontSize: '0.85rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                boxShadow: '0 4px 15px rgba(2, 132, 199, 0.3)',
                transition: 'all 0.3s ease',
              }}
            >
              <RefreshCw style={{ width: '15px', height: '15px', animation: loadingProtocol ? 'spin-slow 1s linear infinite' : 'none' }} />
              {loadingProtocol ? 'Évaluation en cours...' : 'Recalculer le Benchmark'}
            </button>
          </div>

          {loadingProtocol ? (
            <LoadingSpinner message="Calcul du benchmark protocolariste et des 500 rééchantillonnages Block Bootstrap..." />
          ) : protocolData?.primary_endpoint_summary ? (
            <>
              {/* Carte Critère Principal de Jugement (§ 5.1) */}
              <div style={{
                ...glassCard,
                background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(30, 41, 59, 0.75) 100%)',
                padding: '1.5rem',
                border: '1px solid rgba(56, 189, 248, 0.25)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <Target style={{ width: '18px', height: '18px', color: '#38bdf8' }} />
                      <span style={{ fontSize: '0.9rem', fontWeight: '700', color: '#e2e8f0', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Critère Principal de Jugement (Section 5.1)
                      </span>
                    </div>
                    <div style={{ fontSize: '1.25rem', fontWeight: '800', color: '#f8fafc', marginTop: '0.35rem' }}>
                      MAE à 30 minutes avec IC à 95% (Block Bootstrap)
                    </div>
                    <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.25rem' }}>
                      Règle de validation du protocole : Le modèle hybride doit surpasser le modèle de persistance (Delta MAE &gt; 0).
                    </div>
                  </div>

                  {/* Résultat du Jumeau vs Persistance */}
                  {(() => {
                    const lgb = protocolData.primary_endpoint_summary.results?.lightgbm;
                    const isSuccess = lgb?.beats_persistence;
                    return (
                      <div style={{
                        background: isSuccess ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)',
                        border: `1px solid ${isSuccess ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                        borderRadius: '12px',
                        padding: '0.85rem 1.25rem',
                        textAlign: 'right',
                      }}>
                        <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase' }}>
                          Validation Critère Principal
                        </div>
                        <div style={{
                          fontSize: '1.3rem', fontWeight: '800',
                          color: isSuccess ? '#34d399' : '#f87171',
                          display: 'flex', alignItems: 'center', gap: '0.4rem', justifyContent: 'flex-end',
                          marginTop: '0.2rem'
                        }}>
                          {isSuccess ? <CheckCircle2 style={{ width: '20px', height: '20px' }} /> : <AlertTriangle style={{ width: '20px', height: '20px' }} />}
                          {isSuccess ? 'CRITÈRE VALIDÉ' : 'NON VALIDÉ'}
                        </div>
                        <div style={{ fontSize: '0.78rem', color: '#cbd5e1', marginTop: '0.25rem' }}>
                          Gain Jumeau vs Persistance : <strong style={{ color: '#38bdf8' }}>+{lgb?.delta_mae_pct}%</strong>
                        </div>
                      </div>
                    );
                  })()}
                </div>

                {/* KPI Comparatifs des 4 modèles sur le Critère Principal à 30 min */}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
                  gap: '1rem',
                  marginTop: '1.5rem',
                }}>
                  {Object.entries(protocolData.primary_endpoint_summary.results || {}).map(([key, item]: [string, any]) => {
                    const isWinner = key === 'lightgbm';
                    return (
                      <div key={key} style={{
                        background: isWinner ? 'rgba(56, 189, 248, 0.08)' : 'rgba(15, 23, 42, 0.5)',
                        border: isWinner ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid rgba(148, 163, 184, 0.1)',
                        borderRadius: '12px',
                        padding: '1rem',
                        position: 'relative',
                      }}>
                        {isWinner && (
                          <span style={{
                            position: 'absolute', top: '-10px', right: '12px',
                            background: '#0284c7', color: 'white', fontSize: '0.65rem',
                            fontWeight: '700', padding: '0.15rem 0.5rem', borderRadius: '10px',
                          }}>
                            JUMEAU RECOMMANDÉ
                          </span>
                        )}
                        <div style={{ fontSize: '0.8rem', fontWeight: '700', color: isWinner ? '#38bdf8' : '#cbd5e1' }}>
                          {item.name}
                        </div>
                        <div style={{ marginTop: '0.6rem' }}>
                          <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>MAE à 30 min</div>
                          <div style={{ fontSize: '1.4rem', fontWeight: '800', color: isWinner ? '#38bdf8' : '#f8fafc' }}>
                            {item.mae} <span style={{ fontSize: '0.75rem', fontWeight: '500', color: '#64748b' }}>mg/dL</span>
                          </div>
                        </div>
                        <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '0.35rem' }}>
                          IC 95% Bootstrap : <span style={{ color: '#e2e8f0', fontWeight: '600' }}>{item.ci_95}</span>
                        </div>
                        <div style={{
                          display: 'flex', justifyContent: 'space-between',
                          marginTop: '0.5rem', paddingTop: '0.5rem',
                          borderTop: '1px solid rgba(148, 163, 184, 0.08)',
                          fontSize: '0.72rem', color: '#94a3b8'
                        }}>
                          <span>Biais: <strong style={{ color: '#cbd5e1' }}>{item.bias > 0 ? `+${item.bias}` : item.bias}</strong></span>
                          <span>Clarke A+B: <strong style={{ color: '#34d399' }}>{item.clarke_ab}%</strong></span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Tableau Détaillé de Validation Multi-Horizons (§ 5.2 Critères Secondaires) */}
              <div style={glassCard}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <div>
                    <div style={{ fontSize: '0.95rem', fontWeight: '700', color: '#e2e8f0' }}>
                      Critères Secondaires : Performance aux Horizons 30m, 60m et 120m
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.2rem' }}>
                      Comparaison chronologique stricte avec purge de 2h (sans data leakage futur)
                    </div>
                  </div>
                  <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
                    Échantillons de test : {protocolData.sample_counts?.test} points
                  </span>
                </div>

                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.15)', color: '#94a3b8', textAlign: 'left' }}>
                        <th style={{ padding: '0.75rem' }}>Modèle Évalué</th>
                        <th style={{ padding: '0.75rem' }}>Horizon</th>
                        <th style={{ padding: '0.75rem' }}>MAE (mg/dL)</th>
                        <th style={{ padding: '0.75rem' }}>IC 95% (Bootstrap)</th>
                        <th style={{ padding: '0.75rem' }}>Δ vs Persistance</th>
                        <th style={{ padding: '0.75rem' }}>RMSE</th>
                        <th style={{ padding: '0.75rem' }}>Biais</th>
                        <th style={{ padding: '0.75rem' }}>MARD</th>
                        <th style={{ padding: '0.75rem' }}>Clarke (A+B)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(protocolData.models || {}).map(([mKey, mVal]: [string, any]) => {
                        return Object.entries(mVal.horizons || {}).map(([hKey, hVal]: [string, any], hIdx: number) => {
                          const isLgb = mKey === 'lightgbm';
                          const delta = hVal.delta_mae_pct_vs_persistence;
                          const deltaColor = delta > 0 ? '#34d399' : delta < 0 ? '#f87171' : '#94a3b8';
                          return (
                            <tr key={`${mKey}-${hKey}`} style={{
                              borderBottom: '1px solid rgba(148, 163, 184, 0.06)',
                              background: isLgb ? 'rgba(56, 189, 248, 0.03)' : 'transparent',
                            }}>
                              <td style={{ padding: '0.65rem 0.75rem', fontWeight: hIdx === 0 ? '700' : '400', color: isLgb ? '#38bdf8' : '#e2e8f0' }}>
                                {hIdx === 0 ? mVal.name : ''}
                              </td>
                              <td style={{ padding: '0.65rem 0.75rem', color: '#cbd5e1', fontWeight: '600' }}>
                                +{hKey}
                              </td>
                              <td style={{ padding: '0.65rem 0.75rem', fontWeight: '700', color: isLgb ? '#38bdf8' : '#f8fafc' }}>
                                {hVal.mae}
                              </td>
                              <td style={{ padding: '0.65rem 0.75rem', color: '#94a3b8', fontSize: '0.75rem' }}>
                                [{hVal.ci_95?.ci_low} - {hVal.ci_95?.ci_high}]
                              </td>
                              <td style={{ padding: '0.65rem 0.75rem', fontWeight: '700', color: deltaColor }}>
                                {delta > 0 ? `+${delta}%` : `${delta}%`}
                              </td>
                              <td style={{ padding: '0.65rem 0.75rem', color: '#cbd5e1' }}>
                                {hVal.rmse}
                              </td>
                              <td style={{ padding: '0.65rem 0.75rem', color: Math.abs(hVal.bias) < 2 ? '#34d399' : '#fbbf24' }}>
                                {hVal.bias > 0 ? `+${hVal.bias}` : hVal.bias}
                              </td>
                              <td style={{ padding: '0.65rem 0.75rem', color: '#cbd5e1' }}>
                                {hVal.mard}%
                              </td>
                              <td style={{ padding: '0.65rem 0.75rem', color: hVal.clarke?.zone_ab >= 95 ? '#34d399' : '#cbd5e1', fontWeight: '600' }}>
                                {hVal.clarke?.zone_ab}%
                              </td>
                            </tr>
                          );
                        });
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Stratification Clinique (§ 5.2 : Hypoglycémie <70 vs Cible vs Hyperglycémie >180) */}
              <div style={glassCard}>
                <div style={{ fontSize: '0.95rem', fontWeight: '700', color: '#e2e8f0', marginBottom: '0.35rem' }}>
                  Stratification Clinique par Plage Glycémique (Jumeau Numérique LightGBM)
                </div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '1rem' }}>
                  Évaluation ciblée de la précision du jumeau en zones critiques (Hypoglycémie &lt; 70 mg/dL et Hyperglycémie &gt; 180 mg/dL)
                </div>

                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                  gap: '1rem',
                }}>
                  {(() => {
                    const lgbStrat = protocolData.models?.lightgbm?.horizons?.['30m']?.stratified;
                    if (!lgbStrat) return null;
                    return (
                      <>
                        {/* Hypoglycémie */}
                        <div style={{
                          background: 'rgba(239, 68, 68, 0.08)',
                          border: '1px solid rgba(239, 68, 68, 0.25)',
                          borderRadius: '12px', padding: '1rem'
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#f87171', fontWeight: '700', fontSize: '0.85rem' }}>
                            <AlertTriangle style={{ width: '15px', height: '15px' }} />
                            Hypoglycémie (&lt; 70 mg/dL)
                          </div>
                          <div style={{ marginTop: '0.65rem', display: 'flex', justifyContent: 'space-between' }}>
                            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>MAE à 30 min:</span>
                            <span style={{ fontWeight: '700', color: '#f8fafc' }}>{lgbStrat.hypo?.mae || 'N/A'} mg/dL</span>
                          </div>
                          <div style={{ marginTop: '0.35rem', display: 'flex', justifyContent: 'space-between' }}>
                            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Biais moyen:</span>
                            <span style={{ fontWeight: '700', color: '#cbd5e1' }}>{lgbStrat.hypo?.bias || '0.0'} mg/dL</span>
                          </div>
                          <div style={{ marginTop: '0.35rem', display: 'flex', justifyContent: 'space-between' }}>
                            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Nombre d'événements:</span>
                            <span style={{ fontWeight: '700', color: '#cbd5e1' }}>{lgbStrat.hypo?.n || 0}</span>
                          </div>
                        </div>

                        {/* Plage Cible */}
                        <div style={{
                          background: 'rgba(16, 185, 129, 0.08)',
                          border: '1px solid rgba(16, 185, 129, 0.25)',
                          borderRadius: '12px', padding: '1rem'
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#34d399', fontWeight: '700', fontSize: '0.85rem' }}>
                            <CheckCircle2 style={{ width: '15px', height: '15px' }} />
                            Plage Cible (70 - 180 mg/dL)
                          </div>
                          <div style={{ marginTop: '0.65rem', display: 'flex', justifyContent: 'space-between' }}>
                            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>MAE à 30 min:</span>
                            <span style={{ fontWeight: '700', color: '#f8fafc' }}>{lgbStrat.target?.mae || 'N/A'} mg/dL</span>
                          </div>
                          <div style={{ marginTop: '0.35rem', display: 'flex', justifyContent: 'space-between' }}>
                            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Biais moyen:</span>
                            <span style={{ fontWeight: '700', color: '#cbd5e1' }}>{lgbStrat.target?.bias || '0.0'} mg/dL</span>
                          </div>
                          <div style={{ marginTop: '0.35rem', display: 'flex', justifyContent: 'space-between' }}>
                            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Nombre de mesures:</span>
                            <span style={{ fontWeight: '700', color: '#cbd5e1' }}>{lgbStrat.target?.n || 0}</span>
                          </div>
                        </div>

                        {/* Hyperglycémie */}
                        <div style={{
                          background: 'rgba(245, 158, 11, 0.08)',
                          border: '1px solid rgba(245, 158, 11, 0.25)',
                          borderRadius: '12px', padding: '1rem'
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#fbbf24', fontWeight: '700', fontSize: '0.85rem' }}>
                            <TrendingUp style={{ width: '15px', height: '15px' }} />
                            Hyperglycémie (&gt; 180 mg/dL)
                          </div>
                          <div style={{ marginTop: '0.65rem', display: 'flex', justifyContent: 'space-between' }}>
                            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>MAE à 30 min:</span>
                            <span style={{ fontWeight: '700', color: '#f8fafc' }}>{lgbStrat.hyper?.mae || 'N/A'} mg/dL</span>
                          </div>
                          <div style={{ marginTop: '0.35rem', display: 'flex', justifyContent: 'space-between' }}>
                            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Biais moyen:</span>
                            <span style={{ fontWeight: '700', color: '#cbd5e1' }}>{lgbStrat.hyper?.bias || '0.0'} mg/dL</span>
                          </div>
                          <div style={{ marginTop: '0.35rem', display: 'flex', justifyContent: 'space-between' }}>
                            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Nombre d'événements:</span>
                            <span style={{ fontWeight: '700', color: '#cbd5e1' }}>{lgbStrat.hyper?.n || 0}</span>
                          </div>
                        </div>
                      </>
                    );
                  })()}
                </div>
              </div>
            </>
          ) : (
            <div style={{ ...glassCard, padding: '2rem', textAlign: 'center', color: '#94a3b8' }}>
              Cliquez sur « Recalculer le Benchmark » pour lancer l'évaluation protocolariste.
            </div>
          )}
        </div>
      )}

      {/* ════════════════════ TAB 1: DAY REPLAY ════════════════════ */}
      {activeTab === 'replay' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', animation: 'fadeInUp 0.4s ease-out' }}>
          {/* Header + Date Picker */}
          <div style={{
            ...glassCard,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            flexWrap: 'wrap', gap: '1rem',
            padding: '1.25rem 1.5rem',
          }}>
            <div>
              <div style={{
                display: 'flex', alignItems: 'center', gap: '0.6rem',
                fontSize: '1.15rem', fontWeight: '700', color: '#e2e8f0',
              }}>
                <div style={{
                  background: 'linear-gradient(135deg, #6366f1, #a855f7)',
                  borderRadius: '8px', padding: '0.4rem', display: 'flex',
                }}>
                  <Cpu style={{ width: '18px', height: '18px', color: '#fff' }} />
                </div>
                Rejeu de Journée par le Jumeau Numérique
              </div>
              <div style={{ color: '#64748b', fontSize: '0.82rem', marginTop: '0.3rem', marginLeft: '2.5rem' }}>
                Comparaison glycémie réelle vs. dynamique simulée par le modèle physiologique hybride
              </div>
            </div>

            <div style={{
              display: 'flex', alignItems: 'center', gap: '0.5rem',
              background: 'rgba(99, 102, 241, 0.08)',
              border: '1px solid rgba(99, 102, 241, 0.2)',
              borderRadius: '10px', padding: '0.35rem 0.75rem',
            }}>
              <Calendar style={{ width: '14px', height: '14px', color: '#818cf8' }} />
              <select
                value={selectedDate}
                onChange={e => setSelectedDate(e.target.value)}
                style={{
                  background: 'transparent',
                  color: '#e2e8f0',
                  border: 'none',
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                  outline: 'none',
                  fontWeight: '500',
                }}
              >
                {availableDays.map(d => (
                  <option key={d.date} value={d.date} style={{ background: '#1e293b', color: '#e2e8f0' }}>
                    {new Date(d.date).toLocaleDateString('fr-FR', { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' })}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Metric Gauges */}
          {replayData?.metrics && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '1rem' }}>
              <MetricGauge
                label="RMSE" value={replayData.metrics.rmse} unit="mg/dL" color="#60a5fa"
                icon={Activity} subtitle="Erreur Quadratique" maxValue={50}
              />
              <MetricGauge
                label="MAE" value={replayData.metrics.mae} unit="mg/dL" color="#a855f7"
                icon={BarChart3} subtitle="Erreur Absolue Moy." maxValue={40}
              />
              <MetricGauge
                label="MARD" value={replayData.metrics.mard} unit="%" color="#10b981"
                icon={Target} subtitle="Erreur Relative" maxValue={25}
              />
              <MetricGauge
                label="Clarke A+B" value={replayData.metrics.clarke?.zone_ab ?? 98} unit="%"
                color="#34d399" icon={CheckCircle2} subtitle="Précision Clinique" maxValue={100}
              />
            </div>
          )}

          {/* Replay Chart */}
          <div style={glassCard}>
            {loadingReplay ? (
              <LoadingSpinner message="Simulation du jumeau numérique en cours..." />
            ) : (
              <ReactECharts option={replayChartOption} style={{ height: '420px', width: '100%' }} />
            )}
          </div>
        </div>
      )}

      {/* ════════════════════ TAB 2: WHAT-IF SCENARIOS ════════════════════ */}
      {activeTab === 'scenario' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', animation: 'fadeInUp 0.4s ease-out' }}>
          {/* Header */}
          <div style={{
            ...glassCard,
            padding: '1.25rem 1.5rem',
          }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: '0.6rem',
              fontSize: '1.15rem', fontWeight: '700', color: '#e2e8f0',
              marginBottom: '0.4rem',
            }}>
              <div style={{
                background: 'linear-gradient(135deg, #10b981, #06b6d4)',
                borderRadius: '8px', padding: '0.4rem', display: 'flex',
              }}>
                <Sliders style={{ width: '18px', height: '18px', color: '#fff' }} />
              </div>
              Simulateur de Scénarios « Et Si »
            </div>
            <div style={{ color: '#64748b', fontSize: '0.82rem', marginLeft: '2.5rem' }}>
              Modifiez les paramètres sur la journée du <strong style={{ color: '#e2e8f0' }}>{selectedDate}</strong> et observez l'impact simulé en temps réel.
            </div>
          </div>

          {/* Input Form */}
          <div style={{
            ...glassCard,
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '1.25rem',
          }}>
            {/* Event Time */}
            <div>
              <label style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <Clock style={{ width: '13px', height: '13px', color: '#818cf8' }} />Heure de l'Événement
              </label>
              <input
                type="time"
                value={eventTimeStr}
                onChange={e => setEventTimeStr(e.target.value)}
                style={{
                  width: '100%', background: 'rgba(15, 23, 42, 0.6)',
                  color: '#e2e8f0', border: '1px solid rgba(148, 163, 184, 0.15)',
                  padding: '0.6rem 0.75rem', borderRadius: '10px', marginTop: '0.35rem',
                  fontSize: '0.88rem', outline: 'none',
                  transition: 'border-color 0.2s',
                }}
                onFocus={e => e.currentTarget.style.borderColor = 'rgba(99, 102, 241, 0.5)'}
                onBlur={e => e.currentTarget.style.borderColor = 'rgba(148, 163, 184, 0.15)'}
              />
            </div>

            {/* Bolus */}
            <div>
              <label style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <Droplets style={{ width: '13px', height: '13px', color: '#38bdf8' }} />Ajustement Bolus (U)
              </label>
              <input
                type="number" step="0.5"
                value={bolusDelta}
                onChange={e => setBolusDelta(parseFloat(e.target.value) || 0)}
                style={{
                  width: '100%', background: 'rgba(15, 23, 42, 0.6)',
                  color: '#e2e8f0', border: '1px solid rgba(148, 163, 184, 0.15)',
                  padding: '0.6rem 0.75rem', borderRadius: '10px', marginTop: '0.35rem',
                  fontSize: '0.88rem', outline: 'none',
                  transition: 'border-color 0.2s',
                }}
                onFocus={e => e.currentTarget.style.borderColor = 'rgba(56, 189, 248, 0.5)'}
                onBlur={e => e.currentTarget.style.borderColor = 'rgba(148, 163, 184, 0.15)'}
              />
            </div>

            {/* Carbs */}
            <div>
              <label style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <Flame style={{ width: '13px', height: '13px', color: '#fbbf24' }} />Ajustement Glucides (g)
              </label>
              <input
                type="number" step="5"
                value={carbsDelta}
                onChange={e => setCarbsDelta(parseFloat(e.target.value) || 0)}
                style={{
                  width: '100%', background: 'rgba(15, 23, 42, 0.6)',
                  color: '#e2e8f0', border: '1px solid rgba(148, 163, 184, 0.15)',
                  padding: '0.6rem 0.75rem', borderRadius: '10px', marginTop: '0.35rem',
                  fontSize: '0.88rem', outline: 'none',
                  transition: 'border-color 0.2s',
                }}
                onFocus={e => e.currentTarget.style.borderColor = 'rgba(251, 191, 36, 0.5)'}
                onBlur={e => e.currentTarget.style.borderColor = 'rgba(148, 163, 184, 0.15)'}
              />
            </div>

            {/* Carb Speed */}
            <div>
              <label style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <Zap style={{ width: '13px', height: '13px', color: '#f59e0b' }} />Vitesse de Digestion
              </label>
              <select
                value={carbSpeed}
                onChange={e => setCarbSpeed(e.target.value)}
                style={{
                  width: '100%', background: 'rgba(15, 23, 42, 0.6)',
                  color: '#e2e8f0', border: '1px solid rgba(148, 163, 184, 0.15)',
                  padding: '0.6rem 0.75rem', borderRadius: '10px', marginTop: '0.35rem',
                  fontSize: '0.85rem', cursor: 'pointer', outline: 'none',
                }}
              >
                <option value="fast" style={{ background: '#1e293b' }}>⚡ Rapide (Jus / Sucres)</option>
                <option value="normal" style={{ background: '#1e293b' }}>🍽 Normale (Repas Équilibré)</option>
                <option value="slow" style={{ background: '#1e293b' }}>🍕 Lente (Pizza / Gras)</option>
              </select>
            </div>

            {/* Basal Multiplier */}
            <div>
              <label style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <Gauge style={{ width: '13px', height: '13px', color: '#a78bfa' }} />Multiplicateur Basal
              </label>
              <select
                value={basalMult}
                onChange={e => setBasalMult(parseFloat(e.target.value))}
                style={{
                  width: '100%', background: 'rgba(15, 23, 42, 0.6)',
                  color: '#e2e8f0', border: '1px solid rgba(148, 163, 184, 0.15)',
                  padding: '0.6rem 0.75rem', borderRadius: '10px', marginTop: '0.35rem',
                  fontSize: '0.85rem', cursor: 'pointer', outline: 'none',
                }}
              >
                <option value={0.5} style={{ background: '#1e293b' }}>0.5x (−50% Basale Temp)</option>
                <option value={0.8} style={{ background: '#1e293b' }}>0.8x (−20% Basale Temp)</option>
                <option value={1.0} style={{ background: '#1e293b' }}>1.0x (Basale Programmée)</option>
                <option value={1.2} style={{ background: '#1e293b' }}>1.2x (+20% Basale Temp)</option>
                <option value={1.5} style={{ background: '#1e293b' }}>1.5x (+50% Basale Temp)</option>
                <option value={2.0} style={{ background: '#1e293b' }}>2.0x (+100% Basale Temp)</option>
              </select>
            </div>

            {/* ISF Override */}
            <div>
              <label style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <Beaker style={{ width: '13px', height: '13px', color: '#06b6d4' }} />Surcharge ISF (mg/dL/U)
              </label>
              <input
                type="number"
                placeholder="Auto (par défaut)"
                value={isfOverride}
                onChange={e => setIsfOverride(e.target.value)}
                style={{
                  width: '100%', background: 'rgba(15, 23, 42, 0.6)',
                  color: '#e2e8f0', border: '1px solid rgba(148, 163, 184, 0.15)',
                  padding: '0.6rem 0.75rem', borderRadius: '10px', marginTop: '0.35rem',
                  fontSize: '0.88rem', outline: 'none',
                  transition: 'border-color 0.2s',
                }}
                onFocus={e => e.currentTarget.style.borderColor = 'rgba(6, 182, 212, 0.5)'}
                onBlur={e => e.currentTarget.style.borderColor = 'rgba(148, 163, 184, 0.15)'}
              />
            </div>

            {/* Stress Factor */}
            <div>
              <label style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <Heart style={{ width: '13px', height: '13px', color: '#f43f5e' }} />État Physique / Stress
              </label>
              <select
                value={stressFactor}
                onChange={e => setStressFactor(parseFloat(e.target.value))}
                style={{
                  width: '100%', background: 'rgba(15, 23, 42, 0.6)',
                  color: '#e2e8f0', border: '1px solid rgba(148, 163, 184, 0.15)',
                  padding: '0.6rem 0.75rem', borderRadius: '10px', marginTop: '0.35rem',
                  fontSize: '0.85rem', cursor: 'pointer', outline: 'none',
                }}
              >
                <option value={0.7} style={{ background: '#1e293b' }}>🤒 Stress / Maladie (−30% ISF)</option>
                <option value={0.85} style={{ background: '#1e293b' }}>😟 Stress Léger (−15% ISF)</option>
                <option value={1.0} style={{ background: '#1e293b' }}>😌 Normal / Repos (1.0x)</option>
                <option value={1.25} style={{ background: '#1e293b' }}>🚶 Marche Modérée (+25% ISF)</option>
                <option value={1.5} style={{ background: '#1e293b' }}>🏃 Sport Intense (+50% ISF)</option>
              </select>
            </div>

            {/* Run Button */}
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button
                onClick={handleRunScenario}
                disabled={loadingScenario}
                style={{
                  width: '100%',
                  background: loadingScenario
                    ? 'rgba(16, 185, 129, 0.3)'
                    : 'linear-gradient(135deg, #10b981, #06b6d4)',
                  color: 'white',
                  border: 'none',
                  padding: '0.7rem',
                  borderRadius: '10px',
                  fontWeight: '700',
                  cursor: loadingScenario ? 'wait' : 'pointer',
                  fontSize: '0.9rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem',
                  boxShadow: loadingScenario ? 'none' : '0 4px 15px rgba(16, 185, 129, 0.3)',
                  transition: 'all 0.3s ease',
                }}
                onMouseEnter={e => {
                  if (!loadingScenario) e.currentTarget.style.boxShadow = '0 6px 20px rgba(16, 185, 129, 0.45)';
                }}
                onMouseLeave={e => {
                  if (!loadingScenario) e.currentTarget.style.boxShadow = '0 4px 15px rgba(16, 185, 129, 0.3)';
                }}
              >
                {loadingScenario ? (
                  <RefreshCw style={{ width: '16px', height: '16px', animation: 'spin-slow 1s linear infinite' }} />
                ) : (
                  <Zap style={{ width: '16px', height: '16px' }} />
                )}
                {loadingScenario ? 'Calcul...' : 'Simuler le Scénario'}
              </button>
            </div>
          </div>

          {/* Scenario Results */}
          {scenarioResult?.summary && (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '1rem',
              animation: 'fadeInUp 0.5s ease-out',
            }}>
              <div style={{
                ...glassCard, padding: '1rem', textAlign: 'center',
                borderColor: Math.abs(scenarioResult.summary.max_impact_delta) > 30
                  ? 'rgba(245, 158, 11, 0.3)' : 'rgba(148, 163, 184, 0.12)',
              }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginBottom: '0.3rem' }}>Impact Max du Scénario</div>
                <div style={{
                  fontSize: '1.6rem', fontWeight: '800',
                  color: scenarioResult.summary.max_impact_delta > 0 ? '#fbbf24' : '#38bdf8',
                }}>
                  {scenarioResult.summary.max_impact_delta > 0 ? '+' : ''}{scenarioResult.summary.max_impact_delta}
                  <span style={{ fontSize: '0.65rem', fontWeight: '400', opacity: 0.7 }}> mg/dL</span>
                </div>
              </div>

              <div style={{
                ...glassCard, padding: '1rem', textAlign: 'center',
                borderColor: scenarioResult.summary.risk_hypo ? 'rgba(239, 68, 68, 0.3)' : 'rgba(148, 163, 184, 0.12)',
              }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginBottom: '0.3rem' }}>Glycémie Min Projetée</div>
                <div style={{
                  fontSize: '1.6rem', fontWeight: '800',
                  color: scenarioResult.summary.risk_hypo ? '#f87171' : '#10b981',
                }}>
                  {scenarioResult.summary.min_projected_sgv}
                  <span style={{ fontSize: '0.65rem', fontWeight: '400', opacity: 0.7 }}> mg/dL</span>
                </div>
              </div>

              <div style={{
                ...glassCard, padding: '1rem', textAlign: 'center',
                borderColor: scenarioResult.summary.risk_hyper ? 'rgba(245, 158, 11, 0.3)' : 'rgba(148, 163, 184, 0.12)',
              }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginBottom: '0.3rem' }}>Glycémie Max Projetée</div>
                <div style={{
                  fontSize: '1.6rem', fontWeight: '800',
                  color: scenarioResult.summary.risk_hyper ? '#fbbf24' : '#10b981',
                }}>
                  {scenarioResult.summary.max_projected_sgv}
                  <span style={{ fontSize: '0.65rem', fontWeight: '400', opacity: 0.7 }}> mg/dL</span>
                </div>
              </div>

              <div style={{
                ...glassCard, padding: '1rem',
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                borderColor: (scenarioResult.summary.risk_hypo || scenarioResult.summary.risk_hyper)
                  ? 'rgba(239, 68, 68, 0.3)' : 'rgba(16, 185, 129, 0.3)',
              }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginBottom: '0.5rem' }}>Alerte de Risque</div>
                {scenarioResult.summary.risk_hypo ? (
                  <StatusBadge status="Risque d'Hypoglycémie" type="danger" />
                ) : scenarioResult.summary.risk_hyper ? (
                  <StatusBadge status="Risque d'Hyperglycémie" type="warning" />
                ) : (
                  <StatusBadge status="Dans la Cible" type="success" />
                )}
              </div>
            </div>
          )}

          {/* Scenario Chart */}
          <div style={glassCard}>
            {loadingScenario ? (
              <LoadingSpinner message="Calcul du scénario en cours..." />
            ) : scenarioResult?.timeline ? (
              <ReactECharts option={scenarioChartOption} style={{ height: '420px', width: '100%' }} />
            ) : (
              <div style={{
                height: '280px', display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', gap: '1rem',
              }}>
                <div style={{
                  background: 'rgba(16, 185, 129, 0.08)',
                  borderRadius: '16px', padding: '1.25rem',
                  border: '1px dashed rgba(16, 185, 129, 0.2)',
                }}>
                  <Sliders style={{ width: '32px', height: '32px', color: '#10b981', opacity: 0.6 }} />
                </div>
                <div style={{ color: '#64748b', fontSize: '0.9rem', textAlign: 'center', maxWidth: '340px' }}>
                  Configurez vos paramètres ci-dessus puis cliquez sur <strong style={{ color: '#10b981' }}>« Simuler le Scénario »</strong> pour visualiser l'impact.
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ════════════════════ TAB 3: SETTINGS ANALYSIS ════════════════════ */}
      {activeTab === 'settings' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', animation: 'fadeInUp 0.4s ease-out' }}>
          {/* Header */}
          <div style={{
            ...glassCard,
            padding: '1.25rem 1.5rem',
          }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: '0.6rem',
              fontSize: '1.15rem', fontWeight: '700', color: '#e2e8f0',
              marginBottom: '0.4rem',
            }}>
              <div style={{
                background: 'linear-gradient(135deg, #f59e0b, #f97316)',
                borderRadius: '8px', padding: '0.4rem', display: 'flex',
              }}>
                <Award style={{ width: '18px', height: '18px', color: '#fff' }} />
              </div>
              Analyse de l'Adéquation des Réglages
            </div>
            <div style={{ color: '#64748b', fontSize: '0.82rem', marginLeft: '2.5rem' }}>
              Estimation par le jumeau numérique de l'équilibre de vos réglages par tranches horaires de 3 heures.
              <strong style={{ color: '#fbbf24' }}> Pistes de réflexion à discuter avec votre équipe soignante.</strong>
            </div>
          </div>

          {loadingSettings ? (
            <LoadingSpinner message="Analyse des réglages en cours..." />
          ) : settingsData?.blocks ? (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
              gap: '1rem',
            }}>
              {settingsData.blocks.map((b: SettingBlock, idx: number) => {
                const isHovered = hoveredCard === b.block_id;
                const statusType = b.status_basal.includes('adaptée') || b.status_basal.includes('généralement')
                  ? 'success'
                  : b.status_basal.includes('sous-dosée') ? 'warning' : 'danger';

                // Emojis for time blocks
                const blockEmojis = ['🌙', '🌅', '☀️', '🌤', '🍽', '⛅', '🌆', '🌃'];

                return (
                  <div
                    key={b.block_id}
                    style={{
                      ...(isHovered ? glassCardHover : glassCard),
                      animation: `fadeInUp ${0.3 + idx * 0.06}s ease-out both`,
                      cursor: 'default',
                    }}
                    onMouseEnter={() => setHoveredCard(b.block_id)}
                    onMouseLeave={() => setHoveredCard(null)}
                  >
                    {/* Card Header */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{ fontSize: '1.2rem' }}>{blockEmojis[b.block_id] ?? '⏰'}</span>
                        <span style={{ fontWeight: '700', fontSize: '0.92rem', color: '#e2e8f0' }}>{b.label}</span>
                      </div>
                      <StatusBadge status={b.confidence} type={b.confidence === 'Élevée' ? 'success' : b.confidence === 'Moyenne' ? 'info' : 'warning'} />
                    </div>

                    {/* Mini metric pills */}
                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
                      <span style={{
                        background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.2)',
                        color: '#34d399', padding: '0.2rem 0.6rem', borderRadius: '8px', fontSize: '0.75rem', fontWeight: '600',
                      }}>
                        ISF {b.isf_estimated} mg/dL/U
                      </span>
                      <span style={{
                        background: 'rgba(251, 191, 36, 0.1)', border: '1px solid rgba(251, 191, 36, 0.2)',
                        color: '#fbbf24', padding: '0.2rem 0.6rem', borderRadius: '8px', fontSize: '0.75rem', fontWeight: '600',
                      }}>
                        CR {b.cr_estimated} g/U
                      </span>
                      <span style={{
                        background: 'rgba(99, 102, 241, 0.1)', border: '1px solid rgba(99, 102, 241, 0.2)',
                        color: '#818cf8', padding: '0.2rem 0.6rem', borderRadius: '8px', fontSize: '0.75rem', fontWeight: '600',
                      }}>
                        Basale {b.basal_estimated} U/h
                      </span>
                    </div>

                    {/* TIR mini bar */}
                    {b.sample_count > 0 && (
                      <div style={{ marginBottom: '0.75rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', color: '#64748b', marginBottom: '3px' }}>
                          <span>TBR {b.pct_tbr}%</span>
                          <span>Moy {b.mean_sgv} mg/dL</span>
                          <span>TAR {b.pct_tar}%</span>
                        </div>
                        <div style={{
                          display: 'flex', height: '5px', borderRadius: '3px', overflow: 'hidden',
                          background: 'rgba(255,255,255,0.06)',
                        }}>
                          <div style={{ width: `${b.pct_tbr}%`, background: '#ef4444', transition: 'width 0.8s ease' }} />
                          <div style={{ width: `${100 - b.pct_tbr - b.pct_tar}%`, background: '#10b981', transition: 'width 0.8s ease' }} />
                          <div style={{ width: `${b.pct_tar}%`, background: '#f59e0b', transition: 'width 0.8s ease' }} />
                        </div>
                      </div>
                    )}

                    {/* Status */}
                    <div style={{ marginBottom: '0.5rem' }}>
                      <div style={{
                        fontSize: '0.78rem', fontWeight: '600',
                        color: statusType === 'success' ? '#34d399' : statusType === 'warning' ? '#fbbf24' : '#f87171',
                        display: 'flex', alignItems: 'center', gap: '0.35rem',
                      }}>
                        {statusType === 'success' ? <CheckCircle2 style={{ width: '13px', height: '13px' }} /> :
                          <AlertTriangle style={{ width: '13px', height: '13px' }} />}
                        {b.status_basal}
                      </div>
                    </div>

                    {/* Recommendation */}
                    <div style={{
                      fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.5,
                      background: 'rgba(0,0,0,0.2)', padding: '0.65rem 0.75rem', borderRadius: '8px',
                      borderLeft: '3px solid rgba(245, 158, 11, 0.4)',
                    }}>
                      💡 <em>{b.recommendation_note}</em>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>
      )}

      {/* ════════════════════ TAB 4: MEAL LIBRARY ════════════════════ */}
      {activeTab === 'meals' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', animation: 'fadeInUp 0.4s ease-out' }}>
          {/* Header */}
          <div style={{
            ...glassCard,
            padding: '1.25rem 1.5rem',
          }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: '0.6rem',
              fontSize: '1.15rem', fontWeight: '700', color: '#e2e8f0',
              marginBottom: '0.4rem',
            }}>
              <div style={{
                background: 'linear-gradient(135deg, #f43f5e, #e11d48)',
                borderRadius: '8px', padding: '0.4rem', display: 'flex',
              }}>
                <Utensils style={{ width: '18px', height: '18px', color: '#fff' }} />
              </div>
              Bibliothèque des Repas & Réponses Glycémiques
            </div>
            <div style={{ color: '#64748b', fontSize: '0.82rem', marginLeft: '2.5rem' }}>
              Historique des excursions glycémiques postprandiales observées (+1h, +2h, +3h) selon les types de repas.
            </div>
          </div>

          {/* Category Summary Cards */}
          {mealsData?.category_summary && Object.keys(mealsData.category_summary).length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
              {Object.entries(mealsData.category_summary).map(([cat, data]: [string, any]) => {
                const catEmoji = cat === 'Petit-déjeuner' ? '🌅' : cat === 'Déjeuner' ? '🍽' : cat === 'Dîner' ? '🌆' : '🍪';
                const deltaColor = data.avg_peak_delta > 60 ? '#f87171' : data.avg_peak_delta > 40 ? '#fbbf24' : '#10b981';
                return (
                  <div key={cat} style={{
                    ...glassCard,
                    padding: '1rem',
                    textAlign: 'center',
                  }}>
                    <div style={{ fontSize: '1.5rem', marginBottom: '0.3rem' }}>{catEmoji}</div>
                    <div style={{ fontSize: '0.82rem', fontWeight: '600', color: '#e2e8f0', marginBottom: '0.5rem' }}>{cat}</div>
                    <div style={{ fontSize: '0.72rem', color: '#64748b', marginBottom: '0.3rem' }}>{data.count} repas analysés</div>
                    <div style={{ fontSize: '1.3rem', fontWeight: '800', color: deltaColor }}>
                      +{data.avg_peak_delta}<span style={{ fontSize: '0.6rem', fontWeight: '400', opacity: 0.7 }}> mg/dL</span>
                    </div>
                    <div style={{ fontSize: '0.68rem', color: '#64748b' }}>
                      pic moy. à {data.avg_peak_time_min} min • {data.avg_carbs_g}g moy
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Meals Table */}
          {loadingMeals ? (
            <LoadingSpinner message="Chargement de la bibliothèque de repas..." />
          ) : mealsData?.meals ? (
            <div style={{ ...glassCard, padding: '0', overflow: 'hidden' }}>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                  <thead>
                    <tr style={{
                      background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.9))',
                      textAlign: 'left',
                    }}>
                      <th style={{ padding: '0.85rem 1rem', color: '#94a3b8', fontWeight: '600', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Date & Heure</th>
                      <th style={{ padding: '0.85rem 0.75rem', color: '#94a3b8', fontWeight: '600', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Catégorie</th>
                      <th style={{ padding: '0.85rem 0.75rem', color: '#94a3b8', fontWeight: '600', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Glucides</th>
                      <th style={{ padding: '0.85rem 0.75rem', color: '#94a3b8', fontWeight: '600', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Bolus</th>
                      <th style={{ padding: '0.85rem 0.75rem', color: '#94a3b8', fontWeight: '600', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Départ</th>
                      <th style={{ padding: '0.85rem 0.75rem', color: '#94a3b8', fontWeight: '600', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Pic Max</th>
                      <th style={{ padding: '0.85rem 0.75rem', color: '#94a3b8', fontWeight: '600', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Excursion</th>
                      <th style={{ padding: '0.85rem 0.75rem', color: '#94a3b8', fontWeight: '600', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Réponse +1h/+2h/+3h</th>
                      <th style={{ padding: '0.85rem 0.75rem', color: '#94a3b8', fontWeight: '600', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Qualité</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mealsData.meals.map((m: MealItem) => {
                      const isHovered = hoveredMeal === m.meal_id;
                      const deltaColor = m.peak_delta > 80 ? '#f87171' : m.peak_delta > 50 ? '#fbbf24' : '#10b981';
                      const qualityType = m.response_quality.includes('Maîtrisée') ? 'success'
                        : m.response_quality.includes('Forte') ? 'danger' : 'info';

                      return (
                        <tr
                          key={m.meal_id}
                          style={{
                            borderBottom: '1px solid rgba(148, 163, 184, 0.06)',
                            background: isHovered ? 'rgba(99, 102, 241, 0.04)' : 'transparent',
                            transition: 'background 0.2s ease',
                          }}
                          onMouseEnter={() => setHoveredMeal(m.meal_id)}
                          onMouseLeave={() => setHoveredMeal(null)}
                        >
                          <td style={{ padding: '0.7rem 1rem', color: '#e2e8f0', fontWeight: '500' }}>
                            {new Date(m.datetime).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                          </td>
                          <td style={{ padding: '0.7rem 0.75rem' }}>
                            <span style={{
                              background: 'rgba(99, 102, 241, 0.1)',
                              color: '#a5b4fc',
                              padding: '0.15rem 0.5rem',
                              borderRadius: '6px',
                              fontSize: '0.75rem',
                              fontWeight: '500',
                            }}>
                              {m.category}
                            </span>
                          </td>
                          <td style={{ padding: '0.7rem 0.75rem', fontWeight: '700', color: '#fbbf24' }}>{m.carbs_g}g</td>
                          <td style={{ padding: '0.7rem 0.75rem', color: '#38bdf8', fontWeight: '600' }}>{m.bolus_u}U</td>
                          <td style={{ padding: '0.7rem 0.75rem', color: '#94a3b8' }}>{m.start_sgv}</td>
                          <td style={{ padding: '0.7rem 0.75rem', fontWeight: '700', color: '#e2e8f0' }}>{m.max_sgv}</td>
                          <td style={{ padding: '0.7rem 0.75rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                              {m.peak_delta > 50 ?
                                <TrendingUp style={{ width: '13px', height: '13px', color: deltaColor }} /> :
                                <TrendingDown style={{ width: '13px', height: '13px', color: deltaColor }} />
                              }
                              <span style={{ fontWeight: '700', color: deltaColor }}>+{m.peak_delta}</span>
                              <span style={{ fontSize: '0.68rem', color: '#64748b' }}>({m.peak_time_min}min)</span>
                            </div>
                          </td>
                          <td style={{ padding: '0.7rem 0.75rem' }}>
                            {/* Mini inline sparkline visual */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                              <div style={{
                                display: 'flex', alignItems: 'flex-end', gap: '2px', height: '20px',
                              }}>
                                {[m.start_sgv, m.sgv_1h, m.sgv_2h, m.sgv_3h].map((v, i) => {
                                  const maxH = Math.max(m.start_sgv, m.sgv_1h, m.sgv_2h, m.sgv_3h);
                                  const minH = Math.min(m.start_sgv, m.sgv_1h, m.sgv_2h, m.sgv_3h);
                                  const range = maxH - minH || 1;
                                  const height = 4 + ((v - minH) / range) * 16;
                                  const barColor = v > 180 ? '#f59e0b' : v < 70 ? '#ef4444' : '#10b981';
                                  return (
                                    <div
                                      key={i}
                                      style={{
                                        width: '5px', height: `${height}px`, borderRadius: '2px',
                                        background: barColor, opacity: 0.8 + i * 0.05,
                                        transition: 'height 0.5s ease',
                                      }}
                                      title={`${['Départ', '+1h', '+2h', '+3h'][i]}: ${Math.round(v)} mg/dL`}
                                    />
                                  );
                                })}
                              </div>
                              <span style={{ fontSize: '0.68rem', color: '#64748b' }}>
                                {Math.round(m.sgv_3h)}
                              </span>
                            </div>
                          </td>
                          <td style={{ padding: '0.7rem 0.75rem' }}>
                            <StatusBadge status={m.response_quality.replace(/\(.*\)/, '').trim()} type={qualityType} />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

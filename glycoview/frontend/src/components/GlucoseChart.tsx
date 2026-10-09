import { useEffect, useState, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { Calendar, ChevronLeft, ChevronRight, Zap, Info } from 'lucide-react';
import { API_BASE_URL } from '../config';

interface Entry {
  datetime: string;
  sgv: number;
}

interface Treatment {
  _id: string;
  eventType: string;
  created_at: string;
  insulin?: number;
  carbs?: number;
  rate?: number;
  duration?: number;
  type?: string;
  isSMB?: boolean;
}

interface DeviceStatus {
  iob: number;
  cob: number;
  basal: number;
  sensitivity?: number;
  sensitivity_ratio?: number;
  created_at?: string;
}

interface DayStat {
  date: string;
  low: number;
  target: number;
  high: number;
}

interface GlucoseChartProps {
  selectedDate: string | null;
  onSelectDate: (date: string | null) => void;
  availableDays: DayStat[];
}

export default function GlucoseChart({ selectedDate, onSelectDate, availableDays }: GlucoseChartProps) {
  const [data, setData] = useState<Entry[]>([]);
  const [treatments, setTreatments] = useState<Treatment[]>([]);
  const [deviceStatus, setDeviceStatus] = useState<DeviceStatus>({ iob: 0, cob: 0, basal: 0 });
  const [loading, setLoading] = useState(true);
  const [timeRangeHours, setTimeRangeHours] = useState<number>(24);

  // Load entries and treatments
  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch(`${API_BASE_URL}/api/v1/entries/processed`).then(res => res.json()),
      fetch(`${API_BASE_URL}/api/v1/treatments?limit=5000`).then(res => res.json()),
    ]).then(([entriesData, treatmentsData]) => {
      setData(entriesData);
      setTreatments(treatmentsData);
      setLoading(false);
    }).catch(err => {
      console.error("Error fetching entries/treatments:", err);
      setLoading(false);
    });
  }, []);

  // Load devicestatus when selectedDate changes or on mount
  useEffect(() => {
    const url = selectedDate
      ? `${API_BASE_URL}/api/v1/devicestatus/latest?date=${selectedDate}`
      : `${API_BASE_URL}/api/v1/devicestatus/latest`;

    fetch(url)
      .then(res => res.json())
      .then(statusData => {
        setDeviceStatus({
          iob: statusData.iob ?? 0,
          cob: statusData.cob ?? 0,
          basal: statusData.basal ?? 0,
          sensitivity: statusData.sensitivity ?? 40.0,
          sensitivity_ratio: statusData.sensitivity_ratio ?? 100,
          created_at: statusData.created_at,
        });
      })
      .catch(err => console.error("Error fetching device status:", err));
  }, [selectedDate]);

  // Compute time bounds and filtered data
  const { minDate, maxDate, filteredData, filteredTreatments } = useMemo(() => {
    if (data.length === 0) {
      const now = Date.now();
      return { minDate: now - 86400000, maxDate: now, filteredData: [], filteredTreatments: [] };
    }

    if (selectedDate) {
      // Filter for specific selected day: 00:00:00 to 23:59:59 local/day
      const dayStart = new Date(`${selectedDate}T00:00:00`).getTime();
      const dayEnd = new Date(`${selectedDate}T23:59:59`).getTime();

      const fData = data.filter(d => {
        const t = new Date(d.datetime).getTime();
        return t >= dayStart && t <= dayEnd;
      });

      const fTreatments = treatments.filter(t => {
        const time = new Date(t.created_at).getTime();
        return time >= dayStart && time <= dayEnd;
      });

      return { minDate: dayStart, maxDate: dayEnd, filteredData: fData, filteredTreatments: fTreatments };
    } else {
      // Live / sliding window mode
      const latestDate = new Date(data[data.length - 1].datetime).getTime();
      const min = latestDate - (timeRangeHours * 3600 * 1000);

      const fData = data.filter(d => new Date(d.datetime).getTime() >= min);
      const fTreatments = treatments.filter(t => new Date(t.created_at).getTime() >= min);

      return { minDate: min, maxDate: latestDate, filteredData: fData, filteredTreatments: fTreatments };
    }
  }, [data, treatments, selectedDate, timeRangeHours]);

  // Day navigation helpers
  const dayIndex = availableDays.findIndex(d => d.date === selectedDate);
  const hasPrevDay = dayIndex < availableDays.length - 1 && dayIndex !== -1;
  const hasNextDay = dayIndex > 0;

  const handlePrevDay = () => {
    if (dayIndex === -1 && availableDays.length > 0) {
      onSelectDate(availableDays[0].date);
    } else if (hasPrevDay) {
      onSelectDate(availableDays[dayIndex + 1].date);
    }
  };

  const handleNextDay = () => {
    if (hasNextDay) {
      onSelectDate(availableDays[dayIndex - 1].date);
    } else if (dayIndex === 0) {
      // Next from newest day -> live mode
      onSelectDate(null);
    }
  };

  if (loading) {
    return (
      <div className="card" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
        Chargement des données glycémiques et traitements...
      </div>
    );
  }

  // Treatments segregation
  const isSmbTreatment = (t: Treatment) => t.isSMB === true || t.type === 'SMB';
  const isManualBolusTreatment = (t: Treatment) => !isSmbTreatment(t) && (t.insulin ?? 0) > 0;

  const bolusData = filteredTreatments
    .filter(isManualBolusTreatment)
    .map(t => [new Date(t.created_at).getTime(), 50, Number(t.insulin || 0).toFixed(2)]);

  const smbData = filteredTreatments
    .filter(isSmbTreatment)
    .map(t => [new Date(t.created_at).getTime(), 42, Number(t.insulin || 0).toFixed(2)]);

  const carbsData = filteredTreatments
    .filter(t => (t.carbs ?? 0) > 0)
    .map(t => ({
      name: `${t.carbs}g`,
      value: [new Date(t.created_at).getTime(), 150, t.carbs],
      label: {
        show: true,
        formatter: '{b}',
        position: 'top',
        color: '#fbbf24',
        fontSize: 10,
        fontWeight: 'bold',
        rotate: 25,
      }
    }));

  const basalData = filteredTreatments
    .filter(t => t.eventType === 'Temp Basal' && t.rate !== undefined)
    .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
    .map(t => [new Date(t.created_at).getTime(), Number(t.rate).toFixed(2)]);

  // Total insulin from SMB and Bolus in current view
  const totalSmbInsulin = filteredTreatments
    .filter(isSmbTreatment)
    .reduce((sum, t) => sum + (Number(t.insulin) || 0), 0);
  const totalBolusInsulin = filteredTreatments
    .filter(isManualBolusTreatment)
    .reduce((sum, t) => sum + (Number(t.insulin) || 0), 0);
  const totalCarbs = filteredTreatments
    .filter(t => (t.carbs ?? 0) > 0)
    .reduce((sum, t) => sum + (Number(t.carbs) || 0), 0);

  // ECharts Option
  const option = {
    backgroundColor: '#18181b',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', lineStyle: { color: 'rgba(255, 255, 255, 0.2)' } },
      backgroundColor: 'rgba(24, 24, 27, 0.95)',
      borderColor: '#3f3f46',
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: '#f8fafc', fontSize: 12 },
      formatter: (params: any) => {
        if (!Array.isArray(params) || params.length === 0) return '';
        const timestamp = params[0].value ? params[0].value[0] : params[0].axisValue;
        const timeStr = new Date(timestamp).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
        
        let html = `<div style="font-weight:600;margin-bottom:6px;border-bottom:1px solid #3f3f46;padding-bottom:4px;color:#94a3b8">${timeStr}</div>`;
        
        for (const p of params) {
          const val = p.value || p.data;
          if (!val) continue;
          
          if (p.seriesName === 'SGV') {
            const sgv = Math.round(val[1]);
            let color = '#22c55e';
            if (sgv < 70) color = '#ef4444';
            else if (sgv > 180) color = '#eab308';
            html += `<div style="display:flex;align-items:center;gap:6px;margin:2px 0;">
              <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color}"></span>
              <span style="color:#cbd5e1">SGV (Glycémie) :</span>
              <strong style="color:${color};font-size:13px">${sgv} mg/dL</strong>
            </div>`;
          } else if (p.seriesName === 'Micro-Bolus (SMB)') {
            const dose = val[2];
            html += `<div style="display:flex;align-items:center;gap:6px;margin:2px 0;">
              <span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:#0ea5e9"></span>
              <span style="color:#cbd5e1">Micro-Bolus (SMB) :</span>
              <strong style="color:#38bdf8">${dose} U</strong>
            </div>`;
          } else if (p.seriesName === 'Bolus (Manuel)') {
            const dose = val[2];
            html += `<div style="display:flex;align-items:center;gap:6px;margin:2px 0;">
              <span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:#818cf8"></span>
              <span style="color:#cbd5e1">Bolus Manuel :</span>
              <strong style="color:#a5b4fc">${dose} U</strong>
            </div>`;
          } else if (p.seriesName === 'Glucides') {
            const carbs = val[2];
            html += `<div style="display:flex;align-items:center;gap:6px;margin:2px 0;">
              <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#f59e0b"></span>
              <span style="color:#cbd5e1">Glucides :</span>
              <strong style="color:#fbbf24">${carbs} g</strong>
            </div>`;
          } else if (p.seriesName === 'Basal') {
            const rate = val[1];
            html += `<div style="display:flex;align-items:center;gap:6px;margin:2px 0;">
              <span style="display:inline-block;width:8px;height:8px;background:#38bdf8"></span>
              <span style="color:#cbd5e1">Débit Basal :</span>
              <strong style="color:#7dd3fc">${rate} U/h</strong>
            </div>`;
          }
        }
        return html;
      }
    },
    grid: [
      { top: '6%', bottom: '26%', left: '4%', right: '4%', containLabel: true },
      { top: '78%', bottom: '6%', left: '4%', right: '4%', containLabel: true }
    ],
    xAxis: [
      {
        type: 'time',
        gridIndex: 0,
        boundaryGap: false,
        axisLabel: { show: false },
        axisLine: { show: false },
        splitLine: { show: true, lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } },
        min: minDate,
        max: maxDate,
      },
      {
        type: 'time',
        gridIndex: 1,
        boundaryGap: false,
        axisLabel: {
          color: '#94a3b8',
          fontSize: 11,
          formatter: '{HH}:{mm}'
        },
        axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.1)' } },
        splitLine: { show: true, lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } },
        min: minDate,
        max: maxDate,
      }
    ],
    yAxis: [
      {
        gridIndex: 0,
        type: 'value',
        min: 40,
        max: 300,
        splitLine: { show: true, lineStyle: { color: 'rgba(255, 255, 255, 0.06)' } },
        axisLabel: { color: '#94a3b8', fontSize: 11, formatter: '{value}' }
      },
      {
        gridIndex: 1,
        type: 'value',
        min: 0,
        splitLine: { show: true, lineStyle: { color: 'rgba(255, 255, 255, 0.04)' } },
        axisLabel: { color: '#64748b', fontSize: 9, formatter: '{value} U/h' }
      }
    ],
    visualMap: {
      show: false,
      seriesIndex: 0,
      pieces: [
        { gt: 0, lte: 70, color: '#ef4444' },     // Hypo (rouge)
        { gt: 70, lte: 180, color: '#22c55e' },   // Cible (vert)
        { gt: 180, color: '#eab308' }             // Hyper (jaune)
      ]
    },
    series: [
      {
        name: 'SGV',
        type: 'scatter',
        xAxisIndex: 0,
        yAxisIndex: 0,
        symbolSize: 5,
        data: filteredData.map(item => [new Date(item.datetime).getTime(), item.sgv]),
        markArea: {
          silent: true,
          itemStyle: { color: 'rgba(34, 197, 94, 0.08)' },
          data: [[{ yAxis: 70 }, { yAxis: 180 }]]
        }
      },
      {
        name: 'Bolus (Manuel)',
        type: 'scatter',
        xAxisIndex: 0,
        yAxisIndex: 0,
        symbol: 'triangle',
        symbolRotate: 180, // Pointe vers le bas
        symbolSize: (val: any) => Math.min(Math.max((Number(val[2]) || 1) * 3.5, 12), 24),
        itemStyle: { color: '#818cf8', borderColor: '#4f46e5', borderWidth: 1 },
        data: bolusData,
      },
      {
        name: 'Micro-Bolus (SMB)',
        type: 'scatter',
        xAxisIndex: 0,
        yAxisIndex: 0,
        symbol: 'triangle',
        symbolRotate: 180, // Pointe vers le bas
        symbolSize: (val: any) => Math.min(Math.max((Number(val[2]) || 0.1) * 8, 5), 14),
        itemStyle: { color: '#0ea5e9' },
        data: smbData,
      },
      {
        name: 'Glucides',
        type: 'scatter',
        xAxisIndex: 0,
        yAxisIndex: 0,
        symbol: 'circle',
        symbolSize: 7,
        itemStyle: { color: '#fbbf24', borderColor: '#b45309', borderWidth: 1 },
        data: carbsData,
      },
      {
        name: 'Basal',
        type: 'line',
        step: 'end',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: basalData,
        itemStyle: { color: '#0284c7' },
        lineStyle: { width: 1.5, color: '#0ea5e9' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(14, 165, 233, 0.45)' },
              { offset: 1, color: 'rgba(14, 165, 233, 0.05)' }
            ]
          }
        }
      }
    ]
  };

  // Compute current display stats
  const latestEntry = filteredData.length > 0 ? filteredData[filteredData.length - 1] : null;
  const prevEntry = filteredData.length > 1 ? filteredData[filteredData.length - 2] : latestEntry;
  const sgvDiff = latestEntry && prevEntry ? latestEntry.sgv - prevEntry.sgv : 0;

  let trendArrow = '→';
  if (sgvDiff > 5) trendArrow = '↗';
  if (sgvDiff > 10) trendArrow = '↑';
  if (sgvDiff < -5) trendArrow = '↘';
  if (sgvDiff < -10) trendArrow = '↓';

  let sgvColor = '#22c55e';
  if (latestEntry) {
    if (latestEntry.sgv > 180) sgvColor = '#eab308';
    if (latestEntry.sgv > 250) sgvColor = '#ef4444';
    if (latestEntry.sgv < 70) sgvColor = '#ef4444';
  }

  const minutesAgo = latestEntry
    ? Math.max(0, Math.floor((Date.now() - new Date(latestEntry.datetime).getTime()) / 60000))
    : 0;

  // Day average if viewing a past day
  const dayMean = filteredData.length > 0
    ? Math.round(filteredData.reduce((acc, cur) => acc + cur.sgv, 0) / filteredData.length)
    : null;

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden', backgroundColor: '#18181b', border: '1px solid #27272a' }}>
      
      {/* Barre de sélection de date et navigation temporelle */}
      <div style={{
        backgroundColor: '#202024',
        padding: '0.75rem 1.25rem',
        borderBottom: '1px solid #27272a',
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '0.75rem'
      }}>
        {/* Navigation Jour par Jour */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button
            onClick={handlePrevDay}
            disabled={!hasPrevDay && dayIndex !== -1}
            title="Jour précédent"
            style={{
              background: '#27272a',
              border: '1px solid #3f3f46',
              color: '#f8fafc',
              borderRadius: '6px',
              padding: '0.35rem 0.5rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center'
            }}
          >
            <ChevronLeft size={16} />
          </button>

          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Calendar size={15} style={{ position: 'absolute', left: '10px', color: '#94a3b8', pointerEvents: 'none' }} />
            <select
              value={selectedDate || 'live'}
              onChange={(e) => onSelectDate(e.target.value === 'live' ? null : e.target.value)}
              style={{
                backgroundColor: '#27272a',
                color: '#f8fafc',
                border: '1px solid #3f3f46',
                borderRadius: '6px',
                padding: '0.4rem 0.75rem 0.4rem 2rem',
                fontSize: '0.85rem',
                fontWeight: 500,
                cursor: 'pointer',
                outline: 'none'
              }}
            >
              <option value="live">⚡ En direct (Temps réel)</option>
              {availableDays.map(d => {
                const dateObj = new Date(d.date);
                const formatted = dateObj.toLocaleDateString('fr-FR', { weekday: 'short', day: '2-digit', month: '2-digit' });
                return (
                  <option key={d.date} value={d.date}>
                    📅 {formatted} — TIR {d.target}%
                  </option>
                );
              })}
            </select>
          </div>

          <button
            onClick={handleNextDay}
            disabled={!hasNextDay && dayIndex === -1}
            title="Jour suivant"
            style={{
              background: '#27272a',
              border: '1px solid #3f3f46',
              color: '#f8fafc',
              borderRadius: '6px',
              padding: '0.35rem 0.5rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center'
            }}
          >
            <ChevronRight size={16} />
          </button>

          {selectedDate && (
            <button
              onClick={() => onSelectDate(null)}
              style={{
                background: 'rgba(59, 130, 246, 0.15)',
                color: '#60a5fa',
                border: '1px solid rgba(59, 130, 246, 0.3)',
                borderRadius: '6px',
                padding: '0.35rem 0.65rem',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.3rem'
              }}
            >
              <Zap size={13} /> Revenir au direct
            </button>
          )}
        </div>

        {/* Filtres d'heures (quand en mode direct) */}
        {!selectedDate && (
          <div style={{ display: 'flex', gap: '0.35rem' }}>
            {[6, 12, 24, 72].map(hours => (
              <button 
                key={hours}
                onClick={() => setTimeRangeHours(hours)}
                style={{
                  background: timeRangeHours === hours ? '#3b82f6' : '#27272a',
                  color: timeRangeHours === hours ? '#fff' : '#94a3b8',
                  border: '1px solid',
                  borderColor: timeRangeHours === hours ? '#3b82f6' : '#3f3f46',
                  padding: '0.25rem 0.65rem',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '0.75rem',
                  fontWeight: 500,
                  transition: 'all 0.15s ease'
                }}
              >
                {hours === 72 ? '3 Jours' : `${hours}h`}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Header façon AAPS : Glycémie SGV, IOB, COB et Basal */}
      <div style={{
        backgroundColor: '#1f1f23',
        padding: '1rem 1.5rem',
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: '1px solid #27272a',
        gap: '1rem'
      }}>
        {/* Section Glycémie SGV */}
        <div>
          {filteredData.length === 0 ? (
            <div style={{ color: '#94a3b8' }}>Aucune donnée pour cette période</div>
          ) : selectedDate ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
                  <span style={{ fontSize: '2.5rem', fontWeight: 'bold', color: '#f8fafc', lineHeight: 1 }}>
                    {dayMean}
                  </span>
                  <span style={{ fontSize: '0.9rem', color: '#94a3b8' }}>mg/dL (moy.)</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.2rem' }}>
                  <Info size={12} />
                  <span>SGV (Sensor Glucose Value) • {filteredData.length} mesures</span>
                </div>
              </div>
              <div style={{ borderLeft: '1px solid #333', paddingLeft: '1rem', display: 'flex', gap: '1rem', fontSize: '0.8rem' }}>
                <div>
                  <div style={{ color: '#94a3b8' }}>SMB total</div>
                  <strong style={{ color: '#38bdf8' }}>{totalSmbInsulin.toFixed(2)} U</strong>
                </div>
                <div>
                  <div style={{ color: '#94a3b8' }}>Bolus total</div>
                  <strong style={{ color: '#a5b4fc' }}>{totalBolusInsulin.toFixed(2)} U</strong>
                </div>
                <div>
                  <div style={{ color: '#94a3b8' }}>Glucides</div>
                  <strong style={{ color: '#fbbf24' }}>{totalCarbs} g</strong>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <div style={{ fontSize: '3.25rem', fontWeight: 'bold', color: sgvColor, lineHeight: 1 }}>
                {latestEntry?.sgv.toFixed(0)}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: sgvColor, lineHeight: 1 }}>
                  {trendArrow}
                </div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.3rem' }}>
                  il y a {minutesAgo}m
                </div>
                <div style={{ fontSize: '0.7rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '0.2rem' }} title="Sensor Glucose Value : Glycémie issue du capteur CGM">
                  SGV <Info size={10} />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Section Métriques AAPS : IOB, COB, ISF Dyn. et Basal */}
        <div style={{ display: 'flex', gap: '1.75rem', alignItems: 'center' }}>
          {/* IOB */}
          <div style={{ textAlign: 'center' }} title="Insulin On Board (Insuline Active)">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.35rem', color: '#38bdf8' }}>
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m18 2-6 6"/><path d="m22 6-6 6"/><path d="M16 11l-3 3-4-4 3-3"/><path d="M4 20v-3l9-9 4 4-9 9H4z"/></svg>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8' }}>IOB</span>
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#f8fafc', marginTop: '0.1rem' }}>
              {deviceStatus.iob.toFixed(2)} U
            </div>
          </div>
          
          {/* COB */}
          <div style={{ textAlign: 'center' }} title="Carbs On Board (Glucides Actifs)">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.35rem', color: '#fbbf24' }}>
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m2 22 10-10"/><path d="M8 8.5V2l2 2 2-2v6.5"/><path d="M12 11.5 15.5 8 18 10.5 14.5 14"/><path d="M18 16.5 22 13l-3-3-4 4"/></svg>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8' }}>COB</span>
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#f8fafc', marginTop: '0.1rem' }}>
              {deviceStatus.cob.toFixed(1)} g
            </div>
          </div>

          {/* Sensibilité Dynamique (ISF) */}
          <div style={{ textAlign: 'center' }} title="Sensibilité Dynamique à l'Insuline (ISF / Ratio Autosens)">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.35rem', color: '#10b981' }}>
              <Zap size={15} />
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8' }}>ISF DYN.</span>
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#10b981', marginTop: '0.1rem' }}>
              {deviceStatus.sensitivity ? deviceStatus.sensitivity.toFixed(0) : 40} <small style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 'normal' }}>mg/dL/U</small>
            </div>
          </div>
          
          {/* Basal */}
          <div style={{ textAlign: 'center' }} title="Débit basal actuel">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.35rem', color: '#a855f7' }}>
              <div style={{ width: '14px', height: '2.5px', backgroundColor: '#a855f7', borderRadius: '1px' }}></div>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8' }}>BASAL</span>
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#f8fafc', marginTop: '0.1rem' }}>
              {deviceStatus.basal.toFixed(2)} U/h
            </div>
          </div>
        </div>
      </div>

      {/* Légende rapide et informative */}
      <div style={{
        padding: '0.4rem 1.25rem',
        backgroundColor: '#18181b',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: '0.75rem',
        color: '#64748b',
        borderBottom: '1px solid rgba(255, 255, 255, 0.04)'
      }}>
        <div style={{ display: 'flex', gap: '1.25rem', flexWrap: 'wrap' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#22c55e', display: 'inline-block' }}></span>
            SGV (Capteur)
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ width: 0, height: 0, borderLeft: '4px solid transparent', borderRight: '4px solid transparent', borderTop: '7px solid #818cf8', display: 'inline-block' }}></span>
            Bolus Manuel
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ width: 0, height: 0, borderLeft: '3px solid transparent', borderRight: '3px solid transparent', borderTop: '6px solid #0ea5e9', display: 'inline-block' }}></span>
            Micro-Bolus (SMB)
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#fbbf24', display: 'inline-block' }}></span>
            Glucides (g)
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ width: 10, height: 4, backgroundColor: '#0ea5e9', display: 'inline-block' }}></span>
            Basal (U/h)
          </span>
        </div>

        <div>
          Zone cible : <span style={{ color: '#22c55e', fontWeight: 600 }}>70 - 180 mg/dL</span>
        </div>
      </div>

      {/* Graphique ECharts */}
      <ReactECharts option={option} style={{ height: '420px', width: '100%' }} notMerge={true} />
    </div>
  );
}
